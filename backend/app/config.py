from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./promptbench.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    vllm_base_url: str = "http://localhost:8001"
    cors_origins: list[str] = ["http://localhost:5173", "https://prompt-bench.itman.fyi"]

    # ── Local providers (vLLM, Ollama) ─────────────────────────────────
    # Set to False in production (e.g. Dokku) to hide providers that need
    # a locally-running inference server.
    enable_local_providers: bool = True

    # ── Cache (Redis with in-memory fallback) ───────────────────────────
    # Set REDIS_URL to enable Redis; leave empty to use the in-memory backend.
    redis_url: str = ""
    cache_enabled: bool = True
    # TTLs in seconds. Defaults: response = 30 min, embedding = 24 h.
    cache_ttl_response: int = 30 * 60
    cache_ttl_embedding: int = 24 * 60 * 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


def get_settings() -> Settings:
    return Settings()


# Default instance for startup-time access (database.py, etc).
# Provider API keys are read fresh via get_settings() at call time.
settings = get_settings()
