# Structure

## Repository Root

```
prompt-bench/
├── .dockerignore              # Docker build context exclusions (PR #13)
├── .github/workflows/         # CI/CD (ci.yml, deploy.yml)
├── .planning/codebase/        # Codemap docs (7 files)
├── .freebuff/                 # Preview artifacts (gitignored)
├── AGENTS.md                  # AI coding agent instructions
├── QUICK_START.md             # Quick start guide
├── README.md                  # Project documentation
├── LICENSE                    # MIT
├── docker-compose.yml         # Local full-stack (postgres, redis, backend, frontend)
├── fly.toml                   # Fly.io deployment config
├── justfile                   # Just task runner
├── prek.toml                  # Prek config
├── backend/
│   ├── Dockerfile             # Multi-stage (frontend build + backend build)
│   ├── pyproject.toml         # Dependencies (alembic in main deps since PR #11)
│   ├── uv.lock                # Locked dependency tree
│   ├── alembic.ini            # Alembic migration config
│   ├── alembic/
│   │   ├── env.py             # Migration environment (uses db_utils.normalize_db_url)
│   │   └── versions/
│   │       ├── 2dae871076fe_initial_schema.py
│   │       └── 0002_add_cache_metrics.py   # Idempotent cache columns
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, migrations, health check
│   │   ├── config.py          # Pydantic settings (env vars)
│   │   ├── database.py        # SQLAlchemy engine, session, Base
│   │   ├── db_utils.py        # normalize_db_url() — zero-import shared utility (ADR-008)
│   │   ├── models.py          # Benchmark + BenchmarkResult ORM models
│   │   ├── schemas.py         # Pydantic request/response schemas
│   │   ├── pricing.py         # PRICING dict, calculate_cost(), rebuild_openrouter_pricing()
│   │   ├── limiter.py         # slowapi rate limiter
│   │   ├── session_keys.py    # In-memory SessionKeyStore (30-min TTL)
│   │   ├── routers/
│   │   │   ├── benchmarks.py  # CRUD + run_one() + _sanitize_error()
│   │   │   ├── providers.py   # GET /api/providers
│   │   │   ├── insights.py    # GET /api/insights
│   │   │   ├── cache.py       # Cache stats + clear
│   │   │   └── session_keys.py # POST/DELETE /api/session-key (not routers/session_keys.py — check)
│   │   ├── providers/
│   │   │   ├── base.py        # BaseProvider ABC + ModelInfo dataclass
│   │   │   ├── common.py      # OpenAICompatibleProvider (SSE parsing)
│   │   │   ├── openai.py      # OpenAI provider
│   │   │   ├── anthropic.py   # Anthropic provider (x-api-key, custom SSE)
│   │   │   ├── gemini.py      # Gemini provider (URL query param auth)
│   │   │   ├── openrouter.py  # OpenRouter (dynamic get_models(), PRICING rebuild)
│   │   │   ├── ollama.py      # Ollama local
│   │   │   ├── vllm.py        # vLLM provider
│   │   │   ├── model_lists.py # Model lists, refresh_openrouter_free_models()
│   │   │   └── __init__.py    # PROVIDERS registry
│   │   └── cache/
│   │       ├── __init__.py    # get_response_cache(), get_embedding_cache()
│   │       ├── response_cache.py # Response cache key + storage
│   │       ├── embedding_cache.py
│   │       └── memory_cache.py  # In-memory fallback
│   └── tests/
│       ├── conftest.py        # SQLite fixture, FastAPI TestClient
│       ├── test_providers.py  # 18 BYOK wire-level tests + pricing + SSE parsing
│       ├── test_benchmarks.py # Benchmark API tests
│       ├── test_migrations.py # Migration cycle + downgrade data preservation test
│       └── test_cache.py      # Cache behavior tests
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts         # Dev proxy /api → localhost:8000
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.tsx           # React entry point
        ├── App.tsx            # Router + layout
        ├── index.css          # Tailwind base + dark mode
        ├── types/index.ts     # TypeScript interfaces
        ├── hooks/useMediaQuery.ts
        ├── lib/api.ts         # React Query hooks
        ├── lib/utils.ts       # cn() utility
        ├── components/
        │   ├── ErrorBoundary.tsx
        │   └── ui/            # shadcn/ui components (button, card, table, badge, etc.)
        └── pages/
            ├── BenchmarkRun.tsx
            ├── BenchmarkResults.tsx
            ├── History.tsx
            ├── CompareRuns.tsx
            └── Insights.tsx
```

## Key Locations

| What | Where |
|------|-------|
| Entry point | `backend/app/main.py` (FastAPI), `frontend/src/main.tsx` (React) |
| Database models | `backend/app/models.py` |
| API endpoints | `backend/app/routers/*.py` |
| AI providers | `backend/app/providers/*.py` |
| Cache logic | `backend/app/cache/*.py` |
| Migrations | `backend/alembic/versions/*.py` |
| BYOK tests | `backend/tests/test_providers.py` (3 classes, 18 tests) |
| Downgrade test | `backend/tests/test_migrations.py::test_downgrade_preserves_non_cache_data` |
| Dependencies | `backend/pyproject.toml`, `frontend/package.json` |
| Docker build | `backend/Dockerfile`, `.dockerignore` |
| Dev server | `frontend/` (Vite :5173), `backend/` (Uvicorn :8000) |
| Codemap | `.planning/codebase/` (7 .md files) |
| ADRs | `docs/adr/` (10 records: 001–010) |
