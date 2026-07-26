from .providers.model_lists import (
    OLLAMA_MODELS,
    OPENROUTER_FREE_MODELS,
    VLLM_MODELS,
)

PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input": 0.0025, "output": 0.010},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.010, "output": 0.030},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    },
    "gemini": {
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-2.0-flash-exp": {"input": 0.0, "output": 0.0},
    },
    "openrouter": {
        # Free models — $0 pricing (shared source from model_lists.py)
        **{m: {"input": 0.0, "output": 0.0} for m in OPENROUTER_FREE_MODELS},
        # Paid models
        "openai/gpt-4o": {"input": 0.0025, "output": 0.010},
        "anthropic/claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
        "google/gemini-pro-1.5": {"input": 0.00125, "output": 0.005},
        "meta-llama/llama-3.1-70b-instruct": {"input": 0.00059, "output": 0.00079},
    },
    "ollama": {m: {"input": 0.0, "output": 0.0} for m in OLLAMA_MODELS},
    "vllm": {m: {"input": 0.0, "output": 0.0} for m in VLLM_MODELS},
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICING.get(provider, {}).get(model, {"input": 0.0, "output": 0.0})
    return input_tokens / 1000 * price["input"] + output_tokens / 1000 * price["output"]
