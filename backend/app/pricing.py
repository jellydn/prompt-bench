from .providers.model_lists import (
    OLLAMA_MODELS,
    OPENROUTER_FREE_MODELS,
    VLLM_MODELS,
)

# Single source of truth for OpenRouter paid model pricing — used
# in both the initial PRICING dict and rebuild_openrouter_pricing().
_OPENROUTER_PAID_PRICING: dict[str, dict[str, float]] = {
    "openai/gpt-4.1": {"input": 0.002, "output": 0.008},
    "openai/gpt-4o": {"input": 0.0025, "output": 0.010},
    "anthropic/claude-sonnet-5": {"input": 0.003, "output": 0.015},
    "anthropic/claude-opus-5": {"input": 0.005, "output": 0.025},
    "google/gemini-2.5-pro": {"input": 0.00125, "output": 0.010},
    "google/gemini-3.5-flash": {"input": 0.00015, "output": 0.0006},
    "meta-llama/llama-3.1-70b-instruct": {"input": 0.00059, "output": 0.00079},
}

PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4.1": {"input": 0.002, "output": 0.008},
        "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
        "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},
        "gpt-4o": {"input": 0.0025, "output": 0.010},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "o3": {"input": 0.010, "output": 0.040},
        "o4-mini": {"input": 0.0011, "output": 0.0044},
    },
    "anthropic": {
        "claude-sonnet-5": {"input": 0.003, "output": 0.015},
        "claude-opus-5": {"input": 0.005, "output": 0.025},
        "claude-fable-5": {"input": 0.010, "output": 0.050},
        "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
    },
    "gemini": {
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.010},
        "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
        "gemini-2.5-flash-lite": {"input": 0.000075, "output": 0.0003},
        "gemini-3.5-flash": {"input": 0.00015, "output": 0.0006},
        "gemini-3.6-flash": {"input": 0.00015, "output": 0.0006},
    },
    "openrouter": {
        **{m: {"input": 0.0, "output": 0.0} for m in OPENROUTER_FREE_MODELS},
        **_OPENROUTER_PAID_PRICING,
    },
    "ollama": {m: {"input": 0.0, "output": 0.0} for m in OLLAMA_MODELS},
    "vllm": {m: {"input": 0.0, "output": 0.0} for m in VLLM_MODELS},
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICING.get(provider, {}).get(model, {"input": 0.0, "output": 0.0})
    return input_tokens / 1000 * price["input"] + output_tokens / 1000 * price["output"]


def rebuild_openrouter_pricing() -> None:
    """Rebuild ``PRICING["openrouter"]`` from the current model lists.

    ``refresh_openrouter_free_models()`` updates ``OPENROUTER_FREE_MODELS``
    in-place, but ``PRICING["openrouter"]`` was built at module import time
    from a snapshot of the free model list.  Call this after each refresh so
    ``get_models()`` and ``calculate_cost()`` see the current models.
    """
    PRICING["openrouter"] = {
        **{m: {"input": 0.0, "output": 0.0} for m in OPENROUTER_FREE_MODELS},
        **_OPENROUTER_PAID_PRICING,
    }
