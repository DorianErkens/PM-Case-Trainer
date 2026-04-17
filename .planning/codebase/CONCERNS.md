# Codebase Concerns

**Analysis Date:** 2026-04-17

## Tech Debt

**Hardcoded Iteration Limits:**
- Issue: ReAct loop iteration limits are hardcoded and not configurable
- Files: `agents/persona_agent.py` (line 66: `while iteration < 10`), `agents/feedback_agent.py` (line 56: `while iteration < 15`)
- Impact: If Claude takes more iterations to complete a turn, the loop exits prematurely with incomplete analysis. Different turn types (persona vs feedback) have different limits with no clear rationale documented
- Fix approach: Extract to configuration constants with documented reasoning. Consider per-agent configurable limits or adaptive stopping criteria based on context

**Hardcoded Token Budgets:**
- Issue: `max_tokens` values are scattered and hardcoded with no justification
- Files: 
  - `agents/persona_agent.py` (lines 72, 153, 184): 1024, 512, 1024
  - `agents/feedback_agent.py` (line 62): 2048
- Impact: Report truncation risk if feedback agent needs more tokens. No safety check if response hits token limit
- Fix approach: Define token budget strategy document. Add response validation checking if `stop_reason` indicates truncation

**Hardcoded Initial Resistance Value:**
- Issue: Default resistance level hardcoded as 7 in multiple places
- Files: `agents/persona_agent.py` (line 221 in prompt), `prompts/persona_system.py` (line 24), multiple .get() calls with default 7
- Impact: Persona prompt shows hardcoded value, but persona generation also returns `initial_resistance: 7` from LLM, creating potential mismatch. No validation that generated value matches system prompt expectation
- Fix approach: Ensure persona generator explicitly validates resistance value; use single source of truth for defaults

**JSON Parsing Without Robust Error Handling:**
- Issue: `_parse_json()` function has basic error handling but assumes specific markdown format
- Files: `agents/persona_agent.py` (lines 201-207)
- Impact: If Claude returns JSON in unexpected format (plain JSON, different code block style, partial JSON), parsing fails silently with generic `json.loads()` error. No fallback or retry
- Fix approach: Add detailed logging of parse failures; implement retry with reprompt; consider using pydantic for validation

## Known Bugs

**Persona History Not Passed to Feedback Agent:**
- Symptoms: Feedback agent calls `load_pm_history()` but never receives actual PM email/identifier to find past sessions
- Files: `agents/feedback_agent.py` (lines 103-154 in feedback_tools.py), `storage/session_store.py` (line 76)
- Trigger: Any feedback session runs `load_pm_history()` but tool always returns empty or generic result
- Current state: The PM identity is never captured or stored, so dashboard stats and recurring pattern detection can't work
- Fix approach: Add user identification system (email, session hash, or explicit PM name input) to `session_state` and pass to storage layer

**Missing Score Fields in Feedback Response:**
- Symptoms: Feedback agent returns `score` in feedback_agent.py but field is only set if `compute_score()` tool is called
- Files: `agents/feedback_agent.py` (lines 131-135 return), `app.py` (line 231: assumes `result.get('score')`)
- Impact: If agent skips compute_score tool or tool fails, score is None, breaking score display in UI and database storage
- Fix approach: Add explicit score validation in feedback response; default to computed score if missing

**Revealed Pains State Mutation Bug:**
- Symptoms: `revealed_pains` dict keys are integers from tool, but stored as integers in state and used as dict keys inconsistently
- Files: `tools/persona_tools.py` (line 150: `state["revealed_pains"][pain_id] = level`), `tools/feedback_tools.py` (lines 213-224: reads as int)
- Impact: Minimal current impact since Python dicts handle int/str keys separately, but if session_state is serialized/deserialized (e.g., for storage), type conversion bugs will emerge
- Fix approach: Explicitly validate pain_id types (int) when storing/retrieving; add test for serialization round-trip

**Metric Coverage Matching Too Simplistic:**
- Symptoms: `_match_pains_to_metrics()` uses keyword substring matching, fails on synonyms or complex pain descriptions
- Files: `tools/feedback_tools.py` (lines 242-244)
- Impact: Metrics marked as uncovered when they should be, lowering metric_coverage_rate score unfairly
- Fix approach: Add explicit pain-to-metric mapping table in session state; or use LLM to evaluate relevance rather than keyword matching

## Security Considerations

**Environment Secrets in Code Comments:**
- Risk: `.env` file exists with real credentials; commented examples in CLAUDE.md include full secret structure
- Files: `.env` (not readable per security policy), `CLAUDE.md` (lines 40-44)
- Current mitigation: .env is in .gitignore (per .gitignore), .env.example shows structure without values
- Recommendations: Add pre-commit hook to prevent .env commits; audit git history for past leaks

**Supabase Key Exposure in Streamlit Secrets:**
- Risk: `SUPABASE_KEY` (anon key) is passed through Streamlit secrets and exposed to frontend if debugging is enabled
- Files: `app.py` (lines 11-13), `storage/session_store.py` (line 22)
- Current mitigation: Uses anon key (limited scope), not service role key
- Recommendations: Consider separate backend service for Supabase writes instead of client-side access; audit Supabase RLS policies

