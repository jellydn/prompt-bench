"""Tests for provider error handling and edge cases."""

import json as j
from unittest.mock import Mock, patch

import httpx
import pytest

from app.pricing import PRICING, calculate_cost
from app.providers import PROVIDERS
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ProviderResponse
from app.providers.gemini import GeminiProvider
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
        cost = calculate_cost("anthropic", "claude-haiku-4-5", 100_000, 50_000)
        assert cost > 0
        assert cost < 1000

    def test_all_providers_have_pricing(self):
        for pid in PROVIDERS:
            assert pid in PRICING, f"No pricing entry for {pid}"


class _BYOKTestBase:
    """Shared helpers for BYOK wire-level tests.

    ``_capture_transport``, ``_patched_client``, and ``_mock_settings``
    were previously duplicated across three test classes.  The only
    difference was ``_sse_body`` — now set as a class attribute on each
    subclass.
    """

    _sse_body: str = ""  # Subclasses override

    @classmethod
    def _capture_transport(cls, captured: dict):
        """Return an httpx.MockTransport that captures request details."""
        body = cls._sse_body

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.content
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, text=body)

        return httpx.MockTransport(handler)

    @classmethod
    def _patched_client(cls, captured: dict):
        """Return an AsyncClient subclass that injects our capture transport."""
        transport = cls._capture_transport(captured)

        class _PC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = transport
                super().__init__(*a, **kw)

        return _PC

    @staticmethod
    def _mock_settings(**kw):
        """Return a mock Settings object with the given attributes."""
        return Mock(**kw)


class TestBYOKAuthHeader(_BYOKTestBase):
    """BYOK keys must actually reach the upstream provider's Authorization header.

    PR #7 included a critical bug where BYOK keys were injected into the provider
    instance but common.py's generate() only read self.api_key (the server key),
    silently discarding the client key.  These tests verify the fix.
    """

    _sse_body = (
        'data: {"choices":[{"delta":{"content":"ok"}}],'
        '"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'
        "data: [DONE]\n\n"
    )

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

    @pytest.mark.asyncio
    async def test_byok_key_across_multi_chunk_stream(self):
        """BYOK key persists across the full SSE stream: 3 deltas + usage + [DONE]."""
        provider = OpenAIProvider()
        provider._client_api_key = "sk-byok-stream-key"

        captured: dict = {}

        # 3 content deltas, then a standalone usage chunk, then [DONE].
        body = (
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":10,"completion_tokens":3}}\n\n'
            "data: [DONE]\n\n"
        )

        def _multi_handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, text=body)

        class _MultiPC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = httpx.MockTransport(_multi_handler)
                super().__init__(*a, **kw)

        with patch("app.providers.common.httpx.AsyncClient", _MultiPC):
            result = await provider.generate(
                prompt="test",
                model="gpt-4o-mini",
                temperature=0,
                max_tokens=10,
            )

        # All 3 chunks accumulated.
        assert result.response_text == "Hello world", (
            f"Expected concatenated chunks, got: {result.response_text!r}"
        )
        assert result.input_tokens == 10
        assert result.output_tokens == 3
        assert result.response_chars == 11  # "Hello world"
        assert result.cost > 0  # gpt-4o-mini pricing
        # Mock transport has zero latency — ttft_ms can legitimately be 0.
        assert result.ttft_ms >= 0
        assert result.total_latency_ms >= 0

        # BYOK key is in every request — the mock captures the one and only request.
        auth = captured.get("headers", {}).get("authorization", "")
        assert auth == "Bearer sk-byok-stream-key", (
            f"Expected BYOK key in multi-chunk Authorization header, got: {auth}"
        )


