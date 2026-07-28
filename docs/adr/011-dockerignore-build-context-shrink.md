# 11. .dockerignore Build Context Shrink

Date: 2026-07-28

## Status

Accepted

## Context

The Docker build context was ~300 MB (~19,900 files). Every `fly deploy` (and `docker build`) transferred a bloated tarball containing:

| Path | Size | Source |
|------|------|--------|
| `frontend/node_modules` | ~220 MB | `npm install` in host checkout |
| `backend/.venv` | ~102 MB | `uv sync` in host checkout |
| `.freebuff` | ~16 MB | Preview artifacts, run logs, desktop state |
| `.git` | ~2.5 MB | Full repository history |
| `__pycache__`, `*.pyc` | — | Compiled Python from editor/CLI |

All of these are reinstalled or regenerated inside the Dockerfile. The multi-stage build already runs `npm ci` (frontend stage) and `uv sync --frozen` (backend stage), and Fly.io deploys from a fresh clone — Git history is irrelevant.

Fly.io printed a size warning on every deploy.

## Decision

Add a `.dockerignore` at the repository root that excludes:

- **Reinstalled dependencies**: `frontend/node_modules`, `backend/.venv`
- **Build artifacts**: `__pycache__`, `*.pyc`, `*.pyo`, `.pytest_cache`, `.ruff_cache`, `*.egg-info`
- **Git history**: `.git`
- **Secrets**: `.env`, `.env.*` (except `.env.example`)
- **Dev tooling**: `.freebuff`, `.amp`, `.planning`
- **Logs**: `*.log`
- **OS/IDE noise**: `.DS_Store`, `Thumbs.db`, `.idea`, `.vscode`, swap files

**What is kept** (whitelist-by-omission):

- `frontend/src/`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/*.config.*`, `frontend/index.html`
- `backend/app/`, `backend/alembic/`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/alembic.ini`
- `fly.toml`, `Dockerfile`, `docker-compose.yml`

### Alternatives considered

1. **No `.dockerignore` (do nothing)**: Rejected — 300 MB of unnecessary context slowed every build and produced a Fly.io warning. Pure overhead with no benefit.

2. **Restrictive whitelist (`*` deny + explicit `!` allow rules)**: Rejected — more fragile. Adding a new top-level file (e.g., `justfile`, `LICENSE`) would silently break the build unless the whitelist were updated. The exclusion-based approach is self-documenting: new files are included by default, and only known-large paths are excluded.

3. **Per-service `.dockerignore`**: Rejected — the single Dockerfile uses a multi-stage build and COPYs from both `frontend/` and `backend/`. A single `.dockerignore` at the repo root is the simplest correct approach.

## Consequences

### Positive

- Build context: 300 MB → ~2 MB (150× reduction)
- File count: ~19,900 → ~200 (100× reduction)
- Fly.io deploy warning eliminated
- Docker build cache is more effective (fewer spurious context invalidations)
- Local `docker build` starts faster (smaller context upload)
- Self-documenting: the `.dockerignore` lists exactly what is and isn't needed for production builds

### Negative

- A new top-level file that isn't explicitly excluded will be included in the build context (acceptable — exclusion-based, not whitelist-based)
- If a future build step requires a host-generated artifact (e.g., pre-built frontend), the `.dockerignore` must be updated
