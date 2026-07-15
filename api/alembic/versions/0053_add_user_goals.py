"""Add user_goals table for the goal/quest system.

Revision ID: 0053
Revises: 0052
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_goals",
        sa.Column(
            "goal_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_type", sa.String(length=8), nullable=False),
        sa.Column("client_type", sa.String(length=32), nullable=False),
        sa.Column("table_slug", sa.String(), nullable=True),
        sa.Column("fumen_sha256", sa.Text(), nullable=True),
        sa.Column("fumen_md5", sa.Text(), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("course_md5_list", postgresql.JSONB(), nullable=True),
        sa.Column("target_clear_type", sa.Integer(), nullable=True),
        sa.Column("target_min_bp", sa.Integer(), nullable=True),
        sa.Column("target_rank", sa.String(length=4), nullable=True),
        sa.Column("target_rate", sa.Float(), nullable=True),
        sa.Column("projected_rating", sa.Float(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("baseline_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("achieved_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    op.create_index("ix_user_goals_user_id", "user_goals", ["user_id"])
    op.create_index("ix_user_goals_user_status", "user_goals", ["user_id", "status"])
    op.create_index(
        "ix_user_goals_chart_sha_lookup",
        "user_goals",
        ["user_id", "client_type", "fumen_sha256"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_user_goals_chart_md5_lookup",
        "user_goals",
        ["user_id", "client_type", "fumen_md5"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_user_goals_course_lookup", "user_goals", ["user_id", "course_id"])

    # Partial unique indexes preventing duplicate active goals. NULLs are
    # coalesced to '' because Postgres treats NULL as distinct from NULL in a
    # plain unique index (see plan §3.1 / §7 risk table).
    op.create_index(
        "uq_user_goals_active_chart",
        "user_goals",
        [
            "user_id",
            "client_type",
            sa.text("COALESCE(fumen_sha256, '')"),
            sa.text("COALESCE(fumen_md5, '')"),
            "table_slug",
        ],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND goal_type = 'chart' AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_user_goals_active_course",
        "user_goals",
        ["user_id", "client_type", "course_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND goal_type = 'course' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_goals_active_course", table_name="user_goals")
    op.drop_index("uq_user_goals_active_chart", table_name="user_goals")
    op.drop_index("ix_user_goals_course_lookup", table_name="user_goals")
    op.drop_index("ix_user_goals_chart_md5_lookup", table_name="user_goals")
    op.drop_index("ix_user_goals_chart_sha_lookup", table_name="user_goals")
    op.drop_index("ix_user_goals_user_status", table_name="user_goals")
    op.drop_index("ix_user_goals_user_id", table_name="user_goals")
    op.drop_table("user_goals")