class TestBYOKAnthropicAuthHeader(_BYOKTestBase):
    """Verify BYOK keys reach Anthropic's API.

    AnthropicProvider has its own generate() method (not OpenAICompatibleProvider)
    and uses the x-api-key header / a different SSE format.  These tests mirror
    TestBYOKAuthHeader but for the Anthropic-specific code path.
    """

    _sse_body = (
        'data: {"type":"message_start","message":{"usage":{"input_tokens":1}}}\n\n'
        'data: {"type":"content_block_delta","delta":{"text":"ok"}}\n\n'
        'data: {"type":"message_delta","usage":{"output_tokens":1}}\n\n'
    )

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
                model="claude-haiku-4-5",
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
                    model="claude-haiku-4-5",
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
                    model="claude-haiku-4-5",
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
                    model="claude-haiku-4-5",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        key = captured.get("headers", {}).get("x-api-key", "")
        assert key == "sk-ant-byok-wins", (
            f"Expected BYOK key to take priority in x-api-key header, got: {key}"
        )

    @pytest.mark.asyncio
    async def test_byok_key_across_multi_chunk_stream(self):
        """BYOK key persists across full Anthropic SSE stream: 3 deltas + framing events."""
        provider = AnthropicProvider()
        provider._client_api_key = "sk-ant-byok-stream-key"

        captured: dict = {}

        # message_start → 3 deltas → message_delta (Anthropic has no [DONE] signal).
        body = (
            'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}\n\n'
            'data: {"type":"content_block_delta","delta":{"text":"Hello"}}\n\n'
            'data: {"type":"content_block_delta","delta":{"text":" "}}\n\n'
            'data: {"type":"content_block_delta","delta":{"text":"world"}}\n\n'
            'data: {"type":"message_delta","usage":{"output_tokens":3}}\n\n'
        )

        def _multi_handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, text=body)

        class _MultiPC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = httpx.MockTransport(_multi_handler)
                super().__init__(*a, **kw)

        with patch("app.providers.anthropic.httpx.AsyncClient", _MultiPC):
            result = await provider.generate(
                prompt="test",
                model="claude-haiku-4-5",
                temperature=0,
                max_tokens=10,
            )

        # All 3 chunks accumulated.
        assert result.response_text == "Hello world", (
            f"Expected concatenated chunks, got: {result.response_text!r}"
        )
        assert result.input_tokens == 10
        assert result.output_tokens == 3
        assert result.response_chars == 11
        assert result.cost > 0  # claude-haiku-4-5 pricing
        assert result.ttft_ms >= 0
        assert result.total_latency_ms >= 0

        # BYOK key is in the single request captured by the mock.
        key = captured.get("headers", {}).get("x-api-key", "")
        assert key == "sk-ant-byok-stream-key", (
            f"Expected BYOK key in multi-chunk x-api-key header, got: {key}"
        )


