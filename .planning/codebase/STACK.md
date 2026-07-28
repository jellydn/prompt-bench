# Stack

## Backend

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| Web framework | FastAPI | ≥0.115.0 |
| ASGI server | Uvicorn (standard) | ≥0.34.0 |
| ORM | SQLAlchemy | ≥2.0.0 |
| Migrations | Alembic | ≥1.14.0 (in main deps since PR #11) |
| PostgreSQL driver | psycopg (binary) | ≥3.2.0 |
| Validation | Pydantic + pydantic-settings | ≥2.10.0 / ≥2.7.0 |
| HTTP client | httpx | ≥0.28.0 |
| Rate limiting | slowapi | ≥0.1.9 |
| Caching | Redis | ≥5.0.0 (with in-memory fallback) |
| Config | python-dotenv + pyyaml | ≥1.0.0 / ≥6.0.0 |
| Package manager | uv | latest |
| Linter/formatter | ruff | ≥0.8.0 (dev) |
| Testing | pytest + pytest-asyncio + fakeredis | ≥8.0.0 / ≥0.25.0 / ≥2.0.0 (dev) |

### Key config files

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Dependencies, ruff config, pytest config, build system |
| `backend/uv.lock` | Locked dependency tree |
| `backend/alembic.ini` | Alembic migration config |
| `backend/alembic/env.py` | Migration environment (URL normalization, online/offline modes) |
| `backend/alembic/versions/` | Migration scripts (2 migrations: initial schema + cache columns) |

## Frontend

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | TypeScript | ES2022 target |
| UI library | React | 19 |
| Build tool | Vite | 6.x |
| CSS framework | Tailwind CSS | 4.x |
| Component library | shadcn/ui | latest |
| Charts | Recharts | latest |
| Data fetching | React Query (TanStack) | latest |
| Package manager | npm | latest |
| Linter | ESLint (typescript-eslint) | latest |
| Type checking | tsc (strict mode) | latest |

### Key config files

| File | Purpose |
|------|---------|
| `frontend/package.json` | Dependencies and scripts |
| `frontend/vite.config.ts` | Vite config (dev proxy to :8000) |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/tailwind.config.js` | Tailwind config |
| `frontend/postcss.config.js` | PostCSS config |
| `frontend/eslint.config.js` | ESLint config |

## Infrastructure

| Layer | Technology |
|-------|-----------|
| Container build | Docker (multi-stage) |
| Orchestration (local) | Docker Compose (postgres, redis, backend, frontend) |
| Deployment | Fly.io |
| Build optimizer | `.dockerignore` (excludes 340 MB of deps/artifacts, context ~2 MB) |
| CI | GitHub Actions (ci.yml, deploy.yml) |
