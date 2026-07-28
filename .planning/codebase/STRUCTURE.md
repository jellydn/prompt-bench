# Structure

## Directory Layout

```
prompt-bench/
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── main.py                   # FastAPI app, lifespan, middleware
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── database.py               # SQLAlchemy engine, session, init_db()
│   │   ├── models.py                 # ORM: Benchmark, BenchmarkResult
│   │   ├── schemas.py                # Pydantic: BenchmarkCreate, BenchmarkOut, etc.
│   │   ├── pricing.py                # PRICING dict + calculate_cost()
│   │   ├── limiter.py                # slowapi Limiter (60/min global)
│   │   ├── session_keys.py           # In-memory SessionKeyStore (Phase 2 BYOK)
│   │   ├── routers/
│   │   │   ├── benchmarks.py         # POST /benchmarks, GET /benchmarks, GET /benchmarks/{id}, DELETE
│   │   │   ├── insights.py           # GET /insights (SQL-level aggregation)
│   │   │   ├── providers.py          # GET /providers (cached provider list)
│   │   │   ├── cache.py              # GET /cache/stats, DELETE /cache
│   │   │   └── session_keys.py       # POST/DELETE /session-key
│   │   ├── providers/
│   │   │   ├── __init__.py           # PROVIDERS registry, get_providers_cached()
│   │   │   ├── base.py               # BaseProvider(ABC), ModelInfo, ProviderResponse
│   │   │   ├── common.py             # OpenAICompatibleProvider (shared SSE parsing)
│   │   │   ├── openai.py             # OpenAIProvider
│   │   │   ├── anthropic.py          # AnthropicProvider (custom SSE)
│   │   │   ├── gemini.py             # GeminiProvider (custom SSE + URL auth)
│   │   │   ├── openrouter.py         # OpenRouterProvider
│   │   │   ├── ollama.py             # OllamaProvider (local, JSON-lines)
│   │   │   ├── vllm.py               # VLLMProvider (local)
│   │   │   └── model_lists.py        # Static + runtime-refreshed model IDs
│   │   ├── cache/
│   │   │   ├── __init__.py           # Public API exports
│   │   │   ├── cache.py              # CacheBackend, InMemoryCache, RedisCache
│   │   │   ├── response_cache.py     # ResponseCache, CacheInfo, KeyLockRegistry
│   │   │   ├── embedding_cache.py    # EmbeddingCache, EmbeddingResult
│   │   │   └── keys.py               # Cache key generators
│   │   └── __init__.py
│   ├── alembic/
│   │   ├── env.py                    # Migration environment (reads DATABASE_URL)
│   │   ├── alembic.ini               # Base config (SQLite default)
│   │   ├── script.py.mako            # Migration template
│   │   └── versions/
│   │       ├── 2dae871076fe_initial_schema.py
│   │       └── 0002_add_cache_metrics.py  # Idempotent cache columns
│   ├── tests/
│   │   ├── conftest.py               # Test fixtures (temp SQLite, TestClient)
│   │   ├── test_providers.py         # Provider + BYOK auth header tests
│   │   ├── test_benchmarks.py        # API endpoint + SSE parsing tests
│   │   ├── test_cache.py             # Cache layer tests (fakeredis)
│   │   └── test_migrations.py        # Alembic migration tests
│   ├── pyproject.toml                # Dependencies, ruff config, pytest config
│   ├── uv.lock                       # Locked dependency versions
│   └── Dockerfile                    # Multi-stage: build frontend → backend + static
├── frontend/                         # React 19 SPA
│   ├── src/
│   │   ├── main.tsx                  # ReactDOM.createRoot, QueryClientProvider
│   │   ├── App.tsx                   # Layout, sidebar, bottom tabs, routes
│   │   ├── index.css                 # Tailwind + CSS custom properties (theme)
│   │   ├── types/
│   │   │   └── index.ts              # TypeScript interfaces (Provider, Benchmark, etc.)
│   │   ├── lib/
│   │   │   ├── api.ts                # fetch() wrapper, all API functions
│   │   │   └── utils.ts              # cn(), money(), latency(), tokens()
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui components (11 files)
│   │   │   ├── ErrorBoundary.tsx      # React error boundary
│   │   │   └── BenchmarkCacheSection.tsx  # Cache metrics display + CacheBadge
│   │   ├── hooks/
│   │   │   └── useMediaQuery.ts      # Responsive breakpoint hook
│   │   ├── pages/
│   │   │   ├── BenchmarkRun.tsx       # Prompt input + model selection
│   │   │   ├── BenchmarkResults.tsx   # Results table + charts + cache section
│   │   │   ├── CompareRuns.tsx        # Side-by-side run comparison
│   │   │   ├── History.tsx            # Paginated benchmark list
│   │   │   └── Insights.tsx           # Aggregate statistics cards
│   │   ├── __tests__/
│   │   │   └── BenchmarkResults.test.tsx  # Component rendering test
│   │   └── test-setup.ts             # jest-dom matchers import
│   ├── index.html                    # Vite entry point
│   ├── vite.config.ts                # Vite config (+ @ alias, proxy)
│   ├── vitest.config.ts              # Vitest config (jsdom, @ alias)
│   ├── tsconfig.json                 # TypeScript config (strict, paths)
│   ├── tailwind.config.js            # Tailwind CSS custom colors
│   ├── postcss.config.js             # PostCSS plugins
│   ├── eslint.config.js              # ESLint config (typescript-eslint)
│   ├── package.json                  # Dependencies + scripts
│   └── Dockerfile                    # Dev server (Node 24 Alpine)
├── docs/
│   ├── adr/                          # Architecture Decision Records (7 ADRs)
│   │   ├── 001-response-embedding-cache.md
│   │   ├── 002-provider-abstraction.md
│   │   ├── 003-byok-architecture.md
│   │   ├── 004-stampede-prevention.md
│   │   ├── 005-cache-key-design.md
│   │   ├── 006-frontend-testing.md
│   │   └── 007-cache-byok-guard.md
│   └── caching.md                    # Cache user documentation
├── .github/workflows/
│   ├── ci.yml                        # CI: ruff, pytest, tsc, eslint
│   └── deploy.yml                    # CD: flyctl deploy on push to main
├── docker-compose.yml                # Full stack: postgres, redis, backend, frontend
├── fly.toml                          # Fly.io deployment config
├── AGENTS.md                         # AI coding agent instructions
├── README.md                         # Project README
├── QUICK_START.md                    # Quick start guide
├── justfile                          # Task runner commands
└── .planning/
    ├── codebase/                     # This codemap (7 documents)
    └── handoffs/                     # Session handoff files
```

