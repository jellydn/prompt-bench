"""Cache backends for PromptBench.

Redis is the primary backend. If Redis is unreachable — no server running,
wrong URL, network down — the factory transparently falls back to a
process-local in-memory backend so the application never crashes because of
caching infrastructure.

Both backends expose the same async interface (:class:`CacheBackend`), so
callers never need to know which one is active.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("promptbench.cache")


@dataclass
class CacheStats:
    """Snapshot of cache statistics."""

    backend: str
    entries: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    memory_usage: str = "n/a"
    avg_lookup_ms: float = 0.0

    def as_dict(self) -> dict:
        return {
            "backend": self.backend,
            "entries": self.entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "memory_usage": self.memory_usage,
            "avg_lookup_ms": self.avg_lookup_ms,
        }


# ── Statistics tracking (shared by both backends) ───────────────────────
@dataclass
class _StatsCounters:
    hits: int = 0
    misses: int = 0
    lookup_count: int = 0
    lookup_sum_ms: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def record_hit(self, ms: float) -> None:
        async with self.lock:
            self.hits += 1
            self.lookup_count += 1
            self.lookup_sum_ms += ms

    async def record_miss(self, ms: float) -> None:
        async with self.lock:
            self.misses += 1
            self.lookup_count += 1
            self.lookup_sum_ms += ms

    async def snapshot(self) -> tuple[int, int, int, float]:
        async with self.lock:
            return self.hits, self.misses, self.lookup_count, self.lookup_sum_ms

    async def reset(self) -> None:
        async with self.lock:
            self.hits = 0
            self.misses = 0
            self.lookup_count = 0
            self.lookup_sum_ms = 0.0


# ── Per-key lock registry (shared by response + embedding caches) ───────
class _KeyLockRegistry:
    """Registry of per-key asyncio.Lock objects for stampede prevention.

    Ensures N concurrent requests for the same key trigger exactly one
    compute — no guard lock needed because ``asyncio.Lock()`` is
    synchronous and asyncio only yields at ``await`` points.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> asyncio.Lock:
        """Return or create the per-key lock.

        Avoids ``setdefault`` so we don't construct a throwaway Lock on
        every cache hit (the common path). Safe in asyncio because no
        ``await`` occurs between the check and the assignment, so another
        task cannot interleave.
        """
        lock = self._locks.get(key)
        if lock is not None:
            return lock
        lock = asyncio.Lock()
        self._locks[key] = lock
        return lock


class CacheBackend(ABC):
    """Async cache backend interface."""

    name: str = "base"

    @abstractmethod
    async def get(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def clear(self, prefix: str = "") -> int: ...

    @abstractmethod
    async def count(self, prefix: str = "") -> int: ...

    @abstractmethod
    async def stats(self) -> CacheStats: ...

    @abstractmethod
    async def close(self) -> None: ...


# ── In-memory backend ───────────────────────────────────────────────────
class InMemoryCache(CacheBackend):
    """Process-local TTL cache used when Redis is unavailable."""

    name = "memory"

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, float]] = {}
        self._lock = asyncio.Lock()
        self._counters = _StatsCounters()

    async def get(self, key: str) -> bytes | None:
        started = time.perf_counter()
        async with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                value, expires_at = entry
                if expires_at > time.monotonic():
                    ms = (time.perf_counter() - started) * 1000
                    await self._counters.record_hit(ms)
                    return value
                # expired — evict
                del self._store[key]
        ms = (time.perf_counter() - started) * 1000
        await self._counters.record_miss(ms)
        return None

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic() + max(ttl, 0))

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self, prefix: str = "") -> int:
        async with self._lock:
            if not prefix:
                removed = len(self._store)
                self._store.clear()
                return removed
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    async def count(self, prefix: str = "") -> int:
        now = time.monotonic()
        async with self._lock:
            if not prefix:
                live = sum(1 for _, exp in self._store.values() if exp > now)
                return live
            return sum(
                1 for k, (_, exp) in self._store.items() if k.startswith(prefix) and exp > now
            )

    async def stats(self) -> CacheStats:
        hits, misses, count_n, lookup_sum = await self._counters.snapshot()
        total = hits + misses
        entries = await self.count()
        return CacheStats(
            backend=self.name,
            entries=entries,
            hits=hits,
            misses=misses,
            hit_rate=(hits / total) if total else 0.0,
            memory_usage=f"{entries} keys (local)",
            avg_lookup_ms=(lookup_sum / count_n) if count_n else 0.0,
        )

    async def close(self) -> None:
        # Teardown — clear directly without acquiring the asyncio.Lock so this
        # is safe to call from a different event loop (e.g. test cleanup).
        self._store.clear()


