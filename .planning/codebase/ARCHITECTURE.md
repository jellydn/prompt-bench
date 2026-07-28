# Architecture

## System Design

PromptBench is a **monorepo** with two deployable units:

```
Browser (React SPA) ←→ FastAPI (REST JSON) ←→ PostgreSQL + Redis
                              ↓
                    External AI Provider APIs
                    (OpenAI, Anthropic, Gemini,
                     OpenRouter, Ollama, vLLM)
```

The frontend is a static SPA served by the same FastAPI process in production (Docker multi-stage builds into `backend/static/`). In development, Vite's dev server proxies `/api` to `localhost:8000`.

## Backend Layers

```
┌─────────────────────────────────────────────────┐
│ Routers (benchmarks, insights, providers,       │
│          cache, session_keys)                   │
├─────────────────────────────────────────────────┤
│ Services / Domain Logic                          │
│  - run_one() — benchmark executor               │
│  - ResponseCache.get_or_compute()               │
│  - provider.generate() — API calls              │
│  - SessionKeyStore — session keys               │
│  - _run_alembic_migrations() — DB migration     │
├─────────────────────────────────────────────────┤
│ Data Access (SQLAlchemy ORM)                    │
│  - models.py — Benchmark, BenchmarkResult        │
│  - Session = Depends(get_db)                    │
│  - Alembic migrations (env.py uses db_utils)    │
├─────────────────────────────────────────────────┤
│ Infrastructure                                   │
│  - config.py — Pydantic Settings                │
│  - database.py — engine, sessionmaker            │
│  - db_utils.py — normalize_db_url()             │
│  - limiter.py — slowapi rate limiter            │
│  - cache/ — Redis + in-memory backends          │
└─────────────────────────────────────────────────┘
```

## Startup Flow

```
lifespan (async context manager)
  ├── init_db()                        # create_all (no-op if tables exist)
  ├── _run_alembic_migrations()        # stamp baseline (once) → upgrade head
  ├── _repair_stuck_benchmarks(db)     # reset 'running' benchmarks from crash
  ├── refresh_openrouter_free_models() # fetch free model list from API
  ├── get_cache()                      # initialize Redis or in-memory cache
  └── yield                            # server ready
```

### Migration startup — stamp-then-upgrade

`_run_alembic_migrations()` handles three DB states:

| State | What happens |
|-------|-------------|
| Fresh empty DB | `init_db()` creates tables; `alembic current` fails → stamp baseline → upgrade no-ops |
| Existing DB (no alembic_version) | `init_db()` no-op; `alembic current` fails → stamp baseline → upgrade applies 0002 |
| DB with alembic_version | `alembic current` succeeds → skip stamp → upgrade applies pending |

The `alembic current` check prevents re-stamping on every startup (would overwrite migration state backward).

### Migration 0002 idempotency

Uses SQLAlchemy `inspect()` to check column existence before `batch_alter_table.add_column()`. Avoids `try/except OperationalError` (broken on PostgreSQL — error poisons the Alembic transaction).

## Request Flows

### Run Benchmark

```
POST /api/benchmarks
  → inject pb_session cookie → payload._session_id
  → INSERT Benchmark (status='running')
  → asyncio.gather(run_one() for each model)
    → get_provider(provider_id)
    → inject BYOK key (per-request > session > server)
    → compute response_cache_key()
    → if BYOK active: skip cache, call provider directly
    → ResponseCache.get_or_compute(key, _compute)
      → if cache hit: return serialized ProviderResponse
      → if cache miss: async with _KeyLockRegistry lock → provider.generate()
  → INSERT BenchmarkResult for each outcome
  → UPDATE Benchmark.status
  ← 200 JSON
```

### History

```
GET /api/benchmarks?limit=20&offset=0
  → SELECT benchmarks ORDER BY created_at DESC
  → selectinload(Benchmark.results)
  → aggregate: total_cost, total_tokens, avg_latency_ms
  ← 200 JSON (list[BenchmarkSummary])
```

### Insights

```
GET /api/insights
  → SELECT recent benchmarks (LIMIT 50)
  → SQL aggregation via sqlalchemy.func:
    - most_expensive_prompt, fastest_model, lowest_cost_model, best_cost_performance
  ← 200 JSON
```

## Provider Pattern (ADR-002)

Six providers in `PROVIDERS` dict:
1. `OpenAIProvider(OpenAICompatibleProvider)` — Bearer auth
2. `AnthropicProvider(BaseProvider)` — x-api-key header, custom SSE
3. `GeminiProvider(BaseProvider)` — URL query param auth, custom SSE
4. `OpenRouterProvider(OpenAICompatibleProvider)` — aggregated provider
5. `OllamaProvider(BaseProvider)` — local, always configured
6. `VLLMProvider(OpenAICompatibleProvider)` — local

`BaseProvider.get_models()` uses `.get()` fallback chain for safety:
```python
provider_pricing = PRICING.get(self.provider_id, {})
ModelInfo(k, v, provider_pricing.get(k, {"input": 0.0, "output": 0.0}))
```

## BYOK Key Injection (ADR-003)

Priority chain in `run_one()`:
1. `benchmark_req.client_keys` (per-request JSON body)
2. `SessionKeyStore.get_keys()` (session cookie)
3. Server-configured API key

`copy.copy(provider)` prevents mutating the global singleton.

## Cache Architecture (ADR-005, ADR-007)

- **Response cache**: `get_or_compute(key, compute_fn, cacheable)` — `cacheable=False` always calls provider (BYOK guard)
- **Stampede prevention** (ADR-004): `_KeyLockRegistry` — per-key `asyncio.Lock`
- **Cache key** (ADR-005): provider, model, prompt, system_prompt, temperature, max_tokens, seed, response_format, config_version — deterministic JSON → SHA-256

## Frontend Architecture

### Component Tree

```
App
├── Sidebar (desktop) / Header (mobile hamburger)
├── Bottom Tab Bar (mobile only)
└── Routes (React Router 7, lazy-loaded)
    ├── / → BenchmarkRun (prompt + model selection + BYOK inputs)
    ├── /results/:id → BenchmarkResults (table + responses + cache section)
    ├── /compare → CompareRuns (side-by-side)
    ├── /history → History (paginated table)
    └── /insights → Insights (aggregate cards)
```

### State Management

- **Server state**: TanStack Query (`useQuery`, `useMutation`)
- **Local state**: `useState` for form inputs, BYOK keys (never persisted), dark mode, pagination
- **Theme**: CSS custom properties + `.dark` class, persisted in `localStorage`
