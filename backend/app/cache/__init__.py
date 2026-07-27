"""PromptBench cache layer.

Response and embedding caches backed by Redis with an in-memory fallback.
See ``docs/caching.md`` for architecture and configuration details.
"""

from __future__ import annotations

from .cache import (
    CacheBackend,
    CacheStats,
    InMemoryCache,
    RedisCache,
    get_cache,
    reset_cache_singleton,
)
from .embedding_cache import (
    DEFAULT_EMBEDDING_TTL,
    EmbeddingCache,
    EmbeddingResult,
    get_embedding_cache,
    reset_embedding_cache_singleton,
)
from .keys import (
    BENCHMARK_CONFIG_VERSION,
    embedding_cache_key,
    response_cache_key,
)
from .response_cache import (
    DEFAULT_RESPONSE_TTL,
    CacheInfo,
    ResponseCache,
    get_response_cache,
    reset_response_cache_singleton,
)

__all__ = [
    "BENCHMARK_CONFIG_VERSION",
    "CacheBackend",
    "CacheInfo",
    "CacheStats",
    "DEFAULT_EMBEDDING_TTL",
    "DEFAULT_RESPONSE_TTL",
    "EmbeddingCache",
    "EmbeddingResult",
    "InMemoryCache",
    "RedisCache",
    "ResponseCache",
    "embedding_cache_key",
    "get_cache",
    "get_embedding_cache",
    "get_response_cache",
    "response_cache_key",
    "reset_cache_singleton",
    "reset_embedding_cache_singleton",
    "reset_response_cache_singleton",
]
