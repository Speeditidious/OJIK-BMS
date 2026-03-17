"""Add course tables: courses, user_course_scores, course_score_history.

Stores multi-song course play records from LR2 and Beatoraja.
LR2 course hash: 4×MD5 concatenated (128 chars, header stripped).
Beatoraja course hash: 4×SHA256 concatenated (256 chars).

Revision ID: 0015
Revises: 0014
"""

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # courses — master definition of each course by its song list
    op.create_table(
        "courses",
        sa.Column("course_hash", sa.Text, primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("song_count", sa.Integer, nullable=False),
        sa.Column("song_hashes", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # user_course_scores — best score per (user, course, client_type)
    op.create_table(
        "user_course_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "course_hash",
            sa.Text,
            sa.ForeignKey("courses.course_hash", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column("clear_type", sa.Integer, nullable=True),
        sa.Column("score_rate", sa.Float, nullable=True),
        sa.Column("max_combo", sa.Integer, nullable=True),
        sa.Column("min_bp", sa.Integer, nullable=True),
        sa.Column("play_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clear_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.UniqueConstraint("user_id", "course_hash", "client_type", name="uq_user_course_scores"),
    )
    op.create_index("ix_user_course_scores_user_id", "user_course_scores", ["user_id"])

    # course_score_history — append-only improvement log
    op.create_table(
        "course_score_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_hash", sa.Text, nullable=False),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column("clear_type", sa.Integer, nullable=True),
        sa.Column("old_clear_type", sa.Integer, nullable=True),
        sa.Column("score_rate", sa.Float, nullable=True),
        sa.Column("old_score_rate", sa.Float, nullable=True),
        sa.Column("max_combo", sa.Integer, nullable=True),
        sa.Column("min_bp", sa.Integer, nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_course_score_history_user_id_recorded_at",
        "course_score_history",
        ["user_id", "recorded_at"],
    )
    op.create_index("ix_course_score_history_user_id", "course_score_history", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_course_score_history_user_id", table_name="course_score_history")
    op.drop_index("ix_course_score_history_user_id_recorded_at", table_name="course_score_history")
    op.drop_table("course_score_history")
    op.drop_index("ix_user_course_scores_user_id", table_name="user_course_scores")
    op.drop_table("user_course_scores")
    op.drop_table("courses")
