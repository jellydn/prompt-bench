from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelSelection(BaseModel):
    provider: str
    model: str


class BenchmarkCreate(BaseModel):
    prompt: str = Field(min_length=1)
    system_prompt: str = ""
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(1000, gt=0)
    models: list[ModelSelection] = Field(min_length=1)


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
    response_length: int | None
    response_text: str | None
    error: str | None


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
