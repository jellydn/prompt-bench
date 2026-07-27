"""Embedding cache — caches embedding vectors by deterministic key.

Key shape: ``embedding:{provider}:{model}:{sha256(text)}`` (see
:func:`app.cache.keys.embedding_cache_key`).

TTL defaults to 24 hours. As with the response cache, per-key asyncio locks
prevent cache stampedes when many callers request the same embedding
concurrently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .cache import CacheBackend, get_cache

logger = logging.getLogger("promptbench.cache.embedding")

# Default TTL for cached embeddings (24 hours), in seconds.
DEFAULT_EMBEDDING_TTL = 24 * 60 * 60


@dataclass
class EmbeddingResult:
    """An embedding vector plus its dimensionality and cache metadata."""

    vector: list[float]
    dimension: int
    cache_hit: bool
    cache_lookup_ms: int


class EmbeddingCache:
    """Cached wrapper around embedding generation calls."""

    def __init__(self, backend: CacheBackend, ttl: int = DEFAULT_EMBEDDING_TTL) -> None:
        self._backend = backend
        self._ttl = ttl
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._guards_lock = asyncio.Lock()

    async def _key_lock(self, key: str) -> asyncio.Lock:
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
        compute_fn: Callable[[], Awaitable[tuple[list[float], int]]],
    ) -> EmbeddingResult:
        lookup_start = time.perf_counter()
        cached = await self._backend.get(key)
        lookup_ms = round((time.perf_counter() - lookup_start) * 1000)
        if cached is not None:
            parsed = _deserialize(cached)
            if parsed is not None:
                vector, dimension = parsed
                logger.debug("Embedding HIT key=%s lookup=%dms", key, lookup_ms)
                return EmbeddingResult(vector, dimension, True, lookup_ms)

        lock = await self._key_lock(key)
        async with lock:
            lookup_start = time.perf_counter()
            cached = await self._backend.get(key)
            lookup_ms = round((time.perf_counter() - lookup_start) * 1000)
            if cached is not None:
                parsed = _deserialize(cached)
                if parsed is not None:
                    vector, dimension = parsed
                    return EmbeddingResult(vector, dimension, True, lookup_ms)

            vector, dimension = await compute_fn()
            try:
                await self._backend.set(key, _serialize(vector, dimension), self._ttl)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to store embedding key=%s: %s", key, exc)
            return EmbeddingResult(vector, dimension, False, lookup_ms)


def _serialize(vector: list[float], dimension: int) -> bytes:
    payload = {
        "vector": vector,
        "dimension": dimension,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _deserialize(data: bytes) -> tuple[list[float], int] | None:
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload["vector"], payload["dimension"]


# ── Module-level convenience singleton ──────────────────────────────────
_embedding_cache: EmbeddingCache | None = None


async def get_embedding_cache() -> EmbeddingCache:
    global _embedding_cache  # noqa: PLW0603
    if _embedding_cache is not None:
        return _embedding_cache
    backend = await get_cache()
    from ..config import get_settings  # noqa: PLC0415

    settings = get_settings()
    _embedding_cache = EmbeddingCache(backend, ttl=settings.cache_ttl_embedding)
    return _embedding_cache


async def reset_embedding_cache_singleton() -> None:
    global _embedding_cache  # noqa: PLW0603
    _embedding_cache = None


__all__ = [
    "DEFAULT_EMBEDDING_TTL",
    "EmbeddingCache",
    "EmbeddingResult",
    "get_embedding_cache",
    "reset_embedding_cache_singleton",
]
