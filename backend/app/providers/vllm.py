from ..config import settings
from .common import OpenAICompatibleProvider
from .model_lists import VLLM_MODELS


class VLLMProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "vllm", "vLLM"
    base_url = settings.vllm_base_url.rstrip("/") + "/v1/chat/completions"
    always_configured = True
    model_names = {m: m for m in VLLM_MODELS}
