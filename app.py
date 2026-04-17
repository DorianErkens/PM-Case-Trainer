import os
import sys
import json
import streamlit as st
from dotenv import load_dotenv

# Load .env locally — on Streamlit Cloud, secrets come from st.secrets
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Streamlit Cloud: inject st.secrets into env vars so all downstream code works unchanged
try:
    for key in ["ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "SUPABASE_URL", "SUPABASE_KEY"]:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = st.secrets[key]
except Exception:
    pass

sys.path.insert(0, os.path.dirname(__file__))

from agents.persona_agent import generate_persona, generate_metrics, run_persona_turn
from agents.feedback_agent import run_feedback
from storage.session_store import save_session, get_dashboard_stats

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PM Case Trainer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "step": "context",            # context | metrics | interview | feedback
        "pm_context": "",
        "agent_session": None,        # the mutable session_state passed to agents
        "chat_history": [],           # list of {role, content} for display
        "brain_log": [],              # all agent brain events across all turns
        "feedback_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── Helpers ───────────────────────────────────────────────────────────────────
def push_brain(event: dict):
    st.session_state.brain_log.append(event)

def render_brain_log():
    """Renders the Agent Brain panel — the live debug view."""
    logs = st.session_state.brain_log
    if not logs:
        st.caption("En attente de la première action de l'agent...")
        return

    for entry in logs:
        t = entry.get("type")
        if t == "section":
            st.markdown(f"**— {entry['label']} —**")
        elif t == "llm_call":
            st.markdown(f"→ LLM call #{entry['iteration']}")
        elif t == "llm_response":
            color = "green" if entry["stop_reason"] == "end_turn" else "orange"
            st.markdown(
                f"← :{color}[{entry['stop_reason']}]  "
                f"`{entry.get('input_tokens', '?')}in / {entry.get('output_tokens', '?')}out`"
            )
        elif t == "tool_call":
            st.markdown(f"🔧 **{entry['tool']}**")
            st.code(json.dumps(entry["input"], ensure_ascii=False, indent=2), language="json")
        elif t == "observation":
            st.caption(f"👁 {entry['result'][:120]}")
        elif t == "state_update":
            st.info(entry["message"])
        elif t == "error":
            st.error(f"❌ {entry['stop_reason']}")


def agent_log_to_brain(agent_log: list, section_label: str):
    """Converts an agent_log list into brain_log entries."""
    push_brain({"type": "section", "label": section_label})
    for step in agent_log:
        push_brain(step)


# ── UI Sections ───────────────────────────────────────────────────────────────

def render_step_context(col_main):
    with col_main:
        st.title("🎯 PM Case Trainer")
        st.markdown("Entraîne-toi à mener des entretiens utilisateurs réalistes avec un agent IA.")
        st.divider()

        st.subheader("1. Ton contexte")
        st.markdown("Décris ton métier et le type d'utilisateur avec lequel tu travailles habituellement.")

        pm_context = st.text_area(
            label="Contexte",
            placeholder=(
                "Ex : Je suis PM dans une scale-up B2B SaaS. Mon produit aide les équipes RH "
                "à gérer les entretiens de recrutement. Je veux comprendre les douleurs "
                "des responsables RH en PME."
            ),
            height=140,
            label_visibility="collapsed"
        )

        if st.button("Générer le persona et les métriques →", type="primary", disabled=not pm_context.strip()):
            st.session_state.pm_context = pm_context

            with st.spinner("Génération du persona en cours..."):
                push_brain({"type": "section", "label": "Génération du persona"})
                persona = generate_persona(pm_context)
                push_brain({"type": "state_update", "message": f"Persona créé : {persona['role']} · résistance initiale {persona.get('initial_resistance', 7)}/10"})

            with st.spinner("Proposition des métriques..."):
                push_brain({"type": "section", "label": "Génération des métriques"})
                metrics = generate_metrics(persona, pm_context)
                push_brain({"type": "state_update", "message": f"{len(metrics)} métriques générées"})

            st.session_state.agent_session = {
                "persona": persona,
                "metrics": metrics,
                "conversation_history": [],
                "resistance_level": persona.get("initial_resistance", 7),
                "revealed_pains": {},
                "flagged_questions": []
            }
            st.session_state.step = "metrics"
            st.rerun()


def render_step_metrics(col_main):
    with col_main:
        st.title("🎯 PM Case Trainer")
        st.divider()
        st.subheader("2. Métriques à suivre pendant l'entretien")
        st.markdown(
            "Ces métriques guident ton entretien. Elles seront utilisées pour évaluer "
            "la couverture de ton feedback."
        )

        metrics = st.session_state.agent_session["metrics"]
        selected = []

        for m in metrics:
            col_check, col_text = st.columns([0.08, 0.92])
            with col_check:
                checked = st.checkbox("", value=True, key=f"metric_{m['id']}")
            with col_text:
                st.markdown(f"**{m['name']}**")
                st.caption(m["description"])
                st.caption(f"*Exemple : {m['example']}*")
            if checked:
                selected.append(m)
            st.divider()

        if st.button("Commencer l'entretien →", type="primary", disabled=not selected):
            st.session_state.agent_session["metrics"] = selected
            push_brain({"type": "state_update", "message": f"{len(selected)} métriques validées — entretien prêt"})
            st.session_state.step = "interview"
            st.rerun()


def render_step_interview(col_main):
    with col_main:
        st.title("🎯 PM Case Trainer")

        persona = st.session_state.agent_session["persona"]
        resistance = st.session_state.agent_session["resistance_level"]
        revealed_count = len(st.session_state.agent_session["revealed_pains"])
        total_pains = len(persona.get("pains", []))

        # Live stats bar
        c1, c2, c3 = st.columns(3)
        c1.metric("Résistance", f"{resistance}/10")
        c2.metric("Pains découverts", f"{revealed_count}/{total_pains}")
        c3.metric("Questions posées", len(st.session_state.chat_history) // 2)

        st.divider()

        # Chat history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Chat input
        question = st.chat_input("Posez votre question...")

        if question:
            # Show PM message immediately
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            # Run agent
            with st.chat_message("assistant"):
                with st.spinner("..."):
                    result = run_persona_turn(question, st.session_state.agent_session)

                # Log to brain panel
                agent_log_to_brain(result["agent_log"], f"Tour {len(st.session_state.chat_history)//2}")

                # State change summary
                new_resistance = st.session_state.agent_session["resistance_level"]
                new_revealed = len(st.session_state.agent_session["revealed_pains"])
                if new_resistance != resistance or new_revealed != revealed_count:
                    push_brain({"type": "state_update",
                                "message": f"résistance: {resistance} → {new_resistance} · pains: {revealed_count} → {new_revealed}"})

                st.markdown(result["response"])
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": result["response"]
                })

            st.rerun()

        # End interview button
        st.divider()
        questions_asked = len(st.session_state.chat_history) // 2
        if questions_asked >= 3:
            if st.button("Terminer l'entretien et obtenir le feedback →", type="primary"):
                with st.spinner("Analyse de la session en cours..."):
                    # Pass pm_context into session for storage
                    st.session_state.agent_session["pm_context"] = st.session_state.pm_context
                    push_brain({"type": "section", "label": "Feedback Agent"})
                    result = run_feedback(st.session_state.agent_session)
                    agent_log_to_brain(result["agent_log"], "Analyse feedback")
                    push_brain({"type": "state_update",
                                "message": f"Score final : {result.get('score')}/100"})
                    st.session_state.feedback_result = result

                with st.spinner("Sauvegarde de la session..."):
                    saved = save_session(st.session_state.agent_session, result)
                    if saved:
                        push_brain({"type": "state_update", "message": "Session sauvegardée dans Supabase ✓"})

                st.session_state.step = "feedback"
                st.rerun()
        else:
            st.caption(f"Pose au moins {3 - questions_asked} question(s) de plus pour débloquer le feedback.")


