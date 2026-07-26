from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Benchmark, BenchmarkResult

router = APIRouter()


@router.get("/insights")
def insights(db: Session = Depends(get_db)):
    benchmarks = db.scalars(select(Benchmark).options(selectinload(Benchmark.results))).all()
    expensive = None
    if benchmarks:
        candidate = max(benchmarks, key=lambda b: sum(r.cost or 0 for r in b.results))
        expensive = {"benchmark_id": candidate.id, "prompt": candidate.prompt, "total_cost": sum(r.cost or 0 for r in candidate.results)}

    grouped = defaultdict(list)
    results = db.scalars(select(BenchmarkResult).where(BenchmarkResult.error.is_(None))).all()
    for result in results:
        if result.cost is not None and result.total_latency_ms is not None:
            grouped[(result.provider, result.model)].append(result)
    stats = []
    for (provider, model), rows in grouped.items():
        avg_cost = sum(r.cost for r in rows) / len(rows)
        avg_latency = sum(r.total_latency_ms for r in rows) / len(rows)
        stats.append({"provider": provider, "model": model, "avg_cost": avg_cost, "avg_latency_ms": avg_latency})
    fastest = min(stats, key=lambda x: x["avg_latency_ms"], default=None)
    cheapest = min(stats, key=lambda x: x["avg_cost"], default=None)
    best = min(stats, key=lambda x: x["avg_cost"] * x["avg_latency_ms"], default=None)
    return {
        "most_expensive_prompt": expensive,
        "fastest_model": {k: fastest[k] for k in ("provider", "model", "avg_latency_ms")} if fastest else None,
        "lowest_cost_model": {k: cheapest[k] for k in ("provider", "model", "avg_cost")} if cheapest else None,
        "best_cost_performance": {**best, "score": best["avg_cost"] * best["avg_latency_ms"]} if best else None,
    }
