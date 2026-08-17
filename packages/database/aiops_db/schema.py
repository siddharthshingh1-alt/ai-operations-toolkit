"""Schema bootstrap: pgvector extension and table creation.

For local development only. Production uses Alembic migrations — this module
exists so `docker compose up` gives you a working database in one step.
"""

from __future__ import annotations

from sqlalchemy import text

from aiops_config import Settings, get_settings

# Import models so they register on Base.metadata before create_all().
from aiops_db import models  # noqa: F401
from aiops_db.base import Base
from aiops_db.session import get_engine
from aiops_utils import RemoteSchemaRefused, get_logger

logger = get_logger(__name__)

#: Project packages whose models add tables. Imported lazily by
#: `_register_project_models` so this package never hard-depends on a project —
#: the dependency direction stays one-way (see docs/architecture).
_PROJECT_MODEL_MODULES = (
    "aiops_sop.models",
    "aiops_travelops.models",
    "aiops_builder.models",
    "aiops_tracker.models",
    "aiops_command.models",
)


def _register_project_models() -> None:
    """Import each project's models so `create_all()` knows about their tables."""
    import importlib

    for module in _PROJECT_MODEL_MODULES:
        try:
            importlib.import_module(module)
        except ImportError:  # pragma: no cover — that project is not installed
            logger.debug(
                "project models not available; their tables will not be created",
                # `module` is a reserved LogRecord attribute; it raises KeyError.
                extra={"module_name": module},
            )


def enable_pgvector(settings: Settings | None = None) -> bool:
    """Enable the `vector` extension, needed for SOP semantic search (Project 1).

    Returns True on success. Requires a role with rights to create extensions;
    on managed Postgres (Supabase / Neon) enable it from their dashboard instead.
    """
    try:
        with get_engine(settings).begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension enabled")
        return True
    except Exception as exc:  # noqa: BLE001 — reported, not raised
        logger.warning(
            "could not enable pgvector; enable it manually if semantic search is needed",
            extra={"error": str(exc)},
        )
        return False


def has_pgvector(settings: Settings | None = None) -> bool:
    """True when the `vector` extension is installed. Reported by /health."""
    try:
        with get_engine(settings).connect() as connection:
            result = connection.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            return result.first() is not None
    except Exception:  # noqa: BLE001 — health checks must never raise
        return False


#: Hostnames that count as "a database on this machine".
#:
#: Anything else is somebody's server, and this module's own docstring says it
#: is for local development only.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "db", "postgres", ""})


def is_local_database(settings: Settings | None = None) -> bool:
    """Whether `DATABASE_URL` points at a database on this machine.

    Used to decide whether creating tables is a safe thing to do unasked.
    SQLite is always local — it is a file, or memory.
    """
    from sqlalchemy.engine import make_url

    settings = settings or get_settings()
    if not settings.database_url:
        return True

    try:
        url = make_url(settings.database_url)
    except Exception:  # noqa: BLE001 — an unparseable URL is not provably local
        return False

    if url.drivername.startswith("sqlite"):
        return True
    return (url.host or "") in _LOCAL_HOSTS


def create_all(settings: Settings | None = None) -> None:
    """Create every table declared on `Base`. Safe to run repeatedly.

    **Refuses to run against a database that is not on this machine.**

    This module is for local development, and creating tables is the one thing
    it does that changes a database it did not make. Twice during this project
    a developer's `.env` pointed `DATABASE_URL` at the deployed Supabase while
    `DB_AUTO_CREATE` was true, so simply importing the app in a smoke test
    issued `CREATE TABLE` against production. Nothing broke — the tables were
    the ones the next deploy needed anyway — but it was luck, not design, and
    the same accident with a renamed column would not have been harmless.

    Configuration alone cannot fix that: `.env` is exactly the thing that was
    wrong, so a rule written in it protects nothing. The refusal lives here
    instead, where the destructive call actually happens.

    Deliberate remote schema creation is still possible — set
    `DB_ALLOW_REMOTE_SCHEMA=true` — but it now has to be *chosen*, in the
    environment of the process doing it, rather than happening because an
    unrelated setting was left on.
    """
    settings = settings or get_settings()

    if not is_local_database(settings) and not settings.db_allow_remote_schema:
        # The host is deliberately not named: it is read from a URL that also
        # contains a password, and this message is logged.
        raise RemoteSchemaRefused(
            "Refusing to create tables: DATABASE_URL does not point at a local "
            "database. This is the local-development bootstrap — production "
            "schema changes belong in a migration. If you really mean to do "
            "this, set DB_ALLOW_REMOTE_SCHEMA=true in the environment of this "
            "process only."
        )

    _register_project_models()
    enable_pgvector(settings)
    Base.metadata.create_all(bind=get_engine(settings))
    logger.info("database schema created", extra={"tables": len(Base.metadata.tables)})
