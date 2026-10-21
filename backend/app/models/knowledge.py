from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    JobStatus,
    KnowledgeOrigin,
    KnowledgePointType,
    ReviewStatus,
)
from app.db.base import Base, utc_now
from app.models.subject import new_id

if TYPE_CHECKING:
    from app.models.chapter import Chapter
    from app.models.document import Document, DocumentChunk
    from app.models.subject import Subject


class KnowledgeExtractionJob(Base):
    __tablename__ = "knowledge_extraction_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_knowledge_jobs_progress_range",
        ),
    )

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
        default=JobStatus.QUEUED.value,
        server_default=JobStatus.QUEUED.value,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    extracted_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    merged_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    timings: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    document: Mapped[Document] = relationship(back_populates="jobs")


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_knowledge_points_confidence_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    subject_id: Mapped[str] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    duplicate_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    point_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=KnowledgePointType.BASIC_CONCEPT.value,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    core_points: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quote_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_slide: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_locator: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    source_chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    importance: Mapped[str | None] = mapped_column(String(16), nullable=True)
    prerequisites: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    external_id: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )
    block_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    origin: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=KnowledgeOrigin.AI.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=ReviewStatus.PENDING.value,
        server_default=ReviewStatus.PENDING.value,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    subject: Mapped[Subject] = relationship()
    chapter: Mapped[Chapter | None] = relationship()
    document: Mapped[Document] = relationship(back_populates="knowledge_points")
    source_chunk: Mapped[DocumentChunk | None] = relationship(
        back_populates="knowledge_points",
    )
    parent: Mapped[KnowledgePoint | None] = relationship(
        remote_side="KnowledgePoint.id",
        foreign_keys=[parent_id],
        back_populates="children",
    )
    children: Mapped[list[KnowledgePoint]] = relationship(
        foreign_keys=[parent_id],
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KnowledgePoint.created_at",
    )
    duplicate_of: Mapped[KnowledgePoint | None] = relationship(
        remote_side="KnowledgePoint.id",
        foreign_keys=[duplicate_of_id],
    )
