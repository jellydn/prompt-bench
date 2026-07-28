<h1 align="center">Welcome to PromptBench 👋</h1>

<p align="center">
  <a href="https://github.com/jellydn/prompt-bench">
    <img alt="GitHub stars" src="https://img.shields.io/github/stars/jellydn/prompt-bench" />
  </a>
  <a href="https://github.com/jellydn/prompt-bench/blob/main/LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg" />
  </a>
  <a href="https://twitter.com/jellydn">
    <img alt="Twitter: jellydn" src="https://img.shields.io/twitter/follow/jellydn.svg?style=social" />
  </a>
</p>

<p align="center">
  Open-source benchmarking tool for comparing AI prompts and models by cost, latency, token usage, and output quality.
</p>

[![IT Man - How I Built PromptBench: Open-Source AI Benchmarking Tool with React & FastAPI](https://i.ytimg.com/vi/hzSKeI4tMPk/hqdefault.jpg)](https://www.youtube.com/watch?v=hzSKeI4tMPk)

## Features

- **Benchmark Execution** — Run the same prompt against multiple AI models simultaneously
- **Prompt Comparison** — Compare prompt variants for cost, speed, and quality
- **Performance Metrics** — Input/output tokens, TTFT, total latency, estimated cost, response length
- **Benchmark History** — Store and review previous runs
- **Cost Insights** — Identify the most expensive prompt, fastest model, lowest-cost model, and best cost/performance ratio

## Supported Providers

OpenAI · Anthropic · Google Gemini · OpenRouter · Ollama · vLLM

> **Don't have API keys?** Use [OpenRouter's free models](#testing-with-openrouter-free-models) — zero-cost inference, no credit card required.
>
> **Have your own keys?** See [Bring Your Own Key](#bring-your-own-key-byok) — enter your keys directly in the browser. They are never stored, never logged, and cleared when you close the tab.

## Bring Your Own Key (BYOK)

You can benchmark against OpenAI, Anthropic, Gemini, or OpenRouter by entering your own API key directly in the browser — no server-side configuration needed.

### How it works

1. Open the Run Benchmark page
2. Find a provider card marked "API key not set"
3. Enter your key in the password input (eye icon toggles visibility)
4. Select models and run your benchmark as usual

Your key is sent with that single benchmark request and immediately discarded. It is **never**:

- Stored in a database
- Written to a log file
- Saved to localStorage or sessionStorage
- Included in error messages returned to the browser
- Shared between concurrent requests

### Privacy

| Invariant | How |
|---|---|
| Keys never persisted | Transient Python attribute, no ORM column |
| Keys never cached | BYOK results skip the response cache |
| Keys never logged | Only the provider name is logged at debug level |
| Keys never in errors | Provider error messages are sanitized before returning |
| Keys never in browser storage | React `useState` only — cleared on tab close |

### Provider-specific notes

- **Gemini**: The Gemini API passes the key as a URL query parameter. This means it may appear in Google's server access logs — a limitation of the Gemini API itself, not PromptBench. BYOK is still fully supported, but be aware of this provider behavior.
- **Ollama / vLLM**: Local providers are always "Configured" and do not show a BYOK input — they don't use API keys.

### API

Include `client_keys` in your `POST /api/benchmarks` request:

```json
{
  "prompt": "Explain quantum computing",
  "models": [{"provider": "openai", "model": "gpt-4o-mini"}],
  "client_keys": {
    "openai": "sk-proj-..."
  }
}
```

The `client_keys` field is optional, scoped per-provider, and honored only for the providers you specify. Providers not listed in `client_keys` fall back to server-configured keys.

## Tech Stack

| Layer    | Technologies                                                      |
| -------- | ----------------------------------------------------------------- |
| Frontend | React 19, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Recharts |
| Backend  | FastAPI, PostgreSQL (or SQLite), SQLAlchemy, psycopg v3           |

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
```

Frontend: http://localhost:5173 · Backend API: http://localhost:8000/docs

### Manual (uv + npm)

#### Backend

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
cd backend
cp .env.example .env       # add your API keys
uv sync                    # install dependencies
uv run uvicorn app.main:app --reload --port 8000
```

All Python tooling goes through `uv run` (ruff, pytest, alembic, etc.).

#### Frontend

Requires Node 22+.

```bash
cd frontend
npm install
npm run dev
```

### Common tasks

```bash
# Install just if needed: brew install just
just lint       # ruff + eslint
just format     # ruff format + prettier
just clean      # remove all build artifacts
cd backend && uv run --extra dev pytest  # run tests
```

### Environment Variables

```bash
cd backend
cp .env.example .env
# Then edit .env with your API keys
```

### Caching

PromptBench caches LLM responses and embeddings to speed up repeated benchmark
runs and eliminate provider cost for cached results. Redis is the primary
backend with an automatic in-memory fallback when Redis is unavailable.

```bash
# backend/.env
REDIS_URL=redis://localhost:6379/0   # leave empty for in-memory cache
CACHE_TTL_RESPONSE=1800              # 30 min (seconds)
CACHE_TTL_EMBEDDING=86400            # 24 h (seconds)
```

CLI:

```bash
promptbench cache stats              # show entries, hit rate, memory, latency
promptbench cache clear              # flush all entries
promptbench cache warm bench.yaml    # pre-populate the cache
```

See [docs/caching.md](docs/caching.md) for the full architecture, cache key
design, TTL strategy, and invalidation rules.

## Testing with OpenRouter Free Models

PromptBench ships with a curated set of OpenRouter **free models** (zero-cost inference) so you can benchmark end-to-end without spending anything.

- **Free model collection:** https://openrouter.ai/collections/free-models
- **Get an API key:** https://openrouter.ai/keys — OpenRouter keys start with `sk-or-v1-`. (A key starting with `sk-proj-` is an **OpenAI** key and will be rejected with `401 Unauthorized`.)
- Free model IDs generally end in `:free`. PromptBench also exposes `openrouter/free`, a router that picks an available free model automatically.

### Example

```bash
curl -X POST http://localhost:8000/api/benchmarks -H 'Content-Type: application/json' -d '{
  "prompt": "Reply with exactly: PromptBench test passed",
  "system_prompt": "Follow the output format exactly.",
  "temperature": 0,
  "max_tokens": 40,
  "models": [{"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}]
}'
```

### Available free models

| Model ID                                             | Notes                                |
| ---------------------------------------------------- | ------------------------------------ |
| `openrouter/free`                                    | Auto-selects an available free model |
| `google/gemma-4-31b-it:free`                         | General-purpose, 31B dense           |
| `google/gemma-4-26b-a4b-it:free`                     | 26B MoE, efficient                   |
| `nvidia/nemotron-3-ultra-550b-a55b:free`             | Large reasoning MoE                  |
| `nvidia/nemotron-3-super-120b-a12b:free`             | Hybrid MoE                           |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Multimodal nano                      |
| `cohere/north-mini-code:free`                        | Agentic coding, 30B MoE              |
| `poolside/laguna-s-2.1:free`                         | Coding agent                         |
| `poolside/laguna-xs-2.1:free`                        | Small coding agent                   |
| `poolside/laguna-m.1:free`                           | Flagship coding agent                |
| `inclusionai/ling-3.0-flash:free`                    | 124B MoE, token-efficient            |

## API Overview

| Method | Endpoint               | Description                 |
| ------ | ---------------------- | --------------------------- |
| GET    | `/api/providers`       | List providers and models   |
| POST   | `/api/benchmarks`      | Run a benchmark (supports `client_keys` for BYOK) |
| GET    | `/api/benchmarks`      | List benchmark history      |
| GET    | `/api/benchmarks/{id}` | Get a single benchmark      |
| DELETE | `/api/benchmarks/{id}` | Delete a benchmark          |
| GET    | `/api/insights`        | Cost & performance insights |

## Author

👤 **Dung Huynh**

- Website: https://productsway.com/
- Twitter: [@jellydn](https://twitter.com/jellydn)
- Github: [@jellydn](https://github.com/jellydn)

## Show your support

Give a ⭐️ if this project helped you!

[![kofi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/dunghd)
[![paypal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/dunghd)
[![buymeacoffee](https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/dunghd)

## License

MIT — see [LICENSE](LICENSE) for details.
