# Coding Conventions

**Analysis Date:** 2026-07-26

## Naming Patterns

**Files:**

- Python backend: `snake_case.py` (`main.py`, `config.py`, `models.py`, `schemas.py`, `database.py`, `pricing.py`)
- Python backend modules: `snake_case/` directory with `__init__.py` barrel files (`providers/`, `routers/`)
- Frontend pages: `PascalCase.tsx` (`BenchmarkResults.tsx`, `BenchmarkRun.tsx`, `History.tsx`, `Insights.tsx`)
- Frontend hooks: `camelCase.ts` (`useMediaQuery.ts`)
- Frontend UI primitives: `lowercase.tsx` (`button.tsx`, `card.tsx`, `input.tsx`, `badge.tsx`, `table.tsx`, `tabs.tsx`, `slider.tsx`, `label.tsx`, `select.tsx`, `textarea.tsx`, `separator.tsx`)
- Frontend lib: `camelCase.ts` (`api.ts`, `utils.ts`)
- Frontend types: `index.ts` in a `types/` directory

**Functions:**

- Python: `snake_case` (`get_provider`, `generate`, `get_models`, `calculate_cost`, `utcnow`, `get_db`, `init_db`, `run_one`)
- TypeScript: `camelCase` (`request`, `money`, `latency`, `tokens`, `useMediaQuery`, `cn`)

**Variables:**

- Python: `snake_case` (`provider_id`, `provider_name`, `api_key`, `base_url`, `model_names`, `cors_origins`, `database_url`)
- TypeScript: `camelCase` for local variables, `PascalCase` for types/interfaces

**Types:**

- Pydantic models: `PascalCase` (`BenchmarkCreate`, `BenchmarkOut`, `BenchmarkSummary`, `ResultOut`, `ModelSelection`)
- Dataclasses: `PascalCase` (`ModelInfo`, `ProviderResponse`)
- Python classes: `PascalCase` (`OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`, `OpenRouterProvider`, `OllamaProvider`, `VLLMProvider`, `Settings`, `Benchmark`, `BenchmarkResult`, `BaseProvider`, `OpenAICompatibleProvider`)
- TypeScript interfaces: `PascalCase` (`Provider`, `Benchmark`, `BenchmarkResult`, `BenchmarkHistoryItem`, `Insights`, `CreateBenchmark`, `ProviderModel`, `ModelPricing`)
- TypeScript type aliases: `PascalCase` (`Page`)

## Code Style

**Formatting:**

- Python: `ruff` for both linting and formatting (see `justfile` targets `lint-backend` and `format-backend`)
- TypeScript/TSX: `prettier` for formatting (see `justfile` target `format-frontend`)
- No `.ruff.toml` or `.prettierrc` config files found; defaults are used
- No `.eslintrc` or `.prettierrc` config files found for the frontend; ESLint runs via `npx eslint .`

**Linting:**

- Backend: `ruff check .` (lint), `ruff format .` (format)
- Frontend: `npx eslint .` (lint), `npx prettier --check .` (format check)
- Pre-commit hooks configured via `prek.toml` with `ruff-format`, `ruff-lint`, and `prettier-frontend` hooks

## Import Organization

**Python -- Order:**

1. Standard library (`datetime`, `functools`, `contextlib`, `asyncio`, `json`, `time`)
2. Third-party (`fastapi`, `sqlalchemy`, `pydantic`, `pydantic_settings`, `httpx`)
3. Local/relative (`from .config import settings`, `from ..pricing import PRICING`)

**Python -- Path Aliases:**

- No path aliases; relative imports only (e.g., `from .config import settings`, `from ..pricing import calculate_cost`)

**TypeScript -- Order:**

1. React and React-related (`react`, `react-dom`)
2. Third-party library imports (`@tanstack/react-query`, `lucide-react`, `recharts`, `class-variance-authority`, `clsx`, `tailwind-merge`)
3. Local `@/` alias imports (`@/lib/api`, `@/lib/utils`, `@/types`, `@/components/ui/*`, `@/pages/*`)

**TypeScript -- Path Aliases:**

- `@` maps to `./src` (configured in `vite.config.ts` resolve.alias and `tsconfig.json` paths)

## Error Handling

**Patterns:**

- Python: `try/except` blocks catch broad `Exception` in `run_one()` (benchmarks.py line 30-31), returning error strings instead of raising
- Python: `HTTPException(status_code, detail)` for HTTP error responses (e.g., 404 for not-found resources in routers)
- Python: `response.raise_for_status()` for HTTP transport errors in provider implementations
- Python: No custom exception classes or structured error types
- Python: Error field on `ProviderResponse` dataclass stores error message as `str | None`
- TypeScript/Frontend: Query error states surfaced via React Query's `q.isError` with `q.error.message` displayed inline as text (no toast or notification system)
- No global error boundary or error middleware in the frontend

## Logging

**Framework:** None (no Python `logging` module, no `console.log` in backend code)

**Patterns:**

- No logging, no print statements, no structured logging in any Python or TypeScript source files
- Error information flows through HTTP responses and React Query error states only

## Comments

**When to Comment:**

- Module-level docstring on `backend/app/__init__.py` ("PromptBench backend package.")
- Inline comments in `backend/app/pricing.py` explaining free model pricing source
- Inline comment in `backend/app/providers/openrouter.py` explaining provider attribution headers and free model selection
- No docstrings on functions or classes (absent throughout the codebase)
- No JSDoc or TSDoc comments in frontend TypeScript files

**JSDoc/TSDoc:**

- Not used anywhere in the codebase
- Type annotations are used heavily in TypeScript but without explanatory JSDoc

## Function Design

**Size:**

- Generally small and focused (most functions are 10-30 lines)
- Provider `generate` methods are the largest functions (60-80 lines each), each handling a full streaming HTTP request lifecycle
- Router endpoints are medium-sized (20-140 lines)

**Parameters:**

- Python provider `generate` methods share a common signature: `(self, prompt, model, system_prompt="", temperature=0.7, max_tokens=1000)`
- Pydantic request models used for typed endpoint inputs (`BenchmarkCreate`)
- Pydantic response models used for typed endpoint outputs (`BenchmarkOut`, `ResultOut`)

**Return Values:**

- Python: Provider `generate` methods return `ProviderResponse` dataclass instances
- Python: Router endpoints return Pydantic models directly (FastAPI serializes them)
- Python: `calculate_cost` returns a `float`
- TypeScript: `api` lib functions return `Promise<T>` typed via generic `request<T>()` helper

## Module Design

**Exports:**

- Python: Barrel `__init__.py` files re-export key symbols:
  - `backend/app/providers/__init__.py` exports all provider classes and the `PROVIDERS` dict and `get_provider()` function
  - `backend/app/routers/__init__.py` contains only a docstring (`"""API routers."""`)
- TypeScript: Default exports for page components, named exports for UI primitives (`export const Button`, `export function Badge`)

**Barrel Files:**

- `backend/app/providers/__init__.py` -- aggregates all providers into a `PROVIDERS` dict
- `backend/app/routers/__init__.py` -- docstring only (routers imported directly in `main.py`)
- `backend/app/__init__.py` -- module-level docstring only
- Frontend: `types/index.ts` serves as a barrel for all TypeScript interfaces

---

_Convention analysis: 2026-07-26_
