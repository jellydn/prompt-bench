# 2. Provider Abstraction Pattern

Date: 2026-07-28

## Status

Accepted

## Context

PromptBench benchmarks LLM responses across multiple providers — OpenAI, Anthropic, Google Gemini, OpenRouter, Ollama (local), and vLLM (self-hosted). Each provider has:

- A different API wire format (OpenAI-style chat completions, Anthropic SSE, Gemini REST)
- A different authentication method (Bearer token, `x-api-key` header, URL query param)
- A different streaming protocol (SSE with `data:` prefix, JSON-lines, Server-Sent Events)
- A different pricing structure (per-token input/output, free tiers)
- Different model lists that change over time

Without a shared abstraction:
- Adding a new provider requires touching benchmark orchestration, API endpoints, pricing, and caching.
- Provider-specific auth logic leaks into `run_one()` and the benchmark router.
- Streaming response parsing would be copy-pasted across providers.
- BYOK (client-supplied keys) would need per-provider special-casing in every call site.
- The `/api/providers` endpoint would need manual enumeration.

## Decision

All providers implement a shared `BaseProvider` abstract interface, registered in a module-level `PROVIDERS` dict, with a reusable `OpenAICompatibleProvider` base class for providers that speak the OpenAI chat-completions API.

### 1. BaseProvider interface (`app/providers/base.py`)

```python
class BaseProvider(ABC):
    provider_id: str       # e.g. "openai", "anthropic"
    provider_name: str     # e.g. "OpenAI", "Anthropic"
    _client_api_key: str | None = None  # per-request BYOK override

    async def generate(prompt, model, system_prompt, temperature, max_tokens) -> ProviderResponse
    def get_models() -> list[ModelInfo]
    @property
    def is_configured() -> bool
```

Every provider is responsible for its own HTTP transport, SSE parsing, token counting, and cost calculation — the caller (`run_one()`) only sees the abstract `generate()` contract. This is the **Strategy pattern**: the benchmark orchestration code never knows which provider it's calling.

### 2. PROVIDERS registry (`app/providers/__init__.py`)

```python
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
```

A module-level dict maps `provider_id` → singleton instance. Adding a new provider is a single import + one line in the list. The registry is consumed by:

- `get_provider(provider_id)` — direct lookup used by `run_one()`
- `get_providers_cached()` — compiles model info for `/api/providers`, TTL-cached (5 min)

The registry is intentionally flat — no plugin discovery, no dynamic loading. At PromptBench's scale (6 providers), explicit registration is simpler and greppable.

### 3. OpenAICompatibleProvider (`app/providers/common.py`)

Three providers (OpenAI, OpenRouter, vLLM) share an identical HTTP shape — POST JSON to an OpenAI-style `/v1/chat/completions` endpoint with `Authorization: Bearer <key>`, SSE streaming with `data:` prefix, and `usage` in the final chunk.

Rather than duplicate the 60-line `generate()` method three times, it lives once in `OpenAICompatibleProvider(BaseProvider)`:

```python
class OpenAICompatibleProvider(BaseProvider):
    api_key = ""              # overridden per subclass
    base_url = ""             # e.g. "https://api.openai.com/v1/chat/completions"
    model_names: dict = {}    # e.g. {"gpt-4o": "GPT-4o"}
    always_configured = False  # Ollama/vLLM override to True
    extra_headers: dict = {}   # e.g. OpenRouter attribution headers
```

Subclasses only declare their identity:

```python
class OpenAIProvider(OpenAICompatibleProvider):
    provider_id, provider_name = "openai", "OpenAI"
    base_url = "https://api.openai.com/v1/chat/completions"
    model_names = {"gpt-4o": "GPT-4o", ...}

    @property
    def api_key(self):
        return get_settings().openai_api_key
```

This is the **Template Method pattern**: the base class defines the HTTP orchestration skeleton; subclasses fill in the identity, endpoint, and auth details.

### 4. Per-module provider organization

Each provider lives in its own file:

