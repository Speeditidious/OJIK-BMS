"""Add issue pinning metadata."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "issues",
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("issues", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "issues",
        sa.Column("pinned_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "issues_pinned_by_id_fkey",
        "issues",
        "users",
        ["pinned_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_issues_pinned_activity",
        "issues",
        ["is_pinned", "pinned_at", "last_activity_at", "id"],
    )
    op.create_index(
        "ix_issues_status_pinned_activity",
        "issues",
        ["status", "is_pinned", "pinned_at", "last_activity_at", "id"],
    )
    op.create_index(
        "ix_issues_tag_status_pinned_activity",
        "issues",
        ["tag_id", "status", "is_pinned", "pinned_at", "last_activity_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_issues_tag_status_pinned_activity", table_name="issues")
    op.drop_index("ix_issues_status_pinned_activity", table_name="issues")
    op.drop_index("ix_issues_pinned_activity", table_name="issues")
    op.drop_constraint("issues_pinned_by_id_fkey", "issues", type_="foreignkey")
    op.drop_column("issues", "pinned_by_id")
    op.drop_column("issues", "pinned_at")
    op.drop_column("issues", "is_pinned")
