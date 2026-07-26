import json
import time

import httpx

from ..config import settings
from ..pricing import PRICING
from .base import BaseProvider, ModelInfo, ProviderResponse


class OllamaProvider(BaseProvider):
    provider_id, provider_name = "ollama", "Ollama"
    names = {m: m for m in ["llama3.1", "mistral", "qwen2.5", "phi3"]}

    @property
    def is_configured(self):
        return True

    def get_models(self):
        return [ModelInfo(k, v, PRICING[self.provider_id][k]) for k, v in self.names.items()]

    async def generate(self, prompt, model, system_prompt="", temperature=0.7, max_tokens=1000):
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [
            {"role": "user", "content": prompt}
        ]
        started, first, parts, final = time.perf_counter(), None, [], {}
        async with (
            httpx.AsyncClient(timeout=120) as client,
            client.stream(
                "POST",
                settings.ollama_base_url.rstrip("/") + "/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                final = json.loads(line)
                text = final.get("message", {}).get("content", "")
                if text:
                    first = first or time.perf_counter()
                    parts.append(text)
        ended, text = time.perf_counter(), "".join(parts)
        return ProviderResponse(
            final.get("prompt_eval_count", 0),
            final.get("eval_count", 0),
            round(((first or ended) - started) * 1000),
            round((ended - started) * 1000),
            text,
            len(text),
            0.0,
        )
