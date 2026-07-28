"""Database utility helpers shared across alembic/env.py and app/database.py.

Kept in a standalone module with zero application imports so that
``env.py`` (which runs under Alembic's sys.path) can import it
without triggering engine creation or config loading side-effects.
"""


def normalize_db_url(url: str) -> str:
    """Normalize ``postgres://`` / ``postgresql://`` to ``postgresql+psycopg://``.

    Fly.io and some orchestrators supply ``postgres://``; ``psycopg`` v3
    requires the explicit ``+psycopg`` driver prefix.  URLs that already
    include ``+psycopg`` are returned unchanged.
    """
    if url.startswith("postgres://") and "+psycopg" not in url:
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
