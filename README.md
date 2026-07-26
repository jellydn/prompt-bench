# PromptBench

Open-source benchmarking tool for comparing AI prompts and models by cost, latency, token usage, and output quality.

## Features

- **Benchmark Execution** — Run the same prompt against multiple AI models simultaneously
- **Prompt Comparison** — Compare prompt variants for cost, speed, and quality
- **Performance Metrics** — Input/output tokens, TTFT, total latency, estimated cost, response length
- **Benchmark History** — Store and review previous runs
- **Cost Insights** — Identify the most expensive prompt, fastest model, lowest-cost model, and best cost/performance ratio

## Supported Providers

OpenAI · Anthropic · Google Gemini · OpenRouter · Ollama · vLLM

## Tech Stack

| Layer    | Technologies                                      |
|----------|---------------------------------------------------|
| Frontend | React, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Recharts |
| Backend  | FastAPI, PostgreSQL, SQLAlchemy, Redis (optional)  |

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
```

Frontend: http://localhost:5173 · Backend API: http://localhost:8000/docs

### Manual

#### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

Copy `backend/.env.example` to `backend/.env` and add your API keys:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
```

Ollama and vLLM run locally and need no API key — just set the base URL.

> **Never commit `backend/.env`.** It is gitignored. Run `chmod 600 backend/.env` for extra safety.

## Testing with OpenRouter Free Models

PromptBench ships with a curated set of OpenRouter **free models** (zero-cost
inference) so you can benchmark end-to-end without spending anything.

- **Free model collection:** https://openrouter.ai/collections/free-models
- **Get an API key:** https://openrouter.ai/keys — OpenRouter keys start with
  `sk-or-v1-`. (A key starting with `sk-proj-` is an **OpenAI** key and will be
  rejected by OpenRouter with `401 Unauthorized`.)
- Set `OPENROUTER_API_KEY=sk-or-v1-...` in `backend/.env`, then restart the
  backend.
- Free model IDs generally end in `:free` (for example
  `google/gemma-4-31b-it:free`). PromptBench also exposes `openrouter/free`, a
  router that picks an available free model automatically.
- Estimated cost is **$0** for free models, but free models are subject to
  OpenRouter rate limits and provider availability, which can change at any
  time.

### Example: benchmark a free model via curl

```bash
curl -X POST http://localhost:8000/api/benchmarks -H 'Content-Type: application/json' -d '{
  "prompt": "Reply with exactly: PromptBench test passed",
  "system_prompt": "Follow the output format exactly.",
  "temperature": 0,
  "max_tokens": 40,
  "models": [{"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}]
}'
```

### Available free models (curated)

| Model ID | Notes |
|----------|-------|
| `openrouter/free` | Auto-selects an available free model |
| `google/gemma-4-31b-it:free` | General-purpose, 31B dense |
| `google/gemma-4-26b-a4b-it:free` | 26B MoE, efficient |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Large reasoning MoE |
| `nvidia/nemotron-3-super-120b-a12b:free` | Hybrid MoE |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Multimodal nano |
| `cohere/north-mini-code:free` | Agentic coding, 30B MoE |
| `poolside/laguna-s-2.1:free` | Coding agent |
| `poolside/laguna-xs-2.1:free` | Small coding agent |
| `poolside/laguna-m.1:free` | Flagship coding agent |
| `inclusionai/ling-3.0-flash:free` | 124B MoE, token-efficient |

OpenRouter recommends sending attribution headers (`HTTP-Referer`, `X-Title`);
PromptBench sends them automatically on every OpenRouter request.

## API Overview

| Method | Endpoint                | Description              |
|--------|-------------------------|--------------------------|
| GET    | `/api/providers`        | List providers and models|
| POST   | `/api/benchmarks`       | Run a benchmark          |
| GET    | `/api/benchmarks`       | List benchmark history   |
| GET    | `/api/benchmarks/{id}`  | Get a single benchmark   |
| DELETE | `/api/benchmarks/{id}`  | Delete a benchmark       |
| GET    | `/api/insights`         | Cost & performance insights |

## License

MIT
