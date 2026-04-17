# External Integrations

**Analysis Date:** 2026-04-17

## APIs & External Services

**LLM API:**
- Claude 3.5 Sonnet (via Anthropic API)
  - SDK/Client: `anthropic` Python SDK
  - Auth: `ANTHROPIC_API_KEY` (env var, sk-ant-* format)
  - Usage: Both Persona Agent and Feedback Agent use Claude for ReAct loops with function calling
  - Models used: `claude-sonnet-4-6` (lines 27, 21 in agents/*.py)

**Observability & Tracing:**
- Langfuse Cloud
  - SDK/Client: `langfuse` Python package v4.3.0+
  - Auth: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (env vars)
  - Host: `LANGFUSE_HOST=https://cloud.langfuse.com` (env var)
  - Usage: Automatic tracing via `@observe()` decorator; captures all LLM calls, tool calls, and metadata
  - Pattern: OpenTelemetry under hood; no manual span creation needed for decorated functions
  - See `agents/persona_agent.py` lines 19-50 and `agents/feedback_agent.py` lines 14-48 for implementation

## Data Storage

**Databases:**
- Supabase PostgreSQL (optional, gracefully degraded)
  - Connection: `SUPABASE_URL` and `SUPABASE_KEY` (env vars)
  - Client: `supabase` Python SDK v2.0.0+
  - Table: `sessions` (stores completed interview records)
  - Schema: Inferred from `session_store.py` lines 55-66:
    - `pm_context` (text)
    - `persona_role` (text)
    - `score` (int)
    - `score_breakdown` (JSON: pain_discovery, question_quality, metric_coverage)
    - `flagged_questions` (JSON array)
    - `revealed_pains` (JSON object, key=pain_id, value=reveal_level)
    - `missed_pains` (JSON array)
    - `metrics_covered` (int)
    - `total_questions` (int)
    - `report` (text)
    - `created_at` (timestamp, auto-generated)

**File Storage:**
- Local filesystem only
  - `.env` file for development
  - `.streamlit/secrets.toml.example` for deployment reference

**Caching:**
- None detected; all computation is request-scoped
- Session state is in-memory (Streamlit's `st.session_state`)

## Authentication & Identity

**Auth Provider:**
- Custom environment variable injection
- No user authentication system; app is stateless per session
- Single-user pattern: all sessions written to same Supabase table

**Pattern (app.py lines 7-13):**
```python
# Local: read .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Streamlit Cloud: st.secrets → env vars
for key in ["ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", ...]:
    if key in st.secrets and not os.getenv(key):
        os.environ[key] = st.secrets[key]
```

## Monitoring & Observability

**Error Tracking:**
- Langfuse captures exceptions and stop reasons (non-end_turn stops logged as errors)
- See `agents/persona_agent.py` line 136 and `agents/feedback_agent.py` line 123

**Logs:**
- Console output via `print()` statements (fallback messages when Supabase unavailable)
- `storage/session_store.py` lines 72-73: `print(f"[session_store] Save failed: {e}")`
- Streamlit spinner messages for UX feedback during long operations
- Langfuse dashboard for structured traces

**Agent Brain Panel:**
- Real-time visualization of agent decisions in UI (`app.py` lines 304-309)
- `brain_log` in `st.session_state` stores structured events (llm_call, tool_call, observation, error, state_update)

## CI/CD & Deployment

**Hosting:**
- Streamlit Cloud (https://pm-case-trainer.streamlit.app)
- Deployment: Git push to main branch (GitHub repo linked in Streamlit dashboard)

**CI Pipeline:**
- None detected; Streamlit auto-deploys on main branch push

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Claude API key (sk-ant-...)
- `LANGFUSE_PUBLIC_KEY` - Langfuse public key (pk-lf-...)
- `LANGFUSE_SECRET_KEY` - Langfuse secret key (sk-lf-...)
- `LANGFUSE_HOST` - Langfuse host (default: https://cloud.langfuse.com)

**Optional env vars:**
- `SUPABASE_URL` - Supabase project URL (if omitted, session persistence disabled)
- `SUPABASE_KEY` - Supabase anon key (if omitted, session persistence disabled)

**Secrets location:**
- Development: `.env` file (git-ignored)
- Production (Streamlit Cloud): Settings → Secrets in Streamlit dashboard
- `.env.example` shows all required variables (lines 1-6)
- `.streamlit/secrets.toml.example` shows deployment format

## Webhooks & Callbacks

**Incoming:**
- None detected; all interaction is synchronous HTTP requests via Streamlit

**Outgoing:**
- None detected; no callbacks to external services
- Supabase inserts are synchronous (client.table("sessions").insert().execute())

## Cross-Session Learning

**Session Storage Pattern (storage/session_store.py):**

1. **Save (lines 27-73):**
   - Called at end of interview (`app.py` line 235)
   - Inserts record to Supabase `sessions` table
   - Fails gracefully (returns False, prints error, app continues)

2. **Load (lines 76-96):**
   - `load_recent_sessions(n=5)` returns last N sessions from database
   - Called by Feedback Agent via tool `load_pm_history` (`tools/feedback_tools.py` lines 116-154)
   - Returns [] if Supabase unavailable

3. **Aggregate Stats (lines 99-141):**
   - `get_dashboard_stats()` computes averages and trends
   - Called by UI for progress dashboard (`app.py` line 259)
   - Returns {} if Supabase unavailable
   - Calculates: total_sessions, avg_score, best_score, score_trend, recurring_misses

**Data Flow:**
```
Interview completes
  ↓
save_session() → INSERT to Supabase
  ↓
Feedback Agent runs
  ↓
load_pm_history() tool → SELECT from Supabase (last 5 sessions)
  ↓
Agent references recurring patterns in report
  ↓
UI calls get_dashboard_stats() → SELECT aggregates
  ↓
Progress dashboard displays trends
```

---

*Integration audit: 2026-04-17*
