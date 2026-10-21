from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    PracticeStatus,
    QuestionDifficulty,
    QuestionJobStatus,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
)
from app.db.base import Base, utc_now
from app.models.subject import new_id

if TYPE_CHECKING:
    from app.models.chapter import Chapter
    from app.models.document import Document
    from app.models.knowledge import KnowledgePoint
    from app.models.subject import Subject


question_knowledge_points = Table(
    "question_knowledge_points",
    Base.metadata,
    Column(
        "question_id",
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "knowledge_point_id",
        String(36),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class QuestionGenerationJob(Base):
    __tablename__ = "question_generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_question_jobs_progress_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=QuestionJobStatus.QUEUED.value,
        server_default=QuestionJobStatus.QUEUED.value,
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
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    timings: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
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

    subject: Mapped[Subject] = relationship()
    chapter: Mapped[Chapter | None] = relationship()
    questions: Mapped[list[Question]] = relationship(back_populates="generation_job")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_questions_confidence_range",
        ),
        CheckConstraint(
            "score IS NULL OR score >= 0",
            name="ck_questions_score_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
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
    source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    duplicate_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=QuestionType.SINGLE_CHOICE.value,
        index=True,
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    answer: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    grading_rule: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=QuestionDifficulty.MEDIUM.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=QuestionStatus.PENDING.value,
        server_default=QuestionStatus.PENDING.value,
        index=True,
    )
    origin: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=QuestionOrigin.AI.value,
        server_default=QuestionOrigin.AI.value,
    )
    source_locator: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ai_provider: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    ai_model: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    source_document: Mapped[Document | None] = relationship()
    generation_job: Mapped[QuestionGenerationJob | None] = relationship(
        back_populates="questions",
    )
    duplicate_of: Mapped[Question | None] = relationship(
        remote_side="Question.id",
        foreign_keys=[duplicate_of_id],
    )
    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(
        secondary=question_knowledge_points,
        order_by="KnowledgePoint.name",
    )


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_practice_sessions_score_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=PracticeStatus.IN_PROGRESS.value,
        server_default=PracticeStatus.IN_PROGRESS.value,
        index=True,
    )
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    question_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_manual_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
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
    answers: Mapped[list[PracticeAnswer]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PracticeAnswer(Base):
    __tablename__ = "practice_answers"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_practice_answers_session_question",
        ),
        CheckConstraint(
            "score IS NULL OR score >= 0",
            name="ck_practice_answers_score_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    user_answer: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="auto",
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    session: Mapped[PracticeSession] = relationship(back_populates="answers")
    question: Mapped[Question | None] = relationship()
