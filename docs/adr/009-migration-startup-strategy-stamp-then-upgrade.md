# 9. Migration Startup Strategy — Stamp-Then-Upgrade with Inspector-Based Idempotency

Date: 2026-07-28

## Status

Accepted

## Context

PromptBench was initially deployed with `Base.metadata.create_all()` (via `init_db()`) and no Alembic migration step at startup. When the caching feature added new columns (`cache_hit`, `cache_type`, `cache_lookup_ms`, `provider_latency_ms`) to the `benchmark_results` table via migration `0002_add_cache_metrics`, nothing ran `alembic upgrade head` in production. `create_all()` cannot alter existing tables — it only creates new ones — so the cache columns were never added to the production PostgreSQL database.

The history page (`/api/benchmarks`) started returning 500 errors because SQLAlchemy's `selectinload` tried to load all model columns, including the missing cache columns.

Adding `alembic upgrade head` to the startup flow introduced three new states to handle:

1. **Fresh empty database** — `init_db()` creates tables with the full current schema, then Alembic tries to apply migration 0002 (adding columns that already exist).
2. **Existing production database** — tables exist from `create_all()`, no `alembic_version` tracking table, cache columns missing.
3. **Database with alembic_version present** — normal state after the first migration run.

## Decision

### Stamp-then-upgrade with pre-check

The startup flow runs in this order:

```
init_db()                          # create_all — no-op if tables exist
  ↓
alembic current                    # check if alembic_version table exists
  ↓ (if not)
alembic stamp 2dae871076fe         # one-time bootstrap (marks baseline)
  ↓
alembic upgrade head               # apply pending migrations
```

The `alembic current` pre-check is critical: running `alembic stamp 2dae871076fe` unconditionally on every startup would overwrite the migration state backward, forcing re-execution of already-applied migrations on every restart.

### Inspector-based column existence checks (not try/except)

Migration `0002_add_cache_metrics` uses SQLAlchemy's `inspect()` to check whether each column exists before attempting `batch_alter_table.add_column()`:

```python
def _column_exists(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols
```

Each column is checked and skipped if it already exists. This handles all three DB states correctly:

| State | `init_db()` | `alembic current` | Stamp | Upgrade |
|-------|-------------|--------------------|-------|---------|
| Fresh empty DB | Creates all tables | Fails (no table) | Stamps baseline | 0002 skips (columns exist) |
| Production DB (create_all, no tracking) | No-op | Fails (no table) | Stamps baseline | 0002 adds columns |
| DB with alembic_version | No-op | Succeeds | Skipped | Applies pending |

### Rejected alternative: try/except OperationalError

The first attempt at idempotency wrapped each `add_column` in `try/except OperationalError`. This is **broken on PostgreSQL**: when an `OperationalError` occurs inside Alembic's transaction (e.g., adding a column that already exists), PostgreSQL sets the transaction to an **aborted state**. All subsequent SQL statements within the same transaction fail with `InFailedSqlTransaction`. The try/except catches the first error but cannot un-poison the transaction — subsequent column additions crash. The inspector approach avoids this entirely by checking before any SQL is emitted.

## Consequences

### Positive

- Three DB states handled correctly by a single startup sequence
- `alembic current` pre-check prevents re-stamping on every restart — migrations won't re-execute
- Inspector-based idempotency works on both PostgreSQL and SQLite without transaction-poisoning issues
- Production 500 error on `/api/benchmarks` resolved — cache columns are added on first deployment with the fix
- Future migrations can be added by creating a new revision and deploying — `upgrade head` applies them automatically

### Negative

- Dual schema management (`create_all` + Alembic) is fragile: order dependency is implicit, not programmatically enforced
- `alembic current` adds ~1-3 seconds to every startup for a query that usually confirms "still at head"
- `subprocess.run` is synchronous in the async lifespan — blocks the event loop for up to 90 seconds (30s current + 30s stamp + 30s upgrade)
- Migration `0002` uses 4 separate `batch_alter_table` operations (one per column) instead of a single batch — 4× the I/O on large tables (mitigated by small benchmark data)
- The inspector approach won't work in Alembic's offline mode (`--sql`) — the mock engine has no real connection for `inspect()`
