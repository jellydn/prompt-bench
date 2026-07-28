# Architecture

## System Design

PromptBench is a **monorepo** with two deployable units sharing TypeScript/Python source:

```
Browser (React SPA) ←→ FastAPI (REST JSON) ←→ PostgreSQL + Redis
                              ↓
                    External AI Provider APIs
                    (OpenAI, Anthropic, Gemini,
                     OpenRouter, Ollama, vLLM)
```

The frontend is a static SPA served by the same FastAPI process in production (Docker multi-stage builds frontend into `backend/static/`). In development, Vite's dev server proxies `/api` to `localhost:8000`.

## Backend Architecture

### Layer Diagram

```
┌─────────────────────────────────────────────────┐
│ Routers (benchmarks, insights, providers,       │
│          cache, session_keys)                   │
│  - FastAPI route handlers                       │
│  - Request validation (Pydantic schemas)         │
│  - Dependency injection (get_db, limiter)        │
├─────────────────────────────────────────────────┤
│ Services / Domain Logic                          │
│  - run_one() — benchmark execution orchestrator  │
│  - response_cache.get_or_compute()              │
│  - provider.generate() — API calls               │
│  - SessionKeyStore — in-memory session keys      │
├─────────────────────────────────────────────────┤
│ Data Access (SQLAlchemy ORM)                    │
│  - models.py — Benchmark, BenchmarkResult        │
│  - Session = Depends(get_db)                    │
│  - Alembic migrations                           │
├─────────────────────────────────────────────────┤
│ Infrastructure                                   │
│  - config.py — Pydantic Settings                 │
│  - database.py — engine, sessionmaker            │
│  - limiter.py — slowapi rate limiter             │
│  - cache/ — Redis + in-memory backends          │
└─────────────────────────────────────────────────┘
```

### Request Flow: Run Benchmark

```
POST /api/benchmarks
  → create_benchmark (benchmarks.py)
    → inject pb_session cookie → payload._session_id
    → _repair_stuck_benchmarks(db)
    → INSERT Benchmark (status='running')
    → asyncio.gather(run_one() for each model)
      → get_provider(provider_id)
      → inject BYOK key (per-request > session > server)
      → compute response_cache_key()
      → response_cache.get_or_compute(key, _compute, cacheable=use_cache)
        → if cache hit: return serialized ProviderResponse
        → if cache miss: async with _semaphore → provider.generate()
          → httpx.AsyncClient.stream(POST, provider.base_url, ...)
          → parse SSE events → ProviderResponse
      → return (item, result, error, cache_info)
    → INSERT BenchmarkResult for each outcome
    → UPDATE Benchmark.status → 'completed' or 'failed'
    → return BenchmarkOut with selectinload(results)
  ← 200 JSON
```

### Request Flow: History Page

```
GET /api/benchmarks?limit=20&offset=0
  → history() (benchmarks.py)
    → SELECT benchmarks ORDER BY created_at DESC LIMIT 20
    → selectinload(Benchmark.results) — loads all result rows
    → aggregate per benchmark:
      - total_cost = sum(cost for non-cache-hits)
      - total_tokens = sum(input + output)
      - avg_latency_ms = mean(latencies)
    → return list[BenchmarkSummary]
  ← 200 JSON
```

### Request Flow: Insights

```
GET /api/insights
  → insights() (insights.py)
    → SELECT recent benchmark IDs (LIMIT 50)
    → SQL-level aggregation via sqlalchemy.func:
      - most_expensive_prompt: SUM(cost) GROUP BY benchmark_id
      - fastest_model: AVG(total_latency_ms) GROUP BY (provider, model)
      - lowest_cost_model: AVG(cost) GROUP BY (provider, model)
      - best_cost_performance: computed score = 1/(avg_cost * avg_latency)
    → No application-level loops — all in SQL
  ← 200 JSON
```

### Provider Pattern (ADR-002)

All providers extend `BaseProvider(ABC)` which defines:
- `async generate(prompt, model, ...) → ProviderResponse` — abstract
- `get_models() → list[ModelInfo]` — default implementation reading `PRICING`
- `is_configured` — abstract property

Six providers registered in `PROVIDERS` dict (keyed by `provider_id`):
1. `OpenAIProvider(OpenAICompatibleProvider)` — OpenAI API
2. `AnthropicProvider(BaseProvider)` — Anthropic API (custom SSE)
3. `GeminiProvider(BaseProvider)` — Google Gemini API (custom SSE, URL auth)
4. `OpenRouterProvider(OpenAICompatibleProvider)` — OpenRouter aggregation
5. `OllamaProvider(BaseProvider)` — Local Ollama (always configured)
6. `VLLMProvider(OpenAICompatibleProvider)` — Local vLLM

