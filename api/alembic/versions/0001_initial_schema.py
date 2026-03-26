"""initial_schema

Squashed from migrations 0001–0040. Represents the full DB schema as of Phase 8.
New deployments: run `alembic upgrade head` to create from scratch.
Existing deployments: run `alembic stamp 0001` (schema already applied).

Revision ID: 0001
Revises:
Create Date: 2026-03-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("first_synced_at", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── oauth_accounts ───────────────────────────────────────────────────────
    op.create_table(
        "oauth_accounts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_account_id", sa.String(128), nullable=False),
        sa.Column("provider_username", sa.String(128), nullable=True),
        sa.Column("discord_avatar_url", sa.String(512), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="oauth_accounts_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "provider", name="oauth_accounts_pkey"),
    )

    # ── difficulty_tables ────────────────────────────────────────────────────
    op.create_table(
        "difficulty_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("slug", sa.String(64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("level_order", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="difficulty_tables_pkey"),
        sa.UniqueConstraint("source_url", name="uq_difficulty_tables_source_url"),
    )
    op.create_index("ix_difficulty_tables_slug", "difficulty_tables", ["slug"], unique=False)

    # ── fumens ───────────────────────────────────────────────────────────────
    # No PK constraint in DB — uniqueness enforced by partial unique indexes.
    # SQLAlchemy uses mapper-level composite PK (sha256, md5) without DB enforcement.
    op.execute(sa.text("""
        CREATE TABLE fumens (
            md5         VARCHAR(32),
            sha256      VARCHAR(64),
            title       VARCHAR(512),
            artist      VARCHAR(256),
            bpm         DOUBLE PRECISION,
            total_notes INTEGER,
            total       INTEGER,
            youtube_url TEXT,
            file_url    TEXT,
            file_url_diff TEXT,
            table_entries JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_fumens_hash CHECK (md5 IS NOT NULL OR sha256 IS NOT NULL)
        )
    """))
    op.create_index("ix_fumens_sha256", "fumens", ["sha256"], unique=False)
    op.create_index("ix_fumens_md5", "fumens", ["md5"], unique=False)
    op.create_index(
        "uq_fumens_sha256", "fumens", ["sha256"],
        unique=True,
        postgresql_where=sa.text("sha256 IS NOT NULL"),
    )
    op.create_index(
        "uq_fumens_md5", "fumens", ["md5"],
        unique=True,
        postgresql_where=sa.text("md5 IS NOT NULL AND sha256 IS NULL"),
    )

    # ── user_favorite_difficulty_tables ──────────────────────────────────────
    op.create_table(
        "user_favorite_difficulty_tables",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="user_favorite_tables_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["table_id"],
            ["difficulty_tables.id"],
            name="user_favorite_tables_table_id_fkey",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "table_id", name="uq_user_favorite_difficulty_tables"),
    )

    # ── user_fumen_tags ──────────────────────────────────────────────────────
    op.create_table(
        "user_fumen_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fumen_sha256", sa.String(64), nullable=True),
        sa.Column("fumen_md5", sa.String(32), nullable=True),
        sa.Column("tag", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="user_fumen_tags_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="user_fumen_tags_pkey"),
    )
    op.create_index("ix_user_fumen_tags_user_id", "user_fumen_tags", ["user_id"], unique=False)
    op.create_index("ix_user_fumen_tags_fumen_sha256", "user_fumen_tags", ["fumen_sha256"], unique=False)
    op.create_index("ix_user_fumen_tags_fumen_md5", "user_fumen_tags", ["fumen_md5"], unique=False)
    op.create_index(
        "uq_user_fumen_tags_sha256", "user_fumen_tags",
        ["user_id", "fumen_sha256", "tag"],
        unique=True,
        postgresql_where=sa.text("fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "uq_user_fumen_tags_md5", "user_fumen_tags",
        ["user_id", "fumen_md5", "tag"],
        unique=True,
        postgresql_where=sa.text("fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"),
    )

    # ── user_player_stats ────────────────────────────────────────────────────
    # Functional unique index: one row per (user, client_type, UTC day).
    op.create_table(
        "user_player_stats",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("playcount", sa.Integer(), nullable=True),
        sa.Column("clearcount", sa.Integer(), nullable=True),
        sa.Column("playtime", sa.BigInteger(), nullable=True),
        sa.Column("judgments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="user_player_stats_history_user_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="user_player_stats_pkey"),
    )
    # Expression-based indexes — not representable in SQLAlchemy declarative syntax
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_player_stats
        ON user_player_stats (user_id, client_type, CAST(synced_at AT TIME ZONE 'UTC' AS date))
    """))
    op.execute(sa.text("""
        CREATE INDEX ix_player_stats_user_date
        ON user_player_stats (user_id, CAST(synced_at AT TIME ZONE 'UTC' AS date))
    """))

    # ── user_scores ──────────────────────────────────────────────────────────
    # No FK constraint to users — intentional (matches migration 0023 design).
    op.create_table(
        "user_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_type", sa.String(32), nullable=False),
        sa.Column("scorehash", sa.Text(), nullable=True),
        sa.Column("fumen_sha256", sa.String(64), nullable=True),
        sa.Column("fumen_md5", sa.String(32), nullable=True),
        sa.Column("fumen_hash_others", sa.Text(), nullable=True),
        sa.Column("clear_type", sa.Integer(), nullable=True),
        sa.Column("exscore", sa.Integer(), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("rank", sa.String(4), nullable=True),
        sa.Column("max_combo", sa.Integer(), nullable=True),
        sa.Column("min_bp", sa.Integer(), nullable=True),
        sa.Column("play_count", sa.Integer(), nullable=True),
        sa.Column("clear_count", sa.Integer(), nullable=True),
        sa.Column("judgments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "is_best_clear_type",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_best_exscore",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_best_min_bp",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_best_max_combo",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="user_scores_pkey"),
    )
    op.create_index("ix_user_scores_user_id", "user_scores", ["user_id"], unique=False)
    op.create_index("ix_user_scores_user_id_recorded_at", "user_scores", ["user_id", "recorded_at"])
    op.create_index("ix_user_scores_user_id_fumen_sha256", "user_scores", ["user_id", "fumen_sha256"])
    op.create_index("ix_user_scores_user_id_fumen_md5", "user_scores", ["user_id", "fumen_md5"])
    op.create_index(
        "ix_user_scores_user_id_fumen_hash_others",
        "user_scores",
        ["user_id", "fumen_hash_others"],
    )
    # Partial unique index for scorehash deduplication (migration 0023 design)
    op.create_index(
        "uq_user_scores_scorehash", "user_scores",
        ["scorehash", "user_id", "client_type"],
        unique=True,
        postgresql_where=sa.text("scorehash IS NOT NULL"),
    )
    # Partial indexes for per-field best score lookup (migration 0038)
    op.create_index(
        "ix_user_scores_best_ct_sha256", "user_scores",
        ["user_id", "fumen_sha256", "client_type"],
        postgresql_where=sa.text("is_best_clear_type = TRUE AND fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_ex_sha256", "user_scores",
        ["user_id", "fumen_sha256", "client_type"],
        postgresql_where=sa.text("is_best_exscore = TRUE AND fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_bp_sha256", "user_scores",
        ["user_id", "fumen_sha256", "client_type"],
        postgresql_where=sa.text("is_best_min_bp = TRUE AND fumen_sha256 IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_ct_md5", "user_scores",
        ["user_id", "fumen_md5", "client_type"],
        postgresql_where=sa.text(
            "is_best_clear_type = TRUE AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"
        ),
    )
    op.create_index(
        "ix_user_scores_best_ex_md5", "user_scores",
        ["user_id", "fumen_md5", "client_type"],
        postgresql_where=sa.text(
            "is_best_exscore = TRUE AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"
        ),
    )
    op.create_index(
        "ix_user_scores_best_bp_md5", "user_scores",
        ["user_id", "fumen_md5", "client_type"],
        postgresql_where=sa.text(
            "is_best_min_bp = TRUE AND fumen_md5 IS NOT NULL AND fumen_sha256 IS NULL"
        ),
    )
    op.create_index(
        "ix_user_scores_best_ct_others", "user_scores",
        ["user_id", "fumen_hash_others", "client_type"],
        postgresql_where=sa.text("is_best_clear_type = TRUE AND fumen_hash_others IS NOT NULL"),
    )
    op.create_index(
        "ix_user_scores_best_ex_others", "user_scores",
        ["user_id", "fumen_hash_others", "client_type"],
        postgresql_where=sa.text("is_best_exscore = TRUE AND fumen_hash_others IS NOT NULL"),
    )

    # ── courses ──────────────────────────────────────────────────────────────
    op.create_table(
        "courses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_table_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("md5_list", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sha256_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("dan_title", sa.Text(), server_default="''", nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_table_id"],
            ["difficulty_tables.id"],
            name="courses_source_table_id_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="courses_pkey"),
    )
    op.create_index("ix_courses_is_active", "courses", ["is_active"], unique=False)
    op.create_index("ix_courses_source_table_id", "courses", ["source_table_id"], unique=False)

    # ── custom_difficulty_tables ─────────────────────────────────────────────
    op.create_table(
        "custom_difficulty_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="custom_tables_owner_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="custom_tables_pkey"),
    )
    op.create_index(
        "ix_custom_difficulty_tables_owner_id",
        "custom_difficulty_tables",
        ["owner_id"],
        unique=False,
    )

    # ── custom_courses ───────────────────────────────────────────────────────
    op.create_table(
        "custom_courses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("song_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("course_file_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="custom_courses_owner_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="custom_courses_pkey"),
    )
    op.create_index("ix_custom_courses_owner_id", "custom_courses", ["owner_id"], unique=False)

    # ── schedules ────────────────────────────────────────────────────────────
    op.create_table(
        "schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_time", sa.String(8), nullable=True),
        sa.Column("is_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="schedules_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="schedules_pkey"),
    )
    op.create_index("ix_schedules_user_id", "schedules", ["user_id"], unique=False)
    op.create_index(
        "ix_schedules_user_id_scheduled_date",
        "schedules",
        ["user_id", "scheduled_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("schedules")
    op.drop_table("custom_courses")
    op.drop_table("custom_difficulty_tables")
    op.drop_table("courses")
    op.drop_table("user_scores")
    op.drop_table("user_player_stats")
    op.drop_table("user_fumen_tags")
    op.drop_table("user_favorite_difficulty_tables")
    op.drop_table("fumens")
    op.drop_table("difficulty_tables")
    op.drop_table("oauth_accounts")
    op.drop_table("users")
