# Concerns

## Known Issues

### 1. OpenRouter Free Model Refresh Doesn't Update PRICING

**File**: `backend/app/providers/model_lists.py`, `backend/app/pricing.py`

`PRICING["openrouter"]` is statically computed at module import time using `**{m: {...} for m in OPENROUTER_FREE_MODELS}`. When `refresh_openrouter_free_models()` updates `OPENROUTER_FREE_MODELS` at runtime, the PRICING dict is NOT updated. Additionally, `OpenRouterProvider.model_names` is set at class definition time from the same static lists, so it also doesn't include runtime-added models.

**Impact**: New free models added at runtime have no PRICING entry. `calculate_cost()` defaults to $0 (harmless for free models), but `get_models()` would KeyError if a runtime-added model were somehow included in `model_names`.

**Mitigation**: Both `model_names` and `PRICING` are stale in lockstep — no KeyError in practice. The runtime refresh effectively only helps display updated model lists to the user (via invalidating the provider cache and re-reading `model_names`, which... also hasn't changed).

**Suggested fix**: Make `OpenRouterProvider` regenerate its `model_names` dynamically from the refreshed list, and make `PRICING["openrouter"]` rebuild from the current `OPENROUTER_FREE_MODELS`.

### 2. Sync subprocess.run Blocks Event Loop During Startup

**File**: `backend/app/main.py::_run_alembic_migrations()`

Uses synchronous `subprocess.run()` (up to 60s total: 30s stamp + 30s upgrade) inside `async def lifespan`. This blocks the Uvicorn event loop, preventing health checks and graceful shutdown signal handling during startup.

**Mitigation**: Acceptable during startup since no requests are being served yet. Consistent with other sync operations in `lifespan` (`init_db()`, `_repair_stuck_benchmarks`).

**Suggested fix**: Use `asyncio.create_subprocess_exec` or move DB setup to a pre-start script outside the application boundary.

### 3. env.py/database.py URL Normalization Duplication

**Files**: `backend/alembic/env.py`, `backend/app/database.py`

Both files contain identical `postgres://` → `postgresql+psycopg://` normalization logic. If the normalization changes in one file, the other may drift.

**Suggested fix**: Extract to a shared utility, but requires careful management of import paths (env.py runs under Alembic with different sys.path).

### 4. BYOK Test Helper Duplication

**File**: `backend/tests/test_providers.py`

`_capture_transport`, `_patched_client`, `_mock_settings` are defined identically in three test classes (`TestBYOKAuthHeader`, `TestBYOKAnthropicAuthHeader`, `TestBYOKGeminiAuthHeader`). Only the `_sse_body` differs.

**Suggested fix**: Extract to a shared base class with `_sse_body` as a class attribute.

### 5. No Alembic Downgrade Testing

**File**: `backend/alembic/versions/0002_add_cache_metrics.py`

The `downgrade()` function drops cache columns but has never been tested in CI. On PostgreSQL with batch mode, it creates a temp table, copies data, drops old, renames — but drops the columns from the schema before copying, potentially losing data.

**Suggested fix**: Add a downgrade test in CI.

## Fragile Areas

### 1. init_db() + Alembic Dual Schema Management

**File**: `backend/app/main.py`

The startup uses both `init_db()` (SQLAlchemy `create_all`) and `_run_alembic_migrations()` (Alembic `stamp` + `upgrade`). This dual approach is fragile:

- If `init_db()` creates tables and then Alembic migration fails, the DB is in an inconsistent state
- If Alembic migration partially succeeds, `init_db()` can't repair it
- Order dependency: `init_db()` must run first, but this isn't enforced programmatically

**Mitigation**: The stamp-then-upgrade strategy handles the common cases. The per-column try/except in migration 0002 adds idempotency.

### 2. import Chain: base.py → pricing.py → model_lists.py

**Files**: `backend/app/providers/base.py`, `backend/app/pricing.py`, `backend/app/providers/model_lists.py`

`base.py` now imports `PRICING` from `pricing.py` (added during simplify refactoring). The only thing preventing a circular import is the deferred import in `model_lists.py` (`from . import invalidate_provider_cache` inside `refresh_openrouter_free_models()` with `# noqa: PLC0415`).

**Risk**: If anyone moves that deferred import to module level, or if `pricing.py` gains a direct import from `providers`, the cycle breaks at import time.

**Suggested fix**: Add a comment in `model_lists.py` documenting the deferred import's purpose (breaking the potential base → pricing → model_lists → providers cycle).

### 3. SessionKeyStore is Per-Process (Not Shared Across Workers)

**File**: `backend/app/session_keys.py`

`SessionKeyStore` is a module-level singleton stored in process memory. If Uvicorn runs multiple workers (e.g., `--workers 4`), each worker has its own independent store. A session created on worker A cannot be read by worker B.

**Impact**: Session-scoped BYOK keys are not shared across workers. Currently mitigated by single-machine deployment (1 worker on Fly.io). Would break if scaling to multiple workers.

**Suggested fix**: Use Redis for session storage when available, same as the cache layer.

### 4. No Request-Body Logging Middleware for BYOK Endpoint

**File**: `backend/app/routers/session_keys.py`

The `POST /api/session-key` endpoint receives API keys. If any middleware logs request bodies (even accidentally via debug mode), keys would leak. The ADR-003 requirement "BYOK endpoint excluded from request-body logging middleware" relies on the absence of such middleware, not an explicit guard.

**Suggested fix**: Add explicit body-logging guards or use a dedicated middleware exclusion list.

## Performance

### 1. Migration 0002 Uses 4 Separate Batch Operations

**File**: `backend/alembic/versions/0002_add_cache_metrics.py`

Each cache column is added in its own `batch_alter_table` context (4 temp tables, 4 copies, 4 renames). On large tables, this is 4× the I/O of a single batch operation with all columns.

**Mitigation**: `benchmark_results` is typically small (dev/testing workloads). The per-column approach was chosen for idempotency.

### 2. refresh_openrouter_free_models Fetches All Models and Filters Client-Side

**File**: `backend/app/providers/model_lists.py`

The OpenRouter API returns all models (hundreds), but only free models are kept. The OpenRouter API doesn't have a `?pricing=free` filter.

**Mitigation**: Cached with 1-hour TTL, called only at startup.

## Security

### 1. Gemini API Key in URL Query Parameter

**File**: `backend/app/providers/gemini.py`

Gemini embeds the API key as `?key=...` in the URL. httpx's `HTTPStatusError` includes the request URL in its message. While `_sanitize_error()` is called before logging in the benchmark path, other code paths that handle errors from Gemini could potentially expose the key.

A dedicated test (`test_key_not_leaked_in_error_response_url` in `test_providers.py`) documents this behavior.

### 2. CORS Allows Credentials

**File**: `backend/app/config.py`

`allow_credentials=True` with `allow_origins` set to specific origins (localhost:5173, prompt-bench.fly.dev). This is necessary for the `pb_session` cookie used by session-scoped BYOK keys. The origin list must be kept in sync with actual deployment URLs.

## Uncovered Code Paths

| Path | Status |
|------|--------|
| History endpoint (production 500) | ✅ Fixed by migration startup |
| Insights endpoint (SQL aggregation) | ✅ Covered by tests |
| CompareRuns page | ❌ No tests |
| Session key save/clear/expiry | ❌ No integration tests |
| Real provider API calls | ❌ All mocked |
| Embedding cache with real data | ❌ Not tested |
| Alembic downgrade | ❌ Not tested |
| Redis fallback to in-memory | ✅ Covered |
| Multiple concurrent benchmarks | ✅ Covered (stampede prevention) |
| Rate limiting | ❌ Not tested |
| Frontend dark mode toggle | ❌ Not tested |
| Mobile responsive layout | ❌ Not tested |

## Process Debt

- No pre-commit hooks configured
- No automated dependency updates (Dependabot/Renovate)
- Frontend test coverage is sparse (3 tests, one component)
- No E2E testing framework
- Migration startup order (`init_db` vs alembic) is implicit, not programmatically enforced
- `.env.example` doesn't exist (was `cat backend/.env.example 2>&1` → exit 1 in a previous debugging session)
