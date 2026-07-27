"""Tests for the cache layer (response cache, embedding cache, keys, backends)."""

import asyncio
import time

import fakeredis.aioredis
import pytest
import redis.asyncio as redis_mod

import app.config as config_mod
from app.cache import (
    BENCHMARK_CONFIG_VERSION,
    embedding_cache_key,
    response_cache_key,
)
from app.cache.cache import (
    InMemoryCache,
    RedisCache,
    _safe_url,
    get_cache,
    reset_cache_singleton,
)
from app.cache.embedding_cache import (
    EmbeddingCache,
    get_embedding_cache,
    reset_embedding_cache_singleton,
)
from app.cache.response_cache import (
    ResponseCache,
    get_response_cache,
    reset_response_cache_singleton,
)
from app.cli import main as cli_main
from app.providers import get_provider
from app.providers.base import ProviderResponse


# ── Fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
async def _reset_cache_singletons():
    """Ensure each test starts with a fresh cache backend and singletons."""
    await reset_cache_singleton()
    await reset_response_cache_singleton()
    await reset_embedding_cache_singleton()
    yield
    await reset_cache_singleton()
    await reset_response_cache_singleton()
    await reset_embedding_cache_singleton()


def _make_response(text="Hello", *, error=None, input_tokens=10, output_tokens=20):
    return ProviderResponse(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        ttft_ms=100,
        total_latency_ms=500,
        response_text=text,
        response_chars=len(text),
        cost=0.001,
        error=error,
    )


def _make_key(prompt="Hello", model="gpt-4o-mini", provider="openai", **kw):
    return response_cache_key(
        provider=provider,
        model=model,
        prompt_template=prompt,
        rendered_prompt=prompt,
        system_prompt="",
        temperature=0.7,
        max_tokens=1000,
        benchmark_config_version=BENCHMARK_CONFIG_VERSION,
        **kw,
    )


# ── Cache keys ──────────────────────────────────────────────────────────
class TestCacheKeys:
    def test_identical_inputs_same_key(self):
        k1 = _make_key("Hello")
        k2 = _make_key("Hello")
        assert k1 == k2

    def test_modified_prompt_different_key(self):
        assert _make_key("Hello") != _make_key("Goodbye")

    def test_different_model_different_key(self):
        assert _make_key("Hello", model="gpt-4o") != _make_key("Hello", model="gpt-4o-mini")

    def test_different_provider_different_key(self):
        assert _make_key("Hello", provider="openai") != _make_key("Hello", provider="anthropic")

    def test_different_temperature_different_key(self):
        k1 = response_cache_key(
            provider="openai",
            model="m",
            prompt_template="p",
            rendered_prompt="p",
            system_prompt="",
            temperature=0.7,
            max_tokens=100,
        )
        k2 = response_cache_key(
            provider="openai",
            model="m",
            prompt_template="p",
            rendered_prompt="p",
            system_prompt="",
            temperature=0.0,
            max_tokens=100,
        )
        assert k1 != k2

    def test_different_system_prompt_different_key(self):
        k1 = response_cache_key(
            provider="openai",
            model="m",
            prompt_template="p",
            rendered_prompt="p",
            system_prompt="be concise",
            temperature=0.7,
            max_tokens=100,
        )
        k2 = response_cache_key(
            provider="openai",
            model="m",
            prompt_template="p",
            rendered_prompt="p",
            system_prompt="",
            temperature=0.7,
            max_tokens=100,
        )
        assert k1 != k2

    def test_key_starts_with_response_prefix(self):
        key = _make_key("Hello")
        assert key.startswith("response:openai:gpt-4o-mini:")

    def test_embedding_key_format(self):
        key = embedding_cache_key(provider="openai", model="text-embedding-3-small", text="hi")
        assert key.startswith("embedding:openai:text-embedding-3-small:")
        # same text → same key
        assert key == embedding_cache_key(
            provider="openai", model="text-embedding-3-small", text="hi"
        )

    def test_embedding_key_text_change(self):
        assert embedding_cache_key(provider="p", model="m", text="a") != embedding_cache_key(
            provider="p", model="m", text="b"
        )

    def test_top_p_changes_key(self):
        k1 = response_cache_key(
            provider="openai",
            model="m",
            prompt_template="p",
            rendered_prompt="p",
            system_prompt="",
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
        )
        k2 = response_cache_key(
            provider="openai",
            model="m",
            prompt_template="p",
            rendered_prompt="p",
            system_prompt="",
            temperature=0.7,
            max_tokens=100,
            top_p=1.0,
        )
        assert k1 != k2


