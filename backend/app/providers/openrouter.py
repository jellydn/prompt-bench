from ..config import settings
from .common import OpenAICompatibleProvider

# Curated set of OpenRouter free models (pricing $0) plus a few popular paid
# models. Free model IDs use the `:free` suffix. Source:
# https://openrouter.ai/collections/free-models  (availability changes over time)
FREE_MODELS = [
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

PAID_MODELS = [
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct",
]


class OpenRouterProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "openrouter", "OpenRouter"
    api_key = settings.openrouter_api_key
    base_url = "https://openrouter.ai/api/v1/chat/completions"
    # OpenRouter attribution headers (recommended by OpenRouter docs).
    extra_headers = {"HTTP-Referer": "https://github.com/productsway/PromptBench", "X-Title": "PromptBench"}
    model_names = {m: m for m in FREE_MODELS + PAID_MODELS}

