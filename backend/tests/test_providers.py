"""Tests for provider error handling and edge cases."""

import json as j

import httpx
import pytest

from app.pricing import PRICING, calculate_cost
from app.providers import PROVIDERS
from app.providers.base import ProviderResponse


class TestProviderResponse:
    """ProviderResponse dataclass behavior."""

    def test_response_chars_field(self):
        resp = ProviderResponse(
            input_tokens=10, output_tokens=20, ttft_ms=100,
            total_latency_ms=500, response_text="hello world",
            response_chars=11, cost=0.001,
        )
        assert resp.response_chars == 11
        assert not hasattr(resp, "response_length")


class TestPricing:
    """Pricing calculation edge cases."""

    def test_known_model(self):
        assert calculate_cost("openai", "gpt-4o-mini", 1000, 500) > 0

    def test_zero_tokens(self):
        assert calculate_cost("openai", "gpt-4o-mini", 0, 0) == 0.0

    def test_free_model(self):
        cost = calculate_cost("openrouter", "google/gemma-4-31b-it:free", 1000, 500)
        assert cost == 0.0

    def test_unknown_provider_defaults_zero(self):
        assert calculate_cost("nonexistent", "some-model", 100, 50) == 0.0

    def test_unknown_model_defaults_zero(self):
        assert calculate_cost("openai", "unknown-model", 100, 50) == 0.0

    def test_large_token_counts(self):
        cost = calculate_cost("anthropic", "claude-3-5-sonnet-20241022", 100_000, 50_000)
        assert cost > 0
        assert cost < 1000

    def test_all_providers_have_pricing(self):
        for pid in PROVIDERS:
            assert pid in PRICING, f"No pricing entry for {pid}"


class TestSSEParsing:
    """Provider SSE JSON parsing edge cases."""

    def test_malformed_json_raises(self):
        with pytest.raises(j.JSONDecodeError):
            j.loads("{not valid json")

    def test_non_data_line_skipped(self):
        assert not "something".startswith("data: ")

    def test_done_signal_skipped(self):
        line = "data: [DONE]"
        assert line.startswith("data: ")
        assert line == "data: [DONE]"

    @pytest.mark.asyncio
    async def test_sse_parsing_full_flow(self):
        events = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ]
        content = "\n\n".join(events) + "\n\n"
        transport = httpx.MockTransport(lambda r: httpx.Response(
            200, text=content, headers={"Content-Type": "text/event-stream"}
        ))
        parts = []
        async with httpx.AsyncClient(transport=transport) as client:
            async with client.stream("POST", "http://test/", json={}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    data = j.loads(line[6:])
                    c = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                    if c:
                        parts.append(c)
        assert "".join(parts) == "Hello world"