# ── Redis backend ───────────────────────────────────────────────────────
class RedisCache(CacheBackend):
    """Redis-backed cache. Degrades to misses on connection errors."""

    name = "redis"

    def __init__(self, client) -> None:  # redis.asyncio.Redis
        self._client = client
        self._counters = _StatsCounters()

    async def get(self, key: str) -> bytes | None:
        started = time.perf_counter()
        try:
            value = await self._client.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis GET failed (%s) — treating as miss", exc)
            ms = (time.perf_counter() - started) * 1000
            await self._counters.record_miss(ms)
            return None
        ms = (time.perf_counter() - started) * 1000
        if value is None:
            await self._counters.record_miss(ms)
            return None
        await self._counters.record_hit(ms)
        return value

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        try:
            await self._client.set(key, value, ex=max(ttl, 1))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis SET failed (%s) — entry not stored", exc)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis DELETE failed (%s)", exc)

    async def clear(self, prefix: str = "") -> int:
        try:
            if not prefix:
                await self._client.flushdb()
                return -1  # exact count unknown after flushdb
            count = 0
            async for key in self._client.scan_iter(match=f"{prefix}*"):
                await self._client.delete(key)
                count += 1
            return count
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis CLEAR failed (%s)", exc)
            return 0

    async def count(self, prefix: str = "") -> int:
        try:
            if not prefix:
                return await self._client.dbsize()
            return sum(1 for _ in self._client.scan_iter(match=f"{prefix}*"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis COUNT failed (%s)", exc)
            return 0

    async def stats(self) -> CacheStats:
        hits, misses, count_n, lookup_sum = await self._counters.snapshot()
        total = hits + misses
        memory_usage = "n/a"
        with contextlib.suppress(Exception):
            info = await self._client.info("memory")
            memory_usage = info.get("used_memory_human", "n/a")
        entries = await self.count()
        return CacheStats(
            backend=self.name,
            entries=entries,
            hits=hits,
            misses=misses,
            hit_rate=(hits / total) if total else 0.0,
            memory_usage=memory_usage,
            avg_lookup_ms=(lookup_sum / count_n) if count_n else 0.0,
        )

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._client.aclose()


# ── Factory / singleton ─────────────────────────────────────────────────
_cache: CacheBackend | None = None
_cache_lock: asyncio.Lock | None = None
_cache_lock_loop: asyncio.AbstractEventLoop | None = None


def _singleton_lock() -> asyncio.Lock:
    """Return an asyncio.Lock bound to the currently running event loop.

    The cache singleton is shared module state, but FastAPI's TestClient runs
    the app lifespan in a separate event loop from the test loop. A single
    module-level asyncio.Lock would bind to whichever loop touched it first
    and raise ``RuntimeError`` when awaited from the other. We therefore keep
    one lock per running loop, recreating it when the loop changes.
    """
    global _cache_lock, _cache_lock_loop  # noqa: PLW0603
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _cache_lock is None or _cache_lock_loop is not loop:
        _cache_lock = asyncio.Lock()
        _cache_lock_loop = loop
    return _cache_lock


async def get_cache() -> CacheBackend:
    """Return the shared cache backend, initialising on first call.

    Tries Redis first. If Redis is unavailable, falls back to an in-memory
    backend and logs a warning. The chosen backend is reused for the lifetime
    of the process.
    """
    global _cache  # noqa: PLW0603
    if _cache is not None:
        return _cache
    async with _singleton_lock():
        if _cache is not None:
            return _cache
        _cache = await _init_backend()
        return _cache


async def _init_backend() -> CacheBackend:
    from ..config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if not settings.cache_enabled:
        logger.info("Cache disabled (CACHE_ENABLED=false) — using memory backend (no-op store)")
        return InMemoryCache()

    redis_url = settings.redis_url
    if not redis_url:
        logger.info("No REDIS_URL configured — using in-memory cache")
        return InMemoryCache()

    try:
        import redis.asyncio as redis  # noqa: PLC0415

        client = redis.from_url(redis_url, decode_responses=False, socket_timeout=2)
        await client.ping()
        logger.info("Connected to Redis cache at %s", _safe_url(redis_url))
        return RedisCache(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unavailable (%s) — falling back to in-memory cache", exc)
        return InMemoryCache()


def _safe_url(url: str) -> str:
    """Strip credentials from a Redis URL for logging."""
    if "://" in url and "@" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            host_part = rest.split("@", 1)[1]
            return f"{scheme}://{host_part}"
    return url


async def reset_cache_singleton() -> None:
    """Reset the cached backend singleton (used by tests)."""
    global _cache  # noqa: PLW0603
    async with _singleton_lock():
        if _cache is not None:
            try:
                await _cache.close()
            except Exception:  # noqa: BLE001
                # close() may touch resources bound to a different (now closed)
                # event loop when the singleton is reset from a test loop. The
                # backend is being discarded regardless, so a close error is
                # non-fatal.
                logger.debug("cache backend close failed during reset", exc_info=True)
        _cache = None


__all__ = [
    "CacheBackend",
    "CacheStats",
    "InMemoryCache",
    "RedisCache",
    "get_cache",
    "reset_cache_singleton",
]
