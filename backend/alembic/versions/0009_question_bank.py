"""Add the question bank, AI generation jobs, and practice records.

Revision ID: 0009_question_bank
Revises: 0008_external_import
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_question_bank"
down_revision: str | Sequence[str] | None = "0008_external_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_generation_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("stage", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("request", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timings", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_question_jobs_progress_range",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_question_generation_jobs_subject_id",
        "question_generation_jobs",
        ["subject_id"],
    )
    op.create_index(
        "ix_question_generation_jobs_chapter_id",
        "question_generation_jobs",
        ["chapter_id"],
    )
    op.create_index(
        "ix_question_generation_jobs_status",
        "question_generation_jobs",
        ["status"],
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("generation_job_id", sa.String(length=36), nullable=True),
        sa.Column("duplicate_of_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=24), nullable=False, server_default="single_choice"),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("answer", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "grading_rule",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "difficulty",
            sa.String(length=16),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("origin", sa.String(length=16), nullable=False, server_default="ai"),
        sa.Column("source_locator", sa.String(length=300), nullable=True),
        sa.Column("ai_provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("ai_model", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("duplicate_reason", sa.String(length=300), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_questions_confidence_range",
        ),
        sa.CheckConstraint(
            "score IS NULL OR score >= 0",
            name="ck_questions_score_nonnegative",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["documents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id"],
            ["question_generation_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["questions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "subject_id",
        "chapter_id",
        "source_document_id",
        "generation_job_id",
        "type",
        "difficulty",
        "status",
    ):
        op.create_index(f"ix_questions_{column}", "questions", [column])

    op.create_table(
        "question_knowledge_points",
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_point_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"],
            ["knowledge_points.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("question_id", "knowledge_point_id"),
    )

    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("filters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "question_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "pending_manual_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_practice_sessions_score_range",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_sessions_subject_id", "practice_sessions", ["subject_id"])
    op.create_index("ix_practice_sessions_chapter_id", "practice_sessions", ["chapter_id"])
    op.create_index("ix_practice_sessions_status", "practice_sessions", ["status"])

    op.create_table(
        "practice_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=True),
        sa.Column(
            "question_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "user_answer",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=False, server_default="1"),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("graded_by", sa.String(length=24), nullable=False, server_default="auto"),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "score IS NULL OR score >= 0",
            name="ck_practice_answers_score_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_practice_answers_session_question",
        ),
    )
    op.create_index("ix_practice_answers_session_id", "practice_answers", ["session_id"])
    op.create_index("ix_practice_answers_question_id", "practice_answers", ["question_id"])


def downgrade() -> None:
    op.drop_table("practice_answers")
    op.drop_table("practice_sessions")
    op.drop_table("question_knowledge_points")
    op.drop_table("questions")
    op.drop_table("question_generation_jobs")
