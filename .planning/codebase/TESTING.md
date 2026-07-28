# Testing

## Backend Tests

**Framework**: pytest 8+ with `pytest-asyncio` (`asyncio_mode = "auto"`).

**Location**: `backend/tests/` — 5 test files, 105 tests total.

**Test database**: Temporary file-based SQLite (`tempfile.mkstemp(suffix=".test.db")`) per test session. Tables created/dropped per test via `autouse=True` fixture. FastAPI `TestClient` with dependency overrides pointing to the test DB session.

### Test Structure

| File | Tests | Focus |
|------|-------|-------|
| `test_cache.py` | ~40 | Response/embedding cache, Redis fallback, stampede prevention, cache keys, API endpoints, CLI |
| `test_providers.py` | ~35 | BYOK auth headers (OpenAI, Anthropic, Gemini), pricing calculations, SSE parsing, provider error handling |
| `test_benchmarks.py` | ~20 | API endpoints (CRUD, validation, edge cases), stuck benchmark repair, provider mock transport |
| `test_migrations.py` | ~5 | Alembic migration upgrade/downgrade, stamping, sequence |
| `conftest.py` | — | Fixtures: `_create_tables`, `db_session`, `client`, `pytest_unconfigure` cleanup |

### Key Test Patterns

**BYOK auth header tests**: Mock `httpx.AsyncClient` transport to capture request headers. Verify BYOK key appears in `Authorization: Bearer` (OpenAI), `x-api-key` (Anthropic), or `?key=` URL param (Gemini). Check priority (BYOK > server key) and fallback behavior.

**Cache tests**: 
- `fakeredis.aioredis.FakeRedis` for Redis backend tests (no real Redis needed)
- `InMemoryCache` for in-memory backend tests
- Stampede prevention: `asyncio.Event()` gate to hold first caller, verify N concurrent → 1 provider call + N-1 cache hits
- Cache key determinism: test prompt/model/temperature/seed/response_format changes produce different keys
- Error handling: corrupt cached value → miss, store failure → doesn't raise

**Benchmark endpoint tests**:
- Empty prompt → 422 validation error
- Too many models (>10) → 422
- Unknown provider → error in result
- Cache hit/miss via mocked provider

**Provider mock transport**: `httpx.MockTransport` with hand-crafted SSE bodies for testing stream parsing without real API calls.

### Test Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
asyncio_mode = "auto"
```

### Running Tests

```bash
# Backend
cd backend && uv run pytest                    # All 105 tests
cd backend && uv run pytest -q --tb=short      # Quiet with short tracebacks
cd backend && uv run pytest tests/test_cache.py  # Specific file

# Lint
cd backend && uv run ruff check .
```

## Frontend Tests

**Framework**: Vitest 4 + React Testing Library + jest-dom. **Location**: `frontend/src/__tests__/`

| File | Tests | Focus |
|------|-------|-------|
| `BenchmarkResults.test.tsx` | 3 | Legacy null cache fields render without crash, API error rendering, smoke test |

### Test Configuration

`frontend/vitest.config.ts`: jsdom environment, `@` path alias matching vite.config.ts, react plugin, setup file at `src/test-setup.ts`.

```bash
# Frontend
cd frontend && npm test          # vitest run (3 tests)
cd frontend && npm run test:watch  # vitest watch mode
cd frontend && npx tsc --noEmit   # TypeScript compilation check
cd frontend && npm run lint       # eslint
```

### Test Patterns

**`renderWithClient` wrapper**: Wraps component in `QueryClientProvider` with a fresh `QueryClient` (enabled, `retry: false`). This isolates React Query state per test.

**Module mocking**: `vi.mock("react-router-dom")` stubs `useParams`/`useNavigate`. `vi.mock("@/lib/api")` stubs API calls. `vi.mock("recharts")` stubs `ResponsiveContainer` to avoid ResizeObserver errors in jsdom.

**No snapshots**: Tests use explicit assertions (`toBeInTheDocument`, `toBeNull`) rather than snapshot testing.

## CI Pipeline

`.github/workflows/ci.yml` runs on push/PR to main:

| Step | Command |
|------|---------|
| Backend lint | `ruff check .` |
| Backend test | `pytest` |
| Frontend lint | `eslint .` |
| Frontend typecheck | `tsc --noEmit` |
| Frontend test | `vitest run` |

## Test Coverage Gaps

| Area | Status |
|------|--------|
| Backend unit tests | ✅ Comprehensive (105 tests) |
| Backend integration tests | ✅ Via TestClient with real SQLite |
| Frontend component tests | ⚠️ Only 3 tests (BenchmarkResults) |
| Frontend integration/E2E | ❌ No Playwright/Cypress |
| BYOK session key flow | ❌ Not tested end-to-end |
| CompareRuns page | ❌ No tests |
| Real provider API tests | ❌ All tests use mocked transports |
