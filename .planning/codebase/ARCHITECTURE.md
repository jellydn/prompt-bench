# Architecture

## System Pattern

**Monorepo with separate frontend/backend services.**

```
Browser → Vite dev server (:5173) → /api proxy → Uvicorn (:8000) → SQLite/PostgreSQL
                                                                    → Redis (cache)
                                                                    → AI providers (OpenAI, Anthropic, Gemini, OpenRouter, Ollama, vLLM)
```

Production: React SPA served as static files from FastAPI (Docker multi-stage build).

## Layers

### Backend (`backend/app/`)

```
routers/         HTTP endpoints (FastAPI APIRouter)
providers/       AI model abstraction layer
cache/           Response + embedding cache (Redis + in-memory fallback)
```

### Router dependency chain

```
GET  /api/providers     → providers.router
POST /api/benchmarks    → benchmarks.router   (creates + runs benchmarks)
GET  /api/benchmarks    → benchmarks.router   (history with summaries)
GET  /api/benchmarks/:id → benchmarks.router   (single benchmark detail)
DELETE /api/benchmarks/:id → benchmarks.router
GET  /api/insights      → insights.router
POST /api/session-key   → session_keys.router (BYOK session keys)
DELETE /api/session-key → session_keys.router (clear keys)
GET  /api/cache/stats   → cache.router
POST /api/cache/clear   → cache.router
GET  /api/health        → FastAPI app-level   (no DB dependency)
```

### Provider architecture

```
BaseProvider (ABC)
├── OpenAICompatibleProvider (common.py) — /chat/completions SSE parsing
│   ├── OpenAIProvider (openai.py)
│   ├── OpenRouterProvider (openrouter.py) — dynamic model list + PRICING rebuild
│   └── vLLMProvider (vllm.py)
├── AnthropicProvider (anthropic.py) — custom x-api-key + SSE format
├── GeminiProvider (gemini.py) — URL query param auth + Gemini SSE format
└── OllamaProvider (ollama.py)
```

## Data Flow

### Benchmark execution

```
POST /api/benchmarks
  → _repair_stuck_benchmarks()   (mark stalled runs as failed)
  → create Benchmark row (status=running)
  → asyncio.gather(run_one() for each model)
    → get_provider() → inject BYOK key → check cache → provider.generate()
    → SSE stream parsing → ProviderResponse → BenchmarkResult row
  → update Benchmark status (completed/failed)
  → return BenchmarkOut with results
```

### BYOK key priority (per ADR-003)

```
per-request key  >  session-scoped key (pb_session cookie)  >  server key (.env)
```

### OpenRouter model refresh (startup)

```
lifespan:
  init_db() → _run_alembic_migrations() → _verify_expected_columns()
  → _repair_stuck_benchmarks()
  → refresh_openrouter_free_models()
    → fetch API → filter free models → clear + extend OPENROUTER_FREE_MODELS
    → rebuild_openrouter_pricing()    (PRICING["openrouter"] ← live free + paid constant)
    → invalidate_provider_cache()     (/api/providers sees updated list)
  → get_cache() (init Redis or in-memory)
  → ready
```

### Migration startup (ADR-009)

```
init_db()           → create_all (no-op if tables exist)
_run_alembic_migrations()
  → alembic current  → if no alembic_version table: stamp baseline (one-time)
  → alembic upgrade head → apply pending migrations (0002: cache columns)
_verify_expected_columns()
  → inspector.get_columns("benchmark_results")
  → WARNING if cache columns missing (catches silent migration failures)
```

## Frontend (`frontend/src/`)

```
pages/          5 route-level components (React.lazy + Suspense)
  BenchmarkRun.tsx      → create + run benchmarks
  BenchmarkResults.tsx  → view benchmark results (cache badges, comparison card)
  History.tsx           → paginated benchmark list
  CompareRuns.tsx       → side-by-side benchmark comparison
  Insights.tsx          → charts + analytics
components/
  ui/                   → shadcn/ui components
  ErrorBoundary.tsx     → React error boundary
hooks/
  useMediaQuery.ts      → responsive breakpoint hook
lib/
  api.ts                → API client (React Query hooks)
  utils.ts              → cn() classname utility
```

## Key Abstractions

| Abstraction | File | Purpose |
|-------------|------|---------|
| `BaseProvider` | `providers/base.py` | ABC defining `generate()`, `get_models()`, `is_configured` |
| `OpenAICompatibleProvider` | `providers/common.py` | Shared SSE parsing for OpenAI-compatible APIs |
| `_BYOKTestBase` | `tests/test_providers.py` | Shared transport/patcher/mock helpers for BYOK wire-level tests |
| `normalize_db_url()` | `db_utils.py` | Shared URL normalization (PostgreSQL driver) — zero app imports |
| `response_cache_key()` | `cache/response_cache.py` | Deterministic cache key from provider/model/prompt/params/version |
| `get_response_cache()` | `cache/` | Redis or in-memory cache backend (ADR-004 stampede prevention) |
| `SessionKeyStore` | `session_keys.py` | In-memory session-scoped BYOK key store (30-min TTL) |
