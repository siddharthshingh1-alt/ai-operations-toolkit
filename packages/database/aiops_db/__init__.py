"""PostgreSQL + pgvector access layer."""

from aiops_db.base import Base, TimestampMixin, utcnow
from aiops_db.models import ActivityLog
from aiops_db.schema import create_all, enable_pgvector, has_pgvector
from aiops_db.session import (
    connection_error,
    get_db,
    get_engine,
    get_session_factory,
    ping,
    reset_connection_cache,
    session_scope,
)

__all__ = [
    "ActivityLog",
    "Base",
    "TimestampMixin",
    "connection_error",
    "create_all",
    "enable_pgvector",
    "get_db",
    "get_engine",
    "get_session_factory",
    "has_pgvector",
    "ping",
    "reset_connection_cache",
    "session_scope",
    "utcnow",
]
