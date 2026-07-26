from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .openrouter import OpenRouterProvider
from .vllm import VLLMProvider

PROVIDERS = {
    p.provider_id: p
    for p in [
        OpenAIProvider(),
        AnthropicProvider(),
        GeminiProvider(),
        OpenRouterProvider(),
        OllamaProvider(),
        VLLMProvider(),
    ]
}


def get_provider(provider_id: str):
    return PROVIDERS.get(provider_id)
