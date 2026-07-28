from ..config import get_settings
from .common import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "openai", "OpenAI"
    base_url = "https://api.openai.com/v1/chat/completions"
    model_names = {
        "gpt-4.1": "GPT-4.1",
        "gpt-4.1-mini": "GPT-4.1 mini",
        "gpt-4.1-nano": "GPT-4.1 nano",
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o mini",
        "o3": "o3",
        "o4-mini": "o4-mini",
    }

    @property
    def api_key(self):
        return get_settings().openai_api_key
