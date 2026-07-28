# Conventions

## Code Style

### Python (ruff-enforced)

| Rule | Setting |
|------|---------|
| Line length | 100 |
| Indent | 4 spaces |
| Quotes | Double |
| Target version | Python 3.12 |

**Lint rules** (`pyproject.toml`): E, F, I, N, W, UP, B, SIM, C4, PL. Excludes: `PLR2004` (magic values), `PLR0913` (too many arguments), `B008` (function call defaults), `SIM117` (nested with statements).

**Migrations excluded from linting**: `alembic/versions/*.py` (excluded in `pyproject.toml`).

### TypeScript/React

| Rule | Setting |
|------|---------|
| Target | ES2022 |
| Module | ESNext (bundler resolution) |
| JSX | react-jsx |
| Strict mode | `true` |
| No unused locals | `false` (lenient) |
| No unused params | `false` (lenient) |

ESLint (`eslint.config.js`): typescript-eslint recommended rules.

## Naming Patterns

| Context | Pattern | Example |
|---------|---------|---------|
| Provider IDs | lowercase no spaces | `"openai"`, `"gemini"` |
| Model IDs | lowercase with hyphens | `"gpt-4.1"`, `"claude-sonnet-5"` |
| DB columns | snake_case | `cache_hit`, `total_latency_ms` |
| API endpoints | kebab-case | `/api/session-key`, `/api/cache/stats` |
| React components | PascalCase files | `BenchmarkCacheSection.tsx` |
| Test files | `test_*.py` | `test_providers.py` |
| Test classes/functions | `Test*` / `test_*` | `TestBYOKAuthHeader`, `test_known_model` |
| Python modules | snake_case | `db_utils.py`, `model_lists.py` |

## Patterns

### Error Handling

**Backend**: Provider errors caught in `run_one()` and returned as `error: str` in the result — they don't crash the benchmark. `_sanitize_error()` regex strips API key patterns (`sk-...`, `AIza...`) before logging or returning to the frontend.

**Migrations**: `0002_add_cache_metrics` uses SQLAlchemy `inspect()` to check column existence before each `batch_alter_table.add_column()` — avoids transaction abort on PostgreSQL. `_repair_stuck_benchmarks` catches any exception and rolls back.

**Cache failures**: Both response and embedding caches catch exceptions on store — a cache write failure doesn't fail the benchmark. Cache backend unavailability falls back to in-memory.

**Frontend**: `<ErrorBoundary>` wraps all routes. API errors shown inline via `q.isError ? <error message>`. BYOK key save failures silently uncheck "Remember" checkbox.

### Logging

Structured logging via `logging.basicConfig`:
```
2026-07-28T17:10:33 [INFO] promptbench.main: Database migrations applied successfully
```

Log levels:
- `INFO`: startup, benchmark creation/completion, cache hits, migration status
- `WARNING`: API failures, migration issues, Redis connection failures
- `DEBUG`: BYOK key usage (provider only, never the key itself)
- `ERROR`: Provider call failures

**Security**: API keys NEVER logged. `_sanitize_error()` runs before `logger.error()`. BYOK logs only provider name. Database URL sanitized via `_safe_url()`.

### Dependency Injection

FastAPI's `Depends(get_db)` for database sessions. `slowapi` limiter via `@limiter.limit()`. Test overrides via `app.dependency_overrides[get_db]`.

### Async Patterns

- `asyncio.gather()` for parallel benchmark execution
- `asyncio.Semaphore(5)` limits concurrent provider API calls
- `httpx.AsyncClient.stream()` for SSE response parsing
- `subprocess.run` is sync in `lifespan` (consistent with existing sync `init_db()` and `_repair_stuck_benchmarks`)

### React Patterns

- **Lazy loading**: All 5 page components via `React.lazy()` + `<Suspense>`
- **BYOK state**: Keys in React `useState`, never in localStorage or URL. `type="password"` for key inputs
- **Dark mode**: CSS custom properties + `.dark` class toggle. Persisted in `localStorage`
- **Responsive**: Desktop sidebar + mobile bottom tab bar. `useMediaQuery` hook, `cn()` utility

### URL Normalization

`db_utils.normalize_db_url()` — shared utility for `postgres://` → `postgresql+psycopg://`. Imported by both `database.py` (FastAPI) and `env.py` (Alembic). Zero application imports so both runtime contexts can import it safely.

## Commit Convention

Commitizen conventional commits: `feat(scope):`, `fix(scope):`, `refactor(scope):`, `docs:`, `test:`, `chore:`. Footer: `Generated with Codebuff 🤖 Co-Authored-By: Codebuff <noreply@codebuff.com>`.

## API Conventions

| Rule | Detail |
|------|--------|
| URL prefix | `/api/` for all backend routes |
| Response format | JSON (`response_model=` on all routes) |
| Status codes | 200 (success), 204 (DELETE), 404 (not found), 422 (validation), 429 (rate limit) |
| Error propagation | `error: string \| null` in result objects, never 500 for domain errors |
| CORS | `allow_credentials=True`, methods `GET/POST/DELETE/OPTIONS`, origins from config |
| Rate limiting | 60/min global, 10/min for POST /benchmarks |

## Data Safety

| Rule | Where |
|------|-------|
| BYOK keys never persisted | In-memory only, `copy.copy()` per request |
| BYOK keys never logged | `%s` with provider name only |
| Provider errors sanitized | `_sanitize_error()` regex in `benchmarks.py` |
| Cache disabled for BYOK | `use_cache = req.cache and not client_key` per ADR-007 |
| Database URL sanitized in logs | `_safe_url()` strips credentials |
| Frontend keys never in storage | `useState`, `type="password"` |
| Deferred import documented | `model_lists.py` comment explains cycle-breaking deferred import |
