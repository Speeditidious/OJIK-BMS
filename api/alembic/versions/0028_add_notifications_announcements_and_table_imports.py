"""Add notifications, announcements, and table import metadata.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "announcement_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=64), nullable=True),
        sa.Column("send_notification", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=True),
        sa.Column("body_ja", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["announcement_tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_announcements_published_at", "announcements", ["is_published", "published_at"])
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("announcement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link_url", sa.String(length=512), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index("ix_notifications_published_created", "notifications", ["is_published", "created_at"])
    op.create_index("ix_notifications_target_published_created", "notifications", ["target_user_id", "is_published", "created_at"])
    op.create_index("ix_notifications_type_created", "notifications", ["type", "created_at"])
    op.create_table(
        "notification_reads",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "notification_id"),
    )
    op.create_index("ix_notification_reads_user_deleted", "notification_reads", ["user_id", "deleted_at"])
    op.create_table(
        "notification_user_states",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("read_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "table_import_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_table_import_log_user_created", "table_import_log", ["user_id", "created_at"])
    op.create_index("ix_table_import_log_user_outcome_created", "table_import_log", ["user_id", "outcome", "created_at"])
    op.create_table(
        "table_source_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("alias_url", sa.Text(), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["table_id"], ["difficulty_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias_url"),
    )
    op.execute(
        """
        INSERT INTO announcement_tags (name, color, send_notification, display_order)
        VALUES ('공지', 'primary', true, 0), ('업데이트', 'accent', false, 1)
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("table_source_aliases")
    op.drop_index("ix_table_import_log_user_outcome_created", table_name="table_import_log")
    op.drop_index("ix_table_import_log_user_created", table_name="table_import_log")
    op.drop_table("table_import_log")
    op.drop_table("notification_user_states")
    op.drop_index("ix_notification_reads_user_deleted", table_name="notification_reads")
    op.drop_table("notification_reads")
    op.drop_index("ix_notifications_type_created", table_name="notifications")
    op.drop_index("ix_notifications_target_published_created", table_name="notifications")
    op.drop_index("ix_notifications_published_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_announcements_published_at", table_name="announcements")
    op.drop_table("announcements")
    op.drop_table("announcement_tags")
