# Caching

PromptBench caches LLM responses and embeddings to make repeated benchmark
runs **faster, cheaper, and deterministic**. The cache layer is modular and
works across every benchmark provider.

- Repeated benchmark runs are served from cache — no provider API call.
- Provider costs drop to **$0** for cached results.
- Cache hits/misses are recorded on every benchmark result and surfaced in
  the report and the CLI.

---

## Architecture

```
            ┌──────────────────────────────────────────────┐
            │  Benchmark request (provider, model, params)  │
            └──────────────────────┬───────────────────────┘
                                   │
                       response_cache_key()  →  SHA-256 digest
                                   │
                          ┌────────▼────────┐
                          │  CacheBackend   │  ← Redis (primary)
                          │  get / set / TTL │  ← In-memory (fallback)
                          └────────┬────────┘
                                   │
                        hit? ───────┼─────── miss?
                          │                  │
                   return cached       per-key asyncio.Lock
                   cache_hit=true            │
                                     provider.generate()
                                     store (TTL=30m)
                                     return cache_hit=false
```

### Package layout

```
backend/app/cache/
├── __init__.py        # Public API
├── cache.py           # CacheBackend ABC, RedisCache, InMemoryCache, get_cache()
├── keys.py            # response_cache_key(), embedding_cache_key()
├── response_cache.py  # ResponseCache + stampede prevention + CacheInfo
└── embedding_cache.py # EmbeddingCache
```

Both backends implement the same async `CacheBackend` interface, so callers
never need to know which one is active.

### Redis with in-memory fallback

On startup (`get_cache()`) PromptBench tries to connect to Redis. If Redis is
unreachable — no server, wrong URL, network down — it **transparently falls
back** to a process-local in-memory cache and logs a warning. The application
never crashes because of caching infrastructure.

Individual Redis operation errors (mid-run connection blips) are caught and
treated as cache misses, so a Redis hiccup degrades gracefully to a provider
call rather than a failed benchmark.

---

## Cache key design

Keys are deterministic **SHA-256** digests over the *logical* request inputs.
They never include timestamps or other volatile data, so the same benchmark
configuration always produces the same key — enabling reproducible, cached
runs.

### Response cache key

`response:{provider}:{model}:{sha256(payload)}`

The payload is canonical JSON (`sort_keys=True`, compact separators) over:

| Field                       | Source                                  |
| --------------------------- | --------------------------------------- |
| `provider`                  | provider id (e.g. `openai`)             |
| `model`                     | model id (e.g. `gpt-4o-mini`)           |
| `prompt_template`           | the prompt template                     |
| `rendered_prompt`           | the final rendered prompt sent          |
| `system_prompt`             | system prompt                           |
| `temperature`               | sampling temperature                    |
| `max_tokens`                | max output tokens                       |
| `top_p`                     | nucleus sampling (optional)             |
| `config_version`            | `BENCHMARK_CONFIG_VERSION` constant     |

Bumping `BENCHMARK_CONFIG_VERSION` (in `app/cache/keys.py`) invalidates all
existing entries by changing every key — use this when the benchmark request
shape changes in a backwards-incompatible way.

### Embedding cache key

`embedding:{provider}:{model}:{sha256(text)}`

---

## TTL strategy

| Cache     | Default TTL | Env var                |
| --------- | ----------- | ---------------------- |
| Response  | 30 minutes  | `CACHE_TTL_RESPONSE`   |
| Embedding | 24 hours    | `CACHE_TTL_EMBEDDING`  |

TTLs are configurable via environment variables (in seconds).

---

## Invalidation rules

The cache is **opt-in per request** and never stores bad results.

**Never cached:**

- Provider errors (`ProviderResponse.error` set)
- Timeout / incomplete responses (no output text **and** no tokens)
- Streaming responses before completion (only fully-assembled responses are cached)
- Requests explicitly marked `cache=false` (the `BenchmarkCreate.cache` field)

**Explicit invalidation:**

- `promptbench cache clear` — flush all entries
- `promptbench cache clear --prefix response:` — flush only response entries
- `DELETE /api/cache?prefix=embedding:` — via the API
- TTL expiration (automatic)
- `BENCHMARK_CONFIG_VERSION` bump (changes all keys)

