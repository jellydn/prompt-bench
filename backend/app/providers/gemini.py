import json
import time

import httpx

from ..config import get_settings
from ..pricing import calculate_cost
from .base import BaseProvider, ProviderResponse


class GeminiProvider(BaseProvider):
    provider_id, provider_name = "gemini", "Google Gemini"
    supports_byok = True
    model_names = {
        "gemini-2.5-pro": "Gemini 2.5 Pro",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite",
        "gemini-3.5-flash": "Gemini 3.5 Flash",
        "gemini-3.6-flash": "Gemini 3.6 Flash",
    }

    @property
    def is_configured(self):
        return bool(self._client_api_key or get_settings().gemini_api_key)

    async def generate(self, prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
        )
        started = time.perf_counter()
        first = None
        parts = []
        inp = out = 0
        async with (
            httpx.AsyncClient(timeout=120) as client,
            client.stream(
                "POST",
                url,
                params={"key": self._client_api_key or get_settings().gemini_api_key, "alt": "sse"},
                json=body,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                candidate = (data.get("candidates") or [{}])[0]
                text_parts = candidate.get("content", {}).get("parts", [{}])
                for p in text_parts:
                    text = p.get("text", "")
                    if text:
                        first = first or time.perf_counter()
                        parts.append(text)
                usage = data.get("usageMetadata", {})
                if usage:
                    inp = usage.get("promptTokenCount", inp)
                    out = usage.get("candidatesTokenCount", out)
        ended = time.perf_counter()
        result = "".join(parts)
        ttft = round(((first or ended) - started) * 1000)
        total = round((ended - started) * 1000)
        return ProviderResponse(
            inp,
            out,
            ttft,
            total,
            result,
            len(result),
            calculate_cost(self.provider_id, model, inp, out),
        )
