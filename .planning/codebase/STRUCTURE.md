# Codebase Structure

**Analysis Date:** 2026-07-26

## Directory Layout

```
prompt-bench/
├── backend/                  # FastAPI Python backend
│   ├── app/                  # Application package
│   │   ├── __init__.py       # Package docstring
│   │   ├── main.py           # FastAPI app factory and entry point
│   │   ├── config.py         # Pydantic settings (env-backed)
│   │   ├── database.py       # SQLAlchemy engine, session, Base, get_db()
│   │   ├── models.py         # ORM models (Benchmark, BenchmarkResult)
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── pricing.py        # Pricing lookup table + cost calculator
│   │   ├── providers/        # AI provider implementations
│   │   │   ├── __init__.py   # Provider registry (PROVIDERS dict)
│   │   │   ├── base.py       # BaseProvider ABC + ModelInfo, ProviderResponse
│   │   │   ├── common.py     # OpenAICompatibleProvider shared mixin
│   │   │   ├── openai.py     # OpenAI concrete provider
│   │   │   ├── anthropic.py  # Anthropic concrete provider
│   │   │   ├── gemini.py     # Google Gemini concrete provider
│   │   │   ├── openrouter.py # OpenRouter concrete provider
│   │   │   ├── ollama.py     # Ollama concrete provider
│   │   │   └── vllm.py       # vLLM concrete provider
│   │   └── routers/          # FastAPI router modules
│   │       ├── __init__.py   # Docstring only
│   │       ├── benchmarks.py # CRUD + benchmark execution router
│   │       ├── providers.py  # Provider listing router
│   │       └── insights.py   # Cost/latency analytics router
│   ├── Dockerfile            # Backend container image
│   └── requirements.txt      # Python dependencies
├── frontend/                 # React TypeScript frontend
│   ├── src/                  # Source code
│   │   ├── main.tsx          # React entry point (QueryClient + App)
│   │   ├── App.tsx           # Shell component with navigation/routing
│   │   ├── lib/              # Shared utilities
│   │   │   ├── api.ts        # Fetch-based API client
│   │   │   └── utils.ts      # Formatting helpers (money, latency, tokens, cn)
│   │   ├── hooks/            # Custom React hooks
│   │   │   └── useMediaQuery.ts
│   │   ├── types/            # TypeScript type definitions
│   │   │   └── index.ts
│   │   ├── components/ui/    # shadcn/ui primitive components
│   │   └── pages/            # Route-level page components
│   │       ├── BenchmarkRun.tsx
│   │       ├── BenchmarkResults.tsx
│   │       ├── History.tsx
│   │       └── Insights.tsx
│   ├── Dockerfile            # Frontend container image
│   ├── index.html            # HTML entry point (mounts #root)
│   ├── vite.config.ts        # Vite config (proxy, alias)
│   ├── tailwind.config.js    # Tailwind CSS configuration
│   ├── postcss.config.js     # PostCSS configuration
│   ├── tsconfig.json         # TypeScript compiler config
│   └── package.json          # NPM dependencies and scripts
├── docker-compose.yml        # Full stack orchestration
├── .env                      # Environment variables (gitignored)
├── .gitignore
├── README.md
├── AGENTS.md
├── justfile                  # Task runner (dev, lint, format, clean)
└── prek.toml                 # Pre-commit hooks config
```

## Directory Purposes

