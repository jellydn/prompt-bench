"""Shared model lists used by both provider definitions and pricing.

Single source of truth for model IDs to avoid drift between providers and pricing.
"""

# OpenRouter free models (pricing $0). Free model IDs use `:free` suffix.
# Source: https://openrouter.ai/collections/free-models (availability changes over time)
OPENROUTER_FREE_MODELS = [
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
]

# OpenRouter popular paid models
OPENROUTER_PAID_MODELS = [
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct",
]

# Ollama local models (all free)
OLLAMA_MODELS = ["llama3.1", "mistral", "qwen2.5", "phi3"]

# vLLM models (all free)
VLLM_MODELS = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]
