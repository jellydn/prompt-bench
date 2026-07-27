"""Cache key generation for response and embedding caches.

Keys are deterministic SHA-256 digests over the *logical* request inputs.
They never include timestamps or other volatile data, so the same benchmark
configuration always produces the same key — enabling reproducible, cached
benchmark runs.
"""

from __future__ import annotations

import hashlib
import json

# Bumped whenever the benchmark request shape changes in a backwards-incompatible
# way. Existing cached entries keyed under an old version simply miss, which is
# the desired behavior after a config/schema change.
BENCHMARK_CONFIG_VERSION = "1"


def response_cache_key(
    *,
    provider: str,
    model: str,
    prompt_template: str,
    rendered_prompt: str,
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    top_p: float | None = None,
    benchmark_config_version: str = BENCHMARK_CONFIG_VERSION,
) -> str:
    """Build a deterministic response cache key.

    The key is ``response:{provider}:{model}:{sha256(payload)}`` where the
    payload is a canonical JSON document over every input that affects the
    model output. ``sort_keys`` + compact separators guarantee that two
    logically identical requests hash to the same digest regardless of dict
    insertion order.
    """
    payload = {
        "provider": provider,
        "model": model,
        "prompt_template": prompt_template,
        "rendered_prompt": rendered_prompt,
        "system_prompt": system_prompt,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "top_p": top_p,
        "config_version": benchmark_config_version,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"response:{provider}:{model}:{digest}"


def embedding_cache_key(*, provider: str, model: str, text: str) -> str:
    """Build a deterministic embedding cache key.

    Key shape: ``embedding:{provider}:{model}:{sha256(text)}``.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embedding:{provider}:{model}:{digest}"


__all__ = [
    "BENCHMARK_CONFIG_VERSION",
    "response_cache_key",
    "embedding_cache_key",
]
