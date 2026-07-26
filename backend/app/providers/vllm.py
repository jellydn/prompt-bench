from ..config import settings
from .common import OpenAICompatibleProvider


class VLLMProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "vllm", "vLLM"
    base_url = settings.vllm_base_url.rstrip("/") + "/v1/chat/completions"
    always_configured = True
    model_names = {
        m: m
        for m in [
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ]
    }
