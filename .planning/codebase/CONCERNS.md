# Concerns

## Known Issues

### 1. Sync subprocess.run Blocks Event Loop During Startup

**File**: `backend/app/main.py::_run_alembic_migrations()`

Sync `subprocess.run()` (up to 90s: 30s current + 30s stamp + 30s upgrade) inside `async def lifespan`. Blocks Uvicorn event loop.

**Mitigation**: Acceptable during startup — no requests being served. Consistent with other sync operations (`init_db()`, `_repair_stuck_benchmarks`).

### 2. No Alembic Downgrade Testing

**File**: `backend/alembic/versions/0002_add_cache_metrics.py`

`downgrade()` drops cache columns but never tested in CI. On PostgreSQL batch mode: creates temp table, copies data, drops old, renames — potentially losing data if the copy step fails.

### 2. SessionKeyStore is Per-Process

**File**: `backend/app/session_keys.py`

Module-level singleton in process memory. Multiple Uvicorn workers each get independent stores. Session keys from worker A invisible to worker B.

**Mitigation**: Single-worker deployment on Fly.io.

## Fragile Areas

### 1. init_db() + Alembic Dual Schema Management

**File**: `backend/app/main.py`

Startup uses both `create_all` (init_db) and Alembic (`stamp` + `upgrade`). Dual approach is fragile: order dependency is implicit, partial migration failure leaves inconsistent state.

**Mitigation**: Stamp-then-upgrade strategy with `alembic current` pre-check handles common cases. Migration 0002 uses inspector for idempotency.

### 2. import Chain: base.py → pricing.py → model_lists.py

**Files**: `backend/app/providers/base.py`, `pricing.py`, `model_lists.py`

`base.py` imports `PRICING` from `pricing.py`. The only thing preventing a circular import is the deferred `from . import invalidate_provider_cache` inside `refresh_openrouter_free_models()`.

**Mitigation**: Comment in `model_lists.py` documents the cycle-breaking deferred import.

## Performance

### 1. Migration 0002 Uses 4 Separate Batch Operations

**File**: `backend/alembic/versions/0002_add_cache_metrics.py`

Each column in its own `batch_alter_table` (4 temp tables, 4 copies, 4 renames). On large tables, 4× I/O of a single batch.

**Mitigation**: `benchmark_results` typically small (dev/testing). Per-column approach for idempotency.

### 2. OpenRouter Fetches All Models, Filters Client-Side

**File**: `backend/app/providers/model_lists.py`

API returns hundreds of models, only free ones kept. No server-side filter.

**Mitigation**: Cached 1-hour TTL, called only at startup.

## Security

### 1. Gemini API Key in URL Query Parameter

**File**: `backend/app/providers/gemini.py`

Key embedded as `?key=...` URL param. httpx `HTTPStatusError` includes URL in message. `_sanitize_error()` strips before logging, but non-benchmark error paths could leak.

A dedicated test (`test_key_not_leaked_in_error_response_url`) documents this.

### 2. CORS Allows Credentials

**File**: `backend/app/config.py`

`allow_credentials=True` needed for `pb_session` BYOK cookie. Origin list must stay in sync with deployment URLs.

## Uncovered Code Paths

| Path | Status |
|------|--------|
| History endpoint (production 500) | ✅ Fixed by migration startup |
| Insights endpoint | ✅ Covered |
| CompareRuns page | ❌ No tests |
| Session key save/clear/expiry | ❌ No integration tests |
| Real provider API calls | ❌ All mocked |
| Alembic downgrade | ✅ Covered (`test_downgrade_preserves_non_cache_data`) |
| Redis fallback to in-memory | ✅ Covered |
| Multiple concurrent benchmarks | ✅ Covered (stampede prevention) |
| Rate limiting | ❌ Not tested |
| Frontend dark mode | ❌ Not tested |
| Mobile responsive layout | ❌ Not tested |

## Resolved Issues (since last codemap)

| Issue | Resolution |
|-------|-----------|
| URL normalization duplication (env.py ↔ database.py) | ✅ Extracted to `db_utils.normalize_db_url()` |
| Import chain undocumented | ✅ Comment added in `model_lists.py` |
| Alembic re-stamp on every startup | ✅ `alembic current` pre-check |
| Migration 0002 try/except broken on PostgreSQL | ✅ Replaced with inspector-based column existence check |
| get_models() KeyError on missing pricing | ✅ Replaced with `.get()` fallback chain |
| OpenRouter PRICING stale after free model refresh | ✅ `rebuild_openrouter_pricing()`, dynamic `get_models()` |
| BYOK test helper duplication (3 classes) | ✅ Extracted to `_BYOKTestBase` |
| Alembic downgrade untested (CONCERNS.md #2) | ✅ `test_downgrade_preserves_non_cache_data()` |
| Silent migration failure → production 500 | ✅ Startup `_verify_expected_columns()` health check |
