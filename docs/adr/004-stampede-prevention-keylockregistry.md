# 4. Stampede Prevention via `_KeyLockRegistry`

Date: 2026-07-28

## Status

Accepted

## Context

The cache layer wraps provider calls so that repeated benchmark runs are served from cache without re-calling the LLM provider. When a cache miss occurs — and N concurrent requests all want the same uncached key — a naive implementation would fire N provider calls simultaneously:

```
Request 1: cache.get("key") → miss → call OpenAI
Request 2: cache.get("key") → miss → call OpenAI   ← wasted
Request 3: cache.get("key") → miss → call OpenAI   ← wasted
```

For an LLM call costing $0.01–$0.50 and taking 300 ms–30 s, this is both expensive and slow. The pattern is known as a **cache stampede** (or dog-piling): many concurrent callers race to populate the same cache key.

The original implementation (PR #6) solved this with per-key `asyncio.Lock` objects — but the lock-creation logic was duplicated verbatim (~12 lines) in both `ResponseCache` and `EmbeddingCache`. Each had its own `_key_locks` dict, its own `_guards_lock`, and its own `_key_lock()` method with identical double-checked locking.

## Decision

Extract the per-key lock registry into a shared `_KeyLockRegistry` helper that both caches use. The design eliminates the async guard lock entirely by exploiting a property of asyncio's cooperative multitasking.

### Original code (duplicated in both caches)

```python
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
```

This is a classic double-checked locking pattern: fast-path lookup, guarded creation. The `async with self._guards_lock` serializes lock creation — only one task can create a new lock at a time.

### Extracted helper (`app/cache/cache.py`)

```python
class _KeyLockRegistry:
    """Registry of per-key asyncio.Lock objects for stampede prevention.
    No guard lock needed — asyncio only yields at `await` points."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> asyncio.Lock:
        """Return or create the per-key lock."""
        lock = self._locks.get(key)
        if lock is not None:
            return lock          # fast path — no allocation on cache hits
        lock = asyncio.Lock()
        self._locks[key] = lock
        return lock
```

Key insight: `asyncio.Lock()` is synchronous — it does not `await`. In asyncio's cooperative multitasking, task switches only occur at `await` expressions. Between `self._locks.get(key)` and `self._locks[key] = lock`, there is no `await`, so no other task can interleave. The original `_guards_lock` was serializing work that was already implicitly serialized by the event loop.

### Stampede prevention flow

```
Request 1: cache.get("key")     → miss
           lock = registry.get("key") → new Lock("key")
           async with lock:             ← acquires Lock("key")
             cache.get("key") → miss    ← re-check inside lock
             result = call_provider()   ← SINGLE provider call
             cache.set("key", result)
           (releases Lock("key"))

Request 2: cache.get("key")     → miss
           lock = registry.get("key") → existing Lock("key")
           async with lock:             ← BLOCKS until Request 1 releases
             cache.get("key") → HIT    ← re-check finds Request 1's result
           (returns cached result)
```

Request 2 finds `lock` already exists, waits on it, and on re-check finds the freshly cached value. The stampede is prevented — N concurrent requests for the same key trigger exactly one provider call.

### Caller changes

Before (async wrapper):
```python
lock = await self._key_lock(key)
async with lock:
    ...
```

After (synchronous, no `await`):
```python
lock = self._key_locks.get(key)
async with lock:
    ...
```

The removal of `await` is correct because `get()` is synchronous — the original `await` was only needed because `_key_lock` was declared `async` to use the guard lock. With the guard lock removed, there is nothing to `await`.

## Consequences

### 📋 Positive

- **24 lines of duplication eliminated**: Two copies of `_key_lock` + `_guards_lock` + `_key_locks` init → one `_KeyLockRegistry(3 lines)` + two `self._key_locks = _KeyLockRegistry()` calls.
- **No async guard lock overhead**: The original `async with self._guards_lock` was an unnecessary `await` on the hot path of lock creation. The new code has zero awaits for lock acquisition.
- **No throwaway allocations on cache hits**: The `get()` method checks `self._locks.get(key)` first — if the lock exists (the common case on a cache hit), it returns immediately without creating a new `asyncio.Lock`. An earlier version used `dict.setdefault(key, asyncio.Lock())` which allocated a throwaway Lock on every call — this was fixed in code review.
- **Testable in isolation**: `_KeyLockRegistry` is a standalone class — it could be unit-tested independently of the cache layer if needed.

### 📋 Negative

- **Unbounded lock accumulation**: The `_locks` dict grows with every unique cache key, and locks are never evicted. For a long-running process handling many unique prompts, this is a slow memory leak. Each lock is ~500 bytes, so 10,000 unique keys would use ~5 MB — acceptable but worth monitoring. A `pop(key)` after the lock is released (when no waiters remain) would prevent the leak.
- **Not thread-safe outside asyncio**: The design relies on asyncio's single-threaded cooperative multitasking. If the cache layer were ever used with threads (e.g., `asyncio.to_thread()` or a ThreadPoolExecutor), the lock registry would race. This is not a concern for the current architecture, which is purely asyncio-based.
- **Private name leaked across modules**: `_KeyLockRegistry` is imported from `response_cache.py` and `embedding_cache.py` with its `_` prefix intact. This is acceptable within the same package but would violate convention if a module outside `app/cache/` imported it.

### Alternatives Considered

**Keep the duplicated code**: The original reviewer flagged this as a code smell but it was not actioned in the initial PR. Rejected — 24 lines of identical logic across two files is maintenance debt, and the deduplication simplified both files.

**`asyncio.Semaphore` per key**: Use a semaphore(1) instead of `asyncio.Lock`. Rejected — a Lock is the semantically correct primitive for mutual exclusion; a semaphore adds confusion without benefit.

**`dict.setdefault(key, asyncio.Lock())`**: Single-line creation but eagerly evaluates the default argument — creates a throwaway `asyncio.Lock` on every call, even cache hits. Rejected in code review for efficiency.

**Cache-wide single lock**: One global lock for ALL cache operations. Rejected — would serialize unrelated cache lookups (a miss on key "A" would block a hit on key "B"). Per-key locks allow concurrent access to different cache keys.

**Distributed lock (Redis Redlock)**: For multi-process deployments, a distributed lock would prevent stampedes across backend instances sharing a Redis cache. Rejected for v1 — single-process asyncio locks are sufficient for the current deployment model, and Redis's `SETNX` could be added later without changing the `_KeyLockRegistry` interface.
