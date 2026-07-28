# Structure

## Directory Layout

```
prompt-bench/
├── backend/                          # Python FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app creation, lifespan, CORS, routers
│   │   ├── config.py                 # Pydantic Settings (.env loading)
│   │   ├── database.py              # SQLAlchemy engine, SessionLocal, init_db()
│   │   ├── db_utils.py              # Shared: normalize_db_url()
│   │   ├── models.py                # ORM: Benchmark, BenchmarkResult
│   │   ├── schemas.py               # Pydantic: BenchmarkCreate, BenchmarkOut, ResultOut
│   │   ├── pricing.py               # PRICING dict, calculate_cost()
│   │   ├── limiter.py               # slowapi rate limiter
│   │   ├── session_keys.py          # SessionKeyStore (Phase 2 BYOK)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── benchmarks.py        # POST/GET/DELETE /api/benchmarks
│   │   │   ├── providers.py         # GET /api/providers
│   │   │   ├── insights.py          # GET /api/insights
│   │   │   ├── cache.py             # GET /api/cache/stats
│   │   │   └── session_keys.py      # POST/DELETE /api/session-key
│   │   ├── providers/
│   │   │   ├── __init__.py          # PROVIDERS dict, get_provider()
│   │   │   ├── base.py              # BaseProvider ABC, ModelInfo, ProviderResponse
│   │   │   ├── common.py            # OpenAICompatibleProvider (shared SSE)
│   │   │   ├── openai.py            # OpenAIProvider
│   │   │   ├── anthropic.py         # AnthropicProvider (custom SSE)
│   │   │   ├── gemini.py            # GeminiProvider (URL auth)
│   │   │   ├── openrouter.py        # OpenRouterProvider
│   │   │   ├── ollama.py            # OllamaProvider (local)
│   │   │   ├── vllm.py              # VLLMProvider (local)
│   │   │   └── model_lists.py       # Shared model lists, runtime refresh
│   │   └── cache/
│   │       ├── __init__.py
│   │       ├── cache.py             # CacheBackend, RedisCache, InMemoryCache
│   │       ├── response_cache.py    # ResponseCache + _KeyLockRegistry
│   │       ├── embedding_cache.py   # EmbeddingCache
│   │       └── keys.py              # response_cache_key(), embedding_cache_key()
│   ├── alembic/
│   │   ├── env.py                   # Migration environment (imports db_utils)
│   │   ├── alembic.ini
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 2dae871076fe_initial_schema.py
│   │       └── 0002_add_cache_metrics.py  # Idempotent: inspector-based
│   ├── tests/
│   │   ├── conftest.py              # Test fixtures, DB setup, app factory
│   │   ├── test_providers.py        # Pricing, BYOK auth header tests (3 providers)
│   │   ├── test_benchmarks.py       # Benchmark CRUD, concurrency
│   │   ├── test_cache.py            # Cache hit/miss, stampede prevention
│   │   └── test_migrations.py       # Migration tests
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── frontend/                         # React SPA
│   ├── src/
│   │   ├── main.tsx                 # React root + QueryClientProvider
│   │   ├── App.tsx                  # Router, sidebar, bottom tabs, theme
│   │   ├── index.css                # Tailwind + CSS custom properties
│   │   ├── types/index.ts           # Shared TypeScript interfaces
│   │   ├── lib/api.ts               # fetch wrapper, query keys, TanStack Query hooks
│   │   ├── lib/utils.ts             # cn() utility
│   │   ├── hooks/useMediaQuery.ts   # Responsive breakpoint
│   │   ├── components/
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── BenchmarkCacheSection.tsx  # Cache badges + latency chart
│   │   │   └── ui/                  # shadcn/ui primitives
│   │   └── pages/
│   │       ├── BenchmarkRun.tsx      # Run page
│   │       ├── BenchmarkResults.tsx  # Results page
│   │       ├── CompareRuns.tsx       # Compare page
│   │       ├── History.tsx           # History page
│   │       └── Insights.tsx          # Insights page
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts               # Vite config + API proxy
│   ├── vitest.config.ts             # Vitest config
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── eslint.config.js
│   ├── index.html
│   └── Dockerfile
├── docker-compose.yml               # Full stack: postgres + redis + backend + frontend
├── fly.toml                         # Fly.io deployment config
├── prek.toml                        # Pre-commit hooks (TOML format)
├── justfile                         # Task runner
├── .github/workflows/
│   ├── ci.yml                       # CI: ruff + pytest + tsc + vitest
│   └── deploy.yml                   # Fly.io deploy on push to main
├── .planning/codebase/              # Codemap documentation (7 files)
├── docs/
│   ├── caching.md                   # Cache architecture and usage guide
│   └── adr/                         # Architecture Decision Records
├── AGENTS.md                        # AI coding agent guide
├── README.md
├── QUICK_START.md
└── LICENSE
```

## Key Locations

| Component | Path |
|-----------|------|
| App entry point | `backend/app/main.py` |
| Settings | `backend/app/config.py` |
| DB config | `backend/app/database.py` |
| DB utils | `backend/app/db_utils.py` |
| Provider registration | `backend/app/providers/__init__.py` |
| Model lists | `backend/app/providers/model_lists.py` |
| Pricing | `backend/app/pricing.py` |
| Cache | `backend/app/cache/` |
| Migrations | `backend/alembic/` |
| Frontend API client | `frontend/src/lib/api.ts` |
| Frontend router | `frontend/src/App.tsx` |
| CI config | `.github/workflows/ci.yml` |

## Naming Conventions

| Context | Pattern | Examples |
|---------|---------|----------|
| Provider IDs | lowercase, no spaces | `"openai"`, `"gemini"` |
| Model IDs | lowercase with hyphens | `"gpt-4.1"`, `"claude-sonnet-5"` |
| DB columns | snake_case | `cache_hit`, `total_latency_ms` |
| API endpoints | kebab-case | `/api/session-key`, `/api/cache/stats` |
| React components | PascalCase files | `BenchmarkCacheSection.tsx` |
| Test files | `test_*.py` | `test_providers.py` |
| Test classes/functions | `Test*` / `test_*` | `TestBYOKAuthHeader` |
| Python modules | snake_case | `db_utils.py`, `model_lists.py` |

## Routes (Frontend)

| Path | Component | Lazy Loaded |
|------|-----------|-------------|
| `/` | `BenchmarkRun` | ✓ |
| `/compare` | `CompareRuns` | ✓ |
| `/history` | `History` | ✓ |
| `/insights` | `Insights` | ✓ |
| `/results/:id` | `BenchmarkResults` | ✓ |

## API Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/providers` | List providers + models |
| POST | `/api/benchmarks` | Create benchmark |
| GET | `/api/benchmarks` | List history |
| GET | `/api/benchmarks/{id}` | Get benchmark + results |
| DELETE | `/api/benchmarks/{id}` | Delete benchmark |
| GET | `/api/insights` | Aggregate statistics |
| GET | `/api/cache/stats` | Cache statistics |
| POST | `/api/session-key` | Save BYOK session key |
| DELETE | `/api/session-key` | Clear BYOK session keys |
| GET | `/api/session-key/providers` | List providers with saved keys |
