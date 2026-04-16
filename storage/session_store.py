"""
Session storage — Supabase client.

Handles saving and loading interview sessions for cross-session learning.
All functions fail gracefully: if Supabase is unreachable, the app keeps working.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _get_client():
    """Returns a Supabase client, or None if credentials are missing."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def save_session(session_state: dict, feedback_result: dict) -> bool:
    """
    Saves a completed interview session to Supabase.
    Called at the end of the feedback step.
    Returns True if saved, False if skipped (no credentials or error).
    """
    client = _get_client()
    if not client:
        return False

    persona = session_state.get("persona", {})
    all_pains = persona.get("pains", [])
    revealed = session_state.get("revealed_pains", {})
    flagged = session_state.get("flagged_questions", [])
    metrics = session_state.get("metrics", [])

    missed_pains = [
        {"id": i, "content": pain}
        for i, pain in enumerate(all_pains)
        if i not in revealed
    ]

    score_breakdown = {
        "pain_discovery": session_state.get("_pain_discovery_rate"),
        "question_quality": session_state.get("_depth_score"),
        "metric_coverage": session_state.get("_metric_coverage_rate")
    }

    record = {
        "pm_context":         session_state.get("pm_context", ""),
        "persona_role":       persona.get("role", ""),
        "score":              feedback_result.get("score"),
        "score_breakdown":    score_breakdown,
        "flagged_questions":  flagged,
        "revealed_pains":     {str(k): v for k, v in revealed.items()},
        "missed_pains":       missed_pains,
        "metrics_covered":    session_state.get("_metric_coverage_rate"),
        "total_questions":    len(flagged),
        "report":             feedback_result.get("report", "")
    }

    try:
        client.table("sessions").insert(record).execute()
        return True
    except Exception as e:
        print(f"[session_store] Save failed: {e}")
        return False


def load_recent_sessions(n: int = 5) -> list:
    """
    Loads the N most recent sessions from Supabase.
    Returns a list of session dicts, or [] if unavailable.
    """
    client = _get_client()
    if not client:
        return []

    try:
        response = (
            client.table("sessions")
            .select("created_at, pm_context, persona_role, score, score_breakdown, flagged_questions, missed_pains, total_questions")
            .order("created_at", desc=True)
            .limit(n)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"[session_store] Load failed: {e}")
        return []


def get_dashboard_stats() -> dict:
    """
    Returns aggregated stats for the progress dashboard.
    Used by the Streamlit sidebar/dashboard view.
    """
    client = _get_client()
    if not client:
        return {}

    try:
        response = (
            client.table("sessions")
            .select("created_at, score, score_breakdown, total_questions, missed_pains")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        sessions = response.data or []
        if not sessions:
            return {}

        scores = [s["score"] for s in sessions if s.get("score") is not None]
        avg_score = round(sum(scores) / len(scores)) if scores else 0

        # Most common question quality issues across all sessions
        pain_miss_counts = {}
        for s in sessions:
            for pain in (s.get("missed_pains") or []):
                content = pain.get("content", "")[:60]
                pain_miss_counts[content] = pain_miss_counts.get(content, 0) + 1

        recurring_misses = sorted(pain_miss_counts.items(), key=lambda x: -x[1])[:3]

        return {
            "total_sessions": len(sessions),
            "avg_score": avg_score,
            "best_score": max(scores) if scores else 0,
            "score_trend": scores[::-1],  # chronological order
            "recurring_misses": recurring_misses,
        }
    except Exception as e:
        print(f"[session_store] Stats failed: {e}")
        return {}
