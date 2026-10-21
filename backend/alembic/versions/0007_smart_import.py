"""Add smart import preferences, import jobs, and chapter provenance.

Revision ID: 0007_smart_import
Revises: 0006_job_cancellation
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_smart_import"
down_revision: str | Sequence[str] | None = "0006_job_cancellation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("default_subject_id", sa.String(length=36), nullable=True),
        sa.Column("default_chapter_id", sa.String(length=36), nullable=True),
        sa.Column(
            "default_mode",
            sa.String(length=24),
            nullable=False,
            server_default="preset",
        ),
        sa.Column(
            "auto_analyze",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "require_preview",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "uncertain_policy",
            sa.String(length=24),
            nullable=False,
            server_default="confirm",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["default_subject_id"],
            ["subjects.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["default_chapter_id"],
            ["chapters.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("stage", sa.String(length=200), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column(
            "auto_analyze",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "require_preview",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "uncertain_policy",
            sa.String(length=24),
            nullable=False,
            server_default="confirm",
        ),
        sa.Column("suggestion", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("analysis_job_id", sa.String(length=36), nullable=True),
        sa.Column(
            "analysis_status",
            sa.String(length=24),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("analysis_error", sa.Text(), nullable=True),
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
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_job_id"],
            ["knowledge_extraction_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_document_id", "import_jobs", ["document_id"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index(
        "ix_import_jobs_analysis_job_id",
        "import_jobs",
        ["analysis_job_id"],
    )

    op.add_column(
        "chapters",
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            nullable=True,
        ),
    )
    op.add_column(
        "chapters",
        sa.Column(
            "source_import_job_id",
            sa.String(length=36),
            nullable=True,
        ),
    )
    op.add_column(
        "chapters",
        sa.Column("source_slide", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_chapters_source_document_id",
        "chapters",
        ["source_document_id"],
    )
    op.create_index(
        "ix_chapters_source_import_job_id",
        "chapters",
        ["source_import_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chapters_source_import_job_id", table_name="chapters")
    op.drop_index("ix_chapters_source_document_id", table_name="chapters")
    op.drop_column("chapters", "source_slide")
    op.drop_column("chapters", "source_import_job_id")
    op.drop_column("chapters", "source_document_id")
    op.drop_index("ix_import_jobs_analysis_job_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_document_id", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_table("import_preferences")
