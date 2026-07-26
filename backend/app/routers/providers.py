from dataclasses import asdict

from fastapi import APIRouter

from ..providers import PROVIDERS

router = APIRouter()


@router.get("/providers")
def list_providers():
    return [
        {
            "id": p.provider_id,
            "name": p.provider_name,
            "configured": p.is_configured,
            "base_url": getattr(p, "base_url", None),
            "models": [asdict(m) for m in p.get_models()],
        }
        for p in PROVIDERS.values()
    ]