**No Input Validation on PM Context:**
- Risk: PM context text is passed directly to Claude without sanitization; could be prompt injection vector
- Files: `app.py` (line 97-106: `st.text_area`), `agents/persona_agent.py` (line 154: used in prompt)
- Current mitigation: Claude prompt is well-structured with clear boundaries
- Recommendations: Add length limit and basic validation on pm_context input; log prompts for audit

## Performance Bottlenecks

**Sequential Tool Calls in Feedback Agent:**
- Problem: Feedback agent makes 5+ sequential LLM calls (one per tool) instead of batch analysis
- Files: `prompts/feedback_system.py` (lines 19-25: explicit tool call order)
- Cause: System prompt enforces strict call sequence; no parallelization possible
- Impact: Feedback takes 2-3x longer than necessary (3-5 seconds per tool * 5 tools vs potential single orchestration call)
- Improvement path: Refactor to allow agent to decide tool order dynamically, or pre-compute analyses in parallel before feedback agent starts

**Unoptimized Metric Matching Algorithm:**
- Problem: O(n*m) keyword matching for every pain-metric pair
- Files: `tools/feedback_tools.py` (lines 238-244)
- Cause: Nested loops with substring search, no indexing
- Impact: With 100+ sessions in database, dashboard stats calculation becomes slow
- Improvement path: Pre-compute pain-metric relationships during session save; cache at database level

**No Streaming for Long-Running Operations:**
- Problem: User sees blank screen during persona/metrics generation (2-3 seconds each)
- Files: `app.py` (lines 111-119: `with st.spinner()`)
- Impact: Streamlit spinner exists but no intermediate token updates. User has no visibility into progress
- Improvement path: Use Claude streaming API to show token generation in real-time in spinner

## Fragile Areas

**Agent Log Structure — Assumed by UI:**
- Files: `app.py` (lines 79-83: `render_brain_log()`), `agents/persona_agent.py` (lines 68, 78, 106, 121, 136)
- Why fragile: Agent brain panel assumes specific log structure (type, iteration, stop_reason fields). No validation that agent_log matches expected schema
- If agent code changes log structure, UI silently skips entries (no error, just blank output)
- Safe modification: Define AgentLogEntry TypedDict; validate in app.py before rendering
- Test coverage: No tests for brain_log rendering; manual testing only

**Persona JSON Generation Without Schema Validation:**
- Files: `agents/persona_agent.py` (lines 154-166 generate_persona), `tools/persona_tools.py` (line 137: accesses `persona["pains"]` without checking)
- Why fragile: If Claude returns persona JSON missing "pains" field, error occurs downstream in reveal_pain tool
- Safe modification: Add pydantic Persona model; validate immediately after parse_json, fail fast with clear error
- Test coverage: No test for persona schema validation

**UI Step Flow State Machine Without Validation:**
- Files: `app.py` (lines 292-301: if/elif step progression)
- Why fragile: Session state `step` is a string; no enum or validation. If someone manually sets invalid step, UI silently renders wrong section
- Safe modification: Use Enum for step types; validate in init_state()
- Test coverage: No tests for step transition logic

**Session State Initialization — Implicit Contract:**
- Files: `app.py` (lines 30-41: `init_state()`), used throughout app and agents
- Why fragile: Session state structure is documented only in code comments. If a new feature needs new field, easy to forget initialization
- Safe modification: Define SessionState TypedDict; make structure explicit
- Test coverage: No tests validating session state schema

## Scaling Limits

**In-Memory Session State Only:**
- Current capacity: Single Streamlit session, resets on browser refresh or navigation
- Limit: Conversation history lost if session reloads; multi-tab users see different state
- Scaling path: Move conversation_history to Supabase or persistent cache (Redis) keyed by session ID; use st.session_state only for UI state

**No Rate Limiting on LLM Calls:**
- Current capacity: Anthropic API rate limits (600 req/min for Claude Sonnet); no client-side throttling
- Limit: If multiple users hit endpoint simultaneously, requests fail with rate limit errors
- Scaling path: Add rate limiter using Redis or in-memory token bucket; return graceful "service busy" message to user

**Supabase Query Scaling:**
- Current capacity: Single table `sessions` with no pagination in `get_dashboard_stats()`
- Limit: Dashboard stats query touches all sessions (`.limit(20)` but no WHERE clause on date range)
- Scaling path: Add date range filter; implement proper pagination; pre-compute dashboard stats in background job

**No Caching of LLM-Generated Content:**
- Current capacity: Persona regenerated for each new session, metrics regenerated every time
- Limit: Similar PM contexts generate same persona repeatedly (wasted tokens)
- Scaling path: Add caching layer (Redis) for persona/metric generation keyed by context hash; TTL 24h

## Dependencies at Risk

