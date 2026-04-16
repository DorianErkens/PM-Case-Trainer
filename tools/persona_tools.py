"""
Tools available to the Persona Agent during the interview.

Each tool has two parts:
  1. DEFINITION  — the JSON schema Claude sees to decide WHEN and HOW to call it
  2. EXECUTOR    — the Python function that actually runs when Claude calls it
"""

# ─────────────────────────────────────────────
# PART 1 — Tool definitions (sent to Claude)
# ─────────────────────────────────────────────

PERSONA_TOOL_DEFINITIONS = [
    {
        "name": "reveal_pain",
        "description": (
            "Reveal one of the persona's hidden pains to the conversation. "
            "Call this when the PM has asked a sufficiently deep or open question "
            "that earns a genuine insight. Do NOT call this for surface-level or "
            "yes/no questions. The revealed pain will be woven into your next response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pain_id": {
                    "type": "integer",
                    "description": "ID of the pain to reveal (from the persona's pain list)"
                },
                "reveal_level": {
                    "type": "string",
                    "enum": ["hint", "partial", "full"],
                    "description": (
                        "hint = vague allusion, partial = acknowledge the problem, "
                        "full = share concrete details and impact"
                    )
                }
            },
            "required": ["pain_id", "reveal_level"]
        }
    },
    {
        "name": "update_resistance",
        "description": (
            "Adjust how open or closed the persona is. "
            "Call this when the PM's questioning style warrants a change: "
            "lower resistance if questions are empathetic and deep, "
            "raise resistance if questions feel salesy, aggressive, or superficial."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "new_level": {
                    "type": "integer",
                    "description": "Resistance level from 1 (very open) to 10 (very closed)",
                    "minimum": 1,
                    "maximum": 10
                },
                "reason": {
                    "type": "string",
                    "description": "Why are you changing the resistance level?"
                }
            },
            "required": ["new_level", "reason"]
        }
    },
    {
        "name": "check_already_revealed",
        "description": (
            "Check if a pain has already been revealed in this conversation. "
            "Call this before revealing a pain to avoid contradicting yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pain_id": {
                    "type": "integer",
                    "description": "ID of the pain to check"
                }
            },
            "required": ["pain_id"]
        }
    },
    {
        "name": "flag_question",
        "description": (
            "Flag the PM's last question for the feedback report. "
            "Call this when a question is notably good or bad. "
            "This data will be used by the Feedback Agent at the end."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quality": {
                    "type": "string",
                    "enum": ["excellent", "good", "weak", "leading", "closed"],
                    "description": "Quality tag for this question"
                },
                "question_text": {
                    "type": "string",
                    "description": "The PM's question, copied verbatim"
                },
                "reason": {
                    "type": "string",
                    "description": "Why this question is flagged"
                }
            },
            "required": ["quality", "question_text", "reason"]
        }
    }
]


# ─────────────────────────────────────────────
# PART 2 — Tool executors (your Python code)
# ─────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict, session_state: dict) -> str:
    """
    Router: receives the tool call from Claude, runs the right function,
    returns a string result that Claude will read as its observation.
    """
    if tool_name == "reveal_pain":
        return _reveal_pain(tool_input, session_state)
    elif tool_name == "update_resistance":
        return _update_resistance(tool_input, session_state)
    elif tool_name == "check_already_revealed":
        return _check_already_revealed(tool_input, session_state)
    elif tool_name == "flag_question":
        return _flag_question(tool_input, session_state)
    else:
        return f"Unknown tool: {tool_name}"


def _reveal_pain(tool_input: dict, state: dict) -> str:
    pain_id = tool_input["pain_id"]
    level = tool_input["reveal_level"]
    pains = state.get("persona", {}).get("pains", [])

    if pain_id >= len(pains):
        return f"Error: pain_id {pain_id} does not exist."

    pain = pains[pain_id]

    if pain_id in state.get("revealed_pains", {}):
        already = state["revealed_pains"][pain_id]
        return f"Pain {pain_id} already revealed at level '{already}'. Staying consistent."

    if "revealed_pains" not in state:
        state["revealed_pains"] = {}
    state["revealed_pains"][pain_id] = level

    return (
        f"Pain {pain_id} revealed at level '{level}'.\n"
        f"Pain content: {pain}\n"
        f"Weave this naturally into your response at the '{level}' depth."
    )


def _update_resistance(tool_input: dict, state: dict) -> str:
    old_level = state.get("resistance_level", 7)
    new_level = tool_input["new_level"]
    reason = tool_input["reason"]
    state["resistance_level"] = new_level
    return f"Resistance updated: {old_level} → {new_level}. Reason: {reason}"


def _check_already_revealed(tool_input: dict, state: dict) -> str:
    pain_id = tool_input["pain_id"]
    revealed = state.get("revealed_pains", {})
    if pain_id in revealed:
        return f"Pain {pain_id} was already revealed at level '{revealed[pain_id]}'. Do not contradict."
    return f"Pain {pain_id} has NOT been revealed yet. You can reveal it if warranted."


def _flag_question(tool_input: dict, state: dict) -> str:
    if "flagged_questions" not in state:
        state["flagged_questions"] = []
    state["flagged_questions"].append({
        "quality": tool_input["quality"],
        "question": tool_input["question_text"],
        "reason": tool_input["reason"]
    })
    return f"Question flagged as '{tool_input['quality']}': logged for feedback report."
