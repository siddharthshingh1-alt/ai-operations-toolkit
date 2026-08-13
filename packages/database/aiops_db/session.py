"""Database engine and session management.

The database is **optional**. A reviewer running the app in Demo Mode with no
`DATABASE_URL` gets a working application; the health endpoint simply reports
the database as `not_configured`. That is a deliberate consequence of
CLAUDE.md Section 3a/3b: nobody should need to stand up Postgres to look at
this portfolio.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from aiops_config import Settings, get_settings
from aiops_utils import ConfigurationError, get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_engine(settings: Settings | None = None) -> Engine:
    """Return the process-wide SQLAlchemy engine.

    Raises `ConfigurationError` when no `DATABASE_URL` is set — check
    `settings.database_configured` first if the caller can work without a DB.
    """
    settings = settings or get_settings()
    if not settings.database_configured:
        raise ConfigurationError(
            "DATABASE_URL is not set. Start Postgres with 'docker compose up -d db' "
            "or point DATABASE_URL at a managed instance (Supabase / Neon)."
        )

    assert settings.database_url is not None  # narrowed by database_configured
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,  # survive a database restart without stale connections
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return the session factory bound to the engine."""
    return sessionmaker(bind=get_engine(settings), expire_on_commit=False)


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Transactional scope: commits on success, rolls back on any exception.

    with session_scope() as db:
        db.add(record)
    """
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db(settings: Settings | None = None) -> Iterator[Session]:
    """FastAPI dependency yielding a session. Use with `Depends(get_db)`."""
    with session_scope(settings) as session:
        yield session


def ping(settings: Settings | None = None) -> bool:
    """True when the database answers a trivial query. Used by /health."""
    try:
        with get_engine(settings).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health checks must never raise
        logger.warning("database ping failed", extra={"error": str(exc)})
        return False


def reset_connection_cache() -> None:
    """Drop cached engine/session factory. Used by tests that swap settings."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