---

## Redis configuration

Add to `backend/.env` (or your environment):

```bash
# Leave empty to use the in-memory backend (default).
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_TTL_RESPONSE=1800     # 30 minutes
CACHE_TTL_EMBEDDING=86400   # 24 hours
```

The Docker Compose stack includes a Redis 7 service and wires
`REDIS_URL=redis://redis:6379/0` into the backend automatically.

Set `CACHE_ENABLED=false` to disable caching entirely (requests always call
the provider; the in-memory no-op backend is used).

---

## Benchmark metrics

Each `BenchmarkResult` now records cache metadata so reports can compare
cached vs. uncached runs:

| Field                 | Description                                        |
| --------------------- | -------------------------------------------------- |
| `cache_hit`           | `true` / `null` (null = miss or error row)         |
| `cache_type`          | `response`, `embedding`, or `null`                 |
| `cache_lookup_ms`     | time spent checking the cache                      |
| `provider_latency_ms` | time spent calling the provider (`0` on a hit)     |
| `total_latency_ms`    | end-to-end latency (lookup + provider)             |

These fields are exposed in the `ResultOut` schema and the `/api/benchmarks`
endpoints.

### Example report

```
Benchmark Results — Run 1
  Provider latency: 1820 ms
  Cache: MISS

Benchmark Results — Run 2  (identical)
  Provider latency: 0 ms
  Cache lookup:   4 ms
  Cache: HIT
  Speedup:        455×
  Tokens saved:   100%
  Estimated cost saved: $0.013
```

---

## CLI

```bash
promptbench cache stats
promptbench cache clear [--prefix PREFIX]
promptbench cache warm <benchmark.yaml>
```

`cache warm` runs a benchmark definition (JSON or YAML) to populate the cache
so subsequent benchmark runs are served from cache without a cold miss.

Example `benchmark.yaml`:

```yaml
prompt: "Summarize the following text: ..."
system_prompt: "be concise"
temperature: 0.7
max_tokens: 500
models:
  - provider: openai
    model: gpt-4o-mini
  - provider: anthropic
    model: claude-3-5-haiku-20241022
```

`cache stats` output:

```
PromptBench Cache Statistics
========================================
  Backend:          redis
  Entries:          142
  Hits:             38
  Misses:           12
  Hit rate:         76.0%
  Avg lookup:       1.23 ms
  Memory usage:     2.4M
```

The same statistics are available via `GET /api/cache/stats`.

---

## Cache-stampede prevention

When N concurrent requests arrive for the same cache key (e.g. the same model
in a parallel benchmark), a **per-key asyncio lock** guarantees only **one**
provider call is made. The remaining requests wait, then re-check the cache
(which the first caller just populated) and return the cached result. This
prevents thundering-herd cost spikes on cold or expired keys.

---

## Performance (before / after)

For an identical benchmark run against a single model:

| Metric              | First run (miss) | Second run (hit) |
| ------------------- | ---------------- | ---------------- |
| Provider API call   | yes              | **no**           |
| Latency             | ~1820 ms         | ~4 ms            |
| Tokens billed       | full             | **0**            |
| Cost                | $0.013           | **$0.000**       |
| Speedup             | —                | **~455×**        |

The exact numbers depend on the model and provider; the cache lookup itself is
sub-millisecond for the in-memory backend and 1–3 ms for Redis over the
network.

---

## Future improvements

- **Semantic cache** — use embeddings to serve near-duplicate prompts from
  cache (similarity threshold), reducing misses on paraphrased prompts.
- **Distributed cache coordination** — share hit/miss counters and lookup
  latencies across multiple backend replicas via Redis (currently per-process
  for the in-memory backend, shared when Redis is used).
- **Cache warming schedules** — pre-populate common benchmark configurations
  on a schedule via `promptbench cache warm`.
- **Tiered TTLs** — longer TTLs for deterministic (temperature=0) runs,
  shorter for creative sampling.
- **Cache key versioning per provider** — allow individual providers to
  declare their own config version when their API behavior changes.
