"""Session key management endpoints for BYOK Phase 2.

POST   /api/session-key — store a provider API key in the session
DELETE /api/session-key — clear all session keys
GET    /api/session-key — list providers with saved keys (never the keys)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..session_keys import get_session_store

logger = logging.getLogger("promptbench.session-keys")

router = APIRouter()

SESSION_COOKIE = "pb_session"
SESSION_MAX_AGE = 30 * 60  # 30 minutes


class SetKeyRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    key: str = Field(min_length=1, max_length=500)


class SetKeyResponse(BaseModel):
    provider: str
    saved: bool


class ClearResponse(BaseModel):
    cleared: bool


class ListResponse(BaseModel):
    providers: list[str]


def _get_or_create_session(request: Request, response: Response) -> str:
    """Return an existing session ID from the cookie, or create a new one."""
    store = get_session_store()
    sid = request.cookies.get(SESSION_COOKIE)
    if sid and store.get_keys(sid) is not None:
        return sid
    sid = store.create()
    response.set_cookie(
        SESSION_COOKIE,
        sid,
        httponly=True,
        samesite="strict",
        max_age=SESSION_MAX_AGE,
        secure=False,  # Allow localhost dev; set True in production
    )
    return sid


@router.post("/session-key", response_model=SetKeyResponse)
async def set_session_key(
    request: Request, response: Response, body: SetKeyRequest
) -> SetKeyResponse:
    """Store an API key for a provider in the session cookie.

    The key is stored server-side in an in-memory store. The cookie
    only contains a random session ID — never the key itself.
    """
    store = get_session_store()
    sid = _get_or_create_session(request, response)
    # Sanitize: strip whitespace and reject keys that are too short to be real
    key = body.key.strip()
    if len(key) < 10:
        raise HTTPException(400, "Key too short — must be at least 10 characters.")
    store.set_key(sid, body.provider, key)
    logger.info("Session %s: saved key for provider=%s", sid[:8], body.provider)
    return SetKeyResponse(provider=body.provider, saved=True)


@router.delete("/session-key", response_model=ClearResponse)
async def clear_session_key(
    request: Request, response: Response
) -> ClearResponse:
    """Remove all session keys and clear the session cookie."""
    store = get_session_store()
    sid = request.cookies.get(SESSION_COOKIE)
    if sid and store.delete(sid):
        logger.info("Session %s: keys cleared", sid[:8])
    response.delete_cookie(SESSION_COOKIE)
    return ClearResponse(cleared=True)


@router.get("/session-key", response_model=ListResponse)
async def list_session_keys(request: Request) -> ListResponse:
    """List providers with saved keys (key values are never returned)."""
    store = get_session_store()
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return ListResponse(providers=[])
    providers = store.list_providers(sid)
    return ListResponse(providers=providers)
