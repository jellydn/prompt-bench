# Codebase Concerns

**Analysis Date:** 2026-07-26

## Tech Debt

**Duplicate model and pricing data across providers and pricing.py:**

- Issue: The OpenRouter free models list is defined identically in `openrouter.py` and `pricing.py`. The Ollama and vLLM model lists are also hardcoded in two places (provider class and `pricing.py`). Any model name change must be updated in multiple locations.
- Files: `backend/app/providers/openrouter.py`, `backend/app/pricing.py`
- Impact: Model name drift between providers and pricing tables causes silent mispricing or KeyError crashes
- Fix approach: Single source of truth -- define models in one place and reference from both

**aiocache and redis_url are dead dependencies:**

- Issue: `aiocache==0.12.3` is in `requirements.txt` and `redis_url` is a `Settings` field, but neither is imported or used anywhere in the backend code.
- Files: `backend/requirements.txt`, `backend/app/config.py`
- Impact: Clutters dependency tree; misleading for future contributors
- Fix approach: Remove `aiocache` from requirements.txt and `redis_url` from Settings, or implement actual caching

**Pre-commit config is misnamed and non-functional:**

- Issue: The pre-commit configuration is in `prek.toml` (TOML format), but pre-commit requires `.pre-commit-config.yaml` (YAML format). The hooks defined in `prek.toml` are not active. AGENTS.md also confirms there are no pre-commit hooks in the repo.
- Files: `prek.toml`
- Impact: No automated linting/formatting on commit despite `justfile` having `lint`/`format` targets
- Fix approach: Rename to `.pre-commit-config.yaml` with proper YAML format and install the hooks, or remove the file entirely

**`response_length` stores character count but is named as if it were token count:**

- Issue: `ProviderResponse.response_length = len(result)` counts characters, not tokens. This is used throughout the UI and database, creating a misleading metric when comparing models with different tokenizers.
- Files: `backend/app/providers/base.py`, `backend/app/models.py`, `backend/app/routers/benchmarks.py`
- Impact: Misleading "Length" column in UI; incorrect token usage reporting
- Fix approach: Either count actual tokens (using tiktoken or provider-reported token counts) or rename the field to `response_chars`

**Provider API keys are evaluated at import time:**

- Issue: All provider classes set `api_key = settings.*_api_key` as class variables when the module is imported. If a user exports an API key after the process starts (e.g., in a `.env` file loaded after import), the key will not be picked up until restart.
- Files: `backend/app/providers/openai.py`, `backend/app/providers/anthropic.py`, `backend/app/providers/gemini.py`, `backend/app/providers/openrouter.py`, `backend/app/providers/vllm.py`
- Impact: Requires server restart to pick up new or changed API keys
- Fix approach: Read API keys at call time from settings (which already uses `lru_cache` on `get_settings()`) instead of caching at import time

**No input sanitization or length limits on prompt text:**

- Issue: The `prompt` field in `BenchmarkCreate` has `min_length=1` but no upper bound. Prompt text is stored verbatim in the database and rendered with `whitespace-pre-wrap` in the frontend.
- Files: `backend/app/schemas.py`, `backend/app/routers/benchmarks.py`, `frontend/src/pages/BenchmarkResults.tsx`
- Impact: No protection against extremely long prompts (storage abuse, slow responses); potential XSS vector if rendered without escaping
- Fix approach: Add `max_length` to the Field validator; ensure frontend escaping of response text

## Known Bugs

**Gemini provider does not really stream -- fetches entire response at once:**

- Symptoms: Gemini benchmark latency will show the full round-trip time as both TTFT and total latency, not just time-to-first-token. No incremental token rendering.
- Files: `backend/app/providers/gemini.py` (lines 41-46)
- Trigger: Running a benchmark with the Gemini provider
- Workaround: None currently; must switch to a different provider for accurate TTFT measurement
- Fix approach: Use `client.stream()` with `aiter_lines()` like all other providers, and parse each SSE event individually

**`BenchmarkResults.tsx` reduce with no initial value on empty results:**

- Symptoms: If all model results have errors, `good` array is empty, and `good.reduce(fn, good[0])` passes `undefined` as the initial accumulator. The reduce callback then accesses `r.total_latency_ms` on `undefined` and crashes.
- Files: `frontend/src/pages/BenchmarkResults.tsx` (lines 52-63)
- Trigger: Running a benchmark where every provider returns an error
- Workaround: None
- Fix approach: Add an early return when `good.length === 0`, or pass a proper initial value to `reduce()`

**OpenRouter hardcoded model list goes stale quickly:**

