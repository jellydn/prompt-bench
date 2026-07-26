import asyncio
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..limiter import limiter
from ..models import Benchmark, BenchmarkResult
from ..providers import get_provider
from ..schemas import BenchmarkCreate, BenchmarkOut, BenchmarkSummary

logger = logging.getLogger("promptbench.benchmarks")

router = APIRouter()

# Concurrency semaphore: max 5 concurrent provider API calls
_semaphore = asyncio.Semaphore(5)


async def run_one(item, benchmark_req):
    provider = get_provider(item.provider)
    if not provider:
        return item, None, f"Unknown provider: {item.provider}"
    if not provider.is_configured:
        return item, None, f"Provider {item.provider} is not configured"
    async with _semaphore:
        try:
            result = await provider.generate(
                benchmark_req.prompt,
                item.model,
                benchmark_req.system_prompt,
                benchmark_req.temperature,
                benchmark_req.max_tokens,
            )
            return item, result, None
        except Exception as exc:
            logger.error("Provider %s/%s failed: %s", item.provider, item.model, exc)
            return item, None, str(exc)


def _repair_stuck_benchmarks(db: Session) -> None:
    """Mark benchmarks stuck as 'running' for over 5 minutes as 'failed'."""
    try:
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        db.execute(
            update(Benchmark)
            .where(Benchmark.status == "running")
            .where(Benchmark.created_at < cutoff)
            .values(status="failed")
        )
        db.commit()
    except Exception:
        # Tables may not exist yet (e.g., during startup before migration)
        db.rollback()


@router.post("/benchmarks", response_model=BenchmarkOut)
@limiter.limit("10/minute")
async def create_benchmark(
    request: Request,
    payload: BenchmarkCreate,
    db: Session = Depends(get_db),
):
    _repair_stuck_benchmarks(db)
    benchmark = Benchmark(
        prompt=payload.prompt,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        status="running",
    )
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)
    logger.info(
        "Benchmark #%d started — %d model(s), prompt=%d chars",
        benchmark.id,
        len(payload.models),
        len(payload.prompt),
    )
    outcomes = await asyncio.gather(*(run_one(item, payload) for item in payload.models))
    for item, result, error in outcomes:
        values = (
            vars(result).copy()
            if result
            else {
                "input_tokens": None,
                "output_tokens": None,
                "ttft_ms": None,
                "total_latency_ms": None,
                "cost": None,
                "response_chars": None,
                "response_text": None,
            }
        )
        values.pop("error", None)
        db.add(
            BenchmarkResult(
                benchmark_id=benchmark.id,
                provider=item.provider,
                model=item.model,
                error=error,
                **values,
            )
        )
    benchmark.status = "failed" if all(error for _, _, error in outcomes) else "completed"
    db.commit()
    logger.info(
        "Benchmark #%d %s — %d/%d succeeded",
        benchmark.id,
        benchmark.status,
        sum(1 for _, _, error in outcomes if not error),
        len(outcomes),
    )
    return db.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.results))
        .where(Benchmark.id == benchmark.id)
    )


@router.get("/benchmarks", response_model=list[BenchmarkSummary])
def history(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    items = db.scalars(
        select(Benchmark)
        .options(selectinload(Benchmark.results))
        .order_by(Benchmark.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .offset(max(offset, 0))
    ).all()
    output = []
    for b in items:
        latencies = [
            r.total_latency_ms for r in b.results if r.total_latency_ms is not None and not r.error
        ]
        output.append(
            BenchmarkSummary(
                id=b.id,
                prompt=b.prompt,
                created_at=b.created_at,
                model_count=len(b.results),
                total_cost=sum(r.cost or 0 for r in b.results),
                total_tokens=sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in b.results),
                avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
                status=b.status,
            )
        )
    return output


@router.get("/benchmarks/{benchmark_id}", response_model=BenchmarkOut)
def detail(benchmark_id: int, db: Session = Depends(get_db)):
    item = db.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.results))
        .where(Benchmark.id == benchmark_id)
    )
    if not item:
        raise HTTPException(404, "Benchmark not found")
    return item


@router.delete("/benchmarks/{benchmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(benchmark_id: int, db: Session = Depends(get_db)):
    item = db.get(Benchmark, benchmark_id)
    if not item:
        raise HTTPException(404, "Benchmark not found")
    db.delete(item)
    db.commit()
    return Response(status_code=204)
