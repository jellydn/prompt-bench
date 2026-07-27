"""Provider registry and cache for compiled provider info."""

import time
from dataclasses import asdict

from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .openrouter import OpenRouterProvider
from .vllm import VLLMProvider

PROVIDERS = {
    p.provider_id: p
    for p in [
        OpenAIProvider(),
        AnthropicProvider(),
        GeminiProvider(),
        OpenRouterProvider(),
        OllamaProvider(),
        VLLMProvider(),
    ]
}

# ── TTL cache for compiled provider info ────────────────────────────
# The /api/providers endpoint re-computes full model lists on every call.
# We cache the serialized result for 5 minutes.

_provider_cache: list[dict] | None = None
_provider_cache_ts: float = 0.0
_PROVIDER_CACHE_TTL = 300  # 5 minutes


def get_provider(provider_id: str):
    return PROVIDERS.get(provider_id)


def get_providers_cached() -> list[dict]:
    """Return compiled provider info, using a TTL cache.

    Each provider's models (name, pricing) are serialized once and
    cached for ``_PROVIDER_CACHE_TTL`` seconds.
    """
    global _provider_cache, _provider_cache_ts  # noqa: PLW0603

    now = time.time()
    if _provider_cache is not None and (now - _provider_cache_ts) < _PROVIDER_CACHE_TTL:
        return _provider_cache

    result = []
    for p in PROVIDERS.values():
        result.append(
            {
                "id": p.provider_id,
                "name": p.provider_name,
                "configured": p.is_configured,
                "base_url": getattr(p, "base_url", None),
                "models": [asdict(m) for m in p.get_models()],
            }
        )
    _provider_cache = result
    _provider_cache_ts = now
    return result


def invalidate_provider_cache() -> None:
    """Clear the cache (e.g., after model list refresh)."""
    global _provider_cache, _provider_cache_ts  # noqa: PLW0603
    _provider_cache = None
    _provider_cache_ts = 0.0
