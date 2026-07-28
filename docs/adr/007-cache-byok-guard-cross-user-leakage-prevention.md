# 7. Cache Runtime Guard — Preventing Cache Hits When BYOK Keys Are Active

Date: 2026-07-28

## Status

Accepted (implemented in PR #7; extended in PR #8 with session keys)

## Context

BYOK (Bring Your Own Key) lets users supply their own API keys for provider
calls. Those calls are billed to the user's account and may return different
results than the same prompt run with the server's key (different rate limits,
different model versions, different fine-tuning). If a BYOK request were served
from the shared cache, two problems arise:

1. **Billing leakage**: User A runs `gpt-4o-mini` with their key. The response
   is cached. User B runs the same prompt with *their* key — but gets User A's
   cached result. User A was billed for tokens User B consumed.

2. **Response leakage**: The cached response contains the model's output for
   User A's request. If User A used a confidential prompt, that output is now
   visible to User B through no fault of either user.

The cache layer itself has no concept of "who" made a request — it only sees
deterministic keys over prompt/model/parameters. The guard must therefore live
outside the cache, at the point where BYOK state is known.

## Decision

Add a **runtime guard** in `backend/app/routers/benchmarks.py:run_one()` that
disables cache reads *and* writes when a client-supplied key is present for a
specific provider in a benchmark run.

### The guard (single line)

```python
use_cache = benchmark_req.cache and not client_key
```

This is evaluated **per provider** inside `run_one()`, not per request. In a
multi-model benchmark where some providers use server keys and others use BYOK
keys, the server-key models still benefit from the cache while BYOK models
bypass it entirely.

### Flow

```
run_one(item, benchmark_req)
  │
  ├─ client_key = extract from benchmark_req.client_keys or session store
  │
  ├─ if client_key:
  │     provider = copy.copy(provider)           # isolate from singleton
  │     provider._client_api_key = client_key    # inject for this request only
  │
  ├─ cache_key = response_cache_key(...)         # computed regardless of BYOK
  │
  ├─ use_cache = benchmark_req.cache and not client_key
  │     │
  │     ├─ True  → get_or_compute(key, fn, cacheable=True)
  │     │          • cache HIT  → return cached response
  │     │          • cache MISS → call provider, store response, return
  │     │
  │     └─ False → get_or_compute(key, fn, cacheable=False)
  │                • skips cache read entirely
  │                • calls provider directly
  │                • skips cache write entirely
  │                • returns with CacheInfo() (all defaults — no cache metadata)
```

When `cacheable=False`, `ResponseCache.get_or_compute()` delegates to
`_compute_and_measure()`, which calls the provider and returns the raw result
without touching the cache backend at all:

```python
if not cacheable:
    return await self._compute_and_measure(compute_fn, CacheInfo())
```

This is a **double-sided guard**: a BYOK request can neither read from nor
write to the cache. Even if a stale server-key entry exists for the same
prompt/model/parameters, the BYOK request will never see it.

### Why the guard is in benchmarks.py, not in ResponseCache

`ResponseCache` is a general-purpose utility that wraps any async callable with
caching. It has no knowledge of providers, API keys, or request ownership.
Pushing the BYOK decision into `ResponseCache` would require it to accept an
additional parameter representing "whose request is this?" — adding coupling
that doesn't belong in the cache layer.

The caller (`run_one`) owns the decision because it alone knows:

- Whether a client key is present
- Whether that key is per-request or session-scoped
- Whether the provider supports BYOK at all (`provider.byok_eligible`)

### Phase 2 extension — session keys

In PR #8, the guard was extended to also check session-scoped keys:

```python
if not client_key and benchmark_req._session_id:
    store = get_session_store()
    session_keys = store.get_keys(benchmark_req._session_id)
    if session_keys:
        client_key = session_keys.get(item.provider)
```

The guard line itself (`use_cache = benchmark_req.cache and not client_key`)
didn't change — it only needed the `client_key` variable to be populated from
the new source. The cache bypass logic is source-agnostic.

