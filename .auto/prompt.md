# Autoresearch: Fix CONCERNS.md + Modernize Tooling

## Objective

Fix all codebase concerns in `.planning/codebase/CONCERNS.md` (excluding product features: auth, TLS, export, templates, comparison view, scheduling) and modernize the dev toolchain.

## Metrics

- **Primary**: `acceptance_passed` (count, higher is better) — number of acceptance checks passing (out of fixed total). See `.auto/measure.sh`.
- **Secondary**: `ruff_violations`, `ruff_errors` (count, lower is better) — Python lint state
- **Secondary**: `ts_errors` (count, lower is better) — TypeScript compilation errors

**IMPORTANT**: The acceptance checks file (`.auto/measure.sh`) is **FIXED** — do not modify it to inflate results. If you need more signal, add to `.auto/checks.sh` (which runs post-benchmark and doesn't affect the metric).

## How to Run

```bash
# The benchmark
./.auto/measure.sh       # runs acceptance suite → METRIC acceptance_passed=N
```

```bash
# Correctness checks (runs automatically after each passing benchmark)
./.auto/checks.sh        # ruff, types, build, tests
```

## Acceptance Checks (20 total)

These are the fixed acceptance criteria. Each passing check = 1 point toward `acceptance_passed`.

### Backend Tooling (4 checks)

1. `pyproject.toml` exists with ruff config (replaces `requirements.txt`)
2. `uv.lock` exists (proves uv-managed deps)
3. No `aiocache` in dependencies (dead dep removed)
4. No `redis_url` in Settings (dead config removed)

### Pre-commit Fix (1 check)

5. `prek.toml` removed or replaced with valid `.pre-commit-config.yaml`

### Gemini Streaming Fix (1 check)

6. Gemini provider uses `client.stream()` instead of `client.post()`

### Empty Results Crash Fix (1 check)

7. `BenchmarkResults.tsx` has early return when `good.length === 0`

### Model List Deduplication (1 check)

8. OpenRouter/VLLM model names defined in ONE place, not duplicated between provider and `pricing.py`

### API Key Evaluation at Call Time (1 check)

9. Provider `api_key` read at call time from `settings`, not as class variable at import time

### response_length → response_chars (1 check)

10. Field renamed to `response_chars` in models, schema, provider base, and UI

### Prompt Input Limits (1 check)

11. `prompt` field in `BenchmarkCreate` has `max_length` constraint

### Settings lru_cache Removal (1 check)

12. `get_settings()` no longer uses `@lru_cache` — config is re-read per call

### Ollama eval_count Safeguard (1 check)

13. Ollama provider validates response shape and logs warning on missing `eval_count`

### Claude Input Tokens Robustness (1 check)

14. Anthropic provider extracts `input_tokens` from both `message_start` and fallback paths

### Rate Limiting (1 check)

15. `slowapi` middleware added to app

### Insights Pagination (1 check)

16. Insights endpoint has limit/offset or date range filter

### Concurrent Benchmark Limit (1 check)

17. `create_benchmark` caps models per request

### Status Recovery (1 check)

18. Stuck "running" benchmarks are detected and repaired

### Error Boundaries (1 check)

19. Frontend has React error boundaries wrapping page components

### Provider Error Handling (1 check)

20. All `generate()` methods validate response structure with try/except

## Files in Scope

### Backend

- `backend/requirements.txt` — replace with `pyproject.toml` + `uv.lock`
- `backend/app/config.py` — remove `redis_url`, remove `@lru_cache`
- `backend/app/main.py` — add slowapi middleware
- `backend/app/models.py` — rename `response_length` → `response_chars`, add status expiry
- `backend/app/schemas.py` — add `max_length` on prompt
- `backend/app/database.py` — minor (add connection pool settings)
- `backend/app/pricing.py` — derive model lists from providers instead of duplicating
- `backend/app/providers/__init__.py` — restructure model info source of truth
- `backend/app/providers/base.py` — rename `response_length` → `response_chars`
- `backend/app/providers/common.py` — add response validation, remove import-time api_key
- `backend/app/providers/openai.py` — read api_key at call time
- `backend/app/providers/anthropic.py` — read api_key at call time, robust input_tokens
- `backend/app/providers/gemini.py` — switch to client.stream(), read api_key at call time
- `backend/app/providers/ollama.py` — add response shape validation
- `backend/app/providers/openrouter.py` — read api_key at call time, remove hardcoded model list copy
- `backend/app/providers/vllm.py` — read config at call time
- `backend/app/routers/benchmarks.py` — cap models, status recovery
- `backend/app/routers/insights.py` — add pagination
- `backend/app/routers/providers.py` — minor
- `backend/Dockerfile` — minor (uv-based)
- `prek.toml` — remove or fix
- `docker-compose.yml` — remove redis (unused)

### Frontend

- `frontend/package.json` — upgrade React 19, latest deps, add error boundary lib
- `frontend/src/main.tsx` — wrap in error boundary
- `frontend/src/App.tsx` — wrap pages in error boundary
- `frontend/src/pages/BenchmarkResults.tsx` — fix empty reduce, rename response_length → response_chars
- `frontend/src/lib/utils.ts` — rename utility usage
- `frontend/Dockerfile` — update node image
- `frontend/vite.config.ts` — minor if needed
- `frontend/index.html` — minor if needed

## Off Limits

- **DO NOT** implement full auth/user isolation features
- **DO NOT** implement TLS termination
- **DO NOT** implement result export/data portability
- **DO NOT** implement prompt templates/save-reuse
- **DO NOT** implement side-by-side comparison view
- **DO NOT** implement scheduling/automated runs
- **DO NOT** add new external Python or npm dependencies unless absolutely necessary
- **DO NOT** modify `.auto/measure.sh` to inflate acceptance_passed scores

## Constraints

- Python lint (`ruff check`) must pass with 0 violations
- Frontend TypeScript must compile with 0 errors
- Frontend build must succeed (`npm run build`)
- All existing functionality must be preserved (the app should still run)
- Tests should be added for all fixed concerns
- Use `uv` for Python dependency management (not pip)
- Use consistent style: ruff for Python, existing code style for TypeScript

## What's Been Tried

_Update this as experiments accumulate._

### Iteration 2 — Python Toolchain Modernization
- Created `pyproject.toml` with ruff config, `uv.lock`
- Removed `aiocache` and `redis_url` (dead deps)
- Removed redis from docker-compose.yml
- Updated backend Dockerfile to use `uv`
- Added comment to `prek.toml` about prek (Rust pre-commit)
- Fixed all ruff violations (SIM117, UP017, etc.)
- Ignored B008 (false positive for FastAPI Depends)
- **Score: 13/20** (+5: response_chars, empty results fix, max_length, Gemini streaming, model dedup)

### Iteration 4 — Rate Limiting, Concurrency, Pagination, Status Recovery
- Added slowapi rate limiting (60/min default, 10/min on benchmark create)
- Added asyncio.Semaphore(5) for concurrent provider API calls
- Added `limit` parameter to insights endpoint (default 50, max 500)
- Added `_repair_stuck_benchmarks()` for stuck 'running' benchmarks
- **Score: 18/20** (+4: rate limiting, pagination, concurrency cap, status recovery)

### Iteration 6 — Config Fixes, DB Migration, Proper Tests
- Fixed SlowAPI runtime: added `Request` parameter to `create_benchmark` endpoint
- Restored `get_settings()` (without `lru_cache`); providers now call at request time
- Added column mapping: `response_chars` → SQL column `response_length` (backward compatible)
- Created `backend/tests/` with conftest (tempfile SQLite), 21 tests
  - Pricing edge cases, provider JSON parsing, API endpoints, stuck recovery, column mapping
- Created `.auto/checks.sh` (ruff + pytest + frontend build)
- Added dev dependencies (pytest, pytest-asyncio)
- **Score: 20/20** ✓ — All acceptance checks passing + checks.sh gates green

## Final Summary

| Category | Before | After |
|----------|--------|-------|
| **Tooling** | pip + requirements.txt | uv + pyproject.toml + ruff |
| **Python lint** | 0% configured | ruff with 0 violations |
| **Dead deps** | aiocache, redis_url | both removed |
| **Bugs fixed** | 5 known bugs | all fixed: Gemini streaming, empty reduce, dedup, input limits, config |
| **Tests** | 0 | 21 pytest tests |
| **CI gates** | none | ruff + pytest + frontend build |
| **Acceptance** | 3/20 (false positives) | 20/20 (real fixes) |