- Symptoms: Free models added or removed by OpenRouter are not reflected until the code is manually updated. The `pricing.py` free models list at lines 20-34 is a separate copy from `openrouter.py` lines 7-19, creating a dual-maintenance problem.
- Files: `backend/app/providers/openrouter.py`, `backend/app/pricing.py`
- Trigger: Using a newly added free model or a model removed from the OpenRouter free tier
- Workaround: None
- Fix approach: Fetch the free model list from OpenRouter API at startup or cache it periodically

**Pydantic Settings `lru_cache` means config is frozen after first call:**

- Symptoms: The `get_settings()` function is wrapped in `@lru_cache`, so any changes to environment variables after the first call return the cached (stale) settings. This compounds the import-time API key issue above.
- Files: `backend/app/config.py` (lines 28-33)
- Impact: Cannot hot-reload configuration, even with `uvicorn --reload`
- Fix approach: Remove `@lru_cache` or re-read settings on each access; use Pydantic's `SettingsConfigDict` env loading properly

**Ollama `eval_count` key may be absent in all response formats:**

- Symptoms: Some Ollama response formats may not include `eval_count` in the final message object. `final.get("eval_count", 0)` defaults to 0, which silently masks the issue but produces incorrect output token counts.
- Files: `backend/app/providers/ollama.py` (line 54)
- Trigger: Using certain Ollama versions or models that don't report `eval_count`
- Workaround: Manual verification of reported token counts
- Fix approach: Validate the response shape and log a warning when expected keys are missing

**No `system_prompt` handling in Claude provider for `content_block_delta` events:**

- Symptoms: The Anthropic provider does not handle `stop_reason` or `input_tokens` from the `message_start` usage block reliably. The `input_tokens` count comes only from `message_start` event, but if that event is missed in the stream, input tokens default to 0.
- Files: `backend/app/providers/anthropic.py` (lines 57-62)
- Impact: Underestimation of input token usage for Claude models
- Fix approach: Extract `input_tokens` from `message_start` more robustly; also check `usage` in the final `message_delta` event

## Security Considerations

**No authentication or authorization on any API endpoint:**

- Risk: All endpoints (create benchmarks, delete benchmarks, view history, view insights) are completely public. Anyone with network access can read and delete all benchmark data.
- Files: `backend/app/routers/benchmarks.py`, `backend/app/routers/insights.py`, `backend/app/routers/providers.py`
- Current mitigation: None
- Recommendations: Add authentication middleware at minimum; consider API key-based auth for the MVP; add CORS restrictions beyond dev defaults

**Permissive CORS configuration in production:**

- Risk: `allow_origins` defaults to `["http://localhost:5173"]` which is fine for development, but `allow_methods=["*"]` and `allow_headers=["*"]` with `allow_credentials=True` means any origin that gets added to the list gains full credentialed access. In Docker, the `cors_origins` config is not set, so it falls back to the dev default.
- Files: `backend/app/config.py` (line 16), `backend/app/main.py` (lines 19-24)
- Current mitigation: Default origin is localhost-only
- Recommendations: Explicitly set `cors_origins` in production `.env`; consider restricting `allow_methods` and `allow_headers` to only what is needed

**Hardcoded credentials in docker-compose.yml:**

- Risk: PostgreSQL password `promptbench` is in plaintext in version control.
- Files: `docker-compose.yml` (line 8)
- Current mitigation: Gitignored in `.gitignore`
- Recommendations: Use Docker secrets or environment variable substitution for production deployments

**No rate limiting on API endpoints:**

- Risk: An attacker or misbehaving client can overwhelm the backend with concurrent benchmark requests, consuming API credits on remote providers.
- Files: `backend/app/routers/benchmarks.py`
- Current mitigation: None
- Recommendations: Add rate limiting middleware (e.g., `slowapi` for FastAPI); set maximum concurrent benchmarks per request

**API keys exposed through providers endpoint:**

- Risk: The `/api/providers` endpoint reveals which providers require API keys (`requires_api_key` field) and whether they are configured, providing information about the deployment's credential setup.
- Files: `backend/app/routers/providers.py` (lines 16-18)
- Current mitigation: Low-severity information disclosure
- Recommendations: Remove `requires_api_key` from the public response or gate it behind authentication

**No HTTPS enforcement anywhere in the stack:**

- Risk: All traffic between frontend and backend, and between backend and AI providers, is unencrypted in the default configuration. Provider API keys are sent over the wire.
- Files: `docker-compose.yml`, `frontend/vite.config.ts`, all provider implementations
- Current mitigation: Provider API calls go to HTTPS endpoints (OpenAI, Anthropic, etc.), but the frontend-to-backend and backend-to-local-proxy connections are plaintext.
- Recommendations: Add TLS termination (nginx, Caddy, or traefik) in the Docker stack for production