**Langfuse v4.3.0 with Breaking Changes History:**
- Risk: v2→v3→v4 had major API changes (observe import location, span methods); v5 could introduce more breaking changes
- Files: `agents/persona_agent.py` (lines 19, 46, 86, 113), `agents/feedback_agent.py` (lines 14, 42, 75, 100), `test_agent.py` (line 17)
- Impact: If Langfuse v5 released with different API, app won't observe traces; no manual fallback tracing
- Migration plan: Pin Langfuse to `>=4.3.0,<5.0.0` in requirements.txt; add deprecation warnings in code where Langfuse API is used; plan v5 migration before it becomes mandatory

**Anthropic SDK Version Not Pinned:**
- Risk: `anthropic>=0.96.0` uses `>=` which allows breaking changes in 1.0+
- Files: `requirements.txt` (line 1), `agents/persona_agent.py` (line 17), `agents/feedback_agent.py` (line 12)
- Impact: If Anthropic SDK 1.0 changes response format (e.g., response.content structure), app breaks
- Migration plan: Use `anthropic>=0.96.0,<1.0.0` or test against latest version regularly

**Streamlit Pinned to 1.56.0+ Without Upper Bound:**
- Risk: Streamlit 2.0 could change API (e.g., `st.session_state`, `st.chat_message`)
- Files: `requirements.txt` (line 2), `app.py` (lines 22, 290, etc.)
- Impact: Layout might break, session state API might change
- Migration plan: Test against Streamlit 2.0 early; add `streamlit<2.0.0` constraint until verified

## Missing Critical Features

**No User Authentication System:**
- Problem: No way to identify which user owns a session; dashboard stats aggregate all users together
- Blocks: Per-user progress tracking, recurring pattern detection, multi-device sync
- Current workaround: Single user assumed; each browser session is treated as new user
- Fix: Add simple auth (magic link, GitHub, Google) before session save; filter stats by user_id

**No Interview History Within Session:**
- Problem: Once interview ends, can't review past questions without reloading entire page
- Blocks: Self-review during feedback, comparing questions to feedback
- Current state: Chat history exists in session_state but feedback generated once at end
- Fix: Add "Review conversation" button that persists chat history; allow side-by-side comparison with feedback

**Persona Not Revealed Option:**
- Problem: README says persona is hidden, but current system doesn't offer option to reveal after feedback
- Blocks: PM can't verify if their questions actually unlocked the designed pains
- Current state: Persona lives only in session_state, never shown in UI
- Fix: Add "Reveal persona" button after feedback shows actual role/pains/resistance

**No Metric Performance Correlation:**
- Problem: Metrics are proposed but never correlated with actual pain discovery
- Blocks: PM can't see which metrics actually guided them to pains
- Current state: `_match_pains_to_metrics()` does simple keyword matching but result not shown in report
- Fix: Add metrics section to feedback report showing coverage and missed metric areas

## Test Coverage Gaps

**No Unit Tests for Agent Logic:**
- What's not tested: ReAct loop iteration logic, tool execution, state mutations
- Files: `agents/persona_agent.py`, `agents/feedback_agent.py`, `tools/persona_tools.py`, `tools/feedback_tools.py`
- Risk: Tool execution bugs (e.g., pain_id out of bounds) only caught in production
- Coverage estimate: 0% (test_agent.py is integration test only)
- Priority: High — tool execution is core logic

**No Tests for JSON Parsing Robustness:**
- What's not tested: `_parse_json()` with malformed LLM output, missing fields, nested markdown
- Files: `agents/persona_agent.py` (lines 201-207)
- Risk: Unexpected LLM formats cause silent failures or cryptic json.loads errors
- Coverage estimate: 0%
- Priority: High — JSON parsing failure blocks entire session

**No Tests for Session State Schema:**
- What's not tested: Session state initialization, field presence validation, type correctness
- Files: `app.py` (lines 30-42), all agent files using session_state
- Risk: Missing fields cause KeyError in tools; wrong types cause serialization failures
- Coverage estimate: 0%
- Priority: Medium — currently caught by manual testing but fragile

**No Tests for UI Step Transitions:**
- What's not tested: step progression (context → metrics → interview → feedback), invalid state handling, rerun() side effects
- Files: `app.py` (lines 292-301, 129-130, 162, 239-240)
- Risk: Step transitions silently break if state mutated incorrectly
- Coverage estimate: 0%
- Priority: Medium — complex state machine should be tested

**No Tests for Feedback Agent Tool Order:**
- What's not tested: Feedback agent tool calling sequence, missing tool calls, tool output validation
- Files: `agents/feedback_agent.py`, `prompts/feedback_system.py`
- Risk: If agent skips a tool, subsequent tools get missing data (e.g., no pain_discovery_rate if identify_missed_pains() skipped)
- Coverage estimate: 0%
- Priority: Medium — tool dependencies are implicit

**No Storage Integration Tests:**
- What's not tested: Supabase CRUD operations, graceful degradation when unavailable, schema mismatch
- Files: `storage/session_store.py`
- Risk: Session save fails silently; missing data in analytics
- Coverage estimate: 0% (only happy path in app.py line 235)
- Priority: Medium — optional feature but should be reliable when enabled

---

*Concerns audit: 2026-04-17*
