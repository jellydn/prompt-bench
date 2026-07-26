# Ideas Backlog — All Addressed ✓

All codebase concerns from `.planning/codebase/CONCERNS.md` are resolved.
All high-impact technical improvements from the ideas backlog are implemented.

## Remaining (Product-level features — out of scope)
- Full auth/user isolation
- TLS termination (nginx/Caddy/traefik)
- Result export (CSV/JSON)
- Prompt templates/save-reuse
- Side-by-side comparison view
- Scheduling/automated runs

## Remaining (Infrastructure)
- Pre-commit CI pipeline (GitHub Actions)
- Alembic database migration infrastructure

## Implemented
- ✅ Python toolchain: uv + pyproject.toml + ruff
- ✅ Dead deps removed (aiocache, redis_url)
- ✅ Gemini streaming (client.stream + alt=sse)
- ✅ Empty results crash fix
- ✅ Model list dedup + OpenRouter API refresh
- ✅ API keys at call time
- ✅ response_length → response_chars
- ✅ Input validation (max_length)
- ✅ Settings lru_cache removed
- ✅ Ollama response warnings
- ✅ Claude input_tokens robustness
- ✅ Rate limiting (slowapi)
- ✅ Concurrency cap (semaphore + max_length)
- ✅ Insights pagination + SQL-level aggregation
- ✅ Stuck benchmark recovery (startup + POST)
- ✅ React ErrorBoundary
- ✅ Provider JSON try/except validation
- ✅ CORS restrictions
- ✅ requires_api_key removed from providers endpoint
- ✅ Docker secrets via env vars + .env.example
- ✅ Connection pooling (NullPool/QueuePool + pre_ping)
- ✅ SQLite dev-only warning
- ✅ psycopg2-binary → psycopg[binary] v3
- ✅ React 19 + Node 24 + code splitting (662KB→256KB)
- ✅ Ruff as dev dep + justfile uv run
- ✅ 27 pytest tests + checks.sh CI gates
- ✅ Draft PR created
