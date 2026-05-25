"""Add announcement_templates table.

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "announcement_templates",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tag_id",
            UUID(as_uuid=True),
            sa.ForeignKey("announcement_tags.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title_template", sa.String(200), nullable=False),
        sa.Column("title_en_template", sa.String(200), nullable=True),
        sa.Column("title_ja_template", sa.String(200), nullable=True),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("body_en_template", sa.Text, nullable=True),
        sa.Column("body_ja_template", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # One template per tag (tag_id IS NOT NULL)
    op.create_index(
        "uq_announcement_templates_tag_id",
        "announcement_templates",
        ["tag_id"],
        unique=True,
        postgresql_where=sa.text("tag_id IS NOT NULL"),
    )

    # At most one global default template (tag_id IS NULL)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_announcement_templates_global
            ON announcement_templates ((1))
         WHERE tag_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_announcement_templates_global")
    op.drop_index("uq_announcement_templates_tag_id", table_name="announcement_templates")
    op.drop_table("announcement_templates")