# ── In-memory backend ───────────────────────────────────────────────────
class TestInMemoryBackend:
    async def test_set_get(self):
        cache = InMemoryCache()
        await cache.set("k", b"v", ttl=60)
        assert await cache.get("k") == b"v"

    async def test_miss_returns_none(self):
        cache = InMemoryCache()
        assert await cache.get("missing") is None

    async def test_ttl_expiration(self):
        cache = InMemoryCache()
        await cache.set("k", b"v", ttl=1)
        assert await cache.get("k") == b"v"
        time.sleep(1.1)
        assert await cache.get("k") is None

    async def test_clear_all(self):
        cache = InMemoryCache()
        await cache.set("response:a", b"1", ttl=60)
        await cache.set("embedding:b", b"2", ttl=60)
        removed = await cache.clear()
        assert removed == 2
        assert await cache.count() == 0

    async def test_clear_prefix(self):
        cache = InMemoryCache()
        await cache.set("response:a", b"1", ttl=60)
        await cache.set("response:b", b"2", ttl=60)
        await cache.set("embedding:c", b"3", ttl=60)
        removed = await cache.clear(prefix="response:")
        assert removed == 2
        assert await cache.count() == 1

    async def test_count_excludes_expired(self):
        cache = InMemoryCache()
        await cache.set("k", b"v", ttl=1)
        assert await cache.count() == 1
        time.sleep(1.1)
        assert await cache.count() == 0

    async def test_stats_track_hits_misses(self):
        cache = InMemoryCache()
        await cache.set("k", b"v", ttl=60)
        await cache.get("k")  # hit
        await cache.get("miss")  # miss
        stats = await cache.stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5
        assert stats.avg_lookup_ms >= 0.0


