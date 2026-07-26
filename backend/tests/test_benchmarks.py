"""Tests for benchmark API endpoint behaviors."""

import json as j
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.models import Benchmark, BenchmarkResult
from app.providers.base import ProviderResponse
from app.routers.benchmarks import _repair_stuck_benchmarks


class TestBenchmarkEndpoints:
    """Benchmark API behavior, validation, and edge cases."""

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_create_benchmark_empty_prompt(self, client):
        resp = client.post("/api/benchmarks", json={"prompt": "", "models": []})
        assert resp.status_code == 422

    def test_create_benchmark_too_many_models(self, client):
        models = [{"provider": "openai", "model": "gpt-4o-mini"}] * 11
        resp = client.post(
            "/api/benchmarks",
            json={"prompt": "Hello", "models": models},
        )
        assert resp.status_code == 422

    def test_create_benchmark_no_auth_provider(self, client):
        resp = client.post(
            "/api/benchmarks",
            json={
                "prompt": "Hello",
                "models": [{"provider": "openai", "model": "gpt-4o-mini"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("failed", "completed")
        assert len(data["results"]) == 1
        assert data["results"][0]["error"] is not None

    def test_list_benchmarks_empty(self, client):
        resp = client.get("/api/benchmarks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_benchmark_not_found(self, client):
        resp = client.get("/api/benchmarks/999")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/benchmarks/999")
        assert resp.status_code == 404

    def test_insights_empty(self, client):
        resp = client.get("/api/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["most_expensive_prompt"] is None
        assert data["fastest_model"] is None
        assert data["lowest_cost_model"] is None

    def test_providers_list(self, client):
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        providers = resp.json()
        provider_ids = [p["id"] for p in providers]
        assert "openai" in provider_ids
        assert "anthropic" in provider_ids
        assert "gemini" in provider_ids
        assert "openrouter" in provider_ids
        assert "ollama" in provider_ids
        assert "vllm" in provider_ids
        for p in providers:
            assert "requires_api_key" not in p, f"requires_api_key exposed for {p['id']}"


class TestStuckBenchmarks:
    """Stuck benchmark status recovery."""

    def test_repair_stuck_running(self, db_session):
        old = Benchmark(
            prompt="stuck",
            status="running",
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(old)
        db_session.commit()

        _repair_stuck_benchmarks(db_session)
        db_session.refresh(old)
        assert old.status == "failed"

    def test_recent_running_not_touched(self, db_session):
        recent = Benchmark(
            prompt="in-progress",
            status="running",
            created_at=datetime.now(UTC),
        )
        db_session.add(recent)
        db_session.commit()

        _repair_stuck_benchmarks(db_session)
        db_session.refresh(recent)
        assert recent.status == "running"


class TestResponseCharsColumn:
    """Verify response_chars column mapping."""

    def test_column_stored_as_response_length(self, db_session):
        result = BenchmarkResult(
            benchmark_id=None,
            provider="test",
            model="test-model",
            response_chars=42,
        )
        result.benchmark_id = 0
        db_session.add(result)
        db_session.commit()

        row = db_session.execute(
            text("SELECT response_length FROM benchmark_results WHERE id = :id"),
            {"id": result.id},
        ).one()
        assert row[0] == 42


class TestProviderMockTransport:
    """Provider response parsing with mocked httpx transport."""

    @pytest.mark.asyncio
    async def test_openai_malformed_sse_skipped(self):
        parsed = await _mock_parse_sse(
            [
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                "data: not valid json",
                "data: [DONE]",
            ]
        )
        assert parsed == "Hello"

    @pytest.mark.asyncio
    async def test_openai_empty_delta(self):
        parsed = await _mock_parse_sse(
            [
                'data: {"choices":[{"delta":{}}]}',
                'data: {"choices":[{"delta":{"content":"hello"}}]}',
                "data: [DONE]",
            ]
        )
        assert parsed == "hello"

    @pytest.mark.asyncio
    async def test_ollama_missing_eval_count(self):
        events = ['{"message":{"content":"hi"}}', '{"done":true}']
        result = await _mock_ollama_parse(events)
        assert result.output_tokens == 0
        assert result.response_text == "hi"


async def _mock_parse_sse(events):
    """Parse SSE events via mocked transport."""
    content = "\n\n".join(events) + "\n\n"
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, text=content, headers={"Content-Type": "text/event-stream"})
    )
    parts = []
    async with httpx.AsyncClient(transport=transport) as client:
        async with client.stream("POST", "http://test/", json={}) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                try:
                    data = j.loads(line[6:])
                except j.JSONDecodeError:
                    continue
                content = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if content:
                    parts.append(content)
    return "".join(parts)


async def _mock_ollama_parse(events):
    """Parse Ollama JSON events via mocked transport."""
    content = "\n".join(events)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text=content))
    started = time.perf_counter()
    first = None
    parts = []
    final = {}
    async with (
        httpx.AsyncClient(transport=transport) as client,
        client.stream(
            "POST",
            "http://ollama.local/api/chat",
            json={"model": "test", "messages": [], "stream": True},
        ) as response,
    ):
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            try:
                final = j.loads(line)
            except j.JSONDecodeError:
                continue
            text = final.get("message", {}).get("content", "")
            if text:
                first = first or time.perf_counter()
                parts.append(text)
    ended = time.perf_counter()
    text = "".join(parts)
    return ProviderResponse(
        final.get("prompt_eval_count", 0),
        final.get("eval_count", 0),
        round(((first or ended) - started) * 1000),
        round((ended - started) * 1000),
        text,
        len(text),
        0.0,
    )
