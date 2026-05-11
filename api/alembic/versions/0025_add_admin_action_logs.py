"""Add admin action progress log tables for sqladmin async actions.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_action_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("parent_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("target_label", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_log_id"], ["admin_action_logs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "admin_action_log_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.Text(), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["log_id"], ["admin_action_logs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_admin_action_logs_parent_log_id", "admin_action_logs", ["parent_log_id"])
    op.create_index("ix_admin_action_logs_action_name", "admin_action_logs", ["action_name"])
    op.create_index("ix_admin_action_logs_target", "admin_action_logs", ["target_kind", "target_id"])
    op.create_index("ix_admin_action_logs_status", "admin_action_logs", ["status"])
    op.create_index("ix_admin_action_logs_started_at", "admin_action_logs", ["started_at"])
    op.create_index(
        "ix_admin_action_log_lines_log_created",
        "admin_action_log_lines",
        ["log_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_action_log_lines_log_created", table_name="admin_action_log_lines")
    op.drop_index("ix_admin_action_logs_started_at", table_name="admin_action_logs")
    op.drop_index("ix_admin_action_logs_status", table_name="admin_action_logs")
    op.drop_index("ix_admin_action_logs_target", table_name="admin_action_logs")
    op.drop_index("ix_admin_action_logs_action_name", table_name="admin_action_logs")
    op.drop_index("ix_admin_action_logs_parent_log_id", table_name="admin_action_logs")
    op.drop_table("admin_action_log_lines")
    op.drop_table("admin_action_logs")
