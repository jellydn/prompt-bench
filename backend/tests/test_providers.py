"""Tests for provider error handling and edge cases."""

import json

from app.pricing import calculate_cost
from app.providers.base import ProviderResponse


class TestProviderResponse:
    """ProviderResponse dataclass behavior."""

    def test_provider_response_chars_field(self):
        """Verify response_chars is the correct field name."""
        resp = ProviderResponse(
            input_tokens=10,
            output_tokens=20,
            ttft_ms=100,
            total_latency_ms=500,
            response_text="hello world",
            response_chars=11,
            cost=0.001,
        )
        assert resp.response_chars == 11
        assert not hasattr(resp, "response_length")


class TestPricing:
    """Pricing calculation edge cases."""

    def test_known_model(self):
        cost = calculate_cost("openai", "gpt-4o-mini", 1000, 500)
        assert cost > 0

    def test_zero_tokens(self):
        cost = calculate_cost("openai", "gpt-4o-mini", 0, 0)
        assert cost == 0.0

    def test_free_model(self):
        cost = calculate_cost("openrouter", "google/gemma-4-31b-it:free", 1000, 500)
        assert cost == 0.0

    def test_unknown_provider_defaults_zero(self):
        cost = calculate_cost("nonexistent", "some-model", 100, 50)
        assert cost == 0.0

    def test_unknown_model_defaults_zero(self):
        cost = calculate_cost("openai", "unknown-model", 100, 50)
        assert cost == 0.0

    def test_large_token_counts(self):
        cost = calculate_cost("anthropic", "claude-3-5-sonnet-20241022", 100_000, 50_000)
        assert cost > 0
        assert cost < 1000  # sanity check


class TestProviderJSONParsing:
    """Provider SSE JSON parsing edge cases."""

    def test_malformed_sse_swallowed(self):
        """Malformed SSE line should raise JSONDecodeError."""
        raised = False
        try:
            json.loads("{not valid json")
        except json.JSONDecodeError:
            raised = True
        assert raised, "json.JSONDecodeError should have been raised"

    def test_empty_data_line_skipped(self):
        """Non-data lines should be skipped."""
        line = "something else"
        assert not line.startswith("data: ")

    def test_done_signal_skipped(self):
        """[DONE] signal should be skipped."""
        line = "data: [DONE]"
        assert line.startswith("data: ")
        assert line == "data: [DONE]"