def render_step_feedback(col_main):
    with col_main:
        st.title("🎯 PM Case Trainer")
        st.divider()

        result = st.session_state.feedback_result
        score = result.get("score", 0)

        # Score display
        color = "green" if score >= 70 else "orange" if score >= 40 else "red"
        st.markdown(f"## Score final : :{color}[{score}/100]")
        st.progress(score / 100)

        # Progress dashboard — only shown if past sessions exist
        stats = get_dashboard_stats()
        if stats and stats.get("total_sessions", 0) > 1:
            st.divider()
            st.subheader("Ta progression")
            c1, c2, c3 = st.columns(3)
            c1.metric("Sessions complétées", stats["total_sessions"])
            c2.metric("Score moyen", f"{stats['avg_score']}/100")
            c3.metric("Meilleur score", f"{stats['best_score']}/100")

            if stats.get("score_trend"):
                st.line_chart({"Score": stats["score_trend"]})

            if stats.get("recurring_misses"):
                st.markdown("**Pains que tu rates régulièrement :**")
                for pain_hint, count in stats["recurring_misses"]:
                    st.caption(f"× {count}x — {pain_hint}...")

        st.divider()

        # Full report
        st.markdown(result["report"])
        st.divider()

        if st.button("🔄 Recommencer une session", type="primary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ── Main layout ───────────────────────────────────────────────────────────────

col_main, col_brain = st.columns([3, 2])

step = st.session_state.step

if step == "context":
    render_step_context(col_main)
elif step == "metrics":
    render_step_metrics(col_main)
elif step == "interview":
    render_step_interview(col_main)
elif step == "feedback":
    render_step_feedback(col_main)

# Agent Brain panel — always visible on the right
with col_brain:
    st.subheader("🧠 Agent Brain")
    st.caption("Ce qui se passe sous le capot à chaque action de l'agent.")
    st.divider()
    with st.container(height=700):
        render_brain_log()