class TestBYOKGeminiAuthHeader(_BYOKTestBase):
    """Verify BYOK keys reach Gemini's API.

    GeminiProvider embeds the API key as a URL query parameter (?key=...),
    not as a header.  These tests capture request.url.params to verify
    the key is correctly injected.
    """

    _sse_body = (
        'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}],'
        '"usageMetadata":{"promptTokenCount":1,"candidatesTokenCount":1}}\n\n'
    )

    @pytest.mark.asyncio
    async def test_byok_key_used_in_url_params(self):
        """When _client_api_key is set, it appears in the ?key= URL parameter."""
        provider = GeminiProvider()
        provider._client_api_key = "sk-gemini-byok-key"

        captured: dict = {}

        with patch(
            "app.providers.gemini.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            result = await provider.generate(
                prompt="test",
                model="gemini-2.5-flash",
                temperature=0,
                max_tokens=10,
            )

        assert result.response_text == "ok"
        params = captured.get("params", {})
        assert params.get("key") == "sk-gemini-byok-key", (
            f"Expected BYOK key in URL ?key= param, got: {params}"
        )
        assert params.get("alt") == "sse"

    @pytest.mark.asyncio
    async def test_server_key_fallback_in_url_params(self):
        """When _client_api_key is NOT set, the server's gemini_api_key is used."""
        provider = GeminiProvider()
        provider._client_api_key = None

        captured: dict = {}

        with patch(
            "app.providers.gemini.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.gemini.get_settings",
                return_value=self._mock_settings(gemini_api_key="sk-gemini-server-key"),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="gemini-2.5-flash",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        params = captured.get("params", {})
        assert params.get("key") == "sk-gemini-server-key", (
            f"Expected server key fallback in URL ?key=, got: {params}"
        )

    @pytest.mark.asyncio
    async def test_empty_key_param_when_no_key(self):
        """When neither key is set, ?key= is empty (Gemini sends it anyway)."""
        provider = GeminiProvider()
        provider._client_api_key = None

        captured: dict = {}

        with patch(
            "app.providers.gemini.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.gemini.get_settings",
                return_value=self._mock_settings(gemini_api_key=""),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="gemini-2.5-flash",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        params = captured.get("params", {})
        # Gemini always sends ?key=; when both are empty it's an empty string.
        assert params.get("key") == "", (
            f"Expected empty ?key= when no key configured, got: {params}"
        )

    @pytest.mark.asyncio
    async def test_byok_priority_over_server_key_in_url(self):
        """When BOTH keys are set, BYOK key MUST take priority in URL params."""
        provider = GeminiProvider()
        provider._client_api_key = "sk-gemini-byok-wins"

        captured: dict = {}

        with patch(
            "app.providers.gemini.httpx.AsyncClient",
            self._patched_client(captured),
        ):
            with patch(
                "app.providers.gemini.get_settings",
                return_value=self._mock_settings(
                    gemini_api_key="sk-gemini-should-not-appear"
                ),
            ):
                result = await provider.generate(
                    prompt="test",
                    model="gemini-2.5-flash",
                    temperature=0,
                    max_tokens=10,
                )

        assert result.response_text == "ok"
        params = captured.get("params", {})
        assert params.get("key") == "sk-gemini-byok-wins", (
            f"Expected BYOK key to take priority in ?key=, got: {params}"
        )

    @pytest.mark.asyncio
    async def test_key_not_leaked_in_error_response_url(self):
        """When Gemini returns an error, the exception URL must not expose the key.

        httpx's HTTPStatusError includes the request URL in its message.  Since
        Gemini puts the key in URL params, a 401/403 error would leak the key
        into logs if the exception is not sanitized.
        """
        provider = GeminiProvider()
        provider._client_api_key = "sk-leaked-key-12345"

        def _error_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Invalid key"}})

        class _ErrorPC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = httpx.MockTransport(_error_handler)
                super().__init__(*a, **kw)

        with patch("app.providers.gemini.httpx.AsyncClient", _ErrorPC):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await provider.generate(
                    prompt="test",
                    model="gemini-2.5-flash",
                    temperature=0,
                    max_tokens=10,
                )

        # The raw httpx exception WILL contain the key in the URL.
        # This test documents that fact — the benchmarks router's _sanitize_error
        # is responsible for stripping it before logging.
        assert "sk-leaked-key-12345" in str(exc_info.value), (
            "Gemini keys appear in httpx exception URLs — "
            "callers MUST sanitize before logging."
        )

    @pytest.mark.asyncio
    async def test_byok_key_across_multi_chunk_stream(self):
        """BYOK key persists across full Gemini SSE stream: 3 parts + usage."""
        provider = GeminiProvider()
        provider._client_api_key = "sk-gemini-stream-key"

        captured: dict = {}

        # 3 content parts, then a usageMetadata chunk.  No [DONE] for Gemini.
        body = (
            'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}\n\n'
            'data: {"candidates":[{"content":{"parts":[{"text":" "}]}}]}\n\n'
            'data: {"candidates":[{"content":{"parts":[{"text":"world"}]}}]}\n\n'
            'data: {"usageMetadata":{"promptTokenCount":10,"candidatesTokenCount":3}}\n\n'
        )

        def _multi_handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, text=body)

        class _MultiPC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = httpx.MockTransport(_multi_handler)
                super().__init__(*a, **kw)

        with patch("app.providers.gemini.httpx.AsyncClient", _MultiPC):
            result = await provider.generate(
                prompt="test",
                model="gemini-2.5-flash",
                temperature=0,
                max_tokens=10,
            )

        assert result.response_text == "Hello world", (
            f"Expected concatenated chunks, got: {result.response_text!r}"
        )
        assert result.input_tokens == 10
        assert result.output_tokens == 3
        assert result.response_chars == 11
        assert result.cost > 0  # gemini-2.5-flash pricing
        assert result.ttft_ms >= 0
        assert result.total_latency_ms >= 0

        params = captured.get("params", {})
        assert params.get("key") == "sk-gemini-stream-key", (
            f"Expected BYOK key in multi-chunk ?key=, got: {params}"
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
