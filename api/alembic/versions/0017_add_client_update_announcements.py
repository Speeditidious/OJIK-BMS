"""Add client update announcements.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_update_announcements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), server_default=sa.text("'stable'"), nullable=False),
        sa.Column("target_os", sa.String(length=16), server_default=sa.text("'windows'"), nullable=False),
        sa.Column("arch", sa.String(length=16), server_default=sa.text("'x86_64'"), nullable=False),
        sa.Column("installer_kind", sa.String(length=16), server_default=sa.text("'nsis'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("release_page_url", sa.Text(), nullable=True),
        sa.Column("update_url", sa.Text(), nullable=False),
        sa.Column("tauri_signature", sa.Text(), nullable=True),
        sa.Column("asset_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("asset_sha256", sa.String(length=64), nullable=True),
        sa.Column("mandatory", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("min_supported_version", sa.String(length=32), nullable=True),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("publish_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version",
            "channel",
            "target_os",
            "arch",
            "installer_kind",
            name="uq_client_update_announcements_release_target",
        ),
    )
    op.create_index(
        "ix_client_update_announcements_visible_target",
        "client_update_announcements",
        ["channel", "target_os", "arch", "installer_kind", "is_published", "publish_after"],
        unique=False,
    )
    op.create_index(
        "ix_client_update_announcements_version",
        "client_update_announcements",
        ["version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_client_update_announcements_version", table_name="client_update_announcements")
    op.drop_index("ix_client_update_announcements_visible_target", table_name="client_update_announcements")
    op.drop_table("client_update_announcements")
