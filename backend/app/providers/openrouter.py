from ..config import settings
from .common import OpenAICompatibleProvider
from .model_lists import OPENROUTER_FREE_MODELS, OPENROUTER_PAID_MODELS


class OpenRouterProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "openrouter", "OpenRouter"
    api_key = settings.openrouter_api_key
    base_url = "https://openrouter.ai/api/v1/chat/completions"
    # OpenRouter attribution headers (recommended by OpenRouter docs).
    extra_headers = {
        "HTTP-Referer": "https://github.com/productsway/PromptBench",
        "X-Title": "PromptBench",
    }
    model_names = {m: m for m in OPENROUTER_FREE_MODELS + OPENROUTER_PAID_MODELS}
