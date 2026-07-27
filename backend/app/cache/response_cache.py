"""Response cache — caches completed LLM responses by deterministic key.

Flow (see module docstring in keys.py for key design):

1. Compute the cache key from the logical request inputs.
2. Look up the backend.
3. On hit → return the cached :class:`ProviderResponse`, marked cache_hit.
4. On miss → call the provider, store the response (TTL = 30 min), return it.

Never cached:
* provider errors (``ProviderResponse.error`` set),
* timeout responses,
* streaming responses that did not complete (no output and no tokens),
* requests explicitly marked ``cacheable=False``.

Cache-stampede prevention: per-key asyncio locks guarantee that N concurrent
requests for the same key trigger exactly one provider call; the rest wait and
receive the freshly stored result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ..providers.base import ProviderResponse
from .cache import CacheBackend, get_cache

logger = logging.getLogger("promptbench.cache.response")

# Default TTL for cached responses (30 minutes), in seconds.
DEFAULT_RESPONSE_TTL = 30 * 60


@dataclass
class CacheInfo:
    """Per-result cache metadata attached to benchmark results."""

    cache_hit: bool = False
    cache_type: str | None = None  # "response" | "embedding" | None
    cache_lookup_ms: int = 0
    provider_latency_ms: int = 0
    total_latency_ms: int = 0


class ResponseCache:
    """Cached wrapper around provider ``generate`` calls."""

    def __init__(self, backend: CacheBackend, ttl: int = DEFAULT_RESPONSE_TTL) -> None:
        self._backend = backend
        self._ttl = ttl
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._guards_lock = asyncio.Lock()

    async def _key_lock(self, key: str) -> asyncio.Lock:
        # Fast path — no await when the lock already exists.
        lock = self._key_locks.get(key)
        if lock is not None:
            return lock
        async with self._guards_lock:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._key_locks[key] = lock
            return lock

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[ProviderResponse]],
        *,
        cacheable: bool = True,
    ) -> tuple[ProviderResponse, CacheInfo]:
        """Return a cached response or compute, cache, and return a new one.

        ``compute_fn`` is called only on a miss (or when ``cacheable`` is
        False). The returned :class:`CacheInfo` records hit/miss, lookup time,
        and provider latency for reporting.
        """
        # Non-cacheable requests always call the provider and never read/write.
        if not cacheable:
            return await self._compute_and_measure(compute_fn, CacheInfo())

        lookup_start = time.perf_counter()
        cached = await self._backend.get(key)
        lookup_ms = round((time.perf_counter() - lookup_start) * 1000)

        if cached is not None:
            response = _deserialize_response(cached)
            if response is not None:
                info = CacheInfo(
                    cache_hit=True,
                    cache_type="response",
                    cache_lookup_ms=lookup_ms,
                    provider_latency_ms=0,
                    total_latency_ms=lookup_ms,
                )
                logger.debug("Cache HIT key=%s lookup=%dms", key, lookup_ms)
                return response, info

        # Miss — guard against stampede with a per-key lock.
        lock = await self._key_lock(key)
        async with lock:
            # Re-check after acquiring: another waiter may have populated it.
            lookup_start = time.perf_counter()
            cached = await self._backend.get(key)
            lookup_ms = round((time.perf_counter() - lookup_start) * 1000)
            if cached is not None:
                response = _deserialize_response(cached)
                if response is not None:
                    return response, CacheInfo(
                        cache_hit=True,
                        cache_type="response",
                        cache_lookup_ms=lookup_ms,
                        provider_latency_ms=0,
                        total_latency_ms=lookup_ms,
                    )

            response, info = await self._compute_and_measure(compute_fn, CacheInfo())
            info.cache_lookup_ms = lookup_ms
            info.total_latency_ms = info.provider_latency_ms + lookup_ms

            if _is_cacheable(response):
                try:
                    await self._backend.set(key, _serialize_response(response), self._ttl)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to store cache entry key=%s: %s", key, exc)
            return response, info

    async def _compute_and_measure(
        self,
        compute_fn: Callable[[], Awaitable[ProviderResponse]],
        info: CacheInfo,
    ) -> tuple[ProviderResponse, CacheInfo]:
        provider_start = time.perf_counter()
        response = await compute_fn()
        provider_ms = round((time.perf_counter() - provider_start) * 1000)
        info.provider_latency_ms = provider_ms
        info.total_latency_ms = provider_ms
        return response, info


# ── Serialization ───────────────────────────────────────────────────────


def _is_cacheable(response: ProviderResponse) -> bool:
    """Return True only for successful, completed, non-error responses."""
    if response.error is not None:
        return False
    # Treat "no output and no tokens" as an incomplete/timeout response.
    return bool(response.response_text or response.input_tokens or response.output_tokens)


def _serialize_response(response: ProviderResponse) -> bytes:
    payload = {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "ttft_ms": response.ttft_ms,
        "total_latency_ms": response.total_latency_ms,
        "response_text": response.response_text,
        "response_chars": response.response_chars,
        "cost": response.cost,
        "error": response.error,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _deserialize_response(data: bytes) -> ProviderResponse | None:
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return ProviderResponse(
        input_tokens=payload["input_tokens"],
        output_tokens=payload["output_tokens"],
        ttft_ms=payload["ttft_ms"],
        total_latency_ms=payload["total_latency_ms"],
        response_text=payload["response_text"],
        response_chars=payload["response_chars"],
        cost=payload["cost"],
        error=payload.get("error"),
    )


# ── Module-level convenience singleton ──────────────────────────────────
_response_cache: ResponseCache | None = None


async def get_response_cache() -> ResponseCache:
    global _response_cache  # noqa: PLW0603
    if _response_cache is not None:
        return _response_cache
    backend = await get_cache()
    from ..config import get_settings  # noqa: PLC0415

    settings = get_settings()
    _response_cache = ResponseCache(backend, ttl=settings.cache_ttl_response)
    return _response_cache


async def reset_response_cache_singleton() -> None:
    global _response_cache  # noqa: PLW0603
    _response_cache = None


__all__ = [
    "CacheInfo",
    "DEFAULT_RESPONSE_TTL",
    "ResponseCache",
    "get_response_cache",
    "reset_response_cache_singleton",
]
