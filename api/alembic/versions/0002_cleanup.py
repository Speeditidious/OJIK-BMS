"""cleanup: drop chatbot tables, fix index names, remove duplicate constraints

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop chatbot tables (Phase 9 removed from models, DB not cleaned up) ─
    op.drop_index("ix_chatbot_messages_conversation_id", table_name="chatbot_messages", if_exists=True)
    op.drop_table("chatbot_messages", if_exists=True)
    op.drop_index("ix_chatbot_conversations_user_id", table_name="chatbot_conversations", if_exists=True)
    op.drop_table("chatbot_conversations", if_exists=True)
    op.drop_table("chatbot_usage_limits", if_exists=True)
    op.drop_index("ix_chatbot_documents_category", table_name="chatbot_documents", if_exists=True)
    op.drop_table("chatbot_documents", if_exists=True)

    # ── Fix index name on custom_difficulty_tables ────────────────────────────
    op.drop_index("ix_custom_tables_owner_id", table_name="custom_difficulty_tables", if_exists=True)
    op.create_index(
        "ix_custom_difficulty_tables_owner_id",
        "custom_difficulty_tables",
        ["owner_id"],
        unique=False,
        if_not_exists=True,
    )

    # ── Fix index names on user_fumen_tags ────────────────────────────────────
    op.drop_index("ix_user_fumen_tags_md5", table_name="user_fumen_tags", if_exists=True)
    op.drop_index("ix_user_fumen_tags_sha256", table_name="user_fumen_tags", if_exists=True)
    op.create_index("ix_user_fumen_tags_fumen_md5", "user_fumen_tags", ["fumen_md5"], unique=False, if_not_exists=True)
    op.create_index(
        "ix_user_fumen_tags_fumen_sha256", "user_fumen_tags", ["fumen_sha256"], unique=False, if_not_exists=True
    )

    # ── Remove duplicate username unique constraint ───────────────────────────
    # ix_users_username (unique index) already enforces uniqueness.
    op.drop_constraint("users_username_key", "users", type_="unique", if_exists=True)


def downgrade() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    op.create_unique_constraint("users_username_key", "users", ["username"])

    op.drop_index("ix_user_fumen_tags_fumen_sha256", table_name="user_fumen_tags")
    op.drop_index("ix_user_fumen_tags_fumen_md5", table_name="user_fumen_tags")
    op.create_index("ix_user_fumen_tags_sha256", "user_fumen_tags", ["fumen_sha256"], unique=False)
    op.create_index("ix_user_fumen_tags_md5", "user_fumen_tags", ["fumen_md5"], unique=False)

    op.drop_index("ix_custom_difficulty_tables_owner_id", table_name="custom_difficulty_tables")
    op.create_index(
        "ix_custom_tables_owner_id", "custom_difficulty_tables", ["owner_id"], unique=False
    )

    op.create_table(
        "chatbot_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatbot_documents_category", "chatbot_documents", ["category"], unique=False)

    op.create_table(
        "chatbot_usage_limits",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "date"),
    )

    op.create_table(
        "chatbot_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatbot_conversations_user_id", "chatbot_conversations", ["user_id"], unique=False)

    op.create_table(
        "chatbot_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chatbot_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chatbot_messages_conversation_id", "chatbot_messages", ["conversation_id"], unique=False)
