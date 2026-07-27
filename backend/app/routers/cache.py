"""Cache inspection and management endpoints."""

from fastapi import APIRouter

from ..cache import get_cache

router = APIRouter()


@router.get("/cache/stats")
async def cache_stats():
    """Return current cache statistics (entries, hit rate, memory, latency)."""
    backend = await get_cache()
    stats = await backend.stats()
    return stats.as_dict()


@router.delete("/cache")
async def cache_clear(prefix: str = ""):
    """Clear cache entries matching ``prefix`` (all entries when omitted)."""
    backend = await get_cache()
    removed = await backend.clear(prefix)
    return {"cleared": removed, "prefix": prefix or None}