## Performance Bottlenecks

**Insights endpoint loads all benchmarks eagerly with full results:**

- Problem: `select(Benchmark).options(selectinload(Benchmark.results))` loads every benchmark and every result row into memory. No pagination or filtering.
- Files: `backend/app/routers/insights.py` (lines 15-17), `backend/app/routers/benchmarks.py` (lines 86-92)
- Cause: No `limit` parameter on the insights endpoint; `selectinload` loads the entire relationship tree
- Improvement path: Add pagination or a date range filter; consider aggregating in SQL with `func.avg`, `func.sum` instead of loading all rows into Python

**No caching of provider lists or pricing data:**

- Problem: Every call to `/api/providers` constructs the full provider info from scratch, including iterating all models and pricing entries. Pricing data is recomputed on every history request.
- Files: `backend/app/routers/providers.py`, `backend/app/pricing.py`, `backend/app/routers/benchmarks.py`
- Cause: `aiocache` is a dependency but unused; no caching layer implemented
- Improvement path: Implement caching using `aiocache` or a simple in-memory dict with TTL; cache provider model lists and pricing lookups

**Gemini provider fetches entire response before returning (non-streaming):**

- Problem: Unlike all other providers, Gemini uses `client.post()` instead of `client.stream()`, fetching the complete response body before calculating any latency metrics. This means TTFT for Gemini is always equal to total latency.
- Files: `backend/app/providers/gemini.py`
- Improvement path: Switch to streaming (`client.stream()`) and parse SSE events like the other providers

**SQLite default database is not suitable for concurrent access:**

- Problem: The default `database_url` uses SQLite with `check_same_thread=False`, which works for single-threaded development but will corrupt data or serialize requests under concurrent write load.
- Files: `backend/app/database.py` (lines 11-14)
- Improvement path: Use PostgreSQL by default in Docker; add connection pool settings for async-compatible use

## Fragile Areas

**All provider generate() methods lack defensive error handling:**

- Files: `backend/app/providers/openai.py` (via common.py), `backend/app/providers/anthropic.py`, `backend/app/providers/gemini.py`, `backend/app/providers/ollama.py`, `backend/app/providers/vllm.py` (via common.py)
- Why fragile: None of the `generate()` methods validate the API response structure before accessing nested keys. A malformed SSE event, unexpected JSON shape, or missing field will raise a `KeyError`, `IndexError`, or `json.JSONDecodeError` that bubbles up to `run_one()` and is caught as a generic `Exception`, but intermediate state may be partially consumed (e.g., partial text collected before the error).
- Safe modification: Add response schema validation; wrap JSON parsing in try/except with context; validate response shape before accessing nested dict keys
- Test coverage: Zero tests exist for any provider

**Benchmark status field has no recovery mechanism:**

- Files: `backend/app/models.py` (line 20), `backend/app/routers/benchmarks.py`
- Why fragile: A benchmark is created with `status="running"`. If the server crashes or the process is killed after `db.commit()` but before all results are written, the benchmark remains stuck as "running" forever. No cleanup or status-reconciliation job exists.
- Safe modification: Add a status expiry check (e.g., mark benchmarks older than N minutes with no results as "failed"); add a `healthcheck` endpoint that repairs stuck benchmarks
- Test coverage: No tests for status lifecycle

**Frontend has no error boundaries or global error handling:**

- Files: `frontend/src/App.tsx`, `frontend/src/main.tsx`
- Why fragile: A render error in any component (e.g., `BenchmarkResults.tsx` accessing `q.data!` on an undefined response) will crash the entire React app with a white screen. There are no React error boundaries anywhere.
- Safe modification: Wrap page components in error boundary components; add global `window.onerror` handler; avoid non-null assertions on potentially undefined data (`q.data!`)
- Test coverage: No frontend tests exist

**`create_benchmark` endpoint has no request size or concurrency limit:**

- Files: `backend/app/routers/benchmarks.py` (lines 34-81)
- Why fragile: A single POST request can trigger `asyncio.gather()` with an arbitrary number of concurrent API calls. Each call has a 120-second httpx timeout. A request with 20 models each calling an unbounded API creates 20 concurrent connections with no backpressure.
- Safe modification: Add a cap on the number of models per benchmark (e.g., `max_length=10` on `models` field); add a semaphore to limit concurrent provider calls; add per-provider timeout backoff
- Test coverage: No load testing or concurrency testing

