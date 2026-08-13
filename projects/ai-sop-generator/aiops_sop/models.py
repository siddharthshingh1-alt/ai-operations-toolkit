"""Database tables for SOPs, their versions, and their embeddings.

Two tables rather than one: `sops` holds identity and governance metadata,
`sop_versions` holds immutable snapshots of content. That split is what makes
version diffing (CLAUDE.md Section 9) possible — old versions are never
overwritten, so any two can be compared.

The embedding lives on the version, not the SOP, so search always reflects the
text that was actually current when it was indexed.
"""

from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_config import get_settings
from aiops_db.base import Base, TimestampMixin
from aiops_utils import new_id, utcnow

#: Must match GEMINI_EMBEDDING_DIMENSIONS. Read once at import so the column
#: width is fixed for the process; changing the setting later requires
#: re-embedding, which is called out in the settings comment.
EMBEDDING_DIMENSIONS = get_settings().gemini_embedding_dimensions


class Sop(Base, TimestampMixin):
    """One standard operating procedure, across all its versions."""

    __tablename__ = "sops"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sop"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    # ----- governance fields (CLAUDE.md Section 9) -----------------------
    owner: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    department: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Version number of the newest version. Denormalised so the library list
    #: does not need a subquery per row.
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    versions: Mapped[list[SopVersion]] = relationship(
        back_populates="sop",
        cascade="all, delete-orphan",
        order_by="SopVersion.version",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_sops_status_updated", "status", "updated_at"),)

    def __repr__(self) -> str:
        return f"<Sop {self.id} v{self.current_version} {self.title[:40]!r}>"


class SopVersion(Base):
    """An immutable snapshot of an SOP's content at one point in time."""

    __tablename__ = "sop_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sopver"))
    sop_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sops.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The full SopContent as JSON. JSONB so the shape can evolve without a
    #: migration per field, and so Postgres can index into it later if needed.
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    #: Short human note describing what changed in this version.
    change_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    #: Was this version's content written by AI, or edited by a human before
    #: saving? Part of the audit trail (CLAUDE.md Section 5).
    ai_generated: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    #: The embedding of this version's searchable text. Nullable because an SOP
    #: is saved even if embedding fails — search degrades, saving does not.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )

    sop: Mapped[Sop] = relationship(back_populates="versions")

    __table_args__ = (
        # One row per (sop, version) — makes double-saving a version impossible.
        UniqueConstraint("sop_id", "version", name="uq_sop_versions_sop_id_version"),
        Index("ix_sop_versions_sop_id_version", "sop_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<SopVersion {self.sop_id} v{self.version}>"
