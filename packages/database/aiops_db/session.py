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

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from aiops_config import Settings, get_settings
from aiops_utils import ConfigurationError, get_logger

logger = get_logger(__name__)

# Engines are cached by connection URL, not by `functools.lru_cache`.
#
# lru_cache hashes its arguments, and `Settings` is a Pydantic model with no
# __hash__ — so `get_engine(settings)` raised "unhashable type: 'Settings'".
# Callers that wrapped it in a broad `except` (the health check, pgvector
# setup) swallowed that into a misleading "database unavailable", which hid
# the real cause. Keying on the URL string also means two different Settings
# objects pointing at the same database correctly share one connection pool.
_ENGINES: dict[str, Engine] = {}
_SESSION_FACTORIES: dict[str, sessionmaker[Session]] = {}

#: How long a single connection attempt may take before giving up.
#:
#: libpq's default is no timeout at all, which on an unreachable host means the
#: OS decides — observed here as roughly two minutes. That is worse than a
#: failure: application startup hung, and each request needing a database held
#: a worker for the whole wait before returning the same error it could have
#: returned immediately. Ten seconds is far above any healthy connection
#: (production connects in well under one) and far below a timeout a person
#: would sit through.
CONNECT_TIMEOUT_SECONDS = 10


def _require_url(settings: Settings | None) -> tuple[Settings, str]:
    settings = settings or get_settings()
    if not settings.database_configured:
        raise ConfigurationError(
            "DATABASE_URL is not set. Start Postgres with 'docker compose up -d db' "
            "or point DATABASE_URL at a managed instance (Supabase / Neon)."
        )
    assert settings.database_url is not None  # narrowed by database_configured
    return settings, settings.database_url


def get_engine(settings: Settings | None = None) -> Engine:
    """Return the engine for this connection URL, creating it on first use.

    Raises `ConfigurationError` when no `DATABASE_URL` is set — check
    `settings.database_configured` first if the caller can work without a DB.
    """
    _, url = _require_url(settings)
    if url not in _ENGINES:
        _ENGINES[url] = create_engine(
            url,
            pool_pre_ping=True,  # survive a database restart without stale connections
            pool_size=5,
            max_overflow=10,
            echo=False,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        )
    return _ENGINES[url]


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return the session factory bound to this connection's engine."""
    _, url = _require_url(settings)
    if url not in _SESSION_FACTORIES:
        _SESSION_FACTORIES[url] = sessionmaker(bind=get_engine(settings), expire_on_commit=False)
    return _SESSION_FACTORIES[url]


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


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session. Use with `Depends(get_db)`.

    Takes **no arguments**, deliberately. FastAPI resolves a dependency's own
    parameters recursively, and a parameter annotated with a Pydantic model
    (as `settings: Settings | None = None` was) is read as a *request body
    field*. That silently turned every route using this dependency into one
    expecting an embedded body — `{"request": {...}}` instead of `{...}` —
    which only shows up when a real client posts to it.

    For a session with non-default settings, use `session_scope(settings)`.
    """
    with session_scope() as session:
        yield session


def connection_error(settings: Settings | None = None) -> str | None:
    """Return the reason the database is unreachable, or None if it is fine.

    A boolean was not enough: a deployment reporting only "did not respond"
    gives an operator nothing to act on, and the connection URL cannot be
    shown because it contains the password. Returning the driver's message
    lets the health endpoint translate it into a specific hint.
    """
    try:
        with get_engine(settings).connect() as connection:
            connection.execute(text("SELECT 1"))
        return None
    except Exception as exc:  # noqa: BLE001 — health checks must never raise
        # The driver sometimes includes the DSN; keep it out of the response.
        message = str(exc).splitlines()[0] if str(exc) else repr(exc)
        logger.warning("database ping failed", extra={"error": message[:300]})
        return message


def ping(settings: Settings | None = None) -> bool:
    """True when the database answers a trivial query."""
    return connection_error(settings) is None


def reset_connection_cache() -> None:
    """Dispose and drop cached engines. Used by tests that swap settings."""
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
    _SESSION_FACTORIES.clear()
