"""Tests for benchmark API endpoint behaviors."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.models import Benchmark, BenchmarkResult
from app.routers.benchmarks import _repair_stuck_benchmarks


class TestBenchmarkEndpoints:
    """Benchmark API behavior, validation, and edge cases."""

    def test_health(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_create_benchmark_empty_prompt(self, client):
        resp = client.post("/api/benchmarks", json={"prompt": "", "models": []})
        assert resp.status_code == 422  # Validation error

    def test_create_benchmark_too_many_models(self, client):
        """Model list max_length=10 should reject 11 models."""
        models = [{"provider": "openai", "model": "gpt-4o-mini"}] * 11
        resp = client.post(
            "/api/benchmarks",
            json={"prompt": "Hello", "models": models},
        )
        assert resp.status_code == 422

    def test_list_benchmarks_empty(self, client):
        resp = client.get("/api/benchmarks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_benchmark_not_found(self, client):
        resp = client.get("/api/benchmarks/999")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/benchmarks/999")
        assert resp.status_code == 404

    def test_insights_empty(self, client):
        resp = client.get("/api/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["most_expensive_prompt"] is None
        assert data["fastest_model"] is None
        assert data["lowest_cost_model"] is None

    def test_providers_list(self, client):
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        providers = resp.json()
        provider_ids = [p["id"] for p in providers]
        assert "openai" in provider_ids
        assert "anthropic" in provider_ids
        assert "gemini" in provider_ids
        assert "openrouter" in provider_ids
        assert "ollama" in provider_ids
        assert "vllm" in provider_ids


class TestStuckBenchmarks:
    """Stuck benchmark status recovery."""

    def test_repair_stuck_running(self, db_session):
        """A 'running' benchmark older than 5 min should be repaired on next read."""
        old = Benchmark(
            prompt="stuck",
            status="running",
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(old)
        db_session.commit()

        _repair_stuck_benchmarks(db_session)

        db_session.refresh(old)
        assert old.status == "failed"

    def test_recent_running_not_touched(self, db_session):
        """A 'running' benchmark from a few seconds ago should remain running."""
        recent = Benchmark(
            prompt="in-progress",
            status="running",
            created_at=datetime.now(UTC),
        )
        db_session.add(recent)
        db_session.commit()

        _repair_stuck_benchmarks(db_session)

        db_session.refresh(recent)
        assert recent.status == "running"


class TestResponseChars:
    """Verify response_chars column mapping to response_length SQL column."""

    def test_column_stored_as_response_length(self, db_session):
        """The Python attribute 'response_chars' maps to SQL column 'response_length'."""
        result = BenchmarkResult(
            benchmark_id=None,
            provider="test",
            model="test-model",
            response_chars=42,
        )
        # Temporarily allow null benchmark_id for this test
        result.benchmark_id = 0
        db_session.add(result)
        db_session.commit()

        # Read back via raw SQL to check actual column name
        row = db_session.execute(
            text("SELECT response_length FROM benchmark_results WHERE id = :id"),
            {"id": result.id},
        ).one()
        assert row[0] == 42
