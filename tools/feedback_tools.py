"""
Tools available to the Feedback Agent after the interview session.
Same pattern as persona_tools: DEFINITIONS (what Claude sees) + EXECUTORS (Python code).
"""

FEEDBACK_TOOL_DEFINITIONS = [
    {
        "name": "analyze_question_patterns",
        "description": (
            "Analyze the quality distribution of the PM's questions. "
            "Call this first to understand the overall questioning style before scoring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "enum": ["depth", "type_ratio", "progression"],
                    "description": (
                        "depth = how well the PM dug into answers, "
                        "type_ratio = open vs closed questions, "
                        "progression = did the PM build on previous answers"
                    )
                }
            },
            "required": ["focus"]
        }
    },
    {
        "name": "identify_missed_pains",
        "description": (
            "Compare the persona's full pain list against what was actually revealed. "
            "Call this to understand what the PM failed to surface."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "match_pains_to_metrics",
        "description": (
            "For each revealed pain, identify which metric it relates to. "
            "Also flag which metrics were never addressed. "
            "Call this after identify_missed_pains to build the coverage picture."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "compute_score",
        "description": (
            "Compute the final score (0-100) based on the analysis so far. "
            "Call this last, after all other tools have run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pain_discovery_weight": {
                    "type": "number",
                    "description": "Weight for pain discovery component (0-1, must sum to 1 with other weights)"
                },
                "question_quality_weight": {
                    "type": "number",
                    "description": "Weight for question quality component"
                },
                "metric_coverage_weight": {
                    "type": "number",
                    "description": "Weight for metric coverage component"
                }
            },
            "required": ["pain_discovery_weight", "question_quality_weight", "metric_coverage_weight"]
        }
    }
]


def execute_feedback_tool(tool_name: str, tool_input: dict, session_state: dict) -> str:
    if tool_name == "analyze_question_patterns":
        return _analyze_question_patterns(tool_input, session_state)
    elif tool_name == "identify_missed_pains":
        return _identify_missed_pains(session_state)
    elif tool_name == "match_pains_to_metrics":
        return _match_pains_to_metrics(session_state)
    elif tool_name == "compute_score":
        return _compute_score(tool_input, session_state)
    return f"Unknown tool: {tool_name}"


def _analyze_question_patterns(tool_input: dict, state: dict) -> str:
    flagged = state.get("flagged_questions", [])
    if not flagged:
        return "No questions were flagged during the interview."

    focus = tool_input["focus"]
    counts = {}
    for q in flagged:
        counts[q["quality"]] = counts.get(q["quality"], 0) + 1

    total = len(flagged)

    if focus == "type_ratio":
        open_types = {"excellent", "good"}
        closed_types = {"weak", "leading", "closed"}
        n_open = sum(counts.get(t, 0) for t in open_types)
        n_closed = sum(counts.get(t, 0) for t in closed_types)
        return (
            f"Question type ratio — Total: {total} | "
            f"Open/deep: {n_open} ({round(n_open/total*100)}%) | "
            f"Closed/weak: {n_closed} ({round(n_closed/total*100)}%)\n"
            f"Distribution: {counts}"
        )

    elif focus == "depth":
        excellent = counts.get("excellent", 0)
        good = counts.get("good", 0)
        weak = counts.get("weak", 0) + counts.get("closed", 0) + counts.get("leading", 0)
        depth_score = round((excellent * 1.0 + good * 0.6) / total * 100) if total else 0
        state["_depth_score"] = depth_score
        return (
            f"Depth analysis — Excellent: {excellent}, Good: {good}, Weak/closed: {weak}\n"
            f"Depth score: {depth_score}/100\n"
            f"Best questions: {[q['question'] for q in flagged if q['quality'] == 'excellent']}"
        )

    elif focus == "progression":
        qualities = [q["quality"] for q in flagged]
        improved = sum(
            1 for i in range(1, len(qualities))
            if qualities[i] in {"excellent", "good"} and qualities[i-1] in {"weak", "closed"}
        )
        return (
            f"Progression — Question sequence: {qualities}\n"
            f"Times PM improved after a weak question: {improved}"
        )

    return f"Unknown focus: {focus}"


def _identify_missed_pains(state: dict) -> str:
    all_pains = state.get("persona", {}).get("pains", [])
    revealed = state.get("revealed_pains", {})

    missed = [(i, pain) for i, pain in enumerate(all_pains) if i not in revealed]
    found = [(i, pain) for i, pain in enumerate(all_pains) if i in revealed]

    state["_pain_discovery_rate"] = round(len(found) / len(all_pains) * 100) if all_pains else 0

    result = f"Pain discovery: {len(found)}/{len(all_pains)} ({state['_pain_discovery_rate']}%)\n\n"
    result += "FOUND:\n"
    for i, pain in found:
        level = revealed[i]
        result += f"  [{i}] ({level}) {pain[:80]}...\n"
    result += "\nMISSED:\n"
    for i, pain in missed:
        result += f"  [{i}] {pain[:80]}...\n"

    return result


def _match_pains_to_metrics(state: dict) -> str:
    metrics = state.get("metrics", [])
    revealed = state.get("revealed_pains", {})
    all_pains = state.get("persona", {}).get("pains", [])

    if not metrics:
        return "No metrics defined for this session."

    coverage = {m["id"]: {"metric": m["name"], "matched_pains": []} for m in metrics}

    # Simple keyword matching between pain content and metric descriptions
    for pain_id, level in revealed.items():
        pain_text = all_pains[pain_id].lower() if pain_id < len(all_pains) else ""
        for metric in metrics:
            keywords = metric["name"].lower().split() + metric["description"].lower().split()
            if any(kw in pain_text for kw in keywords if len(kw) > 4):
                coverage[metric["id"]]["matched_pains"].append(pain_id)

    covered = sum(1 for v in coverage.values() if v["matched_pains"])
    state["_metric_coverage_rate"] = round(covered / len(metrics) * 100) if metrics else 0

    result = f"Metric coverage: {covered}/{len(metrics)} ({state['_metric_coverage_rate']}%)\n\n"
    for m_id, data in coverage.items():
        status = "✓" if data["matched_pains"] else "✗"
        result += f"  {status} [{m_id}] {data['metric']} → pains: {data['matched_pains']}\n"

    return result


def _compute_score(tool_input: dict, state: dict) -> str:
    w_pain = tool_input["pain_discovery_weight"]
    w_question = tool_input["question_quality_weight"]
    w_metric = tool_input["metric_coverage_weight"]

    if abs(w_pain + w_question + w_metric - 1.0) > 0.01:
        return f"Error: weights must sum to 1.0 (got {w_pain + w_question + w_metric})"

    pain_score = state.get("_pain_discovery_rate", 0)
    question_score = state.get("_depth_score", 0)
    metric_score = state.get("_metric_coverage_rate", 0)

    final = round(pain_score * w_pain + question_score * w_question + metric_score * w_metric)
    state["_final_score"] = final

    return (
        f"Score breakdown:\n"
        f"  Pain discovery:   {pain_score}/100 × {w_pain} = {round(pain_score * w_pain)}\n"
        f"  Question quality: {question_score}/100 × {w_question} = {round(question_score * w_question)}\n"
        f"  Metric coverage:  {metric_score}/100 × {w_metric} = {round(metric_score * w_metric)}\n"
        f"  ─────────────────────────────\n"
        f"  FINAL SCORE: {final}/100"
    )
