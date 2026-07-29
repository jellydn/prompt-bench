# AGENTS.md

## Project Overview

PromptBench — open-source benchmarking tool comparing AI prompts/models by cost, latency, token usage, and quality. Monorepo with a React/Vite/TypeScript frontend and a FastAPI/Python/SQLAlchemy backend.

## Repo Structure

| Path                 | Role                                                  |
| -------------------- | ----------------------------------------------------- |
| `frontend/`          | React SPA (Vite + React Query + Recharts + shadcn/ui) |
| `backend/`           | FastAPI app (SQLAlchemy ORM, PostgreSQL or SQLite)    |
| `docker-compose.yml` | Full stack: postgres, redis, backend, frontend        |
| `docs/caching.md`    | Cache architecture, key design, TTL, invalidation     |

## Key Commands

### Docker (recommended)

```bash
docker compose up --build
```

Services: frontend `localhost:5173`, backend API `localhost:8000`, postgres `localhost:5432`, redis `localhost:6379`.

### Frontend

```bash
cd frontend && npm install && npm run dev
```

- Build: `npm run build` (runs `tsc -b && vite build` — TS compile is a required pre-step)
- The Vite dev server proxies `/api` to `http://localhost:8000` (configured in `vite.config.ts`)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Copy `backend/.env.example` → `backend/.env` and add API keys before starting
- **Never commit `backend/.env`** — it is gitignored

## Architecture Notes

- **Database**: SQLite by default (`sqlite:///./promptbench.db`); PostgreSQL used in Docker (`postgresql://promptbench:promptbench@postgres:5432/promptbench`). Switching requires changing `DATABASE_URL` in `.env` and re-creating tables.
- **Providers**: Registered in `backend/app/providers/__init__.py` as a dict keyed by `provider_id`. Adding a new provider means adding an entry there.
- **CORS**: Defaults to `http://localhost:5173` only (set in `backend/app/config.py` `cors_origins`).
- **OpenRouter free models**: API keys start with `sk-or-v1-` (NOT `sk-proj-`). Free model IDs end in `:free` (e.g. `google/gemma-4-31b-it:free`). Using an OpenAI key (`sk-proj-`) with OpenRouter returns 401.
- **Backend lifespan**: `init_db()` is called on app startup via FastAPI `lifespan` context manager; tables are created with `Base.metadata.create_all`.
- **Cache layer**: `backend/app/cache/` provides response + embedding caching. Redis is the primary backend (`REDIS_URL`); when Redis is unavailable it falls back to an in-memory cache without crashing. Response TTL defaults to 30 min, embedding TTL to 24 h. See `docs/caching.md`.

## Deployment (Dokku)

- **Host:** `dokku@docklight.itman.fyi` · **App:** `prompt-bench` · **Domain:** `https://prompt-bench.itman.fyi`
- **Build:** Dokku builds `backend/Dockerfile` with the repo root as context. Two server commands are required **before the first push** (Dokku auto-detects Herokuish since there's no root `Dockerfile`, and fails with `Unable to select a buildpack`): `dokku builder:set prompt-bench selected dockerfile` + `dokku builder-dockerfile:set prompt-bench dockerfile-path backend/Dockerfile`. The image bundles the compiled frontend into `/app/static`; FastAPI serves it (single origin). `EXPOSE 8000`.
- **Deploy:** `git push dokku main` (remote `dokku dokku@docklight.itman.fyi:prompt-bench`). CI auto-deploys on push to `main` via `.github/workflows/deploy.yml` (secret `DOKKU_SSH_KEY`).
- **Persistence:** SQLite on a Dokku storage mount at `/app/data/promptbench.db` (`DATABASE_URL=sqlite:////app/data/promptbench.db`); without it the DB is wiped on redeploy.
- **Prod env:** `ENABLE_LOCAL_PROVIDERS=false` (hide Ollama/vLLM); provider API keys via `dokku config:set`. Redis/Postgres optional via Dokku plugins.
- See [DEPLOY_DOKKU.md](DEPLOY_DOKKU.md) for the full runbook.

## Testing

No test framework is configured. There are no pytest files, CI workflows, or pre-commit hooks in this repo.

## Existing Instruction Files

- `.amp/services.yaml` — Amp dev-environment service definitions (paths use `/home/user/workspace/repo/` prefix, not this repo's actual path)
- `README.md` — Primary documentation; always prefer executable sources (`package.json` scripts, `docker-compose.yml`, `vite.config.ts`) over prose when they conflict
