from abc import ABC, abstractmethod
from dataclasses import dataclass


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

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> ProviderResponse: ...

    @abstractmethod
    def get_models(self) -> list[ModelInfo]: ...

    @property
    @abstractmethod
    def is_configured(self) -> bool: ...
