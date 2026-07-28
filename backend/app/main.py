import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .database import init_db
from .limiter import limiter
from .routers import benchmarks, cache, insights, providers, session_keys

# Configure structured logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("promptbench")
def _verify_expected_columns() -> None:
    """Verify all expected columns exist on benchmark_results after migrations.

    Migration 0002 adds cache columns, but if the alembic CLI is missing
    (e.g., production Docker image built without alembic in main deps),
    the migration never runs and init_db() cannot ALTER existing tables.
    This check catches that failure mode at startup with a clear warning
    rather than letting users discover a 500 on /history.
    """
    import sqlalchemy as sa  # noqa: PLC0415

    from .database import engine  # noqa: PLC0415

    expected = {"cache_hit", "cache_type", "cache_lookup_ms", "provider_latency_ms"}
    try:
        inspector = sa.inspect(engine)
        actual = {c["name"] for c in inspector.get_columns("benchmark_results")}
        missing = expected - actual
        if missing:
            logger.warning(
                "Missing columns on benchmark_results: %s. "
                "The history page will return 500 until migration 0002 is applied. "
                "Ensure alembic is installed and 'alembic upgrade head' runs at startup.",
                ", ".join(sorted(missing)),
            )
    except Exception as exc:
        # Table might not exist yet (fresh database before init_db) —
        # this is a best-effort check, never a startup blocker.
        logger.debug("Column verification skipped: %s", exc)


def _run_alembic_migrations() -> None:
    """Apply pending Alembic migrations after tables exist.

    ``init_db()`` runs first and creates tables with the full current
    schema.  This function then:

    1. Checks whether ``alembic_version`` already exists.  If not, it
       stamps the initial migration (2dae871076fe) so Alembic knows
       the baseline tables already exist — a one-time bootstrap step.
    2. Runs ``upgrade head`` to apply any migrations that ``init_db``
       could not handle (e.g. ALTER TABLE on an existing create_all
       database where columns were missing).

    The stamp check is important: re-stamping on every startup would
    overwrite the migration state and force re-execution of already-
    applied migrations.
    """
    try:
        db_url = str(settings.database_url)
        env = {**os.environ, "DATABASE_URL": db_url}

        # One-time bootstrap: if alembic_version does not exist yet, mark
        # the initial migration as done.  After the first successful run
        # we never stamp again — only upgrade.
        alembic_current = subprocess.run(
            ["alembic", "current"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        need_stamp = alembic_current.returncode != 0 or not alembic_current.stdout.strip()

        if need_stamp:
            stamp = subprocess.run(
                ["alembic", "stamp", "2dae871076fe"],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if stamp.returncode == 0:
                logger.info("Alembic baseline stamped (first run)")
            else:
                logger.warning(
                    "Alembic stamp warning: %s",
                    stamp.stderr.strip(),
                )

        # Apply any incremental migrations.
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            logger.info("Database migrations applied successfully")
            return
        # Defensive: surface common failure patterns clearly.
        stderr_lower = result.stderr.lower()
        if "already exists" in stderr_lower:
            logger.info("Alembic upgrade skipped — schema already up to date")
            return
        logger.warning(
            "Alembic upgrade failed (rc=%d): %s",
            result.returncode,
            result.stderr.strip(),
        )
    except FileNotFoundError:
        logger.info("Alembic CLI not found — migrations not available")
    except subprocess.TimeoutExpired:
        logger.warning("Alembic upgrade timed out after 30 s")
    except Exception as exc:
        logger.warning("Alembic migration error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PromptBench server")
    # Run Alembic migrations before anything touches the database.
    # In production, the initial deployment used create_all() which cannot
    # add columns to existing tables.  Alembic handles incremental changes.
    init_db()  # Create tables first (no-op if they exist)
    _run_alembic_migrations()
    _verify_expected_columns()  # Warn if cache columns are still missing
    # Repair any benchmarks stuck as "running" from a previous crash
    from .database import SessionLocal  # noqa: PLC0415
    from .routers.benchmarks import _repair_stuck_benchmarks  # noqa: PLC0415

    db = SessionLocal()
    try:
        _repair_stuck_benchmarks(db)
    finally:
        db.close()
    # Refresh OpenRouter free model list from API
    from .providers.model_lists import (  # noqa: PLC0415
        OPENROUTER_FREE_MODELS,
        refresh_openrouter_free_models,
    )

    await refresh_openrouter_free_models()
    # Initialise the cache backend (Redis or in-memory fallback) early so the
    # choice is logged at startup rather than on first benchmark request.
    from .cache import get_cache  # noqa: PLC0415

    await get_cache()
    logger.info(
        "PromptBench ready — %d OpenRouter free models",
        len(OPENROUTER_FREE_MODELS),
    )
    yield
    logger.info("PromptBench shutting down")


app = FastAPI(title="PromptBench", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(SlowAPIMiddleware)
app.include_router(providers.router, prefix="/api")
app.include_router(benchmarks.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(cache.router, prefix="/api")
app.include_router(session_keys.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "name": "PromptBench"}


# Serve frontend static files — must be last to avoid catching API routes

_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
    logger.info("Serving frontend from %s", _static_dir)
else:
    logger.info("No static directory found at %s — API only", _static_dir)
