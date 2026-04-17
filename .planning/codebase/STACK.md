# Technology Stack

**Analysis Date:** 2026-04-17

## Languages

**Primary:**
- Python 3.x - All backend logic, agents, tools, and storage operations

## Runtime

**Environment:**
- Python 3.x with venv virtual environment
- `.python-version` or similar version pinning not detected

**Package Manager:**
- pip
- Lockfile: `requirements.txt` (present)

## Frameworks

**Core UI:**
- Streamlit 1.56.0+ - Web interface with real-time agent decision panel

**AI/LLM:**
- Anthropic Python SDK 0.96.0+ - Claude API access for agent function calling
- Langfuse 4.3.0+ - Observability and tracing with OpenTelemetry patterns

**Database Client:**
- Supabase 2.0.0+ - Session persistence and cross-session learning (optional)

**Utilities:**
- python-dotenv 1.0.0+ - Environment variable management

## Key Dependencies

**Critical:**
- `anthropic>=0.96.0` - LLM backbone; enables `function_calling` with `stop_reason` control
- `streamlit>=1.56.0` - UI framework; entire frontend is built on Streamlit components
- `langfuse>=4.3.0` - Observability; enables `@observe()` decorator pattern for automatic span creation (v4 uses OpenTelemetry)

**Infrastructure:**
- `python-dotenv>=1.0.0` - Loads `.env` file locally; Streamlit Cloud reads from `st.secrets`
- `supabase>=2.0.0` - Optional; enables session storage and dashboard stats. App degrades gracefully if credentials missing.

## Configuration

**Environment:**
- Local development: `.env` file (git-ignored)
- Streamlit Cloud: `st.secrets` configuration in dashboard
- See `.env.example` for required variables

**Secrets Injection (app.py lines 7-13):**
```python
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Streamlit Cloud: inject st.secrets into env vars
for key in ["ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", 
            "LANGFUSE_HOST", "SUPABASE_URL", "SUPABASE_KEY"]:
    if key in st.secrets and not os.getenv(key):
        os.environ[key] = st.secrets[key]
```

**Build:**
- No build process; pure Python application
- Streamlit auto-reloads on file changes

## Platform Requirements

**Development:**
- Python 3.x
- pip
- Git
- Text editor or IDE

**Production:**
- Streamlit Cloud (deployed via git push to main branch)
- Anthropic API (via sk-ant-* key)
- Langfuse Cloud (optional but recommended for observability)
- Supabase Cloud (optional; degrades gracefully)

## Model Configuration

**Claude Model:**
- `claude-sonnet-4-6` - Used for both Persona Agent and Feedback Agent
- Context window: adequate for interview transcripts and analysis
- Max tokens per request: 1024 (persona turns) and 2048 (feedback analysis)
- Function calling enabled: required for ReAct loop tool execution

## Observability

**Instrumentation:**
- Langfuse v4 with `@observe()` decorator pattern
- Automatic span creation for each decorated function
- Custom metadata updates via `get_client().update_current_span()`
- Trace hierarchy: root trace → generate_persona/metrics spans → persona-turn spans → react-loop spans → tool spans

**Output:**
- Langfuse dashboard at `https://cloud.langfuse.com`
- Traces include token counts, stop reasons, tool calls, and custom metadata

---

*Stack analysis: 2026-04-17*