# ── Response cache ──────────────────────────────────────────────────────
class TestResponseCache:
    async def test_identical_prompt_is_hit(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return _make_response("Hello")

        key = _make_key("Hello")
        r1, info1 = await cache.get_or_compute(key, compute)
        r2, info2 = await cache.get_or_compute(key, compute)

        assert calls == 1, "provider called only once"
        assert info1.cache_hit is False
        assert info2.cache_hit is True
        assert info2.cache_type == "response"
        assert info2.provider_latency_ms == 0
        assert r1.response_text == r2.response_text == "Hello"

    async def test_modified_prompt_is_miss(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        await cache.get_or_compute(_make_key("Hello"), lambda: _async(_make_response("Hello")))
        _, info = await cache.get_or_compute(
            _make_key("Goodbye"), lambda: _async(_make_response("Goodbye"))
        )
        assert info.cache_hit is False

    async def test_different_model_is_miss(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        await cache.get_or_compute(
            _make_key("Hello", model="gpt-4o"), lambda: _async(_make_response("A"))
        )
        _, info = await cache.get_or_compute(
            _make_key("Hello", model="gpt-4o-mini"), lambda: _async(_make_response("B"))
        )
        assert info.cache_hit is False

    async def test_ttl_expiration(self):
        cache = ResponseCache(InMemoryCache(), ttl=1)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return _make_response("Hello")

        key = _make_key("Hello")
        await cache.get_or_compute(key, compute)
        time.sleep(1.1)
        _, info = await cache.get_or_compute(key, compute)
        assert info.cache_hit is False
        assert calls == 2, "expired entry forced a second provider call"

    async def test_provider_error_not_cached(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return _make_response("oops", error="timeout")

        key = _make_key("err")
        await cache.get_or_compute(key, compute)
        calls_before = calls
        _, info = await cache.get_or_compute(key, compute)
        assert calls == calls_before + 1, "error response must not be cached"
        assert info.cache_hit is False

    async def test_empty_incomplete_response_not_cached(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return _make_response("", input_tokens=0, output_tokens=0)

        key = _make_key("empty")
        await cache.get_or_compute(key, compute)
        await cache.get_or_compute(key, compute)
        assert calls == 2, "incomplete (empty) response must not be cached"

    async def test_cacheable_false_bypasses_cache(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return _make_response("Hello")

        key = _make_key("nocache")
        await cache.get_or_compute(key, compute, cacheable=False)
        await cache.get_or_compute(key, compute, cacheable=False)
        assert calls == 2, "cacheable=False must always call provider"

    async def test_concurrent_only_one_provider_call(self):
        """Cache stampede prevention: N concurrent requests → 1 provider call."""
        cache = ResponseCache(InMemoryCache(), ttl=60)
        calls = 0
        gate = asyncio.Event()

        async def compute():
            nonlocal calls
            calls += 1
            # Hold the first call so other waiters pile up on the key lock.
            await gate.wait()
            return _make_response("Hello")

        async def fire():
            return await cache.get_or_compute(_make_key("concurrent"), compute)

        # Launch 10 concurrent requests; the first acquires the key lock and
        # blocks on `gate`. The rest wait inside get_or_compute.
        tasks = [asyncio.create_task(fire()) for _ in range(10)]
        await asyncio.sleep(0.05)  # let them all queue up
        gate.set()
        results = await asyncio.gather(*tasks)

        assert calls == 1, f"expected 1 provider call, got {calls}"
        assert all(r.response_text == "Hello" for r, _ in results)
        hits = sum(1 for _, info in results if info.cache_hit)
        # The lock-holder is a miss; the 9 waiters are hits (via re-check).
        assert hits == 9

    async def test_cache_info_latency_fields(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)

        async def compute():
            return _make_response("Hello")

        _, miss_info = await cache.get_or_compute(_make_key("lat"), compute)
        assert miss_info.provider_latency_ms >= 0
        assert miss_info.cache_lookup_ms >= 0
        assert (
            miss_info.total_latency_ms == miss_info.provider_latency_ms + miss_info.cache_lookup_ms
        )

        _, hit_info = await cache.get_or_compute(_make_key("lat"), compute)
        assert hit_info.provider_latency_ms == 0
        assert hit_info.total_latency_ms == hit_info.cache_lookup_ms


# ── Embedding cache ─────────────────────────────────────────────────────
class TestEmbeddingCache:
    async def test_embedding_reuse(self):
        cache = EmbeddingCache(InMemoryCache(), ttl=60)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return [0.1, 0.2, 0.3], 3

        key = embedding_cache_key(provider="openai", model="text-embedding-3-small", text="hi")
        r1 = await cache.get_or_compute(key, compute)
        r2 = await cache.get_or_compute(key, compute)

        assert calls == 1
        assert r1.cache_hit is False
        assert r2.cache_hit is True
        assert r1.vector == r2.vector == [0.1, 0.2, 0.3]
        assert r1.dimension == 3

    async def test_different_text_different_key(self):
        cache = EmbeddingCache(InMemoryCache(), ttl=60)
        await cache.get_or_compute(
            embedding_cache_key(provider="p", model="m", text="a"),
            lambda: _async(([0.1], 1)),
        )
        r = await cache.get_or_compute(
            embedding_cache_key(provider="p", model="m", text="b"),
            lambda: _async(([0.9], 1)),
        )
        assert r.cache_hit is False


# ── Backend fallback ────────────────────────────────────────────────────
class TestRedisFallback:
    async def test_redis_unavailable_falls_back_to_memory(self, monkeypatch):
        # Force a Redis URL that will fail to connect.
        monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")
        # Reload config so the new env is picked up.
        monkeypatch.setattr(config_mod, "settings", config_mod.get_settings())
        backend = await get_cache()
        assert backend.name == "memory"
        # The fallback backend must still function.
        await backend.set("k", b"v", ttl=60)
        assert await backend.get("k") == b"v"

    async def test_no_redis_url_uses_memory(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.setattr(config_mod, "settings", config_mod.get_settings())
        backend = await get_cache()
        assert backend.name == "memory"

    async def test_cache_disabled_uses_memory(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")
        monkeypatch.setenv("CACHE_ENABLED", "false")
        monkeypatch.setattr(config_mod, "settings", config_mod.get_settings())
        backend = await get_cache()
        assert backend.name == "memory"


# ── Redis backend (graceful degradation under errors) ───────────────────
class TestRedisBackendErrors:
    async def test_redis_get_error_returns_none(self):
        class BrokenClient:
            async def get(self, key):
                raise ConnectionError("redis down")

            async def set(self, *a, **k):
                raise ConnectionError("redis down")

            async def delete(self, *a, **k):
                raise ConnectionError("redis down")

            async def info(self, section):
                raise ConnectionError("redis down")

            async def dbsize(self):
                raise ConnectionError("redis down")

            def scan_iter(self, match=None):
                raise ConnectionError("redis down")

            async def flushdb(self):
                raise ConnectionError("redis down")

            async def aclose(self):
                pass

        cache = RedisCache(BrokenClient())
        assert await cache.get("k") is None
        await cache.set("k", b"v", ttl=60)  # must not raise
        stats = await cache.stats()
        assert stats.backend == "redis"


# ── API integration ─────────────────────────────────────────────────────
class TestCacheAPI:
    async def test_cache_stats_endpoint(self, client):
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "backend" in data
        assert "entries" in data
        assert "hit_rate" in data

    async def test_cache_clear_endpoint(self, client):
        resp = client.delete("/api/cache")
        assert resp.status_code == 200
        assert "cleared" in resp.json()


# ── CLI ─────────────────────────────────────────────────────────────────
class TestCLI:
    def test_cli_stats(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        rc = cli_main(["cache", "stats"])
        assert rc == 0

    def test_cli_clear(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        rc = cli_main(["cache", "clear"])
        assert rc == 0

    def test_cli_warm_missing_file(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        rc = cli_main(["cache", "warm", "/nonexistent/benchmark.yaml"])
        assert rc == 1


# ── Helpers ─────────────────────────────────────────────────────────────
async def _async(value):
    """Wrap a value in a coroutine for use as a compute_fn."""
    return value


# ── Redis backend (via fakeredis) ───────────────────────────────────────
class TestRedisBackendReal:
    async def test_redis_set_get_delete(self):
        client = fakeredis.aioredis.FakeRedis()
        cache = RedisCache(client)
        await cache.set("k", b"v", ttl=60)
        assert await cache.get("k") == b"v"
        await cache.delete("k")
        assert await cache.get("k") is None
        stats = await cache.stats()
        assert stats.backend == "redis"
        assert stats.entries >= 0
        await cache.close()

    async def test_redis_clear_prefix_and_flush(self):
        client = fakeredis.aioredis.FakeRedis()
        cache = RedisCache(client)
        await cache.set("response:a", b"1", ttl=60)
        await cache.set("response:b", b"2", ttl=60)
        await cache.set("embedding:c", b"3", ttl=60)
        removed = await cache.clear(prefix="response:")
        assert removed == 2
        assert await cache.get("response:a") is None
        assert await cache.get("embedding:c") == b"3"
        # flush all
        await cache.clear()
        assert await cache.count() == 0
        await cache.close()

    async def test_redis_stats_memory_usage(self):
        client = fakeredis.aioredis.FakeRedis()
        cache = RedisCache(client)
        await cache.set("k", b"v", ttl=60)
        stats = await cache.stats()
        assert stats.backend == "redis"
        assert stats.entries == 1
        # memory_usage falls back to "n/a" when the server omits used_memory_human
        # (e.g. fakeredis); with a real Redis it is a human-readable string.
        assert isinstance(stats.memory_usage, str)
        await cache.close()

    async def test_get_cache_uses_redis_when_available(self, monkeypatch):
        """When redis.from_url returns a working client, get_cache picks Redis."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setattr(config_mod, "settings", config_mod.get_settings())

        fake = fakeredis.aioredis.FakeRedis()

        def _from_url(*args, **kwargs):
            return fake

        monkeypatch.setattr(redis_mod, "from_url", _from_url)
        backend = await get_cache()
        assert backend.name == "redis"
        await backend.set("k", b"v", ttl=60)
        assert await backend.get("k") == b"v"


class TestCacheHelpers:
    def test_safe_url_strips_credentials(self):
        assert _safe_url("redis://user:pass@host:6379/0") == "redis://host:6379/0"
        assert _safe_url("redis://host:6379/0") == "redis://host:6379/0"
        assert _safe_url("") == ""

    async def test_reset_close_swallows_errors(self, monkeypatch):
        """reset_cache_singleton must not raise when close() fails."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.setattr(config_mod, "settings", config_mod.get_settings())

        backend = await get_cache()

        async def boom():
            raise RuntimeError("boom")

        backend.close = boom  # type: ignore[method-assign]
        # Should not raise.
        await reset_cache_singleton()
        assert await get_cache() is not None


class TestEmbeddingCacheExtra:
    async def test_concurrent_only_one_compute(self):
        """Stampede prevention: concurrent embedding requests → 1 compute."""
        cache = EmbeddingCache(InMemoryCache(), ttl=60)
        calls = 0
        gate = asyncio.Event()

        async def compute():
            nonlocal calls
            calls += 1
            await gate.wait()
            return [0.1, 0.2], 2

        key = embedding_cache_key(provider="p", model="m", text="shared")
        tasks = [asyncio.create_task(cache.get_or_compute(key, compute)) for _ in range(8)]
        await asyncio.sleep(0.05)
        gate.set()
        results = await asyncio.gather(*tasks)
        assert calls == 1
        assert sum(r.cache_hit for r in results) == 7  # 1 miss + 7 hits

    async def test_set_failure_does_not_raise(self):
        class BrokenBackend(InMemoryCache):
            async def set(self, key, value, ttl):
                raise RuntimeError("disk full")

        cache = EmbeddingCache(BrokenBackend(), ttl=60)

        async def compute():
            return [0.1], 1

        r = await cache.get_or_compute(
            embedding_cache_key(provider="p", model="m", text="x"), compute
        )
        assert r.cache_hit is False
        assert r.vector == [0.1]

    async def test_corrupt_cached_value_treated_as_miss(self):
        cache = EmbeddingCache(InMemoryCache(), ttl=60)
        # Pre-seed a corrupt entry.
        await cache._backend.set(
            embedding_cache_key(provider="p", model="m", text="bad"), b"not json", ttl=60
        )
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return [0.5], 1

        r = await cache.get_or_compute(
            embedding_cache_key(provider="p", model="m", text="bad"), compute
        )
        assert calls == 1
        assert r.cache_hit is False

    async def test_embedding_singletons(self):
        c1 = await get_embedding_cache()
        c2 = await get_embedding_cache()
        assert c1 is c2


class TestResponseCacheExtra:
    async def test_corrupt_cached_response_treated_as_miss(self):
        cache = ResponseCache(InMemoryCache(), ttl=60)
        await cache._backend.set(_make_key("corrupt"), b"not json", ttl=60)
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            return _make_response("ok")

        _, info = await cache.get_or_compute(_make_key("corrupt"), compute)
        assert calls == 1
        assert info.cache_hit is False

    async def test_store_failure_does_not_raise(self):
        class BrokenBackend(InMemoryCache):
            async def set(self, key, value, ttl):
                raise RuntimeError("write error")

        cache = ResponseCache(BrokenBackend(), ttl=60)

        async def compute():
            return _make_response("ok")

        r, info = await cache.get_or_compute(_make_key("bf"), compute)
        assert r.response_text == "ok"
        assert info.cache_hit is False

    async def test_response_cache_singleton(self):
        c1 = await get_response_cache()
        c2 = await get_response_cache()
        assert c1 is c2

    async def test_inmemory_delete(self):
        cache = InMemoryCache()
        await cache.set("k", b"v", ttl=60)
        await cache.delete("k")
        assert await cache.get("k") is None

    async def test_inmemory_count_with_prefix(self):
        cache = InMemoryCache()
        await cache.set("response:a", b"1", ttl=60)
        await cache.set("embedding:b", b"2", ttl=60)
        assert await cache.count(prefix="response:") == 1
        assert await cache.count(prefix="embedding:") == 1
        assert await cache.count() == 2


# ── End-to-end benchmark caching via the API ────────────────────────────
class TestBenchmarkEndpointCaching:
    """Verify the benchmark API serves identical runs from cache."""

    async def test_identical_runs_second_is_cache_hit(self, client, monkeypatch):
        calls = 0

        async def fake_generate(prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
            nonlocal calls
            calls += 1
            return ProviderResponse(
                input_tokens=12,
                output_tokens=34,
                ttft_ms=50,
                total_latency_ms=200,
                response_text=f"hi {model}",
                response_chars=5,
                cost=0.002,
            )

        # Ollama is always configured — patch its generate to a deterministic fake.
        ollama = get_provider("ollama")
        monkeypatch.setattr(ollama, "generate", fake_generate)

        payload = {
            "prompt": "Say hello",
            "system_prompt": "be concise",
            "temperature": 0.7,
            "max_tokens": 200,
            "models": [{"provider": "ollama", "model": "qwen2.5:0.5b"}],
        }

        # Run 1 — miss (provider called)
        r1 = client.post("/api/benchmarks", json=payload)
        assert r1.status_code == 200
        data1 = r1.json()
        res1 = data1["results"][0]
        assert res1["error"] is None
        assert res1["cache_hit"] in (False, None)
        assert calls == 1

        # Run 2 — identical → hit (provider NOT called again)
        r2 = client.post("/api/benchmarks", json=payload)
        assert r2.status_code == 200
        res2 = r2.json()["results"][0]
        assert res2["error"] is None
        assert res2["cache_hit"] is True
        assert res2["cache_type"] == "response"
        assert res2["provider_latency_ms"] == 0
        assert res2["cache_lookup_ms"] is not None
        # Same output, served from cache
        assert res2["response_text"] == res1["response_text"]
        assert calls == 1, "second identical run must not call the provider"

    async def test_modified_prompt_is_cache_miss(self, client, monkeypatch):
        calls = 0

        async def fake_generate(prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
            nonlocal calls
            calls += 1
            return ProviderResponse(
                input_tokens=5,
                output_tokens=5,
                ttft_ms=10,
                total_latency_ms=20,
                response_text="x",
                response_chars=1,
                cost=0.0,
            )

        ollama = get_provider("ollama")
        monkeypatch.setattr(ollama, "generate", fake_generate)

        client.post(
            "/api/benchmarks",
            json={
                "prompt": "prompt A",
                "models": [{"provider": "ollama", "model": "qwen2.5:0.5b"}],
            },
        )
        r2 = client.post(
            "/api/benchmarks",
            json={
                "prompt": "prompt B",
                "models": [{"provider": "ollama", "model": "qwen2.5:0.5b"}],
            },
        )
        res = r2.json()["results"][0]
        assert res["cache_hit"] in (False, None)
        assert calls == 2, "different prompt must call the provider"

    async def test_cache_false_bypasses_cache(self, client, monkeypatch):
        calls = 0

        async def fake_generate(prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
            nonlocal calls
            calls += 1
            return ProviderResponse(
                input_tokens=5,
                output_tokens=5,
                ttft_ms=10,
                total_latency_ms=20,
                response_text="y",
                response_chars=1,
                cost=0.0,
            )

        ollama = get_provider("ollama")
        monkeypatch.setattr(ollama, "generate", fake_generate)

        payload = {
            "prompt": "no cache please",
            "models": [{"provider": "ollama", "model": "qwen2.5:0.5b"}],
            "cache": False,
        }
        client.post("/api/benchmarks", json=payload)
        client.post("/api/benchmarks", json=payload)
        assert calls == 2, "cache=False must always call the provider"

    async def test_provider_error_not_cached_via_api(self, client, monkeypatch):
        calls = 0

        async def fake_generate(prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
            nonlocal calls
            calls += 1
            return ProviderResponse(
                input_tokens=0,
                output_tokens=0,
                ttft_ms=0,
                total_latency_ms=0,
                response_text="",
                response_chars=0,
                cost=0.0,
                error="timeout",
            )

        ollama = get_provider("ollama")
        monkeypatch.setattr(ollama, "generate", fake_generate)

        payload = {
            "prompt": "will fail",
            "models": [{"provider": "ollama", "model": "qwen2.5:0.5b"}],
        }
        client.post("/api/benchmarks", json=payload)
        client.post("/api/benchmarks", json=payload)
        assert calls == 2, "error responses must not be cached"
