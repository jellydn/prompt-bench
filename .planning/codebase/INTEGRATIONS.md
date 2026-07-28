# Integrations

## External AI Provider APIs

All provider calls go through `httpx.AsyncClient` with SSE streaming. Each provider is a class in `backend/app/providers/`.

| Provider | File | Auth Method | Base URL | BYOK |
|----------|------|------------|----------|------|
| OpenAI | `openai.py` | `Authorization: Bearer` header | `https://api.openai.com/v1/chat/completions` | ✓ |
| Anthropic | `anthropic.py` | `x-api-key` header | `https://api.anthropic.com/v1/messages` | ✓ |
| Google Gemini | `gemini.py` | `?key=` URL query param | `https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent` | ✓ |
| OpenRouter | `openrouter.py` | `Authorization: Bearer` header | `https://openrouter.ai/api/v1/chat/completions` | ✓ |
| Ollama | `ollama.py` | None (local) | `http://localhost:11434/api/chat` | ✗ |
| vLLM | `vllm.py` | None (local) | `http://localhost:8001/v1/chat/completions` | ✗ |

### Provider Architecture

**Base class** (`base.py`): `BaseProvider(ABC)` — abstract `generate()`, abstract `is_configured` property, default `get_models()` reading from `PRICING`. All providers set `model_names: dict[str, str]` mapping model IDs to display names.

**Shared base** (`common.py`): `OpenAICompatibleProvider(BaseProvider)` — used by OpenAI, OpenRouter, and vLLM. Implements `generate()` with standard OpenAI-style SSE parsing (delta chunks with `stream_options.include_usage`). Subclasses only set `base_url`, `model_names`, and `api_key`.

**Custom implementations**: Anthropic and Gemini have their own `generate()` methods due to different API protocols (Anthropic uses `content_block_delta` events with `message_start`/`message_delta` framing; Gemini uses URL-embedded keys and `candidates` array parsing). Ollama uses JSON-lines streaming without SSE envelopes.

### OpenRouter Free Model Refresh

`model_lists.py` fetches `https://openrouter.ai/api/v1/models` at startup (TTL: 1 hour) to discover free models (`pricing.prompt == 0 && pricing.completion == 0`). The result replaces `OPENROUTER_FREE_MODELS` in-place and invalidates the provider cache. Static fallback list is used if the API call fails.

### Pricing

`pricing.py` contains a static `PRICING` dict with per-1K-token costs for all models across all providers. `calculate_cost(provider, model, input_tokens, output_tokens)` returns `tokens / 1000 * price` with a default of `{"input": 0.0, "output": 0.0}` for unknown models — it never KeyError's.

OpenRouter paid models are priced at pass-through rates matching the underlying provider. Free models get `$0` pricing.

## Database

**PostgreSQL 16** in production (Fly.io with Supabase). **SQLite 3** for local development and tests.

Connection: `SQLAlchemy 2.0` with `psycopg v3` driver. PostgreSQL URLs are normalized: `postgres://` → `postgresql+psycopg://` (handles Fly.io's `postgres://` format).

Connection pooling (`QueuePool`): `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`. SQLite uses `NullPool`.

Schema managed by Alembic with two migrations:
1. `2dae871076fe` — initial schema (benchmarks + benchmark_results)
2. `0002_add_cache_metrics` — cache columns (idempotent, per-column batch_alter_table with OperationalError fallback)

Startup: `init_db()` (SQLAlchemy `create_all`) → `_run_alembic_migrations()` (stamp baseline → upgrade head). The dual approach handles both fresh DBs (create_all) and existing create_all DBs needing ALTER TABLE.

## Cache Layer

`backend/app/cache/` — response and embedding caches:

| Backend | When Used | Configuration |
|---------|-----------|---------------|
| Redis | `REDIS_URL` env var is set | Default in Docker Compose |
| In-Memory | `REDIS_URL` is empty/Redis unreachable | Default in local dev |

**Response cache** (`response_cache.py`): Caches `ProviderResponse` objects keyed by provider + model + prompt + temperature + max_tokens + system_prompt + seed + response_format + benchmark_config_version. TTL: 30 minutes (configurable).

**Embedding cache** (`embedding_cache.py`): Caches embedding vectors keyed by provider + model + text. TTL: 24 hours.

**BYOK guard**: Cache is disabled when client BYOK keys are active (`use_cache = benchmark_req.cache and not client_key` in `benchmarks.py:run_one()`). This prevents cross-user leakage (ADR-007).

**Stampede prevention**: `_KeyLockRegistry` provides per-key `asyncio.Lock` — N concurrent requests for the same key trigger only 1 provider call, the other N-1 wait and re-check the cache (ADR-004).

**API**: `GET /api/cache/stats`, `DELETE /api/cache` (clear all), CLI: `promptbench cache stats|clear|warm`.

## BYOK (Bring Your Own Key)

Users can supply their own API keys from the browser. Two phases:

**Phase 1 — Per-request keys** (`client_keys` in `CreateBenchmark`): Keys are injected into a shallow-copied provider instance before `generate()`. Never persisted, never logged.

**Phase 2 — Session-scoped keys** (`backend/app/session_keys.py`): `POST /api/session-key` stores keys in an in-memory `SessionKeyStore` with 30-minute inactivity TTL. Session ID is tracked via `pb_session` HttpOnly cookie. Keys are returned via `GET /api/session-key` (provider IDs only, never the keys themselves).

Privacy invariants (ADR-003): keys never logged, provider error messages sanitized (`_sanitize_error` regex in `benchmarks.py`), keys excluded from cache/DB, `type="password"` on the frontend, never in localStorage.

## Rate Limiting

`slowapi` middleware using `get_remote_address`:
- Global: 60 requests/minute
- `POST /api/benchmarks`: 10/minute

## Fly.io Production

`fly.toml`: single machine (`shared-cpu-1x`, 1024 MB) in `sin` region. HTTPS forced. Dockerfile at `backend/Dockerfile` (multi-stage: builds frontend, then serves via FastAPI + static files). Deploy via `.github/workflows/deploy.yml` (triggers on push to main + manual `workflow_dispatch`).

## CI/CD

`.github/workflows/ci.yml`: runs on push/PR to main. Backend: ruff + pytest. Frontend: tsc + eslint. `.github/workflows/deploy.yml`: `flyctl deploy` on push to main.
