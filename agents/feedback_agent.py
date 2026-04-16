"""
Feedback Agent — analyzes the interview session and generates a structured report.

Same ReAct pattern as persona_agent.py but different tools and purpose:
- Persona Agent: plays a role, reacts in real-time
- Feedback Agent: reflects on the full session, builds analysis step by step

Called once at the end of the interview with the complete session_state.
"""

import os
import anthropic
from dotenv import load_dotenv
from langfuse import observe, get_client

from tools.feedback_tools import FEEDBACK_TOOL_DEFINITIONS, execute_feedback_tool
from prompts.feedback_system import build_feedback_system_prompt

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


@observe(name="feedback-agent", as_type="agent")
def run_feedback(session_state: dict) -> dict:
    """
    Entry point for the Feedback Agent.
    Takes the complete session_state and returns a structured report + agent log.
    """
    persona = session_state["persona"]
    metrics = session_state.get("metrics", [])

    system_prompt = build_feedback_system_prompt(persona, metrics)

    # Single trigger message — the agent decides its own analysis sequence via tools
    trigger = (
        "The interview session is complete. "
        "Use your tools to analyze the session data, then generate the feedback report."
    )

    get_client().update_current_span(
        input={"persona_role": persona["role"], "questions_count": len(session_state.get("flagged_questions", []))},
        metadata={
            "revealed_pains": list(session_state.get("revealed_pains", {}).keys()),
            "final_resistance": session_state.get("resistance_level")
        }
    )

    messages = [{"role": "user", "content": trigger}]
    agent_log = []
    report = ""
    iteration = 0

    # ── ReAct loop (same pattern as persona_agent) ────────────────────────────
    while iteration < 15:
        iteration += 1
        agent_log.append({"type": "llm_call", "iteration": iteration})

        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system_prompt,
            tools=FEEDBACK_TOOL_DEFINITIONS,
            messages=messages
        )

        agent_log.append({
            "type": "llm_response",
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        })

        get_client().update_current_span(metadata={
            f"iter_{iteration}_tokens": {
                "in": response.usage.input_tokens,
                "out": response.usage.output_tokens
            }
        })

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    report = block.text
            break

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

                    with get_client().start_as_current_observation(
                        name=f"tool:{block.name}",
                        as_type="tool",
                        input=block.input
                    ) as tool_span:
                        observation = execute_feedback_tool(block.name, block.input, session_state)
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

    get_client().update_current_span(
        output={"score": session_state.get("_final_score"), "report_length": len(report)},
        metadata={"total_iterations": iteration}
    )

    return {
        "report": report,
        "score": session_state.get("_final_score"),
        "agent_log": agent_log
    }
