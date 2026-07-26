from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Benchmark, BenchmarkResult

router = APIRouter()


@router.get("/insights")
def insights(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    # Load recent benchmark IDs (bounded by limit)
    bench_ids_q = select(Benchmark.id).order_by(Benchmark.created_at.desc()).limit(limit)
    bench_ids = [row[0] for row in db.execute(bench_ids_q).all()]
    if not bench_ids:
        return _empty_response()

    # Most expensive prompt (SQL-level SUM)
    expensive_row = db.execute(
        select(
            BenchmarkResult.benchmark_id,
            func.sum(BenchmarkResult.cost).label("total_cost"),
        )
        .where(BenchmarkResult.benchmark_id.in_(bench_ids))
        .where(BenchmarkResult.cost.isnot(None))
        .group_by(BenchmarkResult.benchmark_id)
        .order_by(func.sum(BenchmarkResult.cost).desc())
        .limit(1)
    ).first()

    expensive = _resolve_expensive(db, expensive_row)

    # Model stats via SQL AVG + GROUP BY
    model_rows = db.execute(
        select(
            BenchmarkResult.provider,
            BenchmarkResult.model,
            func.avg(BenchmarkResult.cost).label("avg_cost"),
            func.avg(BenchmarkResult.total_latency_ms).label("avg_latency_ms"),
        )
        .where(BenchmarkResult.benchmark_id.in_(bench_ids))
        .where(BenchmarkResult.error.is_(None))
        .where(BenchmarkResult.cost.isnot(None))
        .where(BenchmarkResult.total_latency_ms.isnot(None))
        .group_by(BenchmarkResult.provider, BenchmarkResult.model)
    ).all()

    fastest = cheapest = best = None
    if model_rows:
        rows = [
            {
                "provider": r.provider,
                "model": r.model,
                "avg_cost": r.avg_cost,
                "avg_latency_ms": r.avg_latency_ms,
            }
            for r in model_rows
        ]
        fastest = min(rows, key=lambda x: x["avg_latency_ms"])
        cheapest = min(rows, key=lambda x: x["avg_cost"])
        best = min(rows, key=lambda x: x["avg_cost"] * x["avg_latency_ms"])

    return {
        "most_expensive_prompt": expensive,
        "fastest_model": {k: fastest[k] for k in ("provider", "model", "avg_latency_ms")}
        if fastest
        else None,
        "lowest_cost_model": {k: cheapest[k] for k in ("provider", "model", "avg_cost")}
        if cheapest
        else None,
        "best_cost_performance": {**best, "score": best["avg_cost"] * best["avg_latency_ms"]}
        if best
        else None,
    }


def _resolve_expensive(db, row):
    if not row:
        return None
    benchmark = db.get(Benchmark, row.benchmark_id)
    if not benchmark:
        return None
    return {
        "benchmark_id": row.benchmark_id,
        "prompt": benchmark.prompt,
        "total_cost": row.total_cost,
    }


def _empty_response():
    return {
        "most_expensive_prompt": None,
        "fastest_model": None,
        "lowest_cost_model": None,
        "best_cost_performance": None,
    }
