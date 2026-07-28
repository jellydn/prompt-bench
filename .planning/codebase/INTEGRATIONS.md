# Integrations

## AI Model Providers

| Provider | Provider ID | Auth Method | Transport | Files |
|----------|------------|-------------|-----------|-------|
| OpenAI | `openai` | `Authorization: Bearer` header | OpenAI SSE (delta chunks + usage) | `openai.py`, `common.py` |
| Anthropic | `anthropic` | `x-api-key` header | Custom SSE (content_block_delta) | `anthropic.py` |
| Google Gemini | `gemini` | `?key=` URL query param | Custom SSE (candidates/parts) | `gemini.py` |
| OpenRouter | `openrouter` | `Authorization: Bearer` header | OpenAI SSE (same as OpenAI) | `openrouter.py`, `common.py` |
| Ollama (local) | `ollama` | None | JSON streaming (one JSON per line) | `ollama.py` |
| vLLM (local) | `vllm` | None | OpenAI SSE (same as OpenAI) | `vllm.py`, `common.py` |

### Provider pattern (ADR-002)

All providers extend `BaseProvider(ABC)`:
- `async generate(prompt, model, system_prompt, temperature, max_tokens) → ProviderResponse`
- `get_models() → list[ModelInfo]` — default implementation reads `PRICING[self.provider_id]` with `.get()` fallback for safety
- `is_configured` property — checks server API key or BYOK key

`OpenAICompatibleProvider` is a shared base for OpenAI, OpenRouter, and vLLM — implements SSE streaming once.

### BYOK (Bring Your Own Key) — ADR-003

Two-phase architecture:
- **Phase 1 (per-request)**: `client_keys: dict[str, str]` in `CreateBenchmark` body. Keys injected via `provider._client_api_key`, never persisted.
- **Phase 2 (session-scoped)**: `SessionKeyStore` with cookie-based session, 30-min inactive TTL. `POST /api/session-key`, `DELETE /api/session-key`, `GET /api/session-key/providers`.

Key priority: per-request > session > server-configured.

### Model lists (July 2026)

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini, o3, o4-mini |
| Anthropic | claude-sonnet-5, claude-opus-5, claude-fable-5, claude-haiku-4-5 |
| Gemini | gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite, gemini-3.5-flash, gemini-3.6-flash |
| OpenRouter | 11 free (refreshed at startup) + 7 paid (static) |
| Ollama | llama3.1, mistral, qwen2.5, phi3 |
| vLLM | Meta-Llama-3.1-8B, Mistral-7B |

Model lists are shared via `model_lists.py` (single source of truth for both providers and pricing). OpenRouter free models refresh from the API at startup (1-hour TTL).

## Databases

| Database | Role | Connection |
|----------|------|-----------|
| PostgreSQL | Primary (production, Docker) | `DATABASE_URL` env var, psycopg v3 driver |
| SQLite | Development fallback | `sqlite:///./promptbench.db` |
| Redis | Cache backend (optional) | `REDIS_URL` env var; falls back to in-memory |

**URL normalization**: `db_utils.normalize_db_url()` handles `postgres://` → `postgresql+psycopg://` for Fly.io compatibility.

## Cache Layer

| Component | Backend | TTL |
|-----------|---------|-----|
| Response cache | Redis / in-memory | 24 hours |
| Embedding cache | Redis / in-memory | 7 days |
| Provider info cache | In-memory (lru_cache) | 5 minutes |

**Stampede prevention** (ADR-004): `_KeyLockRegistry` — per-key `asyncio.Lock` prevents concurrent identical provider calls.

**BYOK isolation** (ADR-007): Cache disabled when BYOK keys are active to prevent cross-user leakage.

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| Global | 60/min (slowapi) |
| POST /api/benchmarks | 10/min |

## GitHub Integrations

| Service | Purpose |
|---------|---------|
| GitHub Actions CI | Backend tests (ruff + pytest), frontend (tsc + vitest) |
| CodeRabbit | AI code review on PRs |
| GitGuardian | Secret scanning |
| Socket | Supply chain security |
| Fly.io deploy | Auto-deploy on push to main |

## Session Keys

`SessionKeyStore` — in-memory session-scoped BYOK keys. Single process only (not shared across Uvicorn workers). Cookie `pb_session` tracks session identity. 30-minute inactivity TTL.
