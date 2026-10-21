"""Create subjects and chapters.

Revision ID: 0002_subjects_chapters
Revises: 0001_initial
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_subjects_chapters"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("icon", sa.String(length=32), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
            "sort_order >= 0",
            name="ck_subjects_sort_order_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subjects_sort_order",
        "subjects",
        ["sort_order"],
        unique=False,
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
            "sort_order >= 0",
            name="ck_chapters_sort_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["chapters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chapters_parent_id",
        "chapters",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapters_sort_order",
        "chapters",
        ["sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_chapters_subject_id",
        "chapters",
        ["subject_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chapters_subject_id", table_name="chapters")
    op.drop_index("ix_chapters_sort_order", table_name="chapters")
    op.drop_index("ix_chapters_parent_id", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("ix_subjects_sort_order", table_name="subjects")
    op.drop_table("subjects")
