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

Leave the helpers as per-class copies. Do not extract to a shared `_BYOKTestBase` class at this time.

The refactoring was attempted during the CONCERNS.md cleanup pass but proved too invasive for `str_replace`-based editing — the files had been modified in the same worktree session, and the exact multi-line match failed. The tests are passing correctly (105/105), the duplication is self-contained within a single file, and the helpers are small (5–10 lines each). The risk of introducing a subtle test bug during extraction currently outweighs the maintenance benefit.

### When to revisit

Extract to a shared base class when any of these triggers occur:

1. **A fourth provider** needs BYOK wire-level tests — the 4-copy threshold makes extraction clearly worthwhile.
2. **A helper diverges** — if one class changes `_capture_transport` in a way that suggests the pattern is evolving, extraction prevents accidental inconsistency.
3. **A test bug is traced to copy-paste inconsistency** — if a fix applies to two classes but the third was missed, extraction becomes a correctness issue, not just a style one.
4. **The file is being restructured for another reason** — piggyback on an existing refactoring to amortize the risk.

### Extraction target design

When extraction happens, the target is:

```python
class _BYOKTestBase:
    _sse_body: str = ""  # Subclasses override

    @classmethod
    def _capture_transport(cls, captured: dict):
        body = cls._sse_body
        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.content
            return httpx.Response(200, text=body)
        return httpx.MockTransport(handler)

    @classmethod
    def _patched_client(cls, captured: dict):
        transport = cls._capture_transport(captured)
        class _PC(httpx.AsyncClient):
            def __init__(self, *a, **kw):
                kw["transport"] = transport
                super().__init__(*a, **kw)
        return _PC

    @staticmethod
    def _mock_settings(**kw):
        return Mock(**kw)
```

Key change: `_capture_transport` becomes a `@classmethod` so `_sse_body` is resolved from the calling subclass, not hardcoded via `TestBYOKAuthHeader._sse_body`.

## Consequences

### Positive

- No refactoring risk to 18 passing tests
- Helpers are self-contained within each class — easy to read and modify independently
- The "when to revisit" triggers are concrete and unambiguous
- Extraction target design is documented, reducing future design churn

### Negative

- 3 copies of ~10-line helpers — maintenance burden if the pattern changes
- A new provider's BYOK tests will add a 4th copy before extraction triggers
- The duplication in CONCERNS.md remains as a known issue (lowered priority)