**backend/app/**

- Purpose: Core backend application code — FastAPI app, database, models, providers, routers
- Contains: All Python application logic
- Key files: `main.py` (entry), `config.py` (settings), `database.py` (ORM setup), `models.py` (data models)

**backend/app/providers/**

- Purpose: Pluggable AI provider implementations following the Provider pattern
- Contains: One file per provider (OpenAI, Anthropic, Gemini, OpenRouter, Ollama, vLLM) plus shared base classes
- Key files: `base.py` (ABC + dataclasses), `common.py` (OpenAI-compatible shared logic), `__init__.py` (registry)

**backend/app/routers/**

- Purpose: FastAPI route handlers organized by domain
- Contains: Three routers — benchmarks, providers, insights
- Key files: `benchmarks.py` (136 lines, the core router), `providers.py` (23 lines), `insights.py` (65 lines)

**frontend/src/**

- Purpose: React SPA source code
- Contains: Entry point, app shell, pages, shared utilities, UI components, types
- Key files: `App.tsx` (shell/navigation), `main.tsx` (entry), `lib/api.ts` (API client)

**frontend/src/pages/**

- Purpose: Top-level page components, one per app section
- Contains: `BenchmarkRun.tsx` (184 lines), `BenchmarkResults.tsx` (220 lines), `History.tsx` (129 lines), `Insights.tsx` (118 lines)

**frontend/src/components/ui/**

- Purpose: shadcn/ui primitive components (button, card, table, tabs, etc.)
- Contains: 10 copied/modified shadcn primitives (badge, button, card, input, label, select, separator, slider, table, textarea)

**frontend/src/lib/**

- Purpose: Shared frontend utilities
- Contains: `api.ts` (fetch wrapper, 35 lines) and `utils.ts` (formatting helpers, 15 lines)

**frontend/src/types/**

- Purpose: TypeScript interface definitions mirroring backend Pydantic schemas
- Contains: `index.ts` (81 lines) with `Benchmark`, `BenchmarkResult`, `Provider`, `Insights`, `CreateBenchmark`, etc.

**frontend/src/hooks/**

- Purpose: Custom React hooks
- Contains: `useMediaQuery.ts` (13 lines) for responsive dark-mode detection

## Key File Locations

**Entry Points:**

- `backend/app/main.py`: FastAPI app creation, router mounting, lifespan (DB init)
- `frontend/src/main.tsx`: React DOM root rendering, QueryClient setup
- `frontend/src/App.tsx`: Top-level React component with page routing state
- `frontend/index.html`: HTML mount point (`<div id="root">`)

**Configuration:**

- `backend/app/config.py`: All backend settings (DB URL, API keys, CORS origins)
- `backend/app/.env.example` (not present as tracked file): Template for env vars
- `frontend/vite.config.ts`: Dev server proxy (`/api` → `http://localhost:8000`), path alias `@` → `./src`
- `docker-compose.yml`: Full stack (postgres, redis, backend, frontend)
- `backend/Dockerfile`: Python 3.12 slim image, installs requirements, runs uvicorn
- `frontend/Dockerfile`: Node 22 Alpine image, installs npm deps, runs dev server

**Core Logic:**

- `backend/app/providers/base.py`: Provider ABC and shared dataclasses (43 lines)
- `backend/app/providers/common.py`: OpenAI-compatible streaming implementation (76 lines)
- `backend/app/providers/pricing.py`: Pricing lookup table and `calculate_cost()` function (60 lines)
- `backend/app/routers/benchmarks.py`: Core benchmark execution and CRUD router (136 lines)
- `backend/app/models.py`: Two SQLAlchemy ORM models (50 lines)
- `backend/app/schemas.py`: Pydantic request/response schemas (54 lines)
- `frontend/src/lib/api.ts`: Centralized API client (35 lines)
- `frontend/src/types/index.ts`: TypeScript type interfaces (81 lines)

## Naming Conventions

**Files:**

- Python: `snake_case.py` (e.g., `main.py`, `benchmarks.py`, `openai.py`)
- TypeScript: `PascalCase.tsx` for components (e.g., `BenchmarkRun.tsx`), `camelCase.ts` for utilities (e.g., `api.ts`, `useMediaQuery.ts`)
- Config: lowercase with extensions (e.g., `tsconfig.json`, `vite.config.ts`, `tailwind.config.js`)

**Directories:**

- Python package: `app/` (backend application root)
- Subpackages: `providers/`, `routers/` (domain-organized)
- Frontend: `pages/` (route-level), `components/ui/` (UI primitives), `lib/` (utilities), `hooks/` (custom hooks), `types/` (TS interfaces)

**Providers:**

- Class names: `{ProviderName}Provider` (e.g., `OpenAIProvider`, `AnthropicProvider`)
- Provider IDs: lowercase single-word identifiers (e.g., `"openai"`, `"anthropic"`, `"openrouter"`)
- Variable names: `provider_id`, `provider_name` as class-level attributes on each provider

**Models/Schemas:**

- ORM models: PascalCase, singular (e.g., `Benchmark`, `BenchmarkResult`)
- Pydantic schemas: PascalCase with suffixes (e.g., `BenchmarkCreate`, `BenchmarkOut`, `BenchmarkSummary`)
- TypeScript interfaces: PascalCase matching Pydantic schema names (e.g., `Benchmark`, `BenchmarkResult`, `Provider`)

**API Endpoints:**

- Prefix: `/api` (mounted in `main.py` for all routers)
- Resources: plural nouns (`/benchmarks`, `/providers`, `/insights`)
- Single-resource: `/benchmarks/{benchmark_id}`

## Where to Add New Code

**New Feature (backend):**

- New router: `backend/app/routers/{name}.py`, then `include_router()` in `backend/app/main.py`
- New model: Add to `backend/app/models.py`
- New schema: Add to `backend/app/schemas.py`
- New provider: Add file to `backend/app/providers/`, import + register in `backend/app/providers/__init__.py`

**New Feature (frontend):**

- New page: Add file to `frontend/src/pages/`
- New API endpoint: Add method to `frontend/src/lib/api.ts`
- New type: Add interface to `frontend/src/types/index.ts`
- New UI component: Add to `frontend/src/components/ui/` or `frontend/src/components/`
- New hook: Add to `frontend/src/hooks/`

**New utility:**

- Shared Python helper: `backend/app/` (root-level module)
- Shared TypeScript helper: `frontend/src/lib/`

## Special Directories

**frontend/src/components/ui/:**

- Purpose: shadcn/ui primitive components (copy-pasted from shadcn/ui template, customized)
- Generated: No (manually maintained)
- Committed: Yes

**backend/.venv/:**

- Purpose: Python virtual environment
- Generated: Yes (created by `python -m venv`)
- Committed: No (gitignored)

**frontend/node_modules/:**

- Purpose: Installed npm dependencies
- Generated: Yes
- Committed: No (gitignored)

**frontend/dist/:**

- Purpose: Production build output from Vite
- Generated: Yes (via `npm run build`)
- Committed: No (gitignored)

**backend/promptbench.db:**

- Purpose: SQLite database file (default dev database)
- Generated: Yes (created on first `init_db()` call)
- Committed: No (gitignored)

---

_Structure analysis: 2026-07-26_
