# PromptBench - Quick Start Guide

The development environment is **already running**! Follow this guide to interact with the application.

## 🌐 Access Points

| Service | URL | Status |
|---------|-----|--------|
| Frontend UI | http://localhost:5173 | ✓ Running |
| Backend API | http://localhost:8000 | ✓ Running |
| API Docs | http://localhost:8000/docs | ✓ Running |
| OpenAPI Schema | http://localhost:8000/openapi.json | ✓ Running |

## 🔌 Test the API

### 1. List Available Providers
```bash
curl http://localhost:8000/api/providers
```

### 2. View Benchmark History
```bash
curl http://localhost:8000/api/benchmarks
```

### 3. Get Insights
```bash
curl http://localhost:8000/api/insights
```

### 4. Create a Benchmark (requires API key)
```bash
curl -X POST http://localhost:8000/api/benchmarks \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Write a haiku about coding",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "max_tokens": 100,
    "models": [
      {"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}
    ]
  }'
```

## 📱 Frontend Pages

Open http://localhost:5173 in your browser to access:

1. **Run Benchmark** - Main page to configure and run benchmarks
   - Select providers and models
   - Configure prompt parameters
   - Execute benchmarks

2. **History** - View past benchmark runs
   - See all executed benchmarks
   - Compare results
   - Delete old benchmarks

3. **Insights** - Analytics dashboard
   - Most expensive prompts
   - Fastest models
   - Best cost/performance ratio

## 🔑 Adding API Keys

**Option 1 — Server-side (.env):**

```bash
# Edit the .env file
nano /workspace/backend/.env

# Add your keys:
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-v1-...
```

The backend automatically reloads when you save the file!

**Option 2 — Browser (BYOK):** Open http://localhost:5173 and enter your key directly in the provider card on the Run Benchmark page. Your key is never stored — it stays in memory for that single request and is cleared when you close the tab. See the [BYOK section](README.md#bring-your-own-key-byok) in the README for privacy details.

### Get API Keys
- **OpenRouter** (free models): https://openrouter.ai/keys
- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/
- **Google Gemini**: https://aistudio.google.com/app/apikey

## 🔧 Managing Services

### View Logs

**Backend logs:**
```bash
tmux attach -t backend-server
# Detach: Ctrl+B, then D
```

**Frontend logs:**
```bash
tmux attach -t frontend-server
# Detach: Ctrl+B, then D
```

### Check Service Status
```bash
# List tmux sessions
tmux list-sessions

# Check processes
ps aux | grep -E "(uvicorn|vite)"

# Test endpoints
curl http://localhost:8000/api/providers
curl http://localhost:5173
```

### Restart Services

If you need to restart:

**Backend:**
```bash
tmux kill-session -t backend-server
cd /workspace/backend
tmux new-session -d -s backend-server
tmux send-keys -t backend-server:0.0 \
  'export PATH="$HOME/.local/bin:$PATH" && uv run uvicorn app.main:app --reload --port 8000' C-m
```

**Frontend:**
```bash
tmux kill-session -t frontend-server
cd /workspace/frontend
tmux new-session -d -s frontend-server
tmux send-keys -t frontend-server:0.0 'npm run dev' C-m
```

## 💾 Database Access

The SQLite database is located at `/workspace/backend/promptbench.db`

**Query the database:**
```bash
cd /workspace/backend
export PATH="$HOME/.local/bin:$PATH"

# Run Python with database access
uv run python3 << 'EOF'
from app.database import SessionLocal
from app.models import Benchmark, BenchmarkResult

with SessionLocal() as db:
    benchmarks = db.query(Benchmark).all()
    print(f"Total benchmarks: {len(benchmarks)}")
    for b in benchmarks:
        print(f"  - ID {b.id}: {b.prompt[:50]}...")
EOF
```

## ⚡ Caching — run twice, pay once

PromptBench caches responses automatically. Run the same benchmark twice and
the second run is served from cache with **$0 cost and 0ms provider latency**.

```bash
# First run — cache MISS (provider is called)
curl -X POST http://localhost:8000/api/benchmarks \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Say hello","temperature":0.7,"max_tokens":200,"models":[{"provider":"ollama","model":"qwen2.5:0.5b"}]}'

# Second run — cache HIT (identical request, served instantly)
curl -X POST http://localhost:8000/api/benchmarks \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Say hello","temperature":0.7,"max_tokens":200,"models":[{"provider":"ollama","model":"qwen2.5:0.5b"}]}'

# Check cache stats
curl http://localhost:8000/api/cache/stats | python3 -m json.tool
```

In the UI, look for the **Cache hit** badge and the **Cache performance**
card showing provider vs cache lookup latency side-by-side.

See [docs/caching.md](docs/caching.md) for architecture, invalidation rules,
and Redis configuration.

## 🧪 Example Benchmark Workflow

### 1. Check available providers
```bash
curl -s http://localhost:8000/api/providers | python3 -m json.tool
```

### 2. Add an API key (e.g., OpenRouter)
```bash
echo 'OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE' >> /workspace/backend/.env
```

Wait 2-3 seconds for the backend to reload.

### 3. Run a benchmark
```bash
curl -X POST http://localhost:8000/api/benchmarks \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "What is 2+2?",
    "temperature": 0,
    "max_tokens": 50,
    "models": [
      {"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}
    ]
  }' | python3 -m json.tool
```

### 4. View results
```bash
# Get benchmark ID from previous response, then:
curl http://localhost:8000/api/benchmarks/1 | python3 -m json.tool
```

### 5. Check insights
```bash
curl http://localhost:8000/api/insights | python3 -m json.tool
```

## 🌟 OpenRouter Free Models

No credit card required! These models are completely free:

```json
{
  "free_models": [
    "openrouter/free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "cohere/north-mini-code:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "poolside/laguna-m.1:free",
    "inclusionai/ling-3.0-flash:free"
  ]
}
```

Just sign up at https://openrouter.ai/keys and add your API key!

## 📚 Additional Resources

- **Full documentation:** See `/workspace/SETUP_COMPLETE.md`
- **Demo output:** See `/workspace/DEMO_OUTPUT.md`
- **Main README:** See `/workspace/README.md`
- **Architecture:** See `/workspace/AGENTS.md`

## 🐛 Troubleshooting

### Backend not responding
```bash
# Check if running
curl http://localhost:8000/api/providers

# View logs
tmux attach -t backend-server

# Check for errors in the last 50 lines
tmux capture-pane -t backend-server:0.0 -p | tail -50
```

### Frontend not loading
```bash
# Check if running
curl http://localhost:5173

# View logs
tmux attach -t frontend-server

# Check for errors
tmux capture-pane -t frontend-server:0.0 -p | tail -50
```

### API key not working
```bash
# Verify the .env file
cat /workspace/backend/.env

# Check backend logs for reload message
tmux capture-pane -t backend-server:0.0 -p | grep -i "reload"

# Test provider configuration
curl http://localhost:8000/api/providers | grep -i "configured"
```

## ✅ Everything Working?

You should see:
- ✅ Backend responds at port 8000
- ✅ Frontend serves UI at port 5173
- ✅ API docs available at /docs
- ✅ Database contains tables
- ✅ Free models loaded (18 OpenRouter models)

**Ready to benchmark prompts!** 🚀
