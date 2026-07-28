# Stack

## Backend

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| Web framework | FastAPI | ≥0.115 |
| ASGI server | Uvicorn | — |
| ORM | SQLAlchemy | 2.x |
| Migrations | Alembic | — |
| Validation | Pydantic | 2.x |
| Rate limiting | slowapi | — |
| HTTP client | httpx (async) | — |
| Redis client | redis-py | — |
| Redis mock (test) | fakeredis | — |
| Linter/formatter | ruff | — |
| Package manager | uv | — |

**Database**: PostgreSQL (production, Docker) / SQLite (local dev). Switched via `DATABASE_URL` in `.env`.

**Key dependency**: `psycopg` v3 driver — URL normalization via `db_utils.normalize_db_url()` handles both `postgres://` and `postgresql://` prefixes (Fly.io uses `postgres://`).

### Backend directory layout

```
backend/
├── app/
│   ├── main.py              # FastAPI app, lifespan, CORS, routers
│   ├── config.py            # Pydantic Settings from .env
│   ├── database.py          # SQLAlchemy engine, session, init_db()
│   ├── db_utils.py          # normalize_db_url() (shared by env.py + database.py)
│   ├── models.py            # ORM models: Benchmark, BenchmarkResult
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── pricing.py           # PRICING dict + calculate_cost()
│   ├── limiter.py           # slowapi rate limiter
│   ├── session_keys.py      # SessionKeyStore for Phase 2 BYOK
│   ├── routers/
│   │   ├── benchmarks.py    # POST/GET /api/benchmarks
│   │   ├── providers.py     # GET /api/providers
│   │   ├── insights.py      # GET /api/insights
│   │   ├── cache.py         # GET /api/cache/stats
│   │   └── session_keys.py  # POST/DELETE /api/session-key
│   ├── providers/
│   │   ├── base.py          # BaseProvider ABC, ModelInfo, ProviderResponse
│   │   ├── common.py        # OpenAICompatibleProvider (shared SSE)
│   │   ├── openai.py        # OpenAIProvider
│   │   ├── anthropic.py     # AnthropicProvider (custom SSE)
│   │   ├── gemini.py        # GeminiProvider (URL auth, custom SSE)
│   │   ├── openrouter.py    # OpenRouterProvider
│   │   ├── ollama.py        # OllamaProvider (local)
│   │   ├── vllm.py          # VLLMProvider (local)
│   │   └── model_lists.py   # Shared model lists, runtime refresh
│   └── cache/
│       ├── cache.py         # CacheBackend, RedisCache, InMemoryCache
│       ├── response_cache.py # ResponseCache with stampede prevention
│       ├── embedding_cache.py # EmbeddingCache
│       └── keys.py          # Cache key generation
├── alembic/
│   ├── env.py               # Migration environment (uses db_utils)
│   └── versions/
│       ├── 2dae871076fe_initial_schema.py
│       └── 0002_add_cache_metrics.py  # Idempotent via inspector
├── tests/
│   ├── conftest.py
│   ├── test_providers.py     # BYOK auth header tests, pricing tests
│   ├── test_benchmarks.py
│   └── test_migrations.py
├── pyproject.toml
└── uv.lock
```

## Frontend

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 19 |
| Bundler | Vite | 6 |
| Language | TypeScript | 5.7 (strict mode) |
| Routing | React Router | 7 |
| Data fetching | TanStack Query (React Query) | 5 |
| Charts | Recharts | — |
| UI primitives | shadcn/ui (Radix) | — |
| Styling | Tailwind CSS | 3.4 |
| Icons | lucide-react | — |
| Testing | Vitest + React Testing Library | — |

### Frontend directory layout

```
frontend/src/
├── main.tsx                  # React root, QueryClientProvider
├── App.tsx                   # Router, sidebar, bottom tab bar, theme toggle
├── index.css                 # Tailwind + CSS custom properties
├── types/index.ts            # Shared TypeScript types
├── lib/
│   ├── api.ts                # API client (fetch wrapper, TanStack Query keys)
│   └── utils.ts              # cn() utility (clsx + tailwind-merge)
├── hooks/
│   └── useMediaQuery.ts      # Responsive breakpoint hook
├── components/
│   ├── ErrorBoundary.tsx     # React error boundary
│   ├── BenchmarkCacheSection.tsx  # Cache badges + comparison + latency chart
│   └── ui/                   # shadcn/ui components
│       ├── button.tsx, card.tsx, badge.tsx, table.tsx, tabs.tsx,
│       ├── select.tsx, slider.tsx, separator.tsx, textarea.tsx,
│       ├── input.tsx, label.tsx
└── pages/
    ├── BenchmarkRun.tsx      # Prompt input + model selection + BYOK keys
    ├── BenchmarkResults.tsx  # Results table + responses tab + cache section
    ├── CompareRuns.tsx       # Side-by-side run comparison
    ├── History.tsx           # Paginated benchmark list
    └── Insights.tsx          # Aggregate statistics cards
```

## Infrastructure

| Component | Technology |
|-----------|-----------|
| Container orchestration | Docker Compose (local) |
| Cloud platform | Fly.io |
| CI/CD | GitHub Actions |
| Code review bot | CodeRabbit |
| Security scanning | GitGuardian, Socket |
| Secret scanning | TruffleHog (autoreview preflight) |
