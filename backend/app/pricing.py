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
        # Free models (https://openrouter.ai/collections/free-models) — $0 pricing
        **{m: {"input": 0.0, "output": 0.0} for m in [
            "openrouter/free",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "cohere/north-mini-code:free",
            "poolside/laguna-s-2.1:free",
            "poolside/laguna-xs-2.1:free",
            "poolside/laguna-m.1:free",
            "inclusionai/ling-3.0-flash:free",
        ]},
        # Paid models
        "openai/gpt-4o": {"input": 0.0025, "output": 0.010},
        "anthropic/claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
        "google/gemini-pro-1.5": {"input": 0.00125, "output": 0.005},
        "meta-llama/llama-3.1-70b-instruct": {"input": 0.00059, "output": 0.00079},
    },
    "ollama": {m: {"input": 0.0, "output": 0.0} for m in ["llama3.1", "mistral", "qwen2.5", "phi3"]},
    "vllm": {m: {"input": 0.0, "output": 0.0} for m in ["meta-llama/Meta-Llama-3.1-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"]},
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICING.get(provider, {}).get(model, {"input": 0.0, "output": 0.0})
    return input_tokens / 1000 * price["input"] + output_tokens / 1000 * price["output"]
