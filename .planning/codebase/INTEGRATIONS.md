# External Integrations

**Analysis Date:** 2026-07-26

## APIs & External Services

**LLM Providers (all called via HTTP/REST with streaming):**

- **OpenAI** — Chat completions via `/v1/chat/completions`
  - SDK/Client: `httpx.AsyncClient` (Python), native `fetch` (frontend)
  - Auth: `OPENAI_API_KEY` (env var `openai_api_key`)
  - Base URL: `https://api.openai.com/v1/chat/completions`
  - Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo

- **Anthropic** — Messages API with SSE streaming
  - SDK/Client: `httpx.AsyncClient` (Python)
  - Auth: `ANTHROPIC_API_KEY` (env var `anthropic_api_key`)
  - Base URL: `https://api.anthropic.com/v1/messages`
  - Headers: `x-api-key`, `anthropic-version: 2023-06-01`
  - Models: claude-3-5-sonnet, claude-3-5-haiku, claude-3-opus

- **Google Gemini** — Generative Language API
  - SDK/Client: `httpx.AsyncClient` (Python)
  - Auth: API key passed as query param (`key=settings.gemini_api_key`)
  - Base URL: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
  - Models: gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash-exp

- **OpenRouter** — Unified LLM gateway (OpenAI-compatible)
  - SDK/Client: `httpx.AsyncClient` via `OpenAICompatibleProvider` base class
  - Auth: `OPENROUTER_API_KEY` (env var `openrouter_api_key`) — keys starting with `sk-or-v1-`
  - Base URL: `https://openrouter.ai/api/v1/chat/completions`
  - Attribution headers: `HTTP-Referer`, `X-Title`
  - 11 free models (`:free` suffix) + 4 paid models
  - Free models: gemma-4-31b-it, gemma-4-26b-a4b-it, nemotron-3 variants,
    north-mini-code, laguna variants, ling-3.0-flash, openrouter/free

**Local LLM Servers (self-hosted, no API key required):**

- **Ollama** — Local LLM inference server
  - SDK/Client: `httpx.AsyncClient`
  - Auth: None (local only)
  - Base URL: configurable via `OLLAMA_BASE_URL` (default `http://localhost:11434`)
  - Endpoint: `/api/chat` (OpenAI-compatible chat format)
  - Models: llama3.1, mistral, qwen2.5, phi3

- **vLLM** — High-throughput LLM serving
  - SDK/Client: `httpx.AsyncClient` via `OpenAICompatibleProvider`
  - Auth: None
  - Base URL: configurable via `VLLM_BASE_URL` (default `http://localhost:8001`)
  - Endpoint: `/v1/chat/completions` (OpenAI-compatible)
  - Models: Meta-Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3

## Data Storage

**Databases:**

- **PostgreSQL 16** — Primary production database (Docker Compose)
  - Connection: `postgresql://promptbench:promptbench@postgres:5432/promptbench`
  - Env var: `DATABASE_URL`
  - Client/ORM: SQLAlchemy 2.0.36 (async not used; sync sessionmaker with `get_db` dependency)
  - Image: `postgres:16-alpine`

- **SQLite** — Default development database
  - Connection: `sqlite:///./promptbench.db` (file-based, local)
  - Same SQLAlchemy ORM, different `connect_args` (`check_same_thread=False`)
  - File: `backend/promptbench.db` (gitignored)

**File Storage:** Local filesystem only (no S3 or object storage).

**Caching:**

- **Redis 7** (optional, via `REDIS_URL` env var, Docker Compose)
  - Image: `redis:7-alpine`
  - Port: 6379
  - Currently imported as `aiocache` dependency but not actively wired into provider logic

## Authentication & Identity

**Auth Provider:** Custom API-key-based (no OAuth, no session auth, no user accounts).

Each LLM provider requires its own API key stored in environment variables:

- `OPENAI_API_KEY` — OpenAI API key
- `ANTHROPIC_API_KEY` — Anthropic API key
- `GEMINI_API_KEY` — Google Gemini API key
- `OPENROUTER_API_KEY` — OpenRouter API key (format `sk-or-v1-`)

No user-facing authentication or authorization layer exists in the application.

## Monitoring & Observability

**Error Tracking:** None (no Sentry, Datadog, or similar service integrated).

**Logs:** Console/stdout via `uvicorn` logging. FastAPI health endpoint at `/` returns `{"status": "ok"}`.

**Metrics:** No Prometheus, Grafana, or APM integration.

## CI/CD & Deployment

**Hosting:** Docker-based deployment only (no cloud platform specified, no Kubernetes config).

**CI Pipeline:** None present (no `.github/workflows/`, no CI config files).

**Deployment:** `docker compose up --build` for full stack; individual `Dockerfile` files for each service:

- Backend: `python:3.12-slim` → `pip install -r requirements.txt` → `uvicorn`
- Frontend: `node:22-alpine` → `npm install` → `npm run dev`

## Environment Configuration

**Required env vars:**

- `DATABASE_URL` — PostgreSQL or SQLite connection string
- `REDIS_URL` — Redis connection string (optional)
- `OPENAI_API_KEY` — OpenAI API key
- `ANTHROPIC_API_KEY` — Anthropic API key
- `GEMINI_API_KEY` — Google Gemini API key
- `OPENROUTER_API_KEY` — OpenRouter API key
- `OLLAMA_BASE_URL` — Ollama server URL (default `http://localhost:11434`)
- `VLLM_BASE_URL` — vLLM server URL (default `http://localhost:8001`)
- `CORS_ORIGINS` — Comma-separated list of allowed origins (default `http://localhost:5173`)
- `VITE_API_URL` — Frontend API proxy target (default `http://localhost:8000`)

**Secrets location:** `.env` file in the `backend/` directory (gitignored, `python-dotenv` loads it). No encrypted secret store or vault configured.

## Webhooks & Callbacks

**Incoming:** None (no webhook endpoints configured in the API).

**Outgoing:** None (the application does not call external webhooks or send notifications to third parties).

---

_Integration audit: 2026-07-26_
