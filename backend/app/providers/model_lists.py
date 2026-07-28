"""Shared model lists used by both provider definitions and pricing.

Single source of truth for model IDs to avoid drift between providers and pricing.
Provides runtime refresh for the OpenRouter free model list from the API.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

# ── Static fallback lists ──────────────────────────────────────────

# OpenRouter free models (pricing $0). Used as fallback if the API fetch fails.
# Source: https://openrouter.ai/collections/free-models
_STATIC_OPENROUTER_FREE = [
    "openrouter/free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "cohere/north-mini-code:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "poolside/laguna-m.1:free",
    "inclusionai/ling-3.0-flash:free",
]

# OpenRouter popular paid models (not refreshed from API)
OPENROUTER_PAID_MODELS = [
    "openai/gpt-4.1",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-opus-5",
    "google/gemini-2.5-pro",
    "google/gemini-3.5-flash",
    "meta-llama/llama-3.1-70b-instruct",
]

# Ollama local models
OLLAMA_MODELS = ["llama3.1", "mistral", "qwen2.5", "phi3"]

# vLLM models
VLLM_MODELS = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]

# ── Runtime-mutable free model list ────────────────────────────────
# Starts as the static list; refresh_openrouter_free_models() replaces it.

OPENROUTER_FREE_MODELS = list(_STATIC_OPENROUTER_FREE)

_OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
_REFRESH_TTL_SECONDS = 3600  # 1 hour
_last_refresh: float = 0.0


async def refresh_openrouter_free_models() -> None:
    """Fetch OpenRouter free model list from the API.

    Updates OPENROUTER_FREE_MODELS in-place. Falls back to the static
    list on any error (network, parse, etc.).
    """
    global _last_refresh  # noqa: PLW0603
    now = time.time()
    if now - _last_refresh < _REFRESH_TTL_SECONDS:
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_OPENROUTER_API_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("OpenRouter model list fetch failed: %s. Using static fallback.", exc)
        return

    free_models = []
    for model in data.get("data", []):
        model_id = model.get("id", "")
        pricing = model.get("pricing", {})
        prompt_price = pricing.get("prompt", None)
        completion_price = pricing.get("completion", None)
        is_free = (
            model_id is not None
            and prompt_price is not None
            and completion_price is not None
            and float(prompt_price) == 0.0
            and float(completion_price) == 0.0
        )
        if is_free:
            free_models.append(model_id)

    if not free_models:
        logger.warning(
            "OpenRouter API returned no free models. Keeping existing list (%d models).",
            len(OPENROUTER_FREE_MODELS),
        )
        return

    old_count = len(OPENROUTER_FREE_MODELS)
    OPENROUTER_FREE_MODELS.clear()
    OPENROUTER_FREE_MODELS.extend(free_models)
    _last_refresh = now
    # Rebuild pricing and invalidate provider cache so refreshed models
    # appear immediately in /api/providers and cost calculations.
    #
    # NOTE: both imports are intentionally deferred (not at module level) to
    # break a potential circular import chain:
    #   base.py → pricing.py → model_lists.py → providers/__init__.py → …
    # Moving them to module level would create an import cycle.
    from ..pricing import rebuild_openrouter_pricing  # noqa: PLC0415
    from . import invalidate_provider_cache  # noqa: PLC0415

    rebuild_openrouter_pricing()
    invalidate_provider_cache()
    logger.info(
        "OpenRouter free models refreshed: %d → %d models",
        old_count,
        len(OPENROUTER_FREE_MODELS),
    )
