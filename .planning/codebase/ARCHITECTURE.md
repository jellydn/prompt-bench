# Architecture

**Analysis Date:** 2026-07-26

## Pattern Overview

**Overall:** Monorepo with a two-tier client-server architecture (React SPA + FastAPI backend) using the Provider pattern for AI model access.

**Key Characteristics:**

- Monorepo split into `frontend/` (React/Vite/TypeScript) and `backend/` (FastAPI/Python/SQLAlchemy)
- Provider abstraction layer: each AI provider implements a common interface, enabling pluggable model backends
- RESTful JSON APIs with no authentication layer; API keys are server-side secrets
- Single-page application with client-side routing and server-side data fetching via TanStack Query
- SQLAlchemy ORM with SQLite (default/dev) and PostgreSQL (Docker/production) via a single config switch

## Layers

**Frontend Presentation Layer:**

- Location: `frontend/src/`
- Contains: React components, page views, UI primitives (shadcn/ui), state hooks, API client
- Depends on: Vite dev server proxy, TanStack Query, Recharts, Tailwind CSS
- Used by: end users via browser at `localhost:5173`

**Backend API Layer:**

- Location: `backend/app/routers/`
- Contains: FastAPI `APIRouter` instances for benchmarks, providers, and insights
- Depends on: `backend/app/providers/`, `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/database.py`
- Used by: frontend and direct API consumers (curl, etc.)

**Provider Abstraction Layer:**

- Location: `backend/app/providers/`
- Contains: `BaseProvider` ABC, `OpenAICompatibleProvider` shared mixin, six concrete provider implementations
- Depends on: `backend/app/config.py`, `backend/app/pricing.py`, `backend/app/providers/base.py`
- Used by: `backend/app/routers/benchmarks.py` (via `get_provider()`)

**Data Persistence Layer:**

- Location: `backend/app/database.py`, `backend/app/models.py`
- Contains: SQLAlchemy `DeclarativeBase`, engine, session maker, two ORM models (`Benchmark`, `BenchmarkResult`)
- Depends on: `backend/app/config.py` (for `DATABASE_URL`)
- Used by: all routers via `get_db()` dependency injection

**Configuration Layer:**

- Location: `backend/app/config.py`
- Contains: Pydantic `Settings` class loaded from `.env` file
- Used by: every backend module that needs settings (providers, database, config)

## Data Flow

**Benchmark Execution Flow:**

1. User submits a prompt + model selections in the frontend (`BenchmarkRun.tsx`)
2. Frontend POSTs to `/api/benchmarks` with `CreateBenchmark` JSON payload
3. FastAPI router in `benchmarks.py` deserializes the request via `BenchmarkCreate` Pydantic schema
4. A new `Benchmark` ORM row is inserted with status `"running"`
5. `asyncio.gather()` concurrently dispatches `run_one()` for each selected model
6. Each `run_one()` resolves the provider via `get_provider()`, checks `is_configured`, then calls `provider.generate()`
7. Each provider streams the AI response, tallies tokens/latency/cost, and returns a `ProviderResponse`
8. Results are batch-committed as `BenchmarkResult` rows linked to the benchmark
9. The updated `Benchmark` (with eager-loaded results) is returned to the frontend
10. Frontend navigates to the results page, fetching individual results via `/api/benchmarks/{id}`

**Cost Calculation Flow:**

1. Each provider calls `calculate_cost(provider_id, model, input_tokens, output_tokens)` from `backend/app/pricing.py`
2. The `PRICING` dict maps `(provider, model)` to `{input: $/1k, output: $/1k}` rates
3. Cost = `(input_tokens / 1000) * input_price + (output_tokens / 1000) * output_price`
4. Providers without pricing data (Ollama, vLLM, free models) return `0.0`

**Insights Flow:**

1. Frontend fetches `/api/insights`
2. Backend queries all benchmarks and benchmark results from the database
3. Computes aggregates: most expensive prompt, fastest model, lowest-cost model, best cost/performance
4. Returns a summary JSON object to the frontend

**Provider Registration Flow:**

1. `backend/app/providers/__init__.py` imports all six provider classes and builds the `PROVIDERS` dict keyed by `provider_id`
2. `get_provider(provider_id)` does a dict lookup at runtime
3. Adding a new provider means: writing the class, importing it in `__init__.py`, and adding it to the `PROVIDERS` dict

## Key Abstractions

**BaseProvider (ABC):**

- Purpose: Defines the contract every AI provider must fulfill
- Examples: `backend/app/providers/base.py`
- Pattern: Abstract base class with three abstract members — `generate()` (async), `get_models()`, `is_configured` (property)

**OpenAICompatibleProvider:**

- Purpose: Shared implementation for all OpenAI-compatible providers (OpenAI, OpenRouter, vLLM)
- Examples: `backend/app/providers/common.py`, `backend/app/providers/openai.py`, `backend/app/providers/openrouter.py`, `backend/app/providers/vllm.py`
- Pattern: Inherits `BaseProvider`, implements streaming HTTP(SSE) logic once, subclasses only set config fields (`api_key`, `base_url`, `model_names`)

**ModelInfo (dataclass):**

- Purpose: Lightweight value object describing an available model
- Examples: `backend/app/providers/base.py`
- Pattern: `id`, `name`, `pricing` fields

**ProviderResponse (dataclass):**

- Purpose: Standardized return value from any provider's `generate()` call
- Examples: `backend/app/providers/base.py`
- Pattern: `input_tokens`, `output_tokens`, `ttft_ms`, `total_latency_ms`, `response_text`, `response_length`, `cost`, `error`

## Entry Points

**Backend:**

- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app` or `docker compose up`
- Responsibilities: Creates the FastAPI app, registers lifespan context (DB init), adds CORS middleware, includes three routers under `/api` prefix, serves root health check

**Frontend:**

- Location: `frontend/src/main.tsx`
- Triggers: `npm run dev` (Vite dev server on port 5173)
- Responsibilities: Creates React root, wraps app in `QueryClientProvider`, renders `App` component

**App Shell:**

- Location: `frontend/src/App.tsx`
- Triggers: Initial render after `main.tsx` mounts
- Responsibilities: Manages page state (`run`/`history`/`insights`/`results`), renders sidebar navigation, conditionally renders page components, handles dark mode toggle

## Error Handling

**Strategy:** Mixed — exceptions from provider HTTP calls are caught in the router's `run_one()` helper and stored as error strings on `BenchmarkResult.error`. The router then sets `benchmark.status` to `"failed"` if all models errored, otherwise `"completed"`.

**Patterns:**

- Provider-level: `response.raise_for_status()` on HTTP responses; general `Exception` catch in `run_one()` that returns error string
- Schema-level: Pydantic field validators (e.g., `temperature` range `0-2`, `max_tokens > 0`, `prompt` min length 1)
- Router-level: `HTTPException(404)` for missing benchmark lookups; `selectinload` for eager loading to avoid N+1

## Cross-Cutting Concerns

**Logging:** No explicit logging framework; relies on Python/stdout and FastAPI's built-in request logging.

**Validation:** Pydantic models for request/response schemas (`schemas.py`); `field_validator` on `Settings` for CORS origin parsing; `@field_validator(mode="before")` for comma-separated CORS origins.

**Authentication:** None. The API is unauthenticated; security relies on API keys being server-side environment variables (never exposed to the frontend). This is appropriate for a local/dev benchmarking tool.

---

_Architecture analysis: 2026-07-26_
