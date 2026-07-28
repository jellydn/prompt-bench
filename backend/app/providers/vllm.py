from ..config import get_settings
from .common import OpenAICompatibleProvider
from .model_lists import VLLM_MODELS


class VLLMProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "vllm", "vLLM"
    always_configured = True
    byok_eligible = False
    model_names = {m: m for m in VLLM_MODELS}

    @property
    def base_url(self):
        return get_settings().vllm_base_url.rstrip("/") + "/v1/chat/completions"
