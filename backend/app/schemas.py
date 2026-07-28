from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelSelection(BaseModel):
    provider: str
    model: str


class BenchmarkCreate(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    prompt: str = Field(min_length=1, max_length=100_000)
    system_prompt: str = ""
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(1000, gt=0)
    models: list[ModelSelection] = Field(min_length=1, max_length=10)
    # Set to False to bypass the response cache for this run (always calls providers).
    cache: bool = True
    # Bring-your-own-key: per-provider API keys supplied by the browser.
    # Keys are never persisted, never logged — kept in memory for this request only.
    client_keys: dict[str, str] | None = None
    # Internal: session ID from cookie for Phase 2 BYOK session keys.
    # Not part of the public API — injected by the benchmark endpoint.
    _session_id: str | None = None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    ttft_ms: int | None
    total_latency_ms: int | None
    cost: float | None
    response_chars: int | None
    response_text: str | None
    error: str | None
    cache_hit: bool | None = None
    cache_type: str | None = None
    cache_lookup_ms: int | None = None
    provider_latency_ms: int | None = None


class BenchmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prompt: str
    system_prompt: str
    temperature: float
    max_tokens: int
    status: str
    created_at: datetime
    results: list[ResultOut]


class BenchmarkSummary(BaseModel):
    id: int
    prompt: str
    created_at: datetime
    model_count: int
    total_cost: float
    total_tokens: int
    avg_latency_ms: float
    status: str
