from fastapi import APIRouter

from ..providers import get_providers_cached

router = APIRouter()


@router.get("/providers")
def list_providers():
    return get_providers_cached()
