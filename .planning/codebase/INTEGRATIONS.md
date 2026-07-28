# Integrations

## AI Model Providers

| Provider | File | Auth method | BYOK support |
|----------|------|-------------|-------------|
| OpenAI | `providers/openai.py` | Bearer token (Authorization header) | ✅ (Authorization header override) |
| Anthropic | `providers/anthropic.py` | x-api-key header | ✅ (x-api-key header override) |
| Google Gemini | `providers/gemini.py` | URL query param (?key=...) | ✅ (URL param override) |
| OpenRouter | `providers/openrouter.py` | Bearer token | ✅ (inherits from OpenAICompatibleProvider) |
| Ollama | `providers/ollama.py` | None (local) | N/A |
| vLLM | `providers/vllm.py` | Optional API key | ✅ |

### OpenRouter dynamic model refresh

`refresh_openrouter_free_models()` fetches the live model list from `https://openrouter.ai/api/v1/models` on startup (1-hour TTL). After each refresh:

1. `OPENROUTER_FREE_MODELS` is updated in-place
2. `rebuild_openrouter_pricing()` regenerates `PRICING["openrouter"]` from live free models + `_OPENROUTER_PAID_PRICING` constant
3. `invalidate_provider_cache()` ensures `/api/providers` returns updated models

Both deferred imports in `model_lists.py` break the circular import chain (`base.py → pricing.py → model_lists.py → providers/__init__.py`).

### BYOK architecture

Three-tier priority per ADR-003:
1. **Per-request key**: `benchmark_req.client_keys[provider]`
2. **Session-scoped key**: `GET /api/session-key` stores in `SessionKeyStore` (in-memory, 30-min TTL), injected via `pb_session` HttpOnly cookie
3. **Server-configured key**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. in `.env`

BYOK disables the response cache (ADR-007) to prevent cross-user response leakage.

## Database

| Environment | URL | Driver |
|-------------|-----|--------|
| Local (SQLite) | `sqlite:///./promptbench.db` | sqlite3 |
| Docker Compose | `postgresql://promptbench:promptbench@postgres:5432/promptbench` | psycopg v3 |
| Fly.io | PostgreSQL (Fly Postgres) | psycopg v3 |

URL normalization: `db_utils.normalize_db_url()` converts `postgres://` → `postgresql+psycopg://` (ADR-008). Used by both `database.py` (FastAPI) and `env.py` (Alembic).

### Migrations

| Migration | Description |
|-----------|-------------|
| `2dae871076fe` | Initial schema (benchmarks + benchmark_results) |
| `0002_cache_metrics` | Cache columns (cache_hit, cache_type, cache_lookup_ms, provider_latency_ms) — idempotent via inspector |

Migrations run at startup via `alembic upgrade head` (ADR-009). Alembic is in main dependencies (moved from dev in PR #11 — was causing production 500 when missing).

### Startup health check

`_verify_expected_columns()` (added in PR #12) checks that all 4 cache columns exist on `benchmark_results` after migrations. Logs WARNING if missing with remediation steps. Best-effort, never blocks startup.

## Caching

| Backend | Driver | Fallback |
|---------|--------|----------|
| Redis | redis-py ≥5.0.0 | In-memory dict (`_InMemoryCache`) |

- Response cache keys include: provider, model, prompt, system_prompt, temperature, max_tokens, benchmark_config_version
- Embedding cache keys include: normalized text, provider, model, dimensions, config version
- Stampede prevention via `_KeyLockRegistry` (ADR-004)
- Cache disabled when BYOK keys active (ADR-007)
- Cache failures never fail benchmarks

## External APIs

| Service | Endpoint | Purpose |
|---------|----------|---------|
| OpenRouter | `/api/v1/models` | Free model list refresh (startup, 1-hour TTL) |

## CORS

`allow_credentials=True` (needed for `pb_session` BYOK cookie). Origins from `settings.cors_origins`. Methods: GET, POST, DELETE, OPTIONS.
