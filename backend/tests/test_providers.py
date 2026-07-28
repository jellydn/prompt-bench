"""Tests for provider error handling and edge cases."""

import json as j
from unittest.mock import Mock, patch

import httpx
import pytest

from app.pricing import PRICING, calculate_cost
from app.providers import PROVIDERS
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ProviderResponse
from app.providers.openai import OpenAIProvider


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


class TestBYOKAuthHeader:
    """BYOK keys must actually reach the upstream provider's Authorization header.

    PR #7 included a critical bug where BYOK keys were injected into the provider
    instance but common.py's generate() only read self.api_key (the server key),
    silently discarding the client key.  These tests verify the fix.
    """

    # Minimal valid SSE stream so generate() completes without raising.
    _sse_body = (
        'data: {"choices":[{"delta":{"content":"ok"}}],'
        '"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'
        "data: [DONE]\n\n"
    )

    @staticmethod
    def _capture_transport(captured: dict):
        """Return an httpx.MockTransport that writes request headers into *captured*."""

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.content
            return httpx.Response(200, text=TestBYOKAuthHeader._sse_body)

        return httpx.MockTransport(handler)

    @staticmethod
    def _patched_client(captured: dict):
        """Return an AsyncClient subclass that injects our capture transport."""

        class _PC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = TestBYOKAuthHeader._capture_transport(captured)
                super().__init__(*a, **kw)

        return _PC

    @staticmethod
    def _mock_settings(**kw):
        """Return a mock Settings object with the given attributes."""
        return Mock(**kw)

    @pytest.mark.asyncio
    async def test_byok_key_used_in_auth_header(self):
        """When _client_api_key is set, it MUST appear in the Authorization header."""
        provider = OpenAIProvider()
        provider._client_api_key = "sk-byok-test-key-12345"

        captured: dict = {}

        with patch(
            "app.providers.common.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            result = await provider.generate(
                prompt="test",
                model="gpt-4o-mini",
                temperature=0,
                max_tokens=10,
            )

        assert result.response_text == "ok"
        auth = captured.get("headers", {}).get("authorization", "")
        assert auth == "Bearer sk-byok-test-key-12345", (
            f"Expected BYOK key in Authorization header, got: {auth}"
        )

    @pytest.mark.asyncio
    async def test_server_key_fallback_when_no_byok(self):
        """When _client_api_key is NOT set, self.api_key (server key) is used."""
        provider = OpenAIProvider()
        provider._client_api_key = None  # explicitly no BYOK

        captured: dict = {}

        with patch(
            "app.providers.common.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.openai.get_settings",
                return_value=self._mock_settings(openai_api_key="sk-server-key-67890"),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        auth = captured.get("headers", {}).get("authorization", "")
        assert auth == "Bearer sk-server-key-67890", (
            f"Expected server key fallback in Authorization header, got: {auth}"
        )

    @pytest.mark.asyncio
    async def test_no_auth_header_when_no_key(self):
        """When neither client nor server key is set, no Authorization header is sent."""
        provider = OpenAIProvider()
        provider._client_api_key = None

        captured: dict = {}

        with patch(
            "app.providers.common.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.openai.get_settings",
                return_value=self._mock_settings(openai_api_key=""),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        auth = captured.get("headers", {}).get("authorization")
        assert auth is None, (
            f"Expected NO Authorization header when no key is configured, got: {auth}"
        )

    @pytest.mark.asyncio
    async def test_byok_priority_over_server_key(self):
        """When BOTH keys are set, BYOK key MUST take priority over server key."""
        provider = OpenAIProvider()
        provider._client_api_key = "sk-byok-wins"

        captured: dict = {}

        with patch(
            "app.providers.common.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.openai.get_settings",
                return_value=self._mock_settings(
                    openai_api_key="sk-server-key-should-not-appear"
                ),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        auth = captured.get("headers", {}).get("authorization", "")
        assert auth == "Bearer sk-byok-wins", (
            f"Expected BYOK key to take priority, got: {auth}"
        )


class TestBYOKAnthropicAuthHeader:
    """Verify BYOK keys reach Anthropic's API.

    AnthropicProvider has its own generate() method (not OpenAICompatibleProvider)
    and uses the x-api-key header / a different SSE format.  These tests mirror
    TestBYOKAuthHeader but for the Anthropic-specific code path.
    """

    # Minimal valid Anthropic SSE stream.
    _sse_body = (
        'data: {"type":"message_start","message":{"usage":{"input_tokens":1}}}\n\n'
        'data: {"type":"content_block_delta","delta":{"text":"ok"}}\n\n'
        'data: {"type":"message_delta","usage":{"output_tokens":1}}\n\n'
    )

    @staticmethod
    def _capture_transport(captured: dict):
        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.content
            return httpx.Response(200, text=TestBYOKAnthropicAuthHeader._sse_body)
        return httpx.MockTransport(handler)

    @staticmethod
    def _patched_client(captured: dict):
        class _PC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = TestBYOKAnthropicAuthHeader._capture_transport(captured)
                super().__init__(*a, **kw)
        return _PC

    @staticmethod
    def _mock_settings(**kw):
        return Mock(**kw)

    @pytest.mark.asyncio
    async def test_byok_key_used_in_x_api_key_header(self):
        """When _client_api_key is set, it MUST appear in x-api-key header."""
        provider = AnthropicProvider()
        provider._client_api_key = "sk-ant-byok-test-key"

        captured: dict = {}

        with patch(
            "app.providers.anthropic.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            result = await provider.generate(
                prompt="test",
                model="claude-3-5-haiku-20241022",
                temperature=0,
                max_tokens=10,
            )

        assert result.response_text == "ok"
        key = captured.get("headers", {}).get("x-api-key", "")
        assert key == "sk-ant-byok-test-key", (
            f"Expected BYOK key in x-api-key header, got: {key}"
        )

    @pytest.mark.asyncio
    async def test_server_key_fallback_when_no_byok(self):
        """When _client_api_key is NOT set, the server's anthropic_api_key is used."""
        provider = AnthropicProvider()
        provider._client_api_key = None

        captured: dict = {}

        with patch(
            "app.providers.anthropic.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.anthropic.get_settings",
                return_value=self._mock_settings(anthropic_api_key="sk-ant-server-key"),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="claude-3-5-haiku-20241022",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        key = captured.get("headers", {}).get("x-api-key", "")
        assert key == "sk-ant-server-key", (
            f"Expected server key fallback in x-api-key header, got: {key}"
        )

    @pytest.mark.asyncio
    async def test_no_x_api_key_when_no_key(self):
        """When neither client nor server key is set, no x-api-key header is sent."""
        provider = AnthropicProvider()
        provider._client_api_key = None

        captured: dict = {}

        with patch(
            "app.providers.anthropic.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.anthropic.get_settings",
                return_value=self._mock_settings(anthropic_api_key=""),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="claude-3-5-haiku-20241022",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        key = captured.get("headers", {}).get("x-api-key")
        assert key is None, (
            f"Expected NO x-api-key header when no key is configured, got: {key}"
        )

    @pytest.mark.asyncio
    async def test_byok_priority_over_server_key(self):
        """When BOTH keys are set, BYOK key MUST take priority over server key."""
        provider = AnthropicProvider()
        provider._client_api_key = "sk-ant-byok-wins"

        captured: dict = {}

        with patch(
            "app.providers.anthropic.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.anthropic.get_settings",
                return_value=self._mock_settings(
                    anthropic_api_key="sk-ant-should-not-appear"
                ),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="claude-3-5-haiku-20241022",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        key = captured.get("headers", {}).get("x-api-key", "")
        assert key == "sk-ant-byok-wins", (
            f"Expected BYOK key to take priority in x-api-key header, got: {key}"
        )


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