## Naming Conventions

| Convention | Example |
|---|---|
| **Backend modules**: lowercase with underscores | `benchmarks.py`, `session_keys.py` |
| **Backend classes**: PascalCase | `BaseProvider`, `BenchmarkResult` |
| **Backend functions**: snake_case | `run_one()`, `_sanitize_error()` |
| **Backend private helpers**: prefixed with `_` | `_run_alembic_migrations()` |
| **Frontend components**: PascalCase, one per file | `BenchmarkRun.tsx` |
| **Frontend utilities**: camelCase | `cn()`, `api.history()` |
| **Frontend types**: PascalCase interfaces | `BenchmarkResult`, `CacheStats` |
| **Database tables**: snake_case plural | `benchmarks`, `benchmark_results` |
| **Database columns**: snake_case | `total_latency_ms`, `cache_hit` |
| **Alembic migrations**: `NNNN_description.py` | `0002_add_cache_metrics.py` |
| **ADR files**: `NNN-slug-name.md` | `003-byok-architecture.md` |
| **Loggers**: `promptbench.module_name` | `promptbench.benchmarks` |

## Key Locations

| What | Where |
|------|-------|
| App entry point | `backend/app/main.py` |
| Startup migrations | `backend/app/main.py::_run_alembic_migrations()` |
| Provider registry | `backend/app/providers/__init__.py::PROVIDERS` |
| Pricing data | `backend/app/pricing.py::PRICING` |
| Benchmark runner | `backend/app/routers/benchmarks.py::run_one()` |
| BYOK key injection | `backend/app/routers/benchmarks.py::run_one()` (lines ~40-60) |
| Cache layer | `backend/app/cache/response_cache.py` |
| Session key store | `backend/app/session_keys.py::SessionKeyStore` |
| Frontend API client | `frontend/src/lib/api.ts` |
| Frontend routes | `frontend/src/App.tsx` (Routes component) |
| UI theme variables | `frontend/src/index.css` |
| Test fixtures | `backend/tests/conftest.py` |
| Migration env | `backend/alembic/env.py::get_url()` |
