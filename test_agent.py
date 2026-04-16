"""
Terminal test — run this to see the ReAct loop + Langfuse traces in action.

Usage:
  python test_agent.py

What you'll see in terminal:
  - Each ReAct iteration with tool calls and observations

What you'll see in Langfuse (cloud.langfuse.com):
  - Full session trace with all spans linked
  - Token usage per LLM call
  - Tool call inputs/outputs
  - Resistance level changes over time
"""

import json
from agents.persona_agent import (
    generate_persona,
    generate_metrics,
    run_persona_turn,
    create_session_trace
)


def print_separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)


def print_agent_log(agent_log: list):
    print("\n  [AGENT BRAIN]")
    for step in agent_log:
        if step["type"] == "llm_call":
            print(f"    → LLM call #{step['iteration']}")
        elif step["type"] == "llm_response":
            print(f"    ← stop_reason: {step['stop_reason']} "
                  f"({step.get('input_tokens', '?')}in / {step.get('output_tokens', '?')}out tokens)")
        elif step["type"] == "tool_call":
            print(f"    🔧 TOOL: {step['tool']}")
            print(f"       {json.dumps(step['input'], ensure_ascii=False)}")
        elif step["type"] == "observation":
            print(f"    👁  OBS: {step['result'][:100]}")
        elif step["type"] == "error":
            print(f"    ❌ ERROR: {step['stop_reason']}")


def run_test():
    pm_context = (
        "Je suis PM dans une scale-up B2B SaaS. "
        "Mon produit aide les équipes RH à gérer les entretiens de recrutement. "
        "Je veux mieux comprendre les douleurs des responsables RH en PME."
    )

    # One trace for the entire session — all spans will be linked under it in Langfuse
    trace = create_session_trace(pm_context)
    print(f"\n  Langfuse trace created. View at: cloud.langfuse.com")

    print_separator("STEP 1 — Persona Generation")
    persona = generate_persona(pm_context, trace=trace)
    print(json.dumps(persona, indent=2, ensure_ascii=False))

    print_separator("STEP 2 — Metrics")
    metrics = generate_metrics(persona, pm_context, trace=trace)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    session_state = {
        "persona": persona,
        "metrics": metrics,
        "conversation_history": [],
        "resistance_level": persona.get("initial_resistance", 7),
        "revealed_pains": {},
        "flagged_questions": []
    }

    print_separator("STEP 3 — Interview (ReAct loop)")

    questions = [
        "Bonjour, merci de me recevoir. Pouvez-vous me décrire votre rôle ?",
        "Et dans votre quotidien, qu'est-ce qui vous prend le plus de temps dans le recrutement ?",
        "Quand vous dites que ça prend du temps — vous pouvez me donner un exemple concret d'une situation récente où ça s'est mal passé ?"
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n  [PM - Q{i}] {question}")
        result = run_persona_turn(question, session_state, trace=trace)

        print_agent_log(result["agent_log"])
        print(f"\n  [PERSONA] {result['response']}")
        print(f"  [STATE] resistance={session_state['resistance_level']} | "
              f"pains_revealed={list(session_state['revealed_pains'].keys())} | "
              f"questions_flagged={len(session_state.get('flagged_questions', []))}")

    # Close the trace with final session summary
    trace.update(
        output={
            "revealed_pains": session_state["revealed_pains"],
            "flagged_questions": session_state.get("flagged_questions", []),
            "final_resistance": session_state["resistance_level"]
        }
    )

    print_separator("SESSION COMPLETE")
    print("  Check cloud.langfuse.com for the full trace.")
    print(json.dumps({
        "revealed_pains": session_state["revealed_pains"],
        "flagged_questions": session_state.get("flagged_questions", []),
        "final_resistance": session_state["resistance_level"]
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_test()
