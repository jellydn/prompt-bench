import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .database import init_db
from .limiter import limiter
from .routers import benchmarks, insights, providers

# Configure structured logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("promptbench")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PromptBench server")
    init_db()
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


@app.get("/")
def health():
    return {"status": "ok", "name": "PromptBench"}
