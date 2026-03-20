"""Add admin_dan_courses and user_dan_badges tables."""
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


def upgrade() -> None:
    op.create_table(
        "admin_dan_courses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_hash", sa.Text(), sa.ForeignKey("courses.course_hash", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("course_hash", name="uq_admin_dan_courses_course_hash"),
    )
    op.create_index("ix_admin_dan_courses_category", "admin_dan_courses", ["category"])

    op.create_table(
        "user_dan_badges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dan_course_id", sa.Integer(), sa.ForeignKey("admin_dan_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clear_type", sa.Integer(), nullable=False),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "dan_course_id", "client_type", name="uq_user_dan_badges"),
    )
    op.create_index("ix_user_dan_badges_user_id", "user_dan_badges", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_dan_badges_user_id", "user_dan_badges")
    op.drop_table("user_dan_badges")
    op.drop_index("ix_admin_dan_courses_category", "admin_dan_courses")
    op.drop_table("admin_dan_courses")
