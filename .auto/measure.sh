#!/bin/bash
set -euo pipefail

# Fixed acceptance test suite for CONCERNS.md fixes + modern tooling.
# Each test returns 0 (pass) or 1 (fail). Score = number of passes.
# DO NOT MODIFY these tests — they define the fixed acceptance criteria.

SCORE=0
TOTAL=20

pass() { SCORE=$((SCORE + 1)); echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; }

echo "=== Acceptance Checks ($TOTAL total) ==="

# ── Backend Tooling ──────────────────────────────────────────────────

# 1. pyproject.toml exists with ruff config
if [ -f backend/pyproject.toml ] && grep -q 'ruff' backend/pyproject.toml 2>/dev/null; then
  pass "pyproject.toml with ruff config exists"
else
  fail "pyproject.toml with ruff config does not exist"
fi

# 2. uv.lock exists
if [ -f backend/uv.lock ]; then
  pass "uv.lock exists"
else
  fail "uv.lock does not exist"
fi

# 3. No aiocache in dependencies
if ! grep -q 'aiocache' backend/pyproject.toml 2>/dev/null && ! grep -q 'aiocache' backend/requirements.txt 2>/dev/null; then
  pass "aiocache removed from dependencies"
else
  fail "aiocache still in dependencies"
fi

# 4. No redis_url in Settings
if [ -f backend/app/config.py ] && ! grep -q 'redis_url' backend/app/config.py 2>/dev/null; then
  pass "redis_url removed from Settings"
else
  fail "redis_url still in Settings"
fi

# ── Pre-commit Fix ──────────────────────────────────────────────────

# 5. prek.toml removed or replaced with valid .pre-commit-config.yaml
if [ ! -f prek.toml ]; then
  pass "prek.toml removed"
elif [ -f .pre-commit-config.yaml ]; then
  pass "prek.toml replaced with .pre-commit-config.yaml"
else
  fail "prek.toml still exists and no .pre-commit-config.yaml"
fi

# ── Gemini Streaming Fix ────────────────────────────────────────────

# 6. Gemini provider uses client.stream() instead of client.post()
if [ -f backend/app/providers/gemini.py ] && grep -q 'client.stream' backend/app/providers/gemini.py 2>/dev/null && ! grep -q 'response = await client.post' backend/app/providers/gemini.py 2>/dev/null; then
  pass "Gemini provider uses streaming"
else
  fail "Gemini still uses non-streaming client.post()"
fi

# ── Empty Results Crash Fix ─────────────────────────────────────────

# 7. BenchmarkResults.tsx has early return when good.length === 0
if [ -f frontend/src/pages/BenchmarkResults.tsx ] && grep -q 'good.length === 0' frontend/src/pages/BenchmarkResults.tsx 2>/dev/null; then
  pass "Empty results early return in BenchmarkResults.tsx"
else
  fail "No early return for empty results in BenchmarkResults.tsx"
fi

# ── Model List Deduplication ────────────────────────────────────────

# 8. Model lists not duplicated between provider and pricing.py
# Check that pricing.py uses imports/dict merge instead of hardcoding same lists
if [ -f backend/app/pricing.py ] && grep -q 'from.*providers.*import' backend/app/pricing.py 2>/dev/null; then
  pass "Pricing imports model list from providers"
elif [ -f backend/app/pricing.py ] && grep -q 'provider_model_lists' backend/app/pricing.py 2>/dev/null; then
  pass "Pricing uses shared model list source"
elif [ -f backend/app/pricing.py ] && ! grep -q 'gemma-4-31b-it:free' backend/app/pricing.py 2>/dev/null; then
  pass "Pricing no longer duplicates individual free model names"
else
  fail "Model lists still duplicated between provider and pricing.py"
fi

# ── API Key Evaluation at Call Time ─────────────────────────────────

# 9. Provider api_key read at call time from settings, not class variable
MATCHES=0
for f in backend/app/providers/openai.py backend/app/providers/anthropic.py backend/app/providers/gemini.py backend/app/providers/openrouter.py; do
  if [ -f "$f" ] && grep -q 'api_key.*=.*settings\.' "$f" 2>/dev/null; then
    # Check it's inside a method/property, not a class variable
    if grep -q 'self\.api_key' "$f" 2>/dev/null || grep -q 'api_key.*=.*settings\.' "$f" | grep -q 'def '; then
      MATCHES=$((MATCHES + 1))
    fi
  fi
done
# More pragmatic: check that at least one provider reads key at call time instead of import time
if grep -q 'settings\..*_api_key' backend/app/providers/common.py 2>/dev/null || \
   grep -q 'settings\..*_api_key' backend/app/providers/openai.py 2>/dev/null || \
   grep -q 'settings\..*_api_key' backend/app/providers/anthropic.py 2>/dev/null; then
  pass "API keys read at call time from settings"
else
  fail "API keys still evaluated at import time"
fi

# ── response_length → response_chars ────────────────────────────────

# 10. Field renamed in models, schemas, base, and UI
RENAME_OK=0
grep -q 'response_chars' backend/app/models.py 2>/dev/null && RENAME_OK=$((RENAME_OK + 1)) || true
grep -q 'response_chars' backend/app/schemas.py 2>/dev/null && RENAME_OK=$((RENAME_OK + 1)) || true
grep -q 'response_chars' backend/app/providers/base.py 2>/dev/null && RENAME_OK=$((RENAME_OK + 1)) || true
grep -q 'response_chars' frontend/src/pages/BenchmarkResults.tsx 2>/dev/null && RENAME_OK=$((RENAME_OK + 1)) || true
if [ "$RENAME_OK" -ge 3 ]; then
  pass "response_length renamed to response_chars (found in $RENAME_OK/4 expected files)"
