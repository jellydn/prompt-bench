from ..config import get_settings
from ..pricing import PRICING
from .base import ModelInfo
from .common import OpenAICompatibleProvider
from .model_lists import OPENROUTER_FREE_MODELS, OPENROUTER_PAID_MODELS


class OpenRouterProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "openrouter", "OpenRouter"
    base_url = "https://openrouter.ai/api/v1/chat/completions"
    # OpenRouter attribution headers (recommended by OpenRouter docs).
    extra_headers = {
        "HTTP-Referer": "https://github.com/productsway/PromptBench",
        "X-Title": "PromptBench",
    }
    # Frozen snapshot at class-def time — get_models() override below
    # reads the live lists instead.  Kept as a fallback for code that
    # accesses model_names directly rather than calling get_models().
    model_names = {m: m for m in OPENROUTER_FREE_MODELS + OPENROUTER_PAID_MODELS}

    def get_models(self) -> list[ModelInfo]:
        """Return current model list — reads live lists, not class-def snapshot.

        ``model_names`` is frozen at class definition time.  Override here
        so that after ``refresh_openrouter_free_models()`` updates
        ``OPENROUTER_FREE_MODELS`` in-place, the provider list reflects
        the refreshed models.
        """
        models = {m: m for m in OPENROUTER_FREE_MODELS + OPENROUTER_PAID_MODELS}
        pricing = PRICING.get(self.provider_id, {})
        return [
            ModelInfo(k, v, pricing.get(k, {"input": 0.0, "output": 0.0}))
            for k, v in models.items()
        ]

    @property
    def api_key(self):
        return get_settings().openrouter_api_key