```
providers/
├── __init__.py      # PROVIDERS registry, get_provider(), get_providers_cached()
├── base.py          # BaseProvider ABC, ModelInfo, ProviderResponse
├── common.py        # OpenAICompatibleProvider (OpenAI/OpenRouter/vLLM)
├── openai.py        # OpenAIProvider
├── anthropic.py     # AnthropicProvider
├── gemini.py        # GeminiProvider
├── openrouter.py    # OpenRouterProvider
├── ollama.py        # OllamaProvider
├── vllm.py          # VLLMProvider
├── model_lists.py   # OpenRouter free/paid model catalog
└── pricing.py       # PRICING dict, calculate_cost()
```

This is deliberate — no god-file for all providers. Adding a new provider means creating one file (~20–80 lines) and adding one entry to `__init__.py`. Everything else (benchmark orchestration, caching, API endpoints) works without changes.

### 5. `is_configured` / `always_configured` distinction

| Pattern | Providers | Meaning |
|---|---|---|
| `is_configured` checks `bool(get_settings().<key>)` | OpenAI, Anthropic, Gemini, OpenRouter | Provider is available only if the server `.env` has the API key (or a BYOK key is supplied) |
| `always_configured = True` | Ollama, vLLM | Local providers — no API key needed, always listed as available |
| BYOK override (`_client_api_key`) | All external providers | Per-request client-supplied key makes the provider `is_configured = True` for that request only |

The frontend uses the `configured` field from `/api/providers` to grey out unavailable providers. With BYOK, a provider becomes selectable when the user enters a key — the `is_configured` property checks `_client_api_key` before falling back to server settings.

### 6. ProviderResponse — shared output contract

All `generate()` methods return the same `ProviderResponse` dataclass:

```python
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
```

This is the **canonical output format** consumed by benchmark results, the cache layer, and the API response schema. Providers translate their native response shape into this contract — the rest of the system never sees provider-specific response formats.

## Consequences

### 📋 Positive

- **Adding a provider is 1 file + 1 line**: `OllamaProvider` is 29 lines, `OpenRouterProvider` is 22 lines.
- **Benchmark orchestration is provider-agnostic**: `run_one()` calls `provider.generate()` without knowing which provider it is. Caching, error handling, and logging work identically across all providers.
- **Code reuse via OpenAICompatibleProvider**: Three providers (OpenAI, OpenRouter, vLLM) share one `generate()` implementation — ~120 lines deduplicated. Adding another OpenAI-compatible provider (e.g., Groq, Together) would be ~5 lines.
- **BYOK is a one-line injection**: `provider._client_api_key = client_key` — no per-provider special casing needed.
- **Testable in isolation**: Each provider can be mocked independently. Tests for the benchmark router only need a fake `BaseProvider`, not a real HTTP client.

### 📋 Negative

- **Provider singletons are mutable**: The `PROVIDERS` dict holds shared instances. Originally, `run_one()` mutated `provider._client_api_key` directly on the singleton — this was fixed by using `copy.copy(provider)` for BYOK requests (see PR #7). Future contributors should be aware that providers are shared state.
- **Gemini auth is a query parameter**: `params={"key": ...}` puts the API key in the URL, which appears in server access logs and proxy logs. This is a Gemini API design constraint, not a PromptBench choice, but it's a privacy consideration for BYOK.
- **No async initialization**: Providers are instantiated synchronously at import time. If a future provider needs async setup (e.g., OAuth token refresh), the singleton pattern would need to change.
- **Anthropic/Gemini bypass OpenAICompatibleProvider**: These two providers have their own `generate()` methods (~80 lines each) because their wire formats differ. If a third non-OpenAI-compatible provider is added (e.g., Cohere), it would follow the same pattern — acceptable at the current scale.

### Alternatives Considered

**Plugin discovery with `importlib`**: Scan a `providers/` directory and auto-register classes. Rejected — at 6 providers, explicit registration is simpler, greppable, and avoids import-time side effects.

**One `generate()` to rule them all**: A single `generate()` method with provider-specific branches (`if provider == "openai": ... elif provider == "anthropic": ...`). Rejected — would create a god-function and force every provider change through one file.

**Adapter objects per request**: Instead of singletons, create a fresh provider instance for each request. Rejected — adds allocation overhead and the singleton pattern has worked correctly (with `copy.copy()` for BYOK).

**OpenAPI-based provider definition**: Define each provider as a YAML/JSON config (endpoint, auth header, model list) with a generic HTTP client. Rejected — each provider's streaming format is different enough (SSE, JSON-lines, Gemini's nested `candidates` structure) that a generic parser would be more complex than per-provider code.
