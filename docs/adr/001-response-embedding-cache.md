# 1. Response & Embedding Cache Layer

Date: 2026-07-28

## Status

Accepted

## Context

PromptBench runs benchmarks by sending identical prompts to multiple LLM providers. Each run incurs provider latency (300 ms – 30 s) and API cost. Users frequently re-run the same benchmark with minor prompt tweaks, which semantically produce identical queries for most models. Without caching:

- Every benchmark run calls every provider for every model, even when the identical query was already executed seconds earlier.
- Provider cost is paid repeatedly for the same input/output.
- Benchmark results are non-deterministic in practice — identical logical requests may return different responses across runs, complicating A/B comparison.

We also anticipate an embedding comparison feature (benchmarking embedding quality across models), where the same text would be embedded by multiple providers repeatedly.

## Decision

Implement a **shared cache layer** across all providers with the following design:

### 1. Deterministic cache keys

Cache keys are SHA-256 digests over canonical JSON of the full logical request:

```
response:{provider}:{model}:{sha256(payload)}
embedding:{provider}:{model}:{sha256(text)}
```

The payload includes: provider, model, prompt template, rendered prompt, system prompt, temperature, max_tokens, top_p, and a `BENCHMARK_CONFIG_VERSION` constant. Bumping the version invalidates all keys.

Timestamps and volatile data are deliberately excluded — the same logical request always maps to the same key.

### 2. Redis primary, in-memory fallback

- **Redis** (`redis://`) is the primary backend, configured via `REDIS_URL`.
- If Redis is unreachable at startup, the app **transparently falls back** to a process-local in-memory TTL cache without crashing. The backend is chosen once at first use and reused for the process lifetime.
- A no-op in-memory backend is used when `CACHE_ENABLED=false`.

### 3. Cache stampede prevention

Per-key `asyncio.Lock` objects guarantee that N concurrent requests for the same key trigger exactly **one** provider call. The lock-holder calls the provider; the remaining (N − 1) waiters re-check the cache after the lock is released and receive the freshly stored result.

### 4. TTL strategy

| Entry type | Default TTL | Env override |
|---|---|---|
| Response | 30 min (`CACHE_TTL_RESPONSE`) | Yes |
| Embedding | 24 h (`CACHE_TTL_EMBEDDING`) | Yes |

### 5. Never cached

- Provider errors (`ProviderResponse.error` set)
- Incomplete/timeout responses (no output and no tokens)
- Streaming responses before completion
- Requests with `cache=false`

### 6. Visibility

- Every `BenchmarkResult` records `cache_hit`, `cache_type`, `cache_lookup_ms`, and `provider_latency_ms`.
- `GET /api/cache/stats` and `DELETE /api/cache` expose cache state.
- `promptbench cache stats|clear|warm` CLI provides operational access.
- An Alembic migration (`0002_add_cache_metrics`) adds cache columns to `benchmark_results`.

### 7. Modular design

The cache layer works through the shared `BaseProvider.generate` interface — individual providers are unaware of caching. A `ResponseCache` wraps the provider call path; an `EmbeddingCache` wraps embedding generation. Both rely on the abstract `CacheBackend` interface (`InMemoryCache` or `RedisCache`).

## Consequences

### 📋 Positive

- **Repeated benchmark runs are sub-millisecond** on cache hit instead of seconds.
- **Provider cost is $0** when results are served from cache.
- **Deterministic benchmark results** — same logical request always produces the same cached output within the TTL window, making A/B prompt comparison reliable.
- **Graceful degradation** — Redis unavailability never crashes the application.
- **Cache statistics visible** via API and CLI, enabling operational monitoring.
- **Cache warming** via `promptbench cache warm <benchmark.yaml>` enables pre-population before critical benchmark runs.

### 📋 Negative

- **Staleness**: Cached responses are frozen in time. If a model is updated server-side within the TTL window, cached results become stale. Mitigated by the 30-minute default TTL and the `BENCHMARK_CONFIG_VERSION` escape hatch.
- **Memory pressure**: The in-memory fallback stores all entries in process-local dicts — fine for development and small deployments, but large-scale production use requires Redis.
- **Key lock memory**: Per-key asyncio.Lock objects accumulate indefinitely in `_key_locks` dictionaries. For long-running processes with many unique keys, this is a slow memory leak. A future cleanup mechanism (e.g., `pop` after lock release) should be added.
- **No distributed invalidation**: When running multiple backend instances, clearing the cache on one instance does not affect others unless Redis is used as the shared backend.

### Alternatives Considered

**No caching (status quo)**: Simpler but wasteful — every benchmark run pays full latency and cost regardless of repetition.

**Per-provider caching**: Each provider ships its own cache. Rejected because it duplicates stampede-prevention logic and key design across providers, and would make the embedding cache a separate concern.

**Cache-aside with manual invalidation**: Rejected for v1 — adding a manual invalidation API and cache-busting UX adds complexity without measurable benefit at this stage. The TTL-based approach is sufficient.

**Only Redis (no fallback)**: Rejected because it would make the app crash-loop if Redis is misconfigured or temporarily down. The in-memory fallback keeps the app functional in all environments.

**Disk-based cache (e.g., SQLite)**: Rejected because Redis provides sub-millisecond lookups with built-in TTL eviction, and the in-memory fallback already covers Redis-less deployments.
