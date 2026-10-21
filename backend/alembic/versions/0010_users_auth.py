"""Add invitation-based users, sessions, grants and ownership.

Revision ID: 0010_users_auth
Revises: 0009_question_bank
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_users_auth"
down_revision: str | Sequence[str] | None = "0009_question_bank"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('owner','user')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.String(length=36), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index("ix_invitations_created_by", "invitations", ["created_by"])
    op.create_table(
        "subject_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("grantee_user_id", sa.String(length=36), nullable=False),
        sa.Column("permission", sa.String(length=16), nullable=False, server_default="read"),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "permission IN ('read','practice','write')",
            name="ck_subject_grants_permission",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grantee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subject_grants_grantee", "subject_grants", ["grantee_user_id"])
    op.create_index("ix_subject_grants_subject", "subject_grants", ["subject_id"])

    with op.batch_alter_table("subjects") as batch:
        batch.add_column(sa.Column("owner_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_subjects_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_subjects_owner_id", ["owner_id"])

    with op.batch_alter_table("practice_sessions") as batch:
        batch.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_practice_sessions_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_practice_sessions_user_id", ["user_id"])

    for table in (
        "import_jobs",
        "knowledge_extraction_jobs",
        "question_generation_jobs",
    ):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("created_by", sa.String(length=36), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_created_by_users",
                "users",
                ["created_by"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_index(f"ix_{table}_created_by", ["created_by"])


def downgrade() -> None:
    for table in (
        "import_jobs",
        "knowledge_extraction_jobs",
        "question_generation_jobs",
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_created_by")
            batch.drop_constraint(f"fk_{table}_created_by_users", type_="foreignkey")
            batch.drop_column("created_by")

    with op.batch_alter_table("practice_sessions") as batch:
        batch.drop_index("ix_practice_sessions_user_id")
        batch.drop_constraint(
            "fk_practice_sessions_user_id_users", type_="foreignkey"
        )
        batch.drop_column("user_id")

    with op.batch_alter_table("subjects") as batch:
        batch.drop_index("ix_subjects_owner_id")
        batch.drop_constraint("fk_subjects_owner_id_users", type_="foreignkey")
        batch.drop_column("owner_id")

    op.drop_index("ix_subject_grants_subject", table_name="subject_grants")
    op.drop_index("ix_subject_grants_grantee", table_name="subject_grants")
    op.drop_table("subject_grants")
    op.drop_index("ix_invitations_created_by", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
