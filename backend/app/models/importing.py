from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now
from app.models.subject import new_id

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.knowledge import KnowledgeExtractionJob


class ImportPreferences(Base):
    __tablename__ = "import_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_subject_id: Mapped[str | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_chapter_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_mode: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="preset",
        server_default="preset",
    )
    auto_analyze: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    require_preview: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    uncertain_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="confirm",
        server_default="confirm",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mode: Mapped[str] = mapped_column(String(24), nullable=False, default="preset")
    source_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="courseware",
        server_default="courseware",
    )
    duplicate_strategy: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )
    auto_analyze: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    require_preview: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    uncertain_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="confirm",
        server_default="confirm",
    )
    suggestion: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    timings: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_extraction_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="not_started",
        server_default="not_started",
    )
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    document: Mapped[Document] = relationship()
    analysis_job: Mapped[KnowledgeExtractionJob | None] = relationship()
