"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # ── oauth_accounts ────────────────────────────────────────────────────────
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=128), nullable=False),
        sa.Column("provider_username", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oauth_accounts_user_id"), "oauth_accounts", ["user_id"], unique=False
    )

    # ── difficulty_tables ─────────────────────────────────────────────────────
    op.create_table(
        "difficulty_tables",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("table_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── user_favorite_tables ──────────────────────────────────────────────────
    op.create_table(
        "user_favorite_tables",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["table_id"], ["difficulty_tables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "table_id"),
        sa.UniqueConstraint("user_id", "table_id", name="uq_user_favorite_tables"),
    )

    # ── songs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "songs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("md5", sa.String(length=32), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("artist", sa.String(length=256), nullable=True),
        sa.Column("bpm", sa.Float(), nullable=True),
        sa.Column("total_notes", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("youtube_url", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_songs_md5"), "songs", ["md5"], unique=True)
    op.create_index(op.f("ix_songs_sha256"), "songs", ["sha256"], unique=True)

    # ── user_scores ───────────────────────────────────────────────────────────
    op.create_table(
        "user_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("song_sha256", sa.String(length=64), nullable=False),
        sa.Column("client_type", sa.String(length=32), nullable=False),
        sa.Column("clear_type", sa.Integer(), nullable=True),
        sa.Column("score_rate", sa.Float(), nullable=True),
        sa.Column("max_combo", sa.Integer(), nullable=True),
        sa.Column("min_bp", sa.Integer(), nullable=True),
        sa.Column("judgments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("play_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "song_sha256", "client_type", name="uq_user_scores"
        ),
    )
    op.create_index(
        op.f("ix_user_scores_user_id"), "user_scores", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_scores_song_sha256"), "user_scores", ["song_sha256"], unique=False
    )

    # ── score_history ─────────────────────────────────────────────────────────
    op.create_table(
        "score_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("song_sha256", sa.String(length=64), nullable=False),
        sa.Column("client_type", sa.String(length=32), nullable=False),
        sa.Column("clear_type", sa.Integer(), nullable=True),
        sa.Column("old_clear_type", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("old_score", sa.Float(), nullable=True),
        sa.Column("combo", sa.Integer(), nullable=True),
        sa.Column("old_combo", sa.Integer(), nullable=True),
        sa.Column("min_bp", sa.Integer(), nullable=True),
        sa.Column("old_min_bp", sa.Integer(), nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_score_history_user_id"), "score_history", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_score_history_song_sha256"),
        "score_history",
        ["song_sha256"],
        unique=False,
    )

    # ── user_song_tags ────────────────────────────────────────────────────────
    op.create_table(
        "user_song_tags",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("song_sha256", sa.String(length=64), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "song_sha256", "tag"),
        sa.UniqueConstraint(
            "user_id", "song_sha256", "tag", name="uq_user_song_tags"
        ),
    )

    # ── custom_tables ─────────────────────────────────────────────────────────
    op.create_table(
        "custom_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("levels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_custom_tables_owner_id"), "custom_tables", ["owner_id"], unique=False
    )

    # ── custom_courses ────────────────────────────────────────────────────────
    op.create_table(
        "custom_courses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("song_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "course_file_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_custom_courses_owner_id"),
        "custom_courses",
        ["owner_id"],
        unique=False,
    )

    # ── schedules ─────────────────────────────────────────────────────────────
    op.create_table(
        "schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_time", sa.String(length=8), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedules_user_id"), "schedules", ["user_id"], unique=False
    )

    # ── user_owned_songs ──────────────────────────────────────────────────────
    op.create_table(
        "user_owned_songs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("song_md5", sa.String(length=32), nullable=True),
        sa.Column("song_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "song_sha256"),
        sa.UniqueConstraint("user_id", "song_sha256", name="uq_user_owned_songs"),
    )

    # ── chatbot_documents ─────────────────────────────────────────────────────
    op.create_table(
        "chatbot_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chatbot_documents_category"),
        "chatbot_documents",
        ["category"],
        unique=False,
    )
    # Add pgvector column separately using raw SQL for compatibility
    op.execute(
        "ALTER TABLE chatbot_documents ADD COLUMN IF NOT EXISTS embedding vector(1536)"
    )
    # Create HNSW index for fast similarity search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chatbot_documents_embedding
        ON chatbot_documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # ── chatbot_conversations ─────────────────────────────────────────────────
    op.create_table(
        "chatbot_conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chatbot_conversations_user_id"),
        "chatbot_conversations",
        ["user_id"],
        unique=False,
    )

    # ── chatbot_messages ──────────────────────────────────────────────────────
    op.create_table(
        "chatbot_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chatbot_conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chatbot_messages_conversation_id"),
        "chatbot_messages",
        ["conversation_id"],
        unique=False,
    )

    # ── chatbot_usage_limits ──────────────────────────────────────────────────
    op.create_table(
        "chatbot_usage_limits",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "date"),
    )


def downgrade() -> None:
    op.drop_table("chatbot_usage_limits")
    op.drop_table("chatbot_messages")
    op.drop_table("chatbot_conversations")
    op.drop_table("chatbot_documents")
    op.drop_table("user_owned_songs")
    op.drop_table("schedules")
    op.drop_table("custom_courses")
    op.drop_table("custom_tables")
    op.drop_table("user_song_tags")
    op.drop_table("score_history")
    op.drop_table("user_scores")
    op.drop_table("songs")
    op.drop_table("user_favorite_tables")
    op.drop_table("difficulty_tables")
    op.drop_table("oauth_accounts")
    op.drop_table("users")

    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
