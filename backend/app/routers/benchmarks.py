import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Benchmark, BenchmarkResult
from ..providers import get_provider
from ..schemas import BenchmarkCreate, BenchmarkOut, BenchmarkSummary

router = APIRouter()


async def run_one(item, request):
    provider = get_provider(item.provider)
    if not provider: return item, None, f"Unknown provider: {item.provider}"
    if not provider.is_configured: return item, None, f"Provider {item.provider} is not configured"
    try:
        result = await provider.generate(request.prompt, item.model, request.system_prompt, request.temperature, request.max_tokens)
        return item, result, None
    except Exception as exc:
        return item, None, str(exc)


@router.post("/benchmarks", response_model=BenchmarkOut)
async def create_benchmark(request: BenchmarkCreate, db: Session = Depends(get_db)):
    benchmark = Benchmark(prompt=request.prompt, system_prompt=request.system_prompt, temperature=request.temperature, max_tokens=request.max_tokens, status="running")
    db.add(benchmark); db.commit(); db.refresh(benchmark)
    outcomes = await asyncio.gather(*(run_one(item, request) for item in request.models))
    for item, result, error in outcomes:
        values = vars(result).copy() if result else {"input_tokens": None, "output_tokens": None, "ttft_ms": None, "total_latency_ms": 0, "cost": None, "response_length": 0, "response_text": None}
        values.pop("error", None)
        db.add(BenchmarkResult(benchmark_id=benchmark.id, provider=item.provider, model=item.model, error=error, **values))
    benchmark.status = "failed" if all(error for _, _, error in outcomes) else "completed"
    db.commit()
    return db.scalar(select(Benchmark).options(selectinload(Benchmark.results)).where(Benchmark.id == benchmark.id))


@router.get("/benchmarks", response_model=list[BenchmarkSummary])
def history(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    items = db.scalars(select(Benchmark).options(selectinload(Benchmark.results)).order_by(Benchmark.created_at.desc()).limit(min(max(limit, 1), 100)).offset(max(offset, 0))).all()
    output = []
    for b in items:
        latencies = [r.total_latency_ms for r in b.results if r.total_latency_ms is not None and not r.error]
        output.append(BenchmarkSummary(id=b.id, prompt=b.prompt, created_at=b.created_at, model_count=len(b.results), total_cost=sum(r.cost or 0 for r in b.results), total_tokens=sum((r.input_tokens or 0)+(r.output_tokens or 0) for r in b.results), avg_latency_ms=sum(latencies)/len(latencies) if latencies else 0, status=b.status))
    return output


@router.get("/benchmarks/{benchmark_id}", response_model=BenchmarkOut)
def detail(benchmark_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(Benchmark).options(selectinload(Benchmark.results)).where(Benchmark.id == benchmark_id))
    if not item: raise HTTPException(404, "Benchmark not found")
    return item


@router.delete("/benchmarks/{benchmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(benchmark_id: int, db: Session = Depends(get_db)):
    item = db.get(Benchmark, benchmark_id)
    if not item: raise HTTPException(404, "Benchmark not found")
    db.delete(item); db.commit()
    return Response(status_code=204)
