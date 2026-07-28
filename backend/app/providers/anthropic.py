import json
import time

import httpx

from ..config import get_settings
from ..pricing import calculate_cost
from .base import BaseProvider, ProviderResponse


class AnthropicProvider(BaseProvider):
    provider_id, provider_name = "anthropic", "Anthropic"
    supports_byok = True
    model_names = {
        "claude-sonnet-5": "Claude Sonnet 5",
        "claude-opus-5": "Claude Opus 5",
        "claude-fable-5": "Claude Fable 5",
        "claude-haiku-4-5": "Claude Haiku 4.5",
    }

    @property
    def is_configured(self):
        return bool(self._client_api_key or get_settings().anthropic_api_key)

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
        api_key = self._client_api_key or get_settings().anthropic_api_key
        headers = {"anthropic-version": "2023-06-01"}
        if api_key:
            headers["x-api-key"] = api_key
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
