# 3. BYOK — Bring Your Own Key Architecture

Date: 2026-07-28

## Status

Accepted (Phase 1 implemented in PR #7)

## Context

PromptBench needs API keys for external providers (OpenAI, Anthropic, Gemini, OpenRouter). Today, those keys are configured server-side in `backend/.env` — only the operator who deployed the service can run benchmarks against those providers.

This creates three problems:

1. **Onboarding friction**: A new user visiting the deployed app sees greyed-out providers and "API key not set" — they can't benchmark anything without the operator adding keys.
2. **Billing confusion**: All benchmarks run through the operator's API accounts. The operator pays for all usage, even from unknown users.
3. **Trust**: Users may not want their prompts routed through an operator's API key — especially for confidential or proprietary prompts used in benchmark comparisons.

The feature request: "we also support end user to BYOK to test from browser, note about this is privacy and we won't store your key."

## Decision

Support client-supplied API keys (BYOK) with a privacy-first design — keys are per-request, in-memory only, never persisted, and never logged. The architecture follows a phased rollout.

### Phase 1 — Per-request keys (in-memory only) ✅ Implemented

**Key flow:**

1. User enters their API key in the browser (React state, `type="password"` input, never `localStorage`)
2. Frontend sends `client_keys: {"openai": "sk-...", "anthropic": "sk-ant-..."}` in the `POST /api/benchmarks` request body
3. Backend `run_one()` extracts the key for the provider being called
4. A **copy** of the provider singleton is created (`copy.copy(provider)`) — this prevents concurrent BYOK requests from racing on the shared instance
5. The client key is injected via `provider._client_api_key = client_key`
6. The provider's `generate()` reads `self._client_api_key` before falling back to `get_settings()`
7. After the request completes, the provider copy is garbage-collected — the key exists only in that request's memory

**Cache isolation:**

BYOK requests skip the response cache per-provider:

```python
use_cache = benchmark_req.cache and not bool(client_key)
```

This prevents User A's cached `gpt-4o-mini` result (billed to User A's key) from being served to User B (billed to User B's key). Pure server-configured providers in the same benchmark run still use the cache.

**Error sanitization:**

Provider error messages may embed the API key (e.g., OpenAI: `"Incorrect API key provided: sk-abc123..."`). Before returning to the frontend, errors pass through `_sanitize_error()`:

```python
re.sub(r"(sk-[a-zA-Z0-9_-]{20,}|AIza[a-zA-Z0-9_-]{30,})", "***", message)
```

**Logging:**

BYOK usage is logged at debug level — the key itself never appears:

```python
logger.debug("BYOK key used for provider=%s", item.provider)
```

### Phase 2 — Session-scoped keys (planned)

Current limitation: the per-request approach means users re-enter their key on every benchmark run. Phase 2 adds session persistence:

- `POST /api/session-key` — store key server-side in a session cookie (HttpOnly, SameSite=Strict)
- `DELETE /api/session-key` — clear the key
- Session keys expire after 30 minutes of inactivity
- CSRF token required on the key endpoint
- Frontend shows "Key saved for this session" and a "Clear my key" button

### Privacy invariants (enforced by design, not policy)

| Invariant | Mechanism |
|---|---|
| Keys never in the database | `_client_api_key` is a transient Python attribute, no ORM column |
| Keys never in cache entries | `use_cache = False` when `client_key` is present |
| Keys never in logs | Only `provider_id` is logged, never the key string |
| Keys never in error responses | `_sanitize_error()` strips `sk-*` and `AIza*` patterns |
| Keys never in `localStorage` | React state only; cleared on tab close |
| Keys never in URL | POST body only (JSON), no query params |
| No cross-request key leakage | `copy.copy(provider)` isolates each request's key |
| No cross-user cache leakage | BYOK results are never cached |

## Consequences

### 📋 Positive

- **Zero-config onboarding**: Users can benchmark OpenAI, Anthropic, or Gemini immediately by bringing their own key — no operator intervention needed.
- **User-owned billing**: Each user's benchmark usage is billed to their own API account. The operator pays nothing for BYOK traffic.
- **Privacy by construction**: Keys cannot leak through logs, caches, databases, or error responses because there are no code paths that write them to those sinks.
- **Incremental deployment**: Phase 1 works with zero server-side state. Phase 2 adds session persistence without changing the core injection mechanism.

### 📋 Negative

- **Re-entry friction (Phase 1)**: Users must paste their key on every benchmark run. Mitigated by Phase 2 session-scoped keys.
- **Gemini URL-param key exposure**: Gemini passes the API key as a URL query parameter (`?key=...`). This means the key appears in server access logs, HTTP referrer headers, and potentially proxy/cache logs. This is a Gemini API design constraint — PromptBench cannot change it. The BYOK documentation should warn users about this provider-specific risk.
- **No key validation (Phase 1)**: A mistyped key is only discovered when the provider returns an error during the benchmark run. A future `/api/validate-key` endpoint (trivial prompt → check for auth error) would improve UX.
- **Rate limiting unchanged**: The existing `@limiter.limit("10/minute")` is IP-based, not key-based. A user with multiple keys is not rate-limited per-key. Acceptable for Phase 1.

### Alternatives Considered

**Proxy through operator keys only (status quo)**: Rejected — blocks onboarding, confuses billing, and limits the audience to operators who have configured all providers.

**Client-side direct API calls**: The browser calls OpenAI/Anthropic directly, bypassing the PromptBench backend entirely. Rejected — this would expose API keys to browser extensions and XSS, require CORS headers from every provider, and prevent PromptBench from measuring latency (TTFT would be meaningless).

**Key passed as HTTP header**: `X-Client-Key: sk-...` instead of JSON body. Rejected — harder to mask in DevTools, and JSON body is more natural alongside the benchmark parameters.

**Encrypted key store with a user-provided passphrase**: Encrypt the key client-side and store the ciphertext in `localStorage`. Rejected — adds complexity for marginal benefit in Phase 1, and the threat model (casual tab-closing) doesn't justify encryption.

**Per-user cache key hashing**: Instead of disabling the cache entirely for BYOK, include a hash of the user's key in the cache key. Rejected — a key hash is effectively a user fingerprint, and cached results could still leak across users if the hash collides. Disabling the cache is simpler and provably correct.

**Global provider clone for all BYOK requests**: One cloned `PROVIDERS` dict per request instead of per-provider copy. Rejected — `copy.copy(provider)` is lighter weight when only one or two providers in a benchmark run use BYOK.
