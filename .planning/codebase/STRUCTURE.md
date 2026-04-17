# Codebase Structure

**Analysis Date:** 2026-04-17

## Directory Layout

```
PM Case Trainer/
├── app.py                      # Streamlit UI entry point — four-step flow + Agent Brain panel
├── test_agent.py               # Terminal-based test pipeline (no UI)
├── requirements.txt            # Python dependencies
├── agents/                     # Agent implementations (ReAct loops)
│   ├── __init__.py
│   ├── persona_agent.py        # Persona Agent: real-time interview responses + 4 tools
│   └── feedback_agent.py       # Feedback Agent: post-interview analysis + 5 tools
├── tools/                      # Tool definitions (JSON schemas) + executors (Python)
│   ├── __init__.py
│   ├── persona_tools.py        # reveal_pain, update_resistance, check_already_revealed, flag_question
│   └── feedback_tools.py       # load_pm_history, analyze_question_patterns, identify_missed_pains, match_pains_to_metrics, compute_score
├── prompts/                    # System prompts (dynamically built from persona/metrics)
│   ├── __init__.py
│   ├── persona_system.py       # build_persona_system_prompt(persona) → string
│   └── feedback_system.py      # build_feedback_system_prompt(persona, metrics) → string
├── storage/                    # Session persistence (Supabase wrapper)
│   ├── __init__.py
│   ├── session_store.py        # save_session, load_recent_sessions, get_dashboard_stats
│   └── schema.sql              # Supabase table definition (manual setup)
├── .planning/                  # Documentation (generated)
│   └── codebase/
│       ├── ARCHITECTURE.md     # Pattern, layers, data flow
│       └── STRUCTURE.md        # This file
├── .streamlit/                 # Streamlit config
├── docs/                       # Project docs (README, screenshots)
└── .git/                       # Version control
```

## Directory Purposes

**agents/:**
- Purpose: Core agent logic — ReAct loops that drive interview and feedback
- Contains: Two @observe-decorated agent classes (conceptually; implemented as functions)
- Key files:
  - `persona_agent.py`: `run_persona_turn()` entry, `_react_loop()` workhorse, `generate_persona()`, `generate_metrics()`
  - `feedback_agent.py`: `run_feedback()` entry, same ReAct pattern as persona agent

**tools/:**
- Purpose: Tool definitions (what Claude sees) + executors (what Python does)
- Contains: JSON schemas in DEFINITIONS list + Python executor functions
- Key files:
  - `persona_tools.py`: 4 tools for interview (reveal_pain, update_resistance, check_already_revealed, flag_question)
  - `feedback_tools.py`: 5 tools for post-interview analysis (load_pm_history, analyze_question_patterns×3, identify_missed_pains, match_pains_to_metrics, compute_score)

**prompts/:**
- Purpose: Dynamic system prompt construction — tells Claude what role to play
- Contains: Functions that take runtime data (persona dict, metrics list) and return formatted prompt strings
- Key files:
  - `persona_system.py`: Encodes persona identity, pain list, behavior rules (resistance, realism, tool usage sequence)
  - `feedback_system.py`: Encodes metrics, required tool order, report format in French

**storage/:**
- Purpose: Persistence and historical analysis — Supabase integration for cross-session learning
- Contains: Supabase client wrapper, CRUD operations, aggregations
- Key files:
  - `session_store.py`: `save_session()`, `load_recent_sessions()`, `get_dashboard_stats()`
  - `schema.sql`: Manual setup — defines `sessions` table with JSONB columns for flexible score/pain storage

## Key File Locations

**Entry Points:**
- `app.py`: Streamlit app entry — run with `streamlit run app.py`
- `test_agent.py`: CLI test harness — run with `python test_agent.py`

**Configuration:**
- `requirements.txt`: Python dependencies (anthropic, streamlit, langfuse, supabase, python-dotenv)
- `.env`: Local environment (contains ANTHROPIC_API_KEY, LANGFUSE_*, SUPABASE_*)
- `.streamlit/config.toml`: Streamlit config (if present)

**Core Logic:**
- Agent orchestration: `agents/persona_agent.py` (generate_persona, generate_metrics, run_persona_turn)
- Agent orchestration: `agents/feedback_agent.py` (run_feedback)
- Tool dispatch: `tools/persona_tools.py` (execute_tool router), `tools/feedback_tools.py` (execute_feedback_tool router)
- State mutation: Tool executors (_reveal_pain, _update_resistance, _compute_score, etc.)
- Prompts: `prompts/persona_system.py`, `prompts/feedback_system.py` (build_*_system_prompt functions)

**Testing:**
- `test_agent.py`: End-to-end pipeline test (no Streamlit; plain Python)

**Persistence:**
- `storage/session_store.py`: Supabase client, save/load, aggregation
- `storage/schema.sql`: Table DDL (manual Supabase setup)

