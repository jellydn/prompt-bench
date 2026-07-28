# Testing

## Framework

| Layer | Framework | Runner |
|-------|-----------|--------|
| Backend | pytest ≥8.0.0 | `uv run pytest` |
| Async | pytest-asyncio ≥0.25.0 | `asyncio_mode = "auto"` |
| Coverage | pytest-cov ≥5.0.0 | — |
| Redis mocking | fakeredis ≥2.0.0 | In-memory fake Redis |
| Frontend | Vitest + React Testing Library | `npx vitest` (planned, not yet configured) |

## Test Structure

```
backend/tests/
├── conftest.py              # SQLite fixture, FastAPI TestClient
├── test_providers.py        # 18 BYOK wire-level tests + pricing + SSE parsing
├── test_benchmarks.py       # Benchmark API CRUD tests
├── test_cache.py            # Cache behavior tests
├── test_migrations.py       # Migration cycle + downgrade data preservation test
frontend/src/
├── (no tests configured yet)
```

## Test Database

- `conftest.py` creates a temporary file-based SQLite database via `tempfile.mkstemp`
- `_create_tables` fixture creates/drops tables before/after each test
- `db_session` fixture provides a clean session
- `client` fixture provides a FastAPI `TestClient` with overridden `get_db` dependency

## Migration Tests

### Alembic config check

`test_alembic_config_exists` — verifies `alembic.ini`, `alembic/` directory, `env.py`, and at least one migration file exist.

### Full cycle test

`test_migration_full_cycle` — creates a temporary SQLite database, runs `upgrade(head)` to create all tables, verifies `benchmarks` + `benchmark_results` + `alembic_version` exist, runs `downgrade(base)` to drop everything, verifies tables are gone. Uses `ALEMBIC_TEST_URL` env var (read by `env.py`).

### Downgrade data preservation test (PR #12)

`test_downgrade_preserves_non_cache_data` — validates that the `batch_alter_table` temp-table-copy-rename cycle preserves non-cache data through:

1. `upgrade(head)` — creates tables with cache columns
2. Insert benchmark + result with cache column values
3. `downgrade("2dae871076fe")` — drops cache columns
4. Verify non-cache data survived (id, provider, model, tokens, cost)
5. Verify cache columns no longer exist in table schema
6. `upgrade(head)` — re-adds cache columns
7. Verify non-cache data intact, cache columns restored as NULL

Uses WAL journal mode + NullPool to avoid SQLite write-lock contention with alembic's engine. Cleans up WAL sidecar files in finally block.

## Provider Tests

### Pricing tests (7 tests)

`TestPricing` — verifies `calculate_cost()` for known models, zero tokens, free models, unknown providers/models, large token counts, and that all registered providers have pricing entries.

### BYOK wire-level tests (18 tests — ADR-010)

Three test classes inheriting from `_BYOKTestBase`:

| Class | Provider | Tests | Auth mechanism |
|-------|----------|-------|---------------|
| `TestBYOKAuthHeader` | OpenAI | 6 | Authorization: Bearer header |
| `TestBYOKAnthropicAuthHeader` | Anthropic | 5 | x-api-key header |
| `TestBYOKGeminiAuthHeader` | Gemini | 7 | URL query param (?key=...) |

Each class tests: BYOK key used, server key fallback, no-key behavior, BYOK priority over server key, multi-chunk SSE stream persistence. Gemini additionally tests key sanitization in error response URLs.

`_BYOKTestBase` provides shared helpers (`_capture_transport`, `_patched_client`, `_mock_settings`) via `@classmethod`/`@staticmethod`. Each subclass defines its own `_sse_body` for provider-specific SSE format.

### SSE parsing tests (4 tests)

`TestSSEParsing` — malformed JSON, non-data line skip, [DONE] signal detection, full SSE stream parsing flow.

## Benchmark API Tests

`test_benchmarks.py` — CRUD operations: create, list, detail, delete. Validates response schemas, error handling, rate limiting.

## Cache Tests

`test_cache.py` — response/embedding cache behavior: hit/miss, TTL expiration, stampede prevention (`_KeyLockRegistry`), Redis fallback to in-memory, cache disabled for BYOK, embedding similarity matching.

## Test Counts

| File | Tests |
|------|-------|
| `test_providers.py` | 18 BYOK + 7 pricing + 4 SSE parsing + 1 dataclass = 30 |
| `test_benchmarks.py` | ~7 (CRUD + edge cases) |
| `test_cache.py` | ~65 (response + embedding cache) |
| `test_migrations.py` | 3 (config check + full cycle + downgrade data preservation) |
| **Total** | **106** |

## CI

| Workflow | File | Trigger |
|----------|------|---------|
| CI | `.github/workflows/ci.yml` | push, pull_request |
| Deploy | `.github/workflows/deploy.yml` | push to main, workflow_dispatch |

CI runs: ruff, pytest, tsc --noEmit.
Deploy runs: `fly deploy` to prompt-bench.fly.dev.
