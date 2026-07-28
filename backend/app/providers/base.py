from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..pricing import PRICING


@dataclass
class ModelInfo:
    id: str
    name: str
    pricing: dict[str, float]


@dataclass
class ProviderResponse:
    input_tokens: int
    output_tokens: int
    ttft_ms: int
    total_latency_ms: int
    response_text: str
    response_chars: int
    cost: float
    error: str | None = None


class BaseProvider(ABC):
    provider_id: str
    provider_name: str
    # Set by run_one() when the user supplies a BYOK key for this provider.
    # Never persisted, never logged — cleared after the request completes.
    _client_api_key: str | None = None

    # Whether this provider supports BYOK (client-supplied API keys).
    # Local providers (Ollama, vLLM) return False — they don't need keys.
    byok_eligible: bool = True

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> ProviderResponse: ...

    def get_models(self) -> list[ModelInfo]:
        """Return model list with pricing from ``PRICING[self.provider_id]``.

        Subclasses only need to set ``model_names: dict[str, str]`` — the
        default implementation reads pricing automatically.  Providers with
        custom lookup logic (e.g. OpenRouter with runtime-refreshed lists)
        can override.
        """
        provider_pricing = PRICING.get(self.provider_id, {})
        return [
            ModelInfo(k, v, provider_pricing.get(k, {"input": 0.0, "output": 0.0}))
            for k, v in self.model_names.items()
        ]

    @property
    @abstractmethod
    def is_configured(self) -> bool: ...
