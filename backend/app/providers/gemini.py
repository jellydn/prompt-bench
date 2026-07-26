import time

import httpx

from ..config import settings
from ..pricing import PRICING, calculate_cost
from .base import BaseProvider, ModelInfo, ProviderResponse


class GeminiProvider(BaseProvider):
    provider_id, provider_name = "gemini", "Google Gemini"
    names = {
        "gemini-1.5-pro": "Gemini 1.5 Pro",
        "gemini-1.5-flash": "Gemini 1.5 Flash",
        "gemini-2.0-flash-exp": "Gemini 2.0 Flash Experimental",
    }

    @property
    def is_configured(self):
        return bool(settings.gemini_api_key)

    def get_models(self):
        return [
            ModelInfo(k, v, PRICING[self.provider_id][k]) for k, v in self.names.items()
        ]

    async def generate(
        self, prompt, model, system_prompt="", temperature=0.7, max_tokens=1000
    ):
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url, params={"key": settings.gemini_api_key}, json=body
            )
            response.raise_for_status()
            data = response.json()
        ended = time.perf_counter()
        text = "".join(
            p.get("text", "")
            for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        )
        usage = data.get("usageMetadata", {})
        inp, out = (
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )
        latency = round((ended - started) * 1000)
        return ProviderResponse(
            inp,
            out,
            latency,
            latency,
            text,
            len(text),
            calculate_cost(self.provider_id, model, inp, out),
        )
