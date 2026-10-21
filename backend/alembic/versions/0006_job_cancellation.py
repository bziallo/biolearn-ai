"""Add cancellation flag to knowledge extraction jobs.

Revision ID: 0006_job_cancellation
Revises: 0005_knowledge_review_note
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_job_cancellation"
down_revision: str | Sequence[str] | None = "0005_knowledge_review_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_extraction_jobs",
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_extraction_jobs", "cancel_requested")
