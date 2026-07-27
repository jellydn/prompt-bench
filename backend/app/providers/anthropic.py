import json
import time

import httpx

from ..config import get_settings
from ..pricing import PRICING, calculate_cost
from .base import BaseProvider, ModelInfo, ProviderResponse


class AnthropicProvider(BaseProvider):
    provider_id, provider_name = "anthropic", "Anthropic"
    model_names = {
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
        "claude-3-opus-20240229": "Claude 3 Opus",
    }

    @property
    def is_configured(self):
        return bool(self._client_api_key or get_settings().anthropic_api_key)

    def get_models(self):
        return [ModelInfo(k, v, PRICING[self.provider_id][k]) for k, v in self.model_names.items()]

    async def generate(self, prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        headers = {
            "x-api-key": self._client_api_key or get_settings().anthropic_api_key,
            "anthropic-version": "2023-06-01",
        }
        started, first, parts, inp, out = time.perf_counter(), None, [], 0, 0
        async with (
            httpx.AsyncClient(timeout=120) as client,
            client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "message_start":
                    inp = event.get("message", {}).get("usage", {}).get("input_tokens", 0)
                if event.get("type") == "content_block_delta":
                    text = event.get("delta", {}).get("text", "")
                    if text:
                        first = first or time.perf_counter()
                        parts.append(text)
                if event.get("type") == "message_delta":
                    out = event.get("usage", {}).get("output_tokens", out)
        ended, text = time.perf_counter(), "".join(parts)
        return ProviderResponse(
            inp,
            out,
            round(((first or ended) - started) * 1000),
            round((ended - started) * 1000),
            text,
            len(text),
            calculate_cost(self.provider_id, model, inp, out),
        )
