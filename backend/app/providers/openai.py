from ..config import get_settings
from .common import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "openai", "OpenAI"
    base_url = "https://api.openai.com/v1/chat/completions"
    model_names = {
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o mini",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-3.5-turbo": "GPT-3.5 Turbo",
    }

    @property
    def api_key(self):
        return get_settings().openai_api_key
