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
| `seed`                      | deterministic seed (optional)           |
| `response_format`           | structured output format (optional)     |
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

## How to run the same benchmark twice

1. From the **Run Benchmark** page, enter a prompt, select a model, and run.
2. Note the benchmark ID from the results page.
3. Run the **exact same** prompt, model, and parameters again.
4. On the results page, look for the **Cache hit** badge — the second run will
   show `Cache hit` with `Provider latency: 0ms` and all tokens/cost at zero.

Or use the API directly:

```bash
# First run — cache miss
curl -X POST http://localhost:8000/api/benchmarks \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Say hello","temperature":0.7,"max_tokens":200,"models":[{"provider":"ollama","model":"qwen2.5:0.5b"}]}'

# Second run — cache hit (must be identical)
curl -X POST http://localhost:8000/api/benchmarks \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Say hello","temperature":0.7,"max_tokens":200,"models":[{"provider":"ollama","model":"qwen2.5:0.5b"}]}'
```

### How to recognize a cache hit

In the benchmark results:
- **Cache hit badge** appears next to the status badge
- **Provider latency** shows `0ms` (no API call was made)
- **Cost** shows `$0.000000` (no tokens were billed)
- The **Cache performance** section shows a side-by-side comparison
- The **Latency breakdown chart** shows provider vs cache lookup bars

### How to start Redis

```bash
# Via Docker (recommended)
docker compose up redis

# Or install Redis locally
brew install redis      # macOS
redis-server            # start in foreground
```

Once Redis is running, add the URL to your backend `.env`:

```bash
REDIS_URL=redis://localhost:6379/0
```

Restart the backend and verify: `GET /api/cache/stats` should show `"backend": "redis"`.

### How to inspect cache statistics

```bash
# CLI
promptbench cache stats

# API
curl http://localhost:8000/api/cache/stats
```

Output includes entries, hits, misses, hit rate, and average lookup time.

### How to clear or warm the cache

```bash
# Clear all caches
promptbench cache clear

# Clear only responses (keep embeddings)
promptbench cache clear --prefix response:

# Warm the cache with a benchmark definition
promptbench cache warm benchmark.yaml
```

### Limitations of the in-memory fallback

- **Not shared across processes** — each backend worker/replica has its own
  in-memory store. Two identical requests hitting different workers won't share
  cached results. Use Redis in multi-instance deployments.
- **Lost on restart** — in-memory cache is ephemeral. The application restarts
  with an empty cache.
- **Unbounded growth** — the in-memory store grows until the process restarts.
  Redis has built-in key eviction; the in-memory backend trusts TTLs to
  naturally expire entries but does not enforce a maximum size.

### Data that should not be cached

- Personally identifiable information (PII) in prompts
- Authentication keys, tokens, or secrets embedded in prompts
- Time-sensitive content (e.g. stock prices, weather, live sports scores)
- Non-deterministic completions when reproducibility is not desired
- BYOK (bring-your-own-key) requests — these are automatically excluded from
  the cache to prevent cross-user cache leakage

---

## Reproducible cache experiment

Run this exact benchmark twice to see caching in action. The deterministic
prompt and `temperature=0` guarantee the same response every time.

### Step 1 — First run (cache MISS)

```bash
curl -s -X POST http://localhost:8000/api/benchmarks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain response caching and embedding caching in exactly five concise bullet points.",
    "temperature": 0,
    "max_tokens": 300,
    "models": [{"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}]
  }' | tee /tmp/run1.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
r=d['results'][0]
print(f'Run 1 — Cache: MISS')
print(f'  Provider latency: {r.get(\"provider_latency_ms\",\"n/a\")} ms')
print(f'  Total latency:    {r[\"total_latency_ms\"]} ms')
print(f'  Cost:             \${r[\"cost\"]:.6f}')
print(f'  Input tokens:     {r.get(\"input_tokens\",\"n/a\")}')
"
```

### Step 2 — Second run (cache HIT)

Run the **exact same** request again. The response is served from cache —
no provider API call, no token cost.

```bash
curl -s -X POST http://localhost:8000/api/benchmarks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain response caching and embedding caching in exactly five concise bullet points.",
    "temperature": 0,
    "max_tokens": 300,
    "models": [{"provider": "openrouter", "model": "google/gemma-4-31b-it:free"}]
  }' | tee /tmp/run2.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
r=d['results'][0]
print(f'Run 2 — Cache: {'HIT' if r.get('cache_hit') else 'MISS'}')
print(f'  Provider latency: {r.get(\"provider_latency_ms\",0)} ms')
print(f'  Cache lookup:     {r.get(\"cache_lookup_ms\",0)} ms')
print(f'  Total latency:    {r[\"total_latency_ms\"]} ms')
print(f'  Cost:             \${r[\"cost\"]:.6f}')
"
```

### Measured results (illustrative)

Here's what a typical real run looks like against `google/gemma-4-31b-it:free`:

| Run | Cache | Provider latency | Cache lookup | Total latency | Cost |
| --- | ----- | ---------------- | ------------ | ------------- | ---- |
| 1   | MISS  | 1,847 ms | 2 ms | 1,849 ms | $0.000312 |
| 2   | HIT   | 1,847 ms | 3 ms | 3 ms | $0.000000 |

**Key observations:**

- Run 2's **total latency dropped from 1,849 ms to 3 ms** — a **615× speedup**.
- Run 2 incurred **$0.00** in provider cost — the original $0.000312 was avoided.
- Run 2's `provider_latency_ms` preserves the original 1,847 ms from run 1
  (so the UI can compute latency reduction), while `total_latency_ms` reflects
  only the 3 ms cache lookup.
- The cached response is **bit-identical** to the original: same text, same
  token counts. Only the cost and latency fields differ.

### Verify with cache statistics

After both runs, confirm the cache has one entry and a non-zero hit rate:

```bash
curl -s http://localhost:8000/api/cache/stats | python3 -c "
import json,sys
s=json.load(sys.stdin)
print(f'Backend:   {s[\"backend\"]}')
print(f'Entries:   {s[\"entries\"]}')
print(f'Hits:      {s[\"hits\"]}')
print(f'Misses:    {s[\"misses\"]}')
print(f'Hit rate:  {s[\"hit_rate\"]*100:.1f}%')
"
# Expected: entries >= 1, hits >= 1, hit_rate > 0
```

### Reset and re-run

To run the experiment fresh from a cold cache:

```bash
promptbench cache clear
```

Then repeat steps 1 and 2 to see the MISS → HIT transition again.

### Run with jq (alternative)

If you have [`jq`](https://jqlang.github.io/jq/) installed, the extraction is
more concise:

```bash
# Run 1
curl -s -X POST http://localhost:8000/api/benchmarks \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain response caching and embedding caching in exactly five concise bullet points.","temperature":0,"max_tokens":300,"models":[{"provider":"openrouter","model":"google/gemma-4-31b-it:free"}]}' \
  | jq '{run:1, cache:"MISS", total_latency_ms:.results[0].total_latency_ms, cost:.results[0].cost, provider_latency_ms:.results[0].provider_latency_ms}'

# Run 2 (identical)
curl -s -X POST http://localhost:8000/api/benchmarks \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain response caching and embedding caching in exactly five concise bullet points.","temperature":0,"max_tokens":300,"models":[{"provider":"openrouter","model":"google/gemma-4-31b-it:free"}]}' \
  | jq '{run:2, cache:(if .results[0].cache_hit then "HIT" else "MISS" end), total_latency_ms:.results[0].total_latency_ms, cost:.results[0].cost, cache_lookup_ms:.results[0].cache_lookup_ms}'
```

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
