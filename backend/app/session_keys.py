"""In-memory session key store with TTL-based expiry.

Session keys are never persisted to disk — they live only in process memory
and expire after 30 minutes of inactivity (extended on each read).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("promptbench.session")


class SessionKeyStore:
    """Per-process session key store with inactivity TTL."""

    def __init__(self, ttl_seconds: int = 30 * 60) -> None:
        self._ttl = ttl_seconds
        self._sessions: dict[str, dict[str, Any]] = {}

    def create(self) -> str:
        """Create a new session and return its ID."""
        sid = uuid.uuid4().hex
        self._sessions[sid] = {"keys": {}, "expires_at": time.monotonic() + self._ttl}
        logger.debug("Session %s created", sid[:8])
        return sid

    def get_keys(self, sid: str) -> dict[str, str] | None:
        """Return the session's keys dict, or None if expired/missing.

        Extends the TTL on every successful read.
        """
        session = self._sessions.get(sid)
        if session is None:
            return None
        if time.monotonic() > session["expires_at"]:
            del self._sessions[sid]
            logger.debug("Session %s expired", sid[:8])
            return None
        session["expires_at"] = time.monotonic() + self._ttl
        return session["keys"]

    def set_key(self, sid: str, provider: str, key: str) -> None:
        """Store or update a key for a provider in the given session."""
        session = self._sessions.get(sid)
        if session is None:
            return
        session["keys"][provider] = key
        session["expires_at"] = time.monotonic() + self._ttl
        logger.debug("Session %s: key set for provider=%s", sid[:8], provider)

    def delete(self, sid: str) -> bool:
        """Delete a session. Returns False if the session didn't exist."""
        existed = sid in self._sessions
        self._sessions.pop(sid, None)
        if existed:
            logger.debug("Session %s deleted", sid[:8])
        return existed

    def list_providers(self, sid: str) -> list[str]:
        """Return the provider IDs with saved keys (never the keys themselves).

        Extends the TTL on every call so that polling the session-key endpoint
        keeps the session alive (same as get_keys).
        """
        session = self._sessions.get(sid)
        if session is None or time.monotonic() > session["expires_at"]:
            return []
        session["expires_at"] = time.monotonic() + self._ttl
        return list(session["keys"].keys())

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        now = time.monotonic()
        expired = [sid for sid, s in self._sessions.items() if now > s["expires_at"]]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.debug("Cleaned up %d expired sessions", len(expired))
        return len(expired)


# Module-level singleton
_store: SessionKeyStore | None = None


def get_session_store() -> SessionKeyStore:
    """Return the singleton SessionKeyStore, creating it on first access."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = SessionKeyStore()
    _store.cleanup_expired()
    return _store
