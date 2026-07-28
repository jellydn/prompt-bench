# Stack

## Languages & Runtimes

| Layer | Language | Runtime |
|-------|----------|---------|
| Backend | Python 3.12+ | uvicorn 0.34+ (ASGI) |
| Frontend | TypeScript 5.7+ | Node ≥22, Vite 6, React 19 |
| Database | — | PostgreSQL 16 (prod), SQLite 3 (dev) |
| Cache | — | Redis 7 (prod), in-memory (fallback) |

## Backend — FastAPI + SQLAlchemy + Alembic

**Framework**: FastAPI ≥0.115 (ASGI web framework with automatic OpenAPI docs)

**Core dependencies** (`backend/pyproject.toml`):
| Package | Purpose |
|---------|---------|
| `fastapi>=0.115.0` | Web framework, routing, dependency injection |
| `uvicorn[standard]>=0.34.0` | ASGI server (production and dev) |
| `sqlalchemy>=2.0.0` | ORM with DeclarativeBase |
| `psycopg[binary]>=3.2.0` | PostgreSQL driver (v3 with async support) |
| `alembic>=1.14.0` | Database migration framework |
| `pydantic>=2.10.0` / `pydantic-settings>=2.7.0` | Validation + settings management |
| `httpx>=0.28.0` | Async HTTP client (provider API calls) |
| `slowapi>=0.1.9` | Rate limiting middleware |
| `redis>=5.0.0` | Redis client for response/embedding cache |
| `python-dotenv>=1.0.0` | `.env` file loading |
| `pyyaml>=6.0.0` | YAML parsing (cache warm CLI) |

**Development dependencies** (`[project.optional-dependencies] dev`):
| Package | Purpose |
|---------|---------|
| `pytest>=8.0.0` + `pytest-asyncio` + `pytest-cov` | Test framework |
| `fakeredis>=2.0.0` | Redis mock for tests |
| `ruff>=0.8.0` | Linting + formatting (replaces black/isort/flake8) |

**Package manager**: uv (lockfile at `backend/uv.lock`)

## Frontend — React 19 + Vite 6 + TypeScript

**Framework**: React 19 SPA bundled by Vite 6, written in TypeScript 5.7

**Core dependencies** (`frontend/package.json`):
| Package | Purpose |
|---------|---------|
| `react@^19.0.0` / `react-dom@^19.0.0` | UI framework |
| `react-router-dom@^7.18.1` | Client-side routing (5 routes) |
| `@tanstack/react-query@^5.62.0` | Server state management & caching |
| `recharts@^2.15.0` | Charting (latency bar charts, pie charts) |
| `lucide-react@^0.468.0` | Icon library (20+ icons used) |
| `class-variance-authority@^0.7.1` | Component variants (shadcn/ui) |
| `tailwind-merge@^2.6.0` + `clsx@^2.1.1` | CSS class merging (via `cn()` utility) |

**Dev dependencies**:
| Package | Purpose |
|---------|---------|
| `vite@^6.0.7` + `@vitejs/plugin-react` | Build tool with HMR |
| `typescript@^5.7.2` | Type checking (`tsc --noEmit` in build) |
| `tailwindcss@^3.4.17` + `postcss` + `autoprefixer` | Utility-first CSS |
| `vitest@^4.1.10` | Test runner (shares Vite config) |
| `@testing-library/react@^16.3.2` + `jest-dom` | Component testing |
| `jsdom@^30.0.0` | DOM environment for tests |
| `eslint@^10.8.0` + `typescript-eslint` | Linting |

**Package manager**: npm (lockfile at `frontend/package-lock.json`)

## Infrastructure

| Component | Local Dev | Production |
|-----------|-----------|------------|
| App server | `uvicorn --reload` | uvicorn inside `backend/Dockerfile` |
| Frontend dev | `vite --host 0.0.0.0 --port 5173` | Static build served by FastAPI |
| DB | SQLite (`sqlite:///./promptbench.db`) | PostgreSQL on Fly.io (Supabase) |
| Cache | In-memory (no Redis) | Redis via `REDIS_URL` env var |
| Reverse proxy | None (direct Vite proxy) | Fly.io edge + force_https |
| CI | `.github/workflows/ci.yml` | pytest + ruff + tsc/eslint |
| CD | `.github/workflows/deploy.yml` | `flyctl deploy` on push to main |

## Configuration

Backend settings via `backend/app/config.py` (Pydantic `BaseSettings`, reads `.env`):
- `DATABASE_URL` — defaults to SQLite, overridden for PostgreSQL
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
- `REDIS_URL` — empty = in-memory cache, set for Redis
- `CACHE_ENABLED`, `CACHE_TTL_RESPONSE` (30 min), `CACHE_TTL_EMBEDDING` (24 h)
- `OLLAMA_BASE_URL` (local), `VLLM_BASE_URL` (local)
- `CORS_ORIGINS` — `localhost:5173` + `prompt-bench.fly.dev`

Frontend config via `VITE_API_URL` env var (defaults to `""` = same-origin).

## Build Pipeline

Frontend (`tsc -b && vite build`):
1. TypeScript compilation check (`tsc -b` — required step, not optional)
2. Vite production build → `frontend/dist/`

Backend (Docker multi-stage, `backend/Dockerfile`):
1. Stage 1: Node 24 Alpine — `npm ci && npm run build` frontend
2. Stage 2: Python 3.12 Slim — `uv sync --frozen`, copy backend + frontend static
3. CMD: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