`OpenAICompatibleProvider` is a shared base for providers using the standard OpenAI SSE format (delta chunks with optional usage). It implements `generate()` with `stream_options: {include_usage: true}`.

Provider info is cached via `get_providers_cached()` (TTL: 5 minutes). The `model_lists.refresh_openrouter_free_models()` call at startup invalidates this cache.

### BYOK Key Injection (ADR-003)

In `run_one()`:
1. Check `benchmark_req.client_keys` (per-request JSON body)
2. Fall back to `SessionKeyStore.get_keys()` (session cookie)
3. If key found: `copy.copy(provider)` → set `_client_api_key`
4. The `copy.copy()` prevents mutating the global singleton

Key priority: per-request > session > server-configured.

### Cache Architecture (ADR-005, ADR-007)

**Response cache**: `ResponseCache.get_or_compute(key, compute_fn, cacheable)` — if `cacheable=False`, always calls the provider. Used for BYOK requests (ADR-007 prevents cross-user leakage).

**Stampede prevention** (ADR-004): `_KeyLockRegistry` is an `asyncio.Lock` per cache key. First waiter acquires lock and calls the provider; subsequent waiters re-check the cache after release.

**Cache key** (ADR-005): Includes provider, model, prompt_template, rendered_prompt, system_prompt, temperature, max_tokens, seed, response_format, and benchmark_config_version. Deterministic JSON serialization before SHA-256 hashing.

**Cache metrics**: `CacheInfo` dataclass with `cache_hit`, `cache_type`, `cache_lookup_ms`, `provider_latency_ms`, `total_latency_ms`. On cache hits, `provider_latency_ms` preserves the original run's time (not zero) so the frontend can compute speedup.

## Frontend Architecture

### Component Tree

```
App
├── Sidebar (desktop) / Header (mobile hamburger)
│   ├── Run Benchmark (/)
│   ├── Compare (/compare)
│   ├── History (/history)
│   └── Insights (/insights)
├── Bottom Tab Bar (mobile only)
└── Routes
    ├── BenchmarkRun
    │   ├── Card: Prompt input (textarea + sliders)
    │   └── Card: Model selection (per-provider with BYOK inputs)
    ├── BenchmarkResults
    │   ├── Summary (prompt, params)
    │   ├── Results Table (latency/cost/tokens per model)
    │   ├── Tab: Model Responses
    │   ├── Charts (Recharts bar/pie)
    │   └── BenchmarkCacheSection
    │       ├── Cache Badge (per result)
    │       ├── Performance comparison table
    │       ├── Summary cards (latency reduction, cost avoided)
    │       └── Latency breakdown chart
    ├── CompareRuns
    │   ├── Run ID inputs
    │   └── Side-by-side comparison table (speedup, cost avoided)
    ├── History
    │   └── Table (date, prompt, models, cost, tokens, latency)
    └── Insights
        └── Cards (expensive prompt, fastest model, cheapest, best)
```

### State Management

React Query (`@tanstack/react-query`) handles all server state:
- `useQuery` for providers list, history, insights, session keys, cache stats
- `useMutation` for create benchmark, delete benchmark, save session key
- Query keys: `["providers"]`, `["history", offset]`, `["insights"]`, etc.

Local React state (`useState`) for:
- Form inputs (prompt, temperature, max_tokens, selected models)
- BYOK key inputs (per-provider, never persisted)
- Dark mode toggle (persisted in localStorage)
- Mobile menu open/close
- Pagination offset

### Routing

React Router v7 with 5 routes:
| Path | Component | Lazy Loaded |
|------|-----------|-------------|
| `/` | `BenchmarkRun` | ✓ |
| `/results/:id` | `BenchmarkResults` | ✓ |
| `/compare` | `CompareRuns` | ✓ |
| `/history` | `History` | ✓ |
| `/insights` | `Insights` | ✓ |

All pages are lazy-loaded with `React.lazy()` + `<Suspense>`.

### Theme

Dark/light mode via CSS custom properties (`--background`, `--foreground`, `--primary`, etc.) in `index.css`. Toggled by `.dark` class on `<html>`. Persisted in `localStorage("theme")`. shadcn/ui components use these CSS variables.

### Component Library

shadcn/ui components in `components/ui/`: button, card, badge, table, tabs, select, slider, separator, textarea, input, label. All use Tailwind CSS with `cn()` utility for class merging (`clsx` + `tailwind-merge`).

Custom components: `ErrorBoundary`, `BenchmarkCacheSection` (with exported `CacheBadge`).
