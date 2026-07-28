# 5. Cache Key Design — seed, response_format, and Frontend Visibility

Date: 2026-07-28

## Status

Accepted

## Context

ADR-001 established deterministic SHA-256 cache keys for response caching. The initial implementation included provider, model, prompt, system prompt, temperature, max_tokens, top_p, and a config version in the key payload. However, two additional parameters — `seed` and `response_format` — can materially affect model output and were omitted from the key. This omission meant that changing `seed` or `response_format` would return a stale cached response from the wrong parameters.

Additionally, the frontend had no cache visibility. Users running a benchmark twice could not confirm whether the second run was served from cache, how much latency was saved, or which cache backend was active. The `cache_hit`, `cache_type`, `cache_lookup_ms`, and `provider_latency_ms` fields were stored in the database but never surfaced in the UI.

## Decision

### 1. Add `seed` and `response_format` to the cache key payload

Both parameters are now included in the canonical JSON payload that feeds the SHA-256 digest:

```python
payload: dict = {
    ...
    "seed": seed,               # int | None  — None serializes to null
    "response_format": response_format,  # dict | None
    ...
}
```

**Serialization**: `None` values serialize to JSON `null`, so `seed=None` and `seed=0` produce different hashes. This is intentional — an unspecified seed and an explicit seed of zero have different semantics across providers (OpenAI treats `seed=0` as a specific deterministic seed; omitting it leaves the sampling non-deterministic). Similarly, `response_format=None` (plain text) and `response_format={"type": "json_object"}` (structured output) produce different keys.

**Backward compatibility**: Existing cached entries keyed under the old format (without `seed`/`response_format` fields) naturally miss against the new key format, which is the desired behavior — they would have been stale for any request that now includes these fields.

### 2. Expose cache metrics in the BenchmarkResult schema

Every result row now includes four nullable cache fields:

| Field | Type | Description |
|---|---|---|
| `cache_hit` | `bool \| null` | `true` = served from cache, `false` = miss, `null` = legacy/error |
| `cache_type` | `str \| null` | `"response"`, `"embedding"`, or `null` |
| `cache_lookup_ms` | `int \| null` | Time spent checking/pulling from cache |
| `provider_latency_ms` | `int \| null` | Time spent calling the provider (`0` on miss from wall-clock, preserved from first run on hit) |

These fields are nullable to support legacy benchmark results created before the cache schema migration. The frontend uses `null` to distinguish "cache was not involved" (legacy) from "cache was active and this was a miss" (`cache_hit: false`).

### 3. Preserve original provider latency on cache hits

When a response is served from cache, `provider_latency_ms` retains the **original provider call time** from the first run (deserialized from `response.total_latency_ms` in the cached payload). This enables the frontend to compute:

- **Latency reduction %**: `((original_provider_time − cache_lookup_time) / original_provider_time) × 100`
- **Latency saved**: `original_provider_time − cache_lookup_time`
- **Speedup multiplier**: `original_provider_time / cache_lookup_time`

Without this preservation, every cache hit would show `provider_latency_ms = 0`, making it impossible to quantify how much time the cache actually saved.

### 4. Exclude cache hits from history cost aggregation

The `/api/benchmarks` history endpoint sums costs across all results. If cache hits retained the original provider cost, the aggregate would double-count — showing cost for runs that incurred zero new spend. The fix: the history `total_cost` sum now filters out cache hits:

```python
total_cost=sum(r.cost or 0 for r in b.results if not r.cache_hit)
```

Cache hits still store the original cost in their `cost` field so the detail page can show "Cost avoided: $X."

### 5. Frontend cache visibility

Three UI additions to `BenchmarkResults.tsx` (later extracted into `BenchmarkCacheSection.tsx`):

**a. Cache status badges**: Every result in the table shows one of:
- **Cache hit** (emerald) — served from cache
- **Cache miss** (default) — provider was called
- **Cache disabled** (secondary) — caching was not active or result is legacy

**b. Cache performance comparison card**: A table and summary cards showing provider latency, cache lookup time, total latency, and cost per provider/model. For cache hits, the card displays latency reduction %, latency saved, and cost avoided.

**c. Latency breakdown chart**: A stacked bar chart comparing provider latency vs cache lookup time per model.

**d. Active cache backend badge**: The cache performance card header shows which backend is active ("redis" or "memory"), fetched from `GET /api/cache/stats`.

### 6. Component extraction

The cache section was extracted into a standalone `BenchmarkCacheSection.tsx` component (ADR-004's Divergent Change fix) with two exports:
- `CacheBadge` — reusable cache status badge used in both the results table and the comparison table
- `BenchmarkCacheSection` — the full cache comparison section with an internal `null` guard (returns nothing when no cache metrics exist)

## Consequences

### 📋 Positive

- **Complete cache key coverage**: Every parameter that can affect model output is part of the key. No false cache hits from mismatched `seed` or `response_format`.
- **Quantifiable cache savings**: Users can see exactly how much latency and cost the cache saved, making the feature's value tangible.
- **Graceful legacy handling**: All cache fields are nullable — pre-migration benchmark rows render without errors and without cache badges.
- **Clean component boundary**: Cache UI lives in its own component with a clear props interface (`results`, `cacheBackend`), reducing the parent component by ~70 lines.
- **Accurate billing history**: The history list shows only actual provider spend, not cached-result costs.

### 📋 Negative

- **Cache key bloat**: Adding more fields to the payload increases key length and subtlety of key-miss behavior. A future `BENCHMARK_CONFIG_VERSION` bump remains the escape hatch for incompatible key changes.
- **provider_latency_ms dual meaning**: On cache misses, `provider_latency_ms` is wall-clock measured time (from `response.total_latency_ms`). On cache hits, it's the original run's time. The frontend must handle both cases correctly, and the distinction is not visible from the field name alone.
- **cacheStats fetch on every page load**: The `useQuery` for `/api/cache/stats` fires on every BenchmarkResults mount, even for legacy benchmarks where the cache section never renders. Mitigated by a 60-second `staleTime`.

### Alternatives Considered

**Add seed/response_format as separate key components**: Rejected — bundling them into the canonical JSON payload is simpler, more extensible, and matches how all other parameters are handled.

**Store cost = 0 for cache hits in DB**: Rejected — would lose the original cost needed for "cost avoided" display and historical audit. The history endpoint filter achieves the same result without data loss.

**Add a `cache_enabled` flag to BenchmarkResult**: Rejected — `cache_hit` already encodes the three states (hit, miss, not involved) via `true`/`false`/`null`. Adding a fourth field would complicate the schema without adding expressiveness.

**Always set `provider_latency_ms = 0` on hits**: Rejected — makes latency savings invisible. Preserving the original value is a single-line change in `response_cache.py` that enables the entire savings display.