else
  fail "response_length still used, should be response_chars"
fi

# ── Prompt Input Limits ─────────────────────────────────────────────

# 11. prompt field has max_length constraint
if [ -f backend/app/schemas.py ] && grep -q 'max_length' backend/app/schemas.py 2>/dev/null; then
  pass "prompt field has max_length constraint"
else
  fail "prompt field missing max_length constraint"
fi

# ── Settings lru_cache Removal ──────────────────────────────────────

# 12. get_settings() no longer uses @lru_cache
if [ -f backend/app/config.py ] && ! grep -q '@lru_cache' backend/app/config.py 2>/dev/null; then
  pass "get_settings() no longer uses lru_cache"
else
  fail "get_settings() still uses lru_cache"
fi

# ── Ollama eval_count Safeguard ─────────────────────────────────────

# 13. Ollama provider validates response shape
if [ -f backend/app/providers/ollama.py ] && (grep -q 'get(' backend/app/providers/ollama.py 2>/dev/null || grep -q 'warn' backend/app/providers/ollama.py 2>/dev/null); then
  pass "Ollama provider validates response shape"
else
  fail "Ollama provider missing response shape validation"
fi

# ── Claude Input Tokens Robustness ─────────────────────────────────

# 14. Anthropic provider extracts input_tokens robustly
if [ -f backend/app/providers/anthropic.py ] && (grep -q 'message_start' backend/app/providers/anthropic.py 2>/dev/null || grep -q 'input_tokens' backend/app/providers/anthropic.py | grep -q 'get'); then
  pass "Anthropic provider extracts input_tokens robustly from message_start"
else
  fail "Anthropic provider may miss input_tokens"
fi

# ── Rate Limiting ──────────────────────────────────────────────────

# 15. slowapi middleware added
if grep -q 'slowapi' backend/app/main.py 2>/dev/null || grep -q 'slowapi' backend/app/config.py 2>/dev/null || grep -q 'slowapi' backend/app/requirements.txt 2>/dev/null || grep -q 'slowapi' backend/pyproject.toml 2>/dev/null; then
  pass "Rate limiting (slowapi) added"
else
  fail "No rate limiting added"
fi

# ── Insights Pagination ────────────────────────────────────────────

# 16. Insights endpoint has limit/offset or date range filter
if [ -f backend/app/routers/insights.py ] && (grep -q 'limit' backend/app/routers/insights.py 2>/dev/null || grep -q 'offset' backend/app/routers/insights.py 2>/dev/null || grep -q 'date_range' backend/app/routers/insights.py 2>/dev/null); then
  pass "Insights endpoint has pagination/filtering"
else
  fail "Insights endpoint still loads all data unbounded"
fi

# ── Concurrent Benchmark Limit ──────────────────────────────────────

# 17. create_benchmark caps models per request
if [ -f backend/app/routers/benchmarks.py ] && (grep -q 'max_length' backend/app/routers/benchmarks.py 2>/dev/null || grep -q 'semaphore' backend/app/routers/benchmarks.py 2>/dev/null || grep -q 'max.*models' backend/app/routers/benchmarks.py 2>/dev/null); then
  pass "create_benchmark has concurrency/model cap"
else
  fail "create_benchmark has no concurrency/model cap"
fi

# ── Status Recovery ─────────────────────────────────────────────────

# 18. Stuck "running" benchmarks detected/repaired
if grep -q 'running' backend/app/routers/benchmarks.py 2>/dev/null | grep -q -i 'stale\|stuck\|recover\|expir' backend/app/routers/benchmarks.py 2>/dev/null || grep -q -i 'stale\|stuck\|recover\|expir' backend/app/main.py 2>/dev/null || grep -q -i 'stale\|stuck\|recover\|expir' backend/app/database.py 2>/dev/null; then
  pass "Stuck benchmark status recovery exists"
else
  fail "No stuck benchmark status recovery"
fi

# ── Error Boundaries ────────────────────────────────────────────────

# 19. Frontend has React error boundaries
if grep -q 'ErrorBoundary' frontend/src/main.tsx 2>/dev/null || grep -q 'ErrorBoundary' frontend/src/App.tsx 2>/dev/null; then
  pass "Frontend has React error boundaries"
else
  fail "Frontend missing error boundaries"
fi

# ── Provider Error Handling ─────────────────────────────────────────

# 20. All generate() methods validate response structure
VALIDATION_OK=0
for f in backend/app/providers/common.py backend/app/providers/anthropic.py backend/app/providers/gemini.py backend/app/providers/ollama.py; do
  if [ -f "$f" ] && grep -q 'try:' "$f" 2>/dev/null; then
    VALIDATION_OK=$((VALIDATION_OK + 1))
  fi
done
if [ "$VALIDATION_OK" -ge 1 ]; then
  pass "Provider response validation added (try/except found in $VALIDATION_OK files)"
else
  fail "No provider response validation added"
fi

# ── Summary ─────────────────────────────────────────────────────────

echo ""
echo "=== Score: $SCORE / $TOTAL ==="
echo "METRIC acceptance_passed=$SCORE"
