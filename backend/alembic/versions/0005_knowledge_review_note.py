"""Add review notes to knowledge points.

Revision ID: 0005_knowledge_review_note
Revises: 0004_documents_and_knowledge
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_knowledge_review_note"
down_revision: str | Sequence[str] | None = "0004_documents_and_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_points",
        sa.Column("review_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_points", "review_note")