## Naming Conventions

**Files:**
- Agents: `{role}_agent.py` (persona_agent.py, feedback_agent.py)
- Tools: `{role}_tools.py` (persona_tools.py, feedback_tools.py)
- Prompts: `{role}_system.py` (persona_system.py, feedback_system.py)
- Private functions: `_{name}()` (e.g., `_react_loop()`, `_reveal_pain()`, `_parse_json()`)
- Public functions: `{name}()` (e.g., `run_persona_turn()`, `generate_persona()`, `execute_tool()`)

**Directories:**
- Lowercase, plural or descriptive: `agents/`, `tools/`, `prompts/`, `storage/`, `docs/`

**Functions:**
- `generate_*()`: Creates new data (generate_persona, generate_metrics)
- `run_*()`: Executes a flow (run_persona_turn, run_feedback)
- `build_*()`: Constructs formatted strings (build_persona_system_prompt)
- `execute_*()`: Dispatches tool calls (execute_tool, execute_feedback_tool)
- `load_*()`, `save_*()`: Database operations (load_recent_sessions, save_session)
- `_*()`: Private/internal (\_react_loop, \_reveal_pain, \_parse_json)

**Variables:**
- Agent message lists: `messages` (sent to Claude), `agent_log` (captured for UI)
- Session state: `session_state`, `agent_session` (both plain dicts)
- Tool input/output: `tool_input` (dict), `tool_name` (str), observation (str returned to Claude)
- State fields: `resistance_level`, `revealed_pains`, `_pain_discovery_rate`, `_final_score` (underscore prefix = computed by feedback agent)

**Types:**
- Persona: dict with keys: name, role, company_type, personality, initial_resistance, pains (list)
- Metrics: list of dicts with keys: id, name, description, example
- Flagged question: dict with keys: quality (str), question (str), reason (str)

## Where to Add New Code

**New Tool (e.g., "validate_answer"):**
1. Add definition to `PERSONA_TOOL_DEFINITIONS` in `tools/persona_tools.py`:
   ```python
   {
       "name": "validate_answer",
       "description": "Check if answer is coherent with persona...",
       "input_schema": {"type": "object", "properties": {...}}
   }
   ```
2. Add executor in `tools/persona_tools.py`:
   ```python
   def _validate_answer(tool_input: dict, state: dict) -> str:
       # Modify state, return observation
       return "Validation result..."
   ```
3. Add case to `execute_tool()` router:
   ```python
   elif tool_name == "validate_answer":
       return _validate_answer(tool_input, session_state)
   ```
4. Update persona agent's system prompt in `prompts/persona_system.py` to reference the tool.

**New Agent (e.g., "scoring_agent"):**
1. Create `agents/scoring_agent.py` with @observe-decorated entry function (e.g., `run_scoring()`)
2. Implement ReAct loop following pattern in `agents/persona_agent.py:_react_loop()`
3. Create `tools/scoring_tools.py` with tool definitions + executors
4. Create `prompts/scoring_system.py` with `build_scoring_system_prompt()`
5. Call from `app.py` at appropriate step

**New UI Step (e.g., "calibration"):**
1. Add step name to session defaults in `init_state()` in `app.py:30–41`
2. Create `render_step_calibration(col_main)` function in `app.py`
3. Add elif branch to main loop (`app.py:294–301`)
4. Button handling: set `st.session_state.step` and call `st.rerun()`

**New Field in Session State:**
- Initialize in `init_state()` defaults dict (`app.py:31–41`)
- Access via `st.session_state[key]`
- For agent_session fields: initialize in `render_step_context` when creating agent_session (`app.py:121–128`)

**Utilities / Shared Helpers:**
- Add to top of `app.py` (if UI-related) or create new module `utils.py` at root
- For agent-related utilities: add to `agents/` (e.g., new file `agents/utils.py`)
- For tool-related utilities: add to `tools/` (e.g., new file `tools/utils.py`)

## Special Directories

**`.planning/codebase/`:**
- Purpose: Architecture and structure documentation (auto-generated by /gsd-map-codebase)
- Generated: Yes
- Committed: Yes
- Contents: ARCHITECTURE.md, STRUCTURE.md, and others as needed

**`docs/`:**
- Purpose: Project documentation (README, screenshots, user guide)
- Generated: No (manual)
- Committed: Yes
- Contents: README.md, screenshots, architecture diagrams

**`.streamlit/`:**
- Purpose: Streamlit configuration (theme, logging, etc.)
- Generated: No (manual)
- Committed: Yes
- Contents: config.toml

**`.env` (not shown in ls, but exists):**
- Purpose: Local environment variables
- Generated: No (manual, user creates)
- Committed: No (.gitignore)
- Contents: ANTHROPIC_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST, SUPABASE_URL, SUPABASE_KEY

---

*Structure analysis: 2026-04-17*
