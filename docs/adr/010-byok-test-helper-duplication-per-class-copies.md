# 10. BYOK Test Helper Duplication — Per-Class Copies vs Shared Base

Date: 2026-07-28

## Status

Accepted

## Context

`backend/tests/test_providers.py` contains three BYOK wire-level test classes — `TestBYOKAuthHeader` (OpenAI), `TestBYOKAnthropicAuthHeader` (Anthropic), and `TestBYOKGeminiAuthHeader` (Gemini) — totalling 18 tests. Each class defines three identical static/class methods:

```python
@staticmethod
def _capture_transport(captured: dict):
    """Return an httpx.MockTransport that writes request headers into *captured*."""
    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200, text=cls._sse_body)
    return httpx.MockTransport(handler)

@staticmethod
def _patched_client(captured: dict):
    """Return an AsyncClient subclass that injects our capture transport."""
    class _PC(httpx.AsyncClient):
        def __init__(self, *a, **kw):
            kw["transport"] = cls._capture_transport(captured)
            super().__init__(*a, **kw)
    return _PC

@staticmethod
def _mock_settings(**kw):
    """Return a mock Settings object with the given attributes."""
    return Mock(**kw)
```

The only difference between classes is `_sse_body` — each provider has a different SSE stream format (OpenAI delta chunks, Anthropic content_block_delta events, Gemini candidates/parts).

This is ~30 lines duplicated across three classes. A new provider with BYOK tests would add a fourth copy.

## Decision

Extract the three helpers — `_capture_transport`, `_patched_client`, `_mock_settings` — into a shared `_BYOKTestBase` class. All three BYOK test classes (`TestBYOKAuthHeader`, `TestBYOKAnthropicAuthHeader`, `TestBYOKGeminiAuthHeader`) inherit from this base.

Initially deferred ("too invasive for str_replace"), the extraction was successfully completed in a subsequent code-quality pass. The `_BYOKTestBase` is a plain `object` subclass — no pytest collection (leading underscore), no shared mutable state (each method creates fresh objects per call), and each subclass keeps its own `_sse_body` class attribute for provider-specific SSE formats.

### What was extracted

```python
class _BYOKTestBase:
    _sse_body: str = ""  # Subclasses override

    @classmethod
    def _capture_transport(cls, captured: dict):
        """Return an httpx.MockTransport that captures request details."""
        body = cls._sse_body
        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.content
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, text=body)
        return httpx.MockTransport(handler)

    @classmethod
    def _patched_client(cls, captured: dict):
        """Return an AsyncClient subclass with capture transport injected."""
        transport = cls._capture_transport(captured)
        class _PC(httpx.AsyncClient):
            def __init__(self, *a, **kw):  # noqa: PLW0642
                kw["transport"] = transport
                super().__init__(*a, **kw)
        return _PC

    @staticmethod
    def _mock_settings(**kw):
        """Return a mock Settings object with the given attributes."""
        return Mock(**kw)
```

Key design: `_capture_transport` and `_patched_client` are `@classmethod` so `cls._sse_body` resolves to the calling subclass's attribute at call time (MRO). `_mock_settings` remains `@staticmethod` since it needs no class context.

### What was NOT extracted

- `_sse_body` — each provider has a different SSE stream format and remains a class attribute on each test class.

## Consequences

### What was NOT extracted

- `_sse_body` — each provider has a different SSE stream format and must remain in its own test class.

## Consequences

### Positive

- 3 duplicate copies removed (~30 lines saved), single source of truth for transport/patcher/mock helpers
- A fourth provider's BYOK tests now inherit helpers for free — no new copy needed
- Each subclass keeps its own `_sse_body` — provider-specific formats remain independent
- CONCERNS.md #4 resolved; the file is cleaner

### Negative

- `_BYOKTestBase` adds one level of indirection — new contributors must trace MRO to find helpers
- If a future provider needs a fundamentally different transport pattern, the shared base adds friction
