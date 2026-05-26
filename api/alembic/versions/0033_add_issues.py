"""Add issue domain tables (issue_tags, issues, issue_comments, issue_user_mentions, issue_issue_references).

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-25
"""

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Seed data ──────────────────────────────────────────────────────────────────

bug_hint = """### 버그 제보 팁
1. 문제가 발생하는 상황을 구체적으로 적어주세요. 재현 가능하다면 어떤 조건에서 재현되는지 상세히 적어주시면 큰 도움이 됩니다.
2. 클라이언트 측 버그의 경우 클라이언트 버전과 컴퓨터 운영체제를 기재해주세요. 또한, 동기화 이슈라면 동기화 할 때 뜨는 활동 로그도 올려주세요.
3. 이미 다뤄진 이슈인지 확인해주세요. Open 상태가 아닌데 추가 의견을 제시하고 싶으신 경우, 그 이슈 참조를 내용에 포함해주세요."""

other_hint = "해당 태그는 버그 제보, 건의사항, 질문 등 존재하는 태그 전부 부합하지 않은 내용일 때 사용해주세요."

_SEED_TAGS = [
    {
        "id": str(uuid.uuid4()),
        "slug": "bug",
        "name": "버그",
        "name_en": "Bug",
        "name_ja": "バグ",
        "color": "destructive",
        "content_hint": bug_hint,
        "display_order": 0,
        "is_active": True,
    },
    {
        "id": str(uuid.uuid4()),
        "slug": "suggestion",
        "name": "건의",
        "name_en": "Suggestion",
        "name_ja": "提案",
        "color": "primary",
        "content_hint": None,
        "display_order": 1,
        "is_active": True,
    },
    {
        "id": str(uuid.uuid4()),
        "slug": "question",
        "name": "질문",
        "name_en": "Question",
        "name_ja": "質問",
        "color": "secondary",
        "content_hint": None,
        "display_order": 2,
        "is_active": True,
    },
    {
        "id": str(uuid.uuid4()),
        "slug": "other",
        "name": "기타",
        "name_en": "Other",
        "name_ja": "その他",
        "color": "muted",
        "content_hint": other_hint,
        "display_order": 3,
        "is_active": True,
    },
]


def upgrade() -> None:
    now = datetime.now(UTC)

    # ── issue_tags ────────────────────────────────────────────────────────────
    op.create_table(
        "issue_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("name_en", sa.String(64), nullable=True),
        sa.Column("name_ja", sa.String(64), nullable=True),
        sa.Column("color", sa.String(64), nullable=True),
        sa.Column("content_hint", sa.Text, nullable=True),
        sa.Column("display_order", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_issue_tags_slug"),
    )
    op.create_index("ix_issue_tags_active_order", "issue_tags", ["is_active", "display_order", "name"])

    # ── issues ────────────────────────────────────────────────────────────────
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), server_default=sa.text("'open'"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("comment_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tag_id"], ["issue_tags.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["closed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('open', 'completed', 'not_planned')", name="ck_issues_status"),
    )
    op.create_index("ix_issues_status_activity", "issues", ["status", "last_activity_at", "id"])
    op.create_index("ix_issues_tag_status_activity", "issues", ["tag_id", "status", "last_activity_at", "id"])
    op.execute(
        "CREATE INDEX ix_issues_search_all ON issues USING gin "
        "(to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, '')))"
    )
    op.execute(
        "CREATE INDEX ix_issues_search_title ON issues USING gin "
        "(to_tsvector('simple', coalesce(title, '')))"
    )
    op.execute(
        "CREATE INDEX ix_issues_search_body ON issues USING gin "
        "(to_tsvector('simple', coalesce(body, '')))"
    )

    # ── issue_comments ────────────────────────────────────────────────────────
    op.create_table(
        "issue_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("issue_id", sa.Integer, nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_issue_comments_issue_created", "issue_comments", ["issue_id", "created_at", "id"])
    op.create_index("ix_issue_comments_author_created", "issue_comments", ["author_id", "created_at"])

    # ── issue_user_mentions ───────────────────────────────────────────────────
    op.create_table(
        "issue_user_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("issue_id", sa.Integer, nullable=False),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mentioned_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_text", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["comment_id"], ["issue_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mentioned_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("issue_id", "comment_id", "mentioned_user_id", name="uq_issue_user_mentions_source_user"),
    )
    op.create_index("ix_issue_user_mentions_user_created", "issue_user_mentions", ["mentioned_user_id", "created_at"])

    # ── issue_issue_references ────────────────────────────────────────────────
    op.create_table(
        "issue_issue_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_issue_id", sa.Integer, nullable=False),
        sa.Column("source_comment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_issue_id", sa.Integer, nullable=False),
        sa.Column("source_text", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_comment_id"], ["issue_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_issue_id", "source_comment_id", "target_issue_id", name="uq_issue_issue_refs_source_target"),
    )
    op.create_index("ix_issue_issue_refs_target_created", "issue_issue_references", ["target_issue_id", "created_at"])

    # ── Seed tags ─────────────────────────────────────────────────────────────
    issue_tags_table = sa.table(
        "issue_tags",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("name_en", sa.String),
        sa.column("name_ja", sa.String),
        sa.column("color", sa.String),
        sa.column("content_hint", sa.Text),
        sa.column("display_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        issue_tags_table,
        [
            {**tag, "created_at": now, "updated_at": now}
            for tag in _SEED_TAGS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_issue_issue_refs_target_created", table_name="issue_issue_references")
    op.drop_table("issue_issue_references")

    op.drop_index("ix_issue_user_mentions_user_created", table_name="issue_user_mentions")
    op.drop_table("issue_user_mentions")

    op.drop_index("ix_issue_comments_author_created", table_name="issue_comments")
    op.drop_index("ix_issue_comments_issue_created", table_name="issue_comments")
    op.drop_table("issue_comments")

    op.execute("DROP INDEX IF EXISTS ix_issues_search_body")
    op.execute("DROP INDEX IF EXISTS ix_issues_search_title")
    op.execute("DROP INDEX IF EXISTS ix_issues_search_all")
    op.drop_index("ix_issues_tag_status_activity", table_name="issues")
    op.drop_index("ix_issues_status_activity", table_name="issues")
    op.drop_table("issues")

    op.drop_index("ix_issue_tags_active_order", table_name="issue_tags")
    op.drop_table("issue_tags")
