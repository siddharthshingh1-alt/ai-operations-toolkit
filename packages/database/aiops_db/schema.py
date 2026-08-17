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
from aiops_utils import get_logger

logger = get_logger(__name__)

#: Project packages whose models add tables. Imported lazily by
#: `_register_project_models` so this package never hard-depends on a project —
#: the dependency direction stays one-way (see docs/architecture).
_PROJECT_MODEL_MODULES = (
    "aiops_sop.models",
    "aiops_travelops.models",
    "aiops_builder.models",
    "aiops_tracker.models",
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


def create_all(settings: Settings | None = None) -> None:
    """Create every table declared on `Base`. Safe to run repeatedly."""
    settings = settings or get_settings()
    _register_project_models()
    enable_pgvector(settings)
    Base.metadata.create_all(bind=get_engine(settings))
    logger.info("database schema created", extra={"tables": len(Base.metadata.tables)})
