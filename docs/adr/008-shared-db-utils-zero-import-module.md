# 8. Shared DB Utility Module with Zero Application Imports

Date: 2026-07-28

## Status

Accepted

## Context

Two modules — `backend/alembic/env.py` (Alembic migration environment) and `backend/app/database.py` (FastAPI database setup) — contained identical URL normalization logic:

```python
if url.startswith("postgres://") and "+psycopg" not in url:
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://") and "+psycopg" not in url:
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
```

This duplicated ~5 lines across two files. Fly.io and some orchestrators supply `postgres://` URLs, while `psycopg` v3 requires the explicit `+psycopg` driver prefix. If the normalization logic changed in one file (e.g., handling a new prefix), the other file would drift silently.

Extracting to a shared location was non-trivial because:
- `env.py` runs under Alembic's `sys.path`, not the FastAPI application context
- `database.py` creates a SQLAlchemy engine at module level — importing from it would trigger side effects (engine creation, config loading)
- Any shared module must import nothing from the application (`app.config`, `app.database`, etc.) to be importable from both contexts

## Decision

Create `backend/app/db_utils.py` — a module with **zero application imports** — containing a single pure function `normalize_db_url(url: str) -> str`.

Both `env.py` and `database.py` import from this module:

```python
# database.py (FastAPI context)
from .db_utils import normalize_db_url

# env.py (Alembic context)
from app.db_utils import normalize_db_url  # noqa: E402
```

The module has no dependencies on any `app.*` package, making it safe to import from Alembic's alternate sys.path without triggering engine creation, settings loading, or any other side effects.

## Consequences

### Positive

- Single source of truth for URL normalization — both contexts always stay in sync
- Zero-import design documented clearly in the module docstring
- Importable from Alembic's `sys.path` without triggering `app.database` engine/connection side effects
- Pure function — trivial to test, no state, no side effects
- +20 lines overall (new module + simplified call sites)

### Negative

- Another small module in the already-flat `app/` namespace
- The dual import styles (`from .db_utils` vs `from app.db_utils`) are syntactically different, though semantically identical — could confuse new contributors
- If future utility functions require access to `settings` or other app state, they cannot live in this module without breaking the Alembic import path
