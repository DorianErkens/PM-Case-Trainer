"""
Terminal test — run this to see the ReAct loop + Langfuse traces in action.

Usage:
  python test_agent.py

In terminal: each ReAct iteration with tool calls and observations.
In Langfuse (cloud.langfuse.com): full nested trace with all child spans.
"""

import json
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from langfuse import observe
from agents.persona_agent import generate_persona, generate_metrics, run_persona_turn


def print_sep(title: str):
    print(f"\n{'═' * 60}\n  {title}\n{'═' * 60}")


def print_agent_log(agent_log: list):
    print("\n  [AGENT BRAIN]")
    for step in agent_log:
        if step["type"] == "llm_call":
            print(f"    → LLM call #{step['iteration']}")
        elif step["type"] == "llm_response":
            print(f"    ← {step['stop_reason']}  "
                  f"({step.get('input_tokens')}in / {step.get('output_tokens')}out tokens)")
        elif step["type"] == "tool_call":
            print(f"    🔧 {step['tool']}  {json.dumps(step['input'], ensure_ascii=False)}")
        elif step["type"] == "observation":
            print(f"    👁  {step['result'][:100]}")
        elif step["type"] == "error":
            print(f"    ❌ {step['stop_reason']}")


# @observe() here = root trace. All nested @observe() calls become child spans automatically.
@observe(name="interview-session")
def run_test():
    pm_context = (
        "Je suis PM dans une scale-up B2B SaaS. "
        "Mon produit aide les équipes RH à gérer les entretiens de recrutement. "
        "Je veux mieux comprendre les douleurs des responsables RH en PME."
    )

    print_sep("STEP 1 — Persona Generation")
    persona = generate_persona(pm_context)
    print(json.dumps(persona, indent=2, ensure_ascii=False))

    print_sep("STEP 2 — Metrics")
    metrics = generate_metrics(persona, pm_context)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    session_state = {
        "persona": persona,
        "metrics": metrics,
        "conversation_history": [],
        "resistance_level": persona.get("initial_resistance", 7),
        "revealed_pains": {},
        "flagged_questions": []
    }

    print_sep("STEP 3 — Interview (ReAct loop)")

    questions = [
        "Bonjour, merci de me recevoir. Pouvez-vous me décrire votre rôle ?",
        "Et dans votre quotidien, qu'est-ce qui vous prend le plus de temps dans le recrutement ?",
        "Quand vous dites que ça prend du temps — pouvez-vous me donner un exemple concret d'une situation récente où ça s'est mal passé ?"
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n  [PM - Q{i}] {question}")
        result = run_persona_turn(question, session_state)
        print_agent_log(result["agent_log"])
        print(f"\n  [PERSONA] {result['response']}")
        print(f"  [STATE] resistance={session_state['resistance_level']} | "
              f"pains={list(session_state['revealed_pains'].keys())} | "
              f"flagged={len(session_state.get('flagged_questions', []))}")

    print_sep("DONE — check cloud.langfuse.com for the full trace")


if __name__ == "__main__":
    run_test()
