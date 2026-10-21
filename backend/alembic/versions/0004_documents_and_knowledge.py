"""Add documents, chunks, extraction jobs, and knowledge points.

Revision ID: 0004_documents_and_knowledge
Revises: 0003_seed_initial_subjects
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_documents_and_knowledge"
down_revision: str | Sequence[str] | None = "0003_seed_initial_subjects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("content_title", sa.String(length=300), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("parse_warnings", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("slide_count", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_chapter_id", "documents", ["chapter_id"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_subject_id", "documents", ["subject_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.String(length=500), nullable=True),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("slide_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("block_start", sa.Integer(), nullable=True),
        sa.Column("block_end", sa.Integer(), nullable=True),
        sa.Column("location_label", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_order",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
    )

    op.create_table(
        "knowledge_extraction_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("stage", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_knowledge_jobs_progress_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_extraction_jobs_document_id",
        "knowledge_extraction_jobs",
        ["document_id"],
    )
    op.create_index(
        "ix_knowledge_extraction_jobs_status",
        "knowledge_extraction_jobs",
        ["status"],
    )

    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("duplicate_of_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column(
            "point_type",
            sa.String(length=40),
            nullable=False,
            server_default="basic_concept",
        ),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "core_points",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column(
            "source_quote_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("source_slide", sa.Integer(), nullable=True),
        sa.Column("source_locator", sa.String(length=200), nullable=True),
        sa.Column("source_chunk_id", sa.String(length=36), nullable=True),
        sa.Column("block_start", sa.Integer(), nullable=True),
        sa.Column("block_end", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "origin",
            sa.String(length=16),
            nullable=False,
            server_default="ai",
        ),
        sa.Column(
            "review_status",
            sa.String(length=24),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_knowledge_points_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["knowledge_points.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["knowledge_points.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"],
            ["document_chunks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_points_chapter_id", "knowledge_points", ["chapter_id"])
    op.create_index("ix_knowledge_points_document_id", "knowledge_points", ["document_id"])
    op.create_index("ix_knowledge_points_parent_id", "knowledge_points", ["parent_id"])
    op.create_index(
        "ix_knowledge_points_review_status",
        "knowledge_points",
        ["review_status"],
    )
    op.create_index(
        "ix_knowledge_points_source_chunk_id",
        "knowledge_points",
        ["source_chunk_id"],
    )
    op.create_index("ix_knowledge_points_subject_id", "knowledge_points", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_points_subject_id", table_name="knowledge_points")
    op.drop_index(
        "ix_knowledge_points_source_chunk_id",
        table_name="knowledge_points",
    )
    op.drop_index(
        "ix_knowledge_points_review_status",
        table_name="knowledge_points",
    )
    op.drop_index("ix_knowledge_points_parent_id", table_name="knowledge_points")
    op.drop_index("ix_knowledge_points_document_id", table_name="knowledge_points")
    op.drop_index("ix_knowledge_points_chapter_id", table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_index(
        "ix_knowledge_extraction_jobs_status",
        table_name="knowledge_extraction_jobs",
    )
    op.drop_index(
        "ix_knowledge_extraction_jobs_document_id",
        table_name="knowledge_extraction_jobs",
    )
    op.drop_table("knowledge_extraction_jobs")
    op.drop_index(
        "ix_document_chunks_document_id",
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_subject_id", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_index("ix_documents_chapter_id", table_name="documents")
    op.drop_table("documents")
