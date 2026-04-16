"""
Persona Agent — ReAct loop with Langfuse observability.

Langfuse trace structure for each interview turn:
  Trace: "interview-session"
    └── Span: "persona-turn"
          └── Generation: "react-iteration-N"  (each LLM call)
                └── Event: "tool-call:{name}"  (each tool execution)
"""

import os
import anthropic
from dotenv import load_dotenv
from langfuse import Langfuse

from tools.persona_tools import PERSONA_TOOL_DEFINITIONS, execute_tool
from prompts.persona_system import build_persona_system_prompt

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
langfuse = Langfuse()  # reads LANGFUSE_PUBLIC_KEY, SECRET_KEY, HOST from env
MODEL = "claude-sonnet-4-6"


def run_persona_turn(pm_question: str, session_state: dict, trace=None) -> dict:
    """
    Main ReAct loop for one interview turn.

    Args:
        pm_question: The PM's question
        session_state: Full mutable session (persona, history, resistance, etc.)
        trace: Langfuse trace object (pass the session trace for continuity)

    Returns:
        {response, agent_log, session_state}
    """
    system_prompt = build_persona_system_prompt(session_state["persona"])

    session_state["conversation_history"].append({
        "role": "user",
        "content": pm_question
    })

    messages = list(session_state["conversation_history"])
    agent_log = []

    # Langfuse: one span per PM turn
    span = trace.span(
        name="persona-turn",
        input={"pm_question": pm_question},
        metadata={"resistance_level": session_state.get("resistance_level")}
    ) if trace else None

    final_response = ""
    iteration = 0
    max_iterations = 10

    # ── ReAct loop ───────────────────────────────────────────────────────────
    while iteration < max_iterations:
        iteration += 1
        agent_log.append({"type": "llm_call", "iteration": iteration})

        # Langfuse: track each LLM call as a Generation (captures tokens + latency)
        generation = span.generation(
            name=f"react-iteration-{iteration}",
            model=MODEL,
            input=messages,
            metadata={"system_prompt_length": len(system_prompt)}
        ) if span else None

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=PERSONA_TOOL_DEFINITIONS,
            messages=messages
        )

        # Log token usage to Langfuse
        if generation:
            generation.end(
                output=_extract_text_blocks(response.content),
                usage={
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens
                }
            )

        agent_log.append({
            "type": "llm_response",
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        })

        # ── Claude is done → extract response and exit
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_response = block.text
            break

        # ── Claude wants tools → execute each one and feed observations back
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

                    # Langfuse: log each tool call as an Event inside the span
                    if span:
                        span.event(
                            name=f"tool-call:{block.name}",
                            input=block.input,
                            metadata={"iteration": iteration}
                        )

                    # Execute — mutates session_state
                    observation = execute_tool(block.name, block.input, session_state)

                    agent_log.append({
                        "type": "observation",
                        "tool": block.name,
                        "result": observation
                    })

                    # Log the observation back on the same event
                    if span:
                        span.event(
                            name=f"observation:{block.name}",
                            output=observation,
                            metadata={"resistance_after": session_state.get("resistance_level")}
                        )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": observation
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            agent_log.append({"type": "error", "stop_reason": response.stop_reason})
            break

    # ── Close span with final output
    if span:
        span.end(
            output={"response": final_response},
            metadata={
                "total_iterations": iteration,
                "revealed_pains": list(session_state.get("revealed_pains", {}).keys()),
                "final_resistance": session_state.get("resistance_level")
            }
        )

    if final_response:
        session_state["conversation_history"].append({
            "role": "assistant",
            "content": final_response
        })

    return {
        "response": final_response,
        "agent_log": agent_log,
        "session_state": session_state
    }


def generate_persona(pm_context: str, trace=None) -> dict:
    """Step 1 — Generates a synthetic persona. Never shown to the PM."""
    span = trace.span(name="generate-persona", input={"pm_context": pm_context}) if trace else None

    generation = span.generation(name="persona-llm-call", model=MODEL) if span else None

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": _persona_prompt(pm_context)}]
    )

    if generation:
        generation.end(
            output=response.content[0].text,
            usage={"input": response.usage.input_tokens, "output": response.usage.output_tokens}
        )

    import json
    persona = _parse_json(response.content[0].text)

    if span:
        span.end(output=persona)

    return persona


def generate_metrics(persona: dict, pm_context: str, trace=None) -> list:
    """Step 2 — Proposes 3-5 relevant metrics for this persona."""
    span = trace.span(name="generate-metrics", input={"persona_role": persona["role"]}) if trace else None

    generation = span.generation(name="metrics-llm-call", model=MODEL) if span else None

    prompt = f"""Given this persona and PM context, propose 4 metrics relevant for a discovery interview.

Persona: {persona['role']} at {persona['company_type']}
PM context: {pm_context}

Return a JSON array:
[{{"id": 0, "name": "...", "description": "...", "example": "..."}}]

Return only the JSON."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )

    if generation:
        generation.end(
            output=response.content[0].text,
            usage={"input": response.usage.input_tokens, "output": response.usage.output_tokens}
        )

    metrics = _parse_json(response.content[0].text)

    if span:
        span.end(output=metrics)

    return metrics


def create_session_trace(pm_context: str) -> object:
    """
    Creates a Langfuse trace for the full interview session.
    Call this once at the start, pass the trace to all subsequent functions.
    This links all spans (persona generation, metrics, each turn) under one session.
    """
    return langfuse.trace(
        name="interview-session",
        input={"pm_context": pm_context},
        tags=["pm-case-trainer"]
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_text_blocks(content: list) -> str:
    return " ".join(b.text for b in content if hasattr(b, "text"))


def _parse_json(text: str) -> dict | list:
    import json
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