**`openrouter.py` free model list is static and will drift:**

- Files: `backend/app/providers/openrouter.py` (lines 7-19), `backend/app/pricing.py` (lines 19-35)
- Why fragile: OpenRouter adds and removes free models regularly. The dual hardcoded lists in `openrouter.py` and `pricing.py` will silently become out of sync, causing either missing free models or incorrect pricing for removed models.
- Safe modification: Fetch free model list from OpenRouter API at startup or cache with periodic refresh; remove pricing duplication
- Test coverage: No tests verify pricing correctness

## Scaling Limits

**SQLite default with no connection pooling:**

- Current capacity: Single process, single-threaded SQLite with `check_same_thread=False`
- Limit: Concurrent writes will serialize or corrupt; not usable beyond a single user or low-traffic deployment
- Scaling path: Switch to PostgreSQL for any concurrent access; add async session management with `NullPool` or `QueuePool`

**Insights endpoint loads unbounded data:**

- Current capacity: Loads all benchmark rows + all result rows with no limit
- Limit: Degrades linearly with total data volume; memory exhaustion with thousands of benchmarks and results
- Scaling path: Add SQL-level aggregation (AVG, SUM) instead of loading all rows; add pagination/filtering

**No rate limiting or request quotas:**

- Current capacity: Unlimited concurrent benchmark requests
- Limit: API costs escalate unboundedly; provider rate limits may be hit silently
- Scaling path: Add rate limiting middleware; add request quotas per user; add provider-side rate limit awareness

## Dependencies at Risk

**`aiocache` in requirements.txt but never used:**

- Risk: Dead dependency adds attack surface and maintenance burden
- Impact: Unused code never exercised; potential vulnerability in unused package
- Migration plan: Remove from `requirements.txt` or implement caching and remove from this concerns list

**`psycopg2-binary` for PostgreSQL driver:**

- Risk: Binary-only package may have wheels incompatible with certain platforms or Python versions; the "binary" variant is discouraged for production use
- Impact: May fail to install on certain systems or after Python upgrades
- Migration plan: Use `psycopg2` (source build) or `psycopg` (modern async driver) for production

**`pydantic-settings` with `lru_cache` on `get_settings()`:**

- Risk: The `lru_cache` decorator means settings are cached forever, including env file parsing. Changes to `.env` require a full process restart, not just uvicorn reload.
- Impact: Configuration changes don't take effect until restart, which is frustrating in development
- Migration plan: Remove `lru_cache` or switch to a settings object that is re-instantiated per request

## Missing Critical Features

**No authentication or user isolation:**

- Problem: All benchmarks are shared globally. Any user can see and delete any other user's benchmarks.
- Blocks: Multi-user deployment; data privacy; user-specific billing

**No result export or data portability:**

- Problem: Results can only be viewed in the web UI. No CSV/JSON export, no API pagination beyond the history list.
- Blocks: Data analysis outside the app; compliance with data export requests

**No prompt templates or save/reuse:**

- Problem: Every benchmark requires retyping the prompt. No way to save and reuse prompts.
- Blocks: Iterative prompt development workflows

**No comparison view (side-by-side):**

- Problem: Results show models in a table but there is no dedicated side-by-side comparison mode.
- Blocks: Quick visual comparison of model outputs

**No scheduling or automated runs:**

- Problem: Benchmarks must be triggered manually each time.
- Blocks: Continuous monitoring of model performance over time

## Test Coverage Gaps

**Zero test coverage across the entire codebase:**

- What's not tested: Every Python module, every API endpoint, every provider, every React component
- Files: All backend and frontend source files
- Risk: Any change can silently break existing functionality with no regression detection
- Priority: High

**No tests for provider error paths:**

- What's not tested: API failures, malformed responses, network timeouts, invalid API keys
- Files: `backend/app/providers/common.py`, `backend/app/providers/anthropic.py`, `backend/app/providers/gemini.py`
- Risk: Error handling code is never exercised; bugs in error paths go undetected
- Priority: High

**No tests for pricing calculation edge cases:**

- What's not tested: Unknown provider/model combinations, zero-token responses, very large token counts
- Files: `backend/app/pricing.py`
- Risk: Incorrect cost calculations go undetected; users may be charged incorrectly
- Priority: Medium

**No database migration or schema versioning:**

- What's not tested: Schema changes, data migrations, concurrent access patterns
- Files: `backend/app/database.py`
- Risk: Schema changes require manual intervention; no rollback path
- Priority: Medium

---

_Concerns audit: 2026-07-26_
