from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now
from app.models.subject import new_id

if TYPE_CHECKING:
    from app.models.subject import Subject


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint(
            "sort_order >= 0",
            name="ck_chapters_sort_order_nonnegative",
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
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        index=True,
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    source_import_job_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    source_slide: Mapped[int | None] = mapped_column(
        Integer,
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

    subject: Mapped[Subject] = relationship(back_populates="chapters")
    parent: Mapped[Chapter | None] = relationship(
        remote_side="Chapter.id",
        back_populates="children",
    )
    children: Mapped[list[Chapter]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chapter.sort_order, Chapter.created_at",
    )
