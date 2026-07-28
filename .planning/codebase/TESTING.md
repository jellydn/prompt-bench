# Testing

## Backend Tests (pytest)

| Category | File | Tests |
|----------|------|-------|
| BYOK auth headers | `test_providers.py` | 18 tests: 6 OpenAI (Bearer), 5 Anthropic (x-api-key), 7 Gemini (URL param) |
| Provider edge cases | `test_providers.py` | ProviderResponse dataclass, pricing edge cases, SSE parsing |
| Benchmark CRUD | `test_benchmarks.py` | Create, list, get, delete, status repair |
| Cache | `test_cache.py` | Hit/miss, stampede prevention, Redis fallback |
| Migrations | `test_migrations.py` | Migration tests |
| **Total** | | **105 tests** |

### Test infrastructure

| Component | Tool |
|-----------|------|
| HTTP transport mocking | `httpx.MockTransport` |
| Settings mocking | `unittest.mock.Mock` |
| Database (tests) | SQLite in-memory (`sqlite:///`) |
| Fixtures | `conftest.py` (app factory, DB setup, test client) |
| Redis mock | `fakeredis` |

### BYOK wire-level tests

Each provider has a dedicated test class verifying:
- BYOK key is sent in the correct location (header vs URL param)
- Server key is used as fallback when no BYOK
- No auth when neither key is set
- BYOK takes priority over server key when both are present
- Multi-chunk streaming preserves BYOK key across full SSE lifecycle
- (Gemini only) Keys appear in httpx exception URLs — callers must sanitize

### Running tests

```bash
cd backend && uv run pytest -q --tb=short
```

## Frontend Tests (Vitest)

| Component | Test |
|-----------|------|
| BenchmarkResults | Renders without crash with legacy null cache fields |

**Coverage**: Sparse (3 tests). Most frontend behavior is untested.

### Running tests

```bash
cd frontend && npx vitest run
```

## CI Pipeline (`.github/workflows/ci.yml`)

| Job | Steps |
|-----|-------|
| Backend | `uv sync`, ruff check, pytest |
| Frontend | `npm ci`, tsc --noEmit, vitest run |

Triggers on push/PR to any branch.

## Coverage Gaps

| Gap | Priority |
|-----|----------|
| Real provider API calls (all mocked) | High |
| CompareRuns page | Medium |
| Session key save/clear/expiry integration | Medium |
| Alembic downgrade | Low |
| Rate limiting | Low |
| Mobile responsive layout | Low |
| Dark mode toggle | Low |
