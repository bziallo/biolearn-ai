"""Add external AI import payloads and job timing records.

Revision ID: 0008_external_import
Revises: 0007_smart_import
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_external_import"
down_revision: str | Sequence[str] | None = "0007_smart_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_extraction_jobs",
        sa.Column("timings", sa.JSON(), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column(
            "source_type",
            sa.String(length=24),
            nullable=False,
            server_default="courseware",
        ),
    )
    op.add_column(
        "import_jobs",
        sa.Column("payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("duplicate_strategy", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("timings", sa.JSON(), nullable=True),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("importance", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("prerequisites", sa.JSON(), nullable=True),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("external_id", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_knowledge_points_external_id",
        "knowledge_points",
        ["external_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_points_external_id", table_name="knowledge_points")
    op.drop_column("knowledge_points", "external_id")
    op.drop_column("knowledge_points", "prerequisites")
    op.drop_column("knowledge_points", "importance")
    op.drop_column("import_jobs", "timings")
    op.drop_column("import_jobs", "duplicate_strategy")
    op.drop_column("import_jobs", "payload")
    op.drop_column("import_jobs", "source_type")
    op.drop_column("knowledge_extraction_jobs", "timings")
