# Technology Stack

**Analysis Date:** 2026-07-26

## Languages

**Primary:**

- Python 3.12 - Backend server, API logic, ORM models, pricing engine
- TypeScript 5.7.2 - Frontend application (React SPA)

**Secondary:**

- JavaScript (ES2020) - Frontend build tooling, Vite config
- YAML - Docker Compose orchestration
- TOML - Pre-commit hook configuration

## Runtime

**Environment:**

- Node.js 22 (frontend Docker: `node:22-alpine`)
- Python 3.12 (backend Docker: `python:3.12-slim`)

**Package Manager:**

- npm (frontend) — lockfile: `package-lock.json` (3,222 lines)
- pip (backend) — requirements file: `requirements.txt`

## Frameworks

**Core:**

- FastAPI 0.115.6 — Python async web framework, REST API server
- React 18.3.1 — Frontend component library
- Vite 6.0.7 — Frontend build tool and dev server
- SQLAlchemy 2.0.36 — Python ORM (SQLite in dev, PostgreSQL in production)
- Pydantic 2.10.4 — Data validation and settings management
- Pydantic Settings 2.7.0 — Environment-based configuration (`BaseSettings`)

**UI Components (shadcn/ui):**

- Custom `components/ui/` directory: badge, button, card, input, label,
  select, separator, slider, table, tabs, textarea
- Styled with Tailwind CSS utility classes

**Frontend Libraries:**

- @tanstack/react-query 5.62.0 — Server state management and caching
- recharts 2.15.0 — Chart rendering (bar charts for latency, cost, tokens)
- lucide-react 0.468.0 — Icon library
- clsx 2.1.1 + tailwind-merge 2.6.0 + class-variance-authority 0.7.1 —
  CSS class composition utilities

**Testing:**

- No test framework configured (no pytest files, no CI workflows)

**Build/Dev:**

- PostCSS 8.4.49 + Autoprefixer 10.4.20 — CSS processing
- Tailwind CSS 3.4.17 — Utility-first CSS framework
- ESLint (frontend, configured via `eslint .` script)
- Prettier (frontend, via `npx prettier`)
- Ruff (backend, via `ruff check` / `ruff format`)
- Pre-commit hooks (prek.toml) — check-yaml, end-of-file-fixer,
  trailing-whitespace, check-added-large-files, ruff-format, ruff-lint,
  prettier-frontend

## Key Dependencies

**Critical:**

- `httpx` 0.28.1 — Async HTTP client for calling LLM provider APIs and streaming responses
- `fastapi` 0.115.6 — Core API framework with async lifespan context manager
- `sqlalchemy` 2.0.36 — ORM with `DeclarativeBase`, sessionmaker, and SQLite/PostgreSQL support
- `pydantic` 2.10.4 — Request/response schema validation (`BaseModel`, `field_validator`)
- `uvicorn` 0.34.0 — ASGI server (`uvicorn app.main:app`)
- `aiocache` 0.12.3 — Async caching layer

**Infrastructure:**

- `psycopg2-binary` 2.9.10 — PostgreSQL adapter (used in Docker with Postgres)
- `python-dotenv` 1.0.1 — Loads `.env` file into environment variables

## Configuration

**Environment:**

- Backend config: `backend/app/config.py` — `Settings` class using `pydantic_settings.BaseSettings` loaded from `.env` file
- Frontend config: `VITE_API_URL` env var in Docker Compose, proxied via Vite dev server
- Docker Compose env vars: `DATABASE_URL`, `REDIS_URL`, `VITE_API_URL`, `CORS_ORIGINS`

**Build:**

- Frontend build: `tsc -b && vite build` (TypeScript compile then Vite bundle)
- Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Docker: `docker compose up --build` (builds frontend and backend images)

**Linting/Formatting:**

- Pre-commit (prek.toml) runs ruff, prettier, and yaml checks automatically

## Platform Requirements

**Development:**

- Docker + Docker Compose (recommended, spins up full stack)
- Or standalone: Node.js 22 + Python 3.12 + pip + npm
- PostgreSQL 16 and Redis 7 (optional, for non-Docker dev)

**Production:**

- Docker containers: `python:3.12-slim` (backend), `node:22-alpine` (frontend)
- PostgreSQL 16 (via `postgres:16-alpine` image)
- Redis 7 (via `redis:7-alpine` image)
- Deployment target: Docker-based, no cloud platform specified

---

_Stack analysis: 2026-07-26_
