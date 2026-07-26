# PromptBench Development Environment Setup - Complete ✓

**Date:** July 26, 2026  
**Environment:** Cloud Agent VM

## Setup Summary

The PromptBench development environment has been successfully configured and is fully operational. Both backend and frontend services are running and communicating correctly.

## Installation Details

### Tools Installed
- **uv** v0.11.32 - Python package manager
- **Node.js** v22.14.0 - JavaScript runtime
- **npm** v10.9.7 - Node package manager
- **Python** v3.12.3 - Backend runtime

### Backend Setup
- **Location:** `/workspace/backend`
- **Dependencies:** Installed via `uv sync` (33 packages)
- **Database:** SQLite (`promptbench.db`) - 16KB, 2 tables created
- **Configuration:** `.env` file created from `.env.example`
- **Port:** 8000
- **Status:** ✓ Running in tmux session `backend-server`

### Frontend Setup
- **Location:** `/workspace/frontend`
- **Dependencies:** Installed via `npm install` (258 packages)
- **Port:** 5173
- **Proxy:** Configured to proxy `/api` requests to `http://localhost:8000`
- **Status:** ✓ Running in tmux session `frontend-server`

## Service Status

### Active Services

```
backend-server:  tmux session (created Jul 26 10:08:10 2026)
frontend-server: tmux session (created Jul 26 10:08:46 2026)
```

### Running Processes

```
uvicorn app.main:app --reload --port 8000  (PID 3824)
vite --host 0.0.0.0 --port 5173           (PID 4287)
```

## Verification Tests

### 1. Backend API Endpoints ✓

**Providers Endpoint:**
```bash
curl http://localhost:8000/api/providers
```
**Result:** Returns 6 providers (OpenAI, Anthropic, Gemini, OpenRouter, Ollama, vLLM) with 18 OpenRouter free models loaded

**Benchmarks Endpoint:**
```bash
curl http://localhost:8000/api/benchmarks
```
**Result:** Returns benchmark history (1 test benchmark created)

**Insights Endpoint:**
```bash
curl http://localhost:8000/api/insights
```
**Result:** Returns analytics data structure

**API Documentation:**
- Swagger UI: http://localhost:8000/docs ✓
- OpenAPI Schema: http://localhost:8000/openapi.json ✓

### 2. Frontend Service ✓

**Home Page:**
```bash
curl http://localhost:5173
```
**Result:** Returns PromptBench HTML with React app initialization

**API Proxy:**
```bash
curl http://localhost:5173/api/providers
```
**Result:** Successfully proxies to backend and returns provider data ✓

### 3. Database ✓

**File:** `/workspace/backend/promptbench.db` (16KB)
**Tables:**
- `benchmarks`
- `benchmark_results`

**Sample Data:** 1 benchmark record created and persisted

## Access URLs

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **API Schema:** http://localhost:8000/openapi.json

## Supported Providers

| Provider | Status | Models Available | API Key Required |
|----------|--------|------------------|------------------|
| OpenAI | Configured | 4 models | Yes (not set) |
| Anthropic | Configured | 3 models | Yes (not set) |
| Google Gemini | Configured | 3 models | Yes (not set) |
| OpenRouter | Configured | 18 free models | Yes (not set) |
| Ollama | Configured | 4 models | No (local) |
| vLLM | Configured | 2 models | No (local) |

### OpenRouter Free Models (Available)
- `openrouter/free` - Auto-selects available free model
- `google/gemma-4-31b-it:free`
- `google/gemma-4-26b-a4b-it:free`
- `nvidia/nemotron-3-ultra-550b-a55b:free`
- `nvidia/nemotron-3-super-120b-a12b:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `cohere/north-mini-code:free`
- `poolside/laguna-s-2.1:free`
- `poolside/laguna-xs-2.1:free`
- `poolside/laguna-m.1:free`
- `inclusionai/ling-3.0-flash:free`
- Plus 7 additional paid models

## Development Workflow

### Managing Services

**View backend logs:**
```bash
tmux attach -t backend-server
```

**View frontend logs:**
```bash
tmux attach -t frontend-server
```

**Detach from tmux:** Press `Ctrl+B` then `D`

**List sessions:**
```bash
tmux list-sessions
```

### Testing the API

**Run a benchmark (requires API key):**
```bash
curl -X POST http://localhost:8000/api/benchmarks \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Reply with exactly: PromptBench test passed",
    "system_prompt": "Follow the output format exactly.",
    "temperature": 0,
    "max_tokens": 40,
    "models": [
      {"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}
    ]
  }'
```

### Adding API Keys

Edit `/workspace/backend/.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-v1-...
```

The backend will automatically reload when the `.env` file is modified.

## Technology Stack

### Frontend
- React 19
- Vite (build tool)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- TanStack Query (data fetching)
- Recharts (visualization)

### Backend
- FastAPI (Python web framework)
- SQLAlchemy 2.0 (ORM)
- SQLite (development database)
- uvicorn (ASGI server)
- Pydantic (data validation)
- httpx (HTTP client)
- SlowAPI (rate limiting)

## Next Steps

To fully test the application with real AI providers:

1. **Get API Keys:**
   - OpenRouter (free models): https://openrouter.ai/keys
   - OpenAI: https://platform.openai.com/api-keys
   - Anthropic: https://console.anthropic.com/
   - Google Gemini: https://aistudio.google.com/app/apikey

2. **Add keys to backend/.env**

3. **Run benchmarks** through the frontend UI at http://localhost:5173

4. **View results** in the History and Insights pages

## Troubleshooting

### Check service status
```bash
tmux list-sessions
ps aux | grep -E "(uvicorn|vite)"
```

### Check backend health
```bash
curl http://localhost:8000/api/providers
```

### Check frontend health
```bash
curl http://localhost:5173
```

### Restart services
```bash
# Kill and restart backend
tmux kill-session -t backend-server
tmux new-session -d -s backend-server -c /workspace/backend
tmux send-keys -t backend-server:0.0 'export PATH="$HOME/.local/bin:$PATH" && uv run uvicorn app.main:app --reload --port 8000' C-m

# Kill and restart frontend
tmux kill-session -t frontend-server
tmux new-session -d -s frontend-server -c /workspace/frontend
tmux send-keys -t frontend-server:0.0 'npm run dev' C-m
```

## Environment Variables

All environment variables are defined in `/workspace/backend/.env`:

```env
# Database (defaults to SQLite)
DATABASE_URL=sqlite:///./promptbench.db

# AI Provider API Keys
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=

# Local Providers
OLLAMA_BASE_URL=http://localhost:11434
VLLM_BASE_URL=http://localhost:8001
```

## Summary

✓ Backend API running on port 8000  
✓ Frontend UI running on port 5173  
✓ Database initialized with schema  
✓ All endpoints responding correctly  
✓ API proxy working between frontend and backend  
✓ 18 OpenRouter free models available  
✓ API documentation accessible  

**The PromptBench development environment is fully operational and ready for use.**
