import json
import time

import httpx

from ..pricing import PRICING, calculate_cost
from .base import BaseProvider, ModelInfo, ProviderResponse


class OpenAICompatibleProvider(BaseProvider):
    api_key = ""
    base_url = ""
    model_names: dict[str, str] = {}
    always_configured = False
    supports_byok = True
    extra_headers: dict[str, str] = {}

    @property
    def is_configured(self) -> bool:
        return self.always_configured or bool(self._client_api_key or self.api_key)

    def get_models(self):
        return [
            ModelInfo(mid, name, PRICING[self.provider_id][mid])
            for mid, name in self.model_names.items()
        ]

    async def generate(self, prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [
            {"role": "user", "content": prompt}
        ]
        api_key = self._client_api_key or self.api_key
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        headers = {**headers, **self.extra_headers}
        started = time.perf_counter()
        first = None
        text, usage = [], {}
        async with (
            httpx.AsyncClient(timeout=120) as client,
            client.stream(
                "POST",
                self.base_url,
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                content = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if content:
                    first = first or time.perf_counter()
                    text.append(content)
                if data.get("usage"):
                    usage = data["usage"]
        ended = time.perf_counter()
        result = "".join(text)
        inp, out = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        return ProviderResponse(
            inp,
            out,
            round(((first or ended) - started) * 1000),
            round((ended - started) * 1000),
            result,
            len(result),
            calculate_cost(self.provider_id, model, inp, out),
        )
