from ..config import get_settings
from .common import OpenAICompatibleProvider
from .model_lists import VLLM_MODELS


class VLLMProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "vllm", "vLLM"
    byok_eligible = False
    model_names = {m: m for m in VLLM_MODELS}

    @property
    def is_configured(self) -> bool:
        """vLLM is only available when local providers are enabled."""
        return get_settings().enable_local_providers

    @property
    def base_url(self):
        return get_settings().vllm_base_url.rstrip("/") + "/v1/chat/completions"
