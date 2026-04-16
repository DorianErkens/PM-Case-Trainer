"""
Persona Agent — ReAct loop with Langfuse v4 observability.

Langfuse v4 uses OpenTelemetry under the hood.
Pattern: @observe() auto-creates spans; get_client() lets you update the current span.

Trace structure in Langfuse dashboard:
  run_test()                  [root trace]
    ├── generate_persona()    [span]
    ├── generate_metrics()    [span]
    └── run_persona_turn()    [span — one per PM question]
          └── _react_loop()  [span — shows each iteration + tool calls]
"""

import os
import json
import anthropic
from dotenv import load_dotenv
from langfuse import observe, get_client

from tools.persona_tools import PERSONA_TOOL_DEFINITIONS, execute_tool
from prompts.persona_system import build_persona_system_prompt

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


@observe(name="persona-turn", as_type="agent")
def run_persona_turn(pm_question: str, session_state: dict) -> dict:
    """
    One interview turn. @observe() auto-captures inputs/outputs as a Langfuse span.
    Because it's nested inside @observe()-decorated callers, it appears as a child span.
    """
    system_prompt = build_persona_system_prompt(session_state["persona"])

    session_state["conversation_history"].append({
        "role": "user",
        "content": pm_question
    })

    result = _react_loop(system_prompt, session_state)

    # Update the current span with extra context visible in Langfuse
    get_client().update_current_span(metadata={
        "resistance_level": session_state.get("resistance_level"),
        "revealed_pains": str(list(session_state.get("revealed_pains", {}).keys())),
        "flagged_questions": len(session_state.get("flagged_questions", []))
    })

    return result


@observe(name="react-loop", as_type="chain")
def _react_loop(system_prompt: str, session_state: dict) -> dict:
    """
    The ReAct loop: Claude reasons → calls tools → observes → repeats until end_turn.
    Each iteration is logged with token counts and tool calls.
    """
    messages = list(session_state["conversation_history"])
    agent_log = []
    final_response = ""
    iteration = 0

    while iteration < 10:
        iteration += 1
        agent_log.append({"type": "llm_call", "iteration": iteration})

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=PERSONA_TOOL_DEFINITIONS,
            messages=messages
        )

        agent_log.append({
            "type": "llm_response",
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        })

        # Log token usage per iteration on the current span
        get_client().update_current_span(metadata={
            f"iter_{iteration}_in_tokens": response.usage.input_tokens,
            f"iter_{iteration}_out_tokens": response.usage.output_tokens,
            f"iter_{iteration}_stop": response.stop_reason,
        })

        # ── Claude is done
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_response = block.text
            break

        # ── Claude wants to call tools
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    agent_log.append({
                        "type": "tool_call",
                        "tool": block.name,
                        "input": block.input
                    })

                    # Each tool call is a child span in Langfuse
                    with get_client().start_as_current_observation(
                        name=f"tool:{block.name}",
                        as_type="tool",
                        input=block.input
                    ) as tool_span:
                        observation = execute_tool(block.name, block.input, session_state)
                        tool_span.update(output=observation)

                    agent_log.append({
                        "type": "observation",
                        "tool": block.name,
                        "result": observation
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": observation
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            agent_log.append({"type": "error", "stop_reason": response.stop_reason})
            break

    if final_response:
        session_state["conversation_history"].append({
            "role": "assistant",
            "content": final_response
        })

    return {"response": final_response, "agent_log": agent_log}


@observe(name="generate-persona", as_type="chain")
def generate_persona(pm_context: str) -> dict:
    """Step 1 — Generates a synthetic persona. Never shown to the PM."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": _persona_prompt(pm_context)}]
    )

    persona = _parse_json(response.content[0].text)

    get_client().update_current_span(metadata={
        "in_tokens": response.usage.input_tokens,
        "out_tokens": response.usage.output_tokens,
        "persona_role": persona.get("role", ""),
        "initial_resistance": persona.get("initial_resistance", 7)
    })

    return persona


@observe(name="generate-metrics", as_type="chain")
def generate_metrics(persona: dict, pm_context: str) -> list:
    """Step 2 — Proposes 4 relevant metrics for this persona and PM context."""
    prompt = f"""Given this persona and PM context, propose 4 metrics relevant for a discovery interview.

Persona: {persona['role']} at {persona['company_type']}
PM context: {pm_context}

Return a JSON array:
[{{"id": 0, "name": "...", "description": "...", "example": "..."}}]

Return only the JSON."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    metrics = _parse_json(response.content[0].text)

    get_client().update_current_span(metadata={
        "in_tokens": response.usage.input_tokens,
        "out_tokens": response.usage.output_tokens,
        "metrics_count": len(metrics)
    })

    return metrics


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _persona_prompt(pm_context: str) -> str:
    return f"""Based on this PM's context, generate a realistic synthetic user persona.

PM context: {pm_context}

Return a JSON object:
{{
  "name": "First Last",
  "role": "Job title",
  "company_type": "Type and size of company",
  "personality": "2-3 word description (e.g. busy, skeptical, pragmatic)",
  "initial_resistance": 7,
  "pains": [
    "Pain 0: specific and concrete",
    "Pain 1: another pain",
    "Pain 2: another pain",
    "Pain 3: deeper, harder to surface"
  ]
}}

Return only the JSON."""