### What about the embedding cache?

The embedding cache (`EmbeddingCache.get_or_compute()`) has no `cacheable`
parameter and no BYOK guard. Embeddings currently use only server-configured
providers. If BYOK support is added for embeddings, the same guard pattern
will need to be replicated there.

### Test coverage

The backend test suite includes BYOK-cache isolation tests
(`test_cache.py::test_byok_skips_cache_write_and_read`) that verify:

- A BYOK request never stores a result in the cache
- A BYOK request never retrieves a previously cached server-key result
- The `CacheInfo` returned for a BYOK request has all default (zero/null) values

## Consequences

### Positive

- **Provably correct**: The guard is a simple boolean — `not client_key`. There
  is no key hashing, no cache-key manipulation, no eviction logic. The cache is
  either on or off for each provider in each benchmark run.
- **Per-provider granularity**: Mixed BYOK/server benchmarks work correctly.
  Running `openai` with a BYOK key and `ollama` with the server key in the same
  benchmark run caches the Ollama result but not the OpenAI result.
- **No stale cache attack surface**: A BYOK request physically cannot read from
  or write to the cache. There is no path where User B's request returns User
  A's cached output.
- **Source-agnostic**: The guard works identically for per-request keys,
  session keys, and any future key-injection mechanism — as long as `client_key`
  is set before the cache decision.
- **Zero overhead for server-key users**: When no BYOK key is present,
  `use_cache` defaults to `benchmark_req.cache` (normally `True`). The cache
  works exactly as it did before BYOK was added.

### Negative

- **Cache key computed unnecessarily**: `response_cache_key()` is called before
  the `use_cache` check. When BYOK is active, this key is computed but never
  used. This is a minor CPU waste (SHA-256 over ~500 bytes, ~1 µs) but avoids
  restructuring the function flow. A future optimization could move the key
  computation inside the `use_cache` branch.
- **No cache for BYOK users**: A BYOK user running the same prompt twice with
  their own key will call the provider twice. The cache could theoretically be
  safe for the same user's repeated requests (same key = same billing account),
  but the guard is conservative — it disables caching entirely for any client
  key. Session-scoped caching (keyed by session ID) could be added later
  without changing the guard logic.
- **Embedding cache gap**: The embedding cache has no BYOK guard. If embeddings
  ever support client-supplied keys, the same guard pattern must be replicated
  in `EmbeddingCache` (or its caller). This is documented here as a known
  future task.

### Alternatives Considered

**Key-hash in cache key**: Include `sha256(client_key)` in the cache key so
BYOK results are cached per-user. Rejected — a key hash is effectively a user
fingerprint. Two users with different keys can never share cache entries,
negating most of the cache's value, and a hash collision would cause the exact
billing-leakage bug this guard prevents. Simply disabling the cache is simpler
and provably correct. (Also documented in ADR-003.)

**Cache key isolation with session ID**: When a session key is active, include
`session_id` in the cache key. This would allow session-scoped caching — the
same user's repeated requests within a session would hit the cache. Deferred
— adds complexity (session ID in cache key, session-gated eviction) for
marginal benefit in Phase 2.

**Purge matching cache entries on BYOK request**: Before running a BYOK
request, evict any existing cache entry for the same prompt/model/parameters.
Rejected — a purge does not prevent the write side (the BYOK result being
cached), and it introduces a race condition (a concurrent server-key request
could re-populate the entry between purge and read).

**Guard inside `ResponseCache`**: Pass an `owner_id` parameter to
`get_or_compute()` and let the cache layer decide. Rejected — couples the
general-purpose cache to domain concepts (API keys, user identity). The caller
making the decision is cleaner and easier to test.

**Always disable cache for BYOK-eligible providers**: If a provider *could*
accept a BYOK key, disable caching even when no key is supplied. Rejected —
unnecessarily penalizes server-key users of BYOK-eligible providers. The guard
only fires when a key is *actually* present.
