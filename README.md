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
