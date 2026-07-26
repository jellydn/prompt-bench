#!/bin/bash
set -euo pipefail

# Correctness checks — runs after each passing benchmark.
# Use to validate that code changes don't break existing functionality.
# NOTE: Only errors are relevant — suppress verbose success output.

echo "=== Checks ==="

# ── Python lint ─────────────────────────────────────────────────────
echo "--- ruff check ---"
cd backend
uv run ruff check . 2>&1 || {
    echo "FAIL: ruff check failed"
    exit 1
}
echo "ruff: ok"

# ── Python tests ────────────────────────────────────────────────────
echo "--- pytest ---"
uv run --extra dev pytest -q --tb=short 2>&1 | tail -20 || {
    echo "FAIL: pytest failed"
    exit 1
}

# ── Frontend checks ─────────────────────────────────────────────────
cd ../frontend
echo "--- npm run build ---"
npm run build 2>&1 | tail -5 || {
    echo "FAIL: frontend build failed"
    exit 1
}

echo "=== All checks passed ==="
