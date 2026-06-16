"""Tests for the issue domain: models, services, and API endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest


# ── Task 1: Model smoke tests ─────────────────────────────────────────────────

def test_issue_models_are_in_metadata() -> None:
    from app.models import Issue, IssueComment, IssueIssueReference, IssueTag, IssueUserMention
    from app.models.base import Base

    assert IssueTag.__tablename__ in Base.metadata.tables
    assert Issue.__tablename__ in Base.metadata.tables
    assert IssueComment.__tablename__ in Base.metadata.tables
    assert IssueUserMention.__tablename__ in Base.metadata.tables
    assert IssueIssueReference.__tablename__ in Base.metadata.tables


def test_issue_migration_timestamp_columns_match_timestamp_mixin() -> None:
    """Issue tables must let the database fill TimestampMixin columns on insert."""
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0033_add_issues.py"
    content = migration.read_text()

    timestamp_column = 'sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)'
    assert content.count(timestamp_column) == 5

    timestamp_column = 'sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)'
    assert content.count(timestamp_column) == 5


# ── Task 2: Parser unit tests ─────────────────────────────────────────────────

def test_extract_issue_references_deduplicates_and_ignores_plain_hash() -> None:
    from app.services.issues import extract_issue_reference_numbers

    assert extract_issue_reference_numbers("See #12 and #12, not #abc or C#.") == [12]


def test_extract_user_mentions_deduplicates_usernames() -> None:
    from app.services.issues import extract_mentioned_usernames

    assert extract_mentioned_usernames("Thanks @RedBall and @redball, cc @player_01.") == ["redball", "player_01"]


def test_extract_user_mentions_supports_korean_usernames() -> None:
    from app.services.issues import extract_mentioned_usernames

    assert extract_mentioned_usernames("@레드볼 확인 부탁드립니다.") == ["레드볼"]


def test_extract_user_mentions_supports_japanese_usernames() -> None:
    from app.services.issues import extract_mentioned_usernames

    assert extract_mentioned_usernames("@レッドボール 確認お願いします。") == ["レッドボール"]


def test_extract_issue_references_empty() -> None:
    from app.services.issues import extract_issue_reference_numbers

    assert extract_issue_reference_numbers("No refs here.") == []


def test_extract_user_mentions_empty() -> None:
    from app.services.issues import extract_mentioned_usernames

    assert extract_mentioned_usernames("No mentions here.") == []


def test_extract_issue_references_multiple_unique() -> None:
    from app.services.issues import extract_issue_reference_numbers

    result = extract_issue_reference_numbers("See #1, #2, #3.")
    assert result == [1, 2, 3]


# ── Task 3: WIP status, sort, and counts wiring ───────────────────────────────

def test_issue_status_enum_includes_work_in_progress() -> None:
    """IssueStatus must carry the four supported statuses."""
    from app.routers.issues import IssueStatus

    assert {s.value for s in IssueStatus} == {
        "open",
        "work_in_progress",
        "completed",
        "not_planned",
    }


def test_commentable_statuses_include_open_and_work_in_progress() -> None:
    """WIP keeps comments open; completed/not_planned do not."""
    from app.routers.issues import _COMMENTABLE_STATUSES

    assert _COMMENTABLE_STATUSES == frozenset({"open", "work_in_progress"})


def test_issue_sort_key_enum_values() -> None:
    """Sort dropdown offers last_activity and created only ('updated' was removed)."""
    from app.routers.issues import IssueSortKey

    assert {s.value for s in IssueSortKey} == {"last_activity", "created"}


def test_issue_comment_read_includes_event_fields() -> None:
    """Comment payload must surface event_type and event_payload for the timeline."""
    from app.routers.issues import IssueCommentRead

    fields = IssueCommentRead.model_fields
    assert "event_type" in fields
    assert "event_payload" in fields
    # body must accept None since system events carry no text.
    assert type(None) in getattr(fields["body"].annotation, "__args__", ())


def test_issue_read_schemas_include_resolved_mentions() -> None:
    """Issue and comment payloads must carry resolved mention metadata for stable user links."""
    from app.routers.issues import IssueCommentRead, IssueMentionRead, IssueRead

    assert "mentions" in IssueRead.model_fields
    assert "mentions" in IssueCommentRead.model_fields
    assert {"source_text", "user"} <= set(IssueMentionRead.model_fields)


def test_extract_user_mention_tokens_preserves_source_text() -> None:
    """Mention persistence needs the original token plus a normalized username lookup key."""
    from app.services.issues import extract_user_mention_tokens

    mentions = extract_user_mention_tokens("Thanks @RedBall and @redball, cc @player_01.")

    assert [(m.username, m.source_text) for m in mentions] == [
        ("redball", "@RedBall"),
        ("player_01", "@player_01"),
    ]


def test_migration_0036_declares_revision_metadata() -> None:
    """Migration 0036 must drop the unused updated_at index and add event columns."""
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0036_add_issue_comment_events.py"
    content = migration.read_text()

    assert 'revision = "0036"' in content
    assert 'down_revision = "0035"' in content
    assert "drop_index(\"ix_issues_status_updated_at\"" in content
    assert "event_type" in content
    assert "event_payload" in content


def test_issue_status_counts_schema_includes_all_statuses() -> None:
    """IssueStatusCounts response must expose a field per status."""
    from app.routers.issues import IssueStatusCounts

    counts = IssueStatusCounts()
    for field in ("open", "work_in_progress", "completed", "not_planned"):
        assert getattr(counts, field) == 0


def test_issue_model_check_constraint_lists_work_in_progress() -> None:
    """The Issue model's CheckConstraint must include 'work_in_progress'."""
    from sqlalchemy import CheckConstraint
    from app.models.issue import Issue

    check_clauses = [c for c in Issue.__table_args__ if isinstance(c, CheckConstraint)]
    assert any(
        "work_in_progress" in str(c.sqltext) for c in check_clauses
    ), "ck_issues_status must allow 'work_in_progress'"


def test_migration_0035_declares_revision_metadata() -> None:
    """Migration 0035 must declare alembic module-level variables (not comments)."""
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0035_add_issue_wip_status_and_sort_indexes.py"
    content = migration.read_text()

    assert 'revision = "0035"' in content
    assert 'down_revision = "0034"' in content
    assert "branch_labels = None" in content
    assert "depends_on = None" in content
    assert "work_in_progress" in content
    assert "ix_issues_status_created_at" in content
    assert "ix_issues_status_updated_at" in content


def test_migration_0040_adds_issue_pinning_columns_and_indexes() -> None:
    """Migration 0040 must add issue pinning metadata and list indexes."""
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0040_add_issue_pinning.py"
    content = migration.read_text()

    assert 'revision = "0040"' in content
    assert 'down_revision = "0039"' in content
    assert "is_pinned" in content
    assert "pinned_at" in content
    assert "pinned_by_id" in content
    assert "ix_issues_pinned_activity" in content
    assert "ix_issues_status_pinned_activity" in content


def test_issue_author_read_includes_admin_flag() -> None:
    from app.routers.issues import IssueAuthorRead

    assert "is_admin" in IssueAuthorRead.model_fields


def test_issue_read_includes_pinning_fields() -> None:
    from app.routers.issues import IssueRead

    for field in ("is_pinned", "pinned_at", "pinned_by"):
        assert field in IssueRead.model_fields


def test_issue_order_by_prioritizes_pinned_before_selected_sort() -> None:
    from app.routers.issues import _issue_order_by, IssueSortKey

    order_columns = [str(expr) for expr in _issue_order_by(IssueSortKey.created)]

    assert "issues.is_pinned" in order_columns[0]
    assert "issues.created_at" in order_columns[1]
    assert "issues.id" in order_columns[2]


def test_issue_pin_update_schema_exists() -> None:
    from app.routers.issues import IssuePinUpdate

    assert "is_pinned" in IssuePinUpdate.model_fields


@pytest.mark.asyncio
async def test_issue_user_search_keeps_all_matching_users() -> None:
    """@mention autocomplete should not hide inactive matching usernames."""
    from sqlalchemy.dialects import postgresql

    from app.routers.issues import search_users

    class EmptyScalars:
        def all(self) -> list:
            return []

    class EmptyResult:
        def scalars(self) -> EmptyScalars:
            return EmptyScalars()

    class RecordingDb:
        def __init__(self) -> None:
            self.statement = None

        async def execute(self, statement):
            self.statement = statement
            return EmptyResult()

    db = RecordingDb()

    await search_users(q="q", db=db)

    assert db.statement is not None
    sql = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "users.is_active IS true" not in sql


def test_issue_search_keyword_normalization_removes_whitespace() -> None:
    from app.routers.issues import _normalize_issue_search_keyword

    assert _normalize_issue_search_keyword(" 질 문 ") == "질문"
    assert _normalize_issue_search_keyword("bug report") == "bugreport"
    assert _normalize_issue_search_keyword("[GEN-GAOZO]") == "gengaozo"


def test_issue_search_condition_includes_whitespace_insensitive_substring_match() -> None:
    from sqlalchemy.dialects import postgresql

    from app.routers.issues import IssueSearchField, _build_search_condition

    compiled = _build_search_condition("질 문", IssueSearchField.title).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)

    assert "to_tsvector" in sql
    assert "plainto_tsquery" in sql
    assert "regexp_replace" in sql
    assert "LIKE" in sql
    assert "%질문%" in compiled.params.values()


def test_issue_search_condition_removes_symbols_for_substring_match() -> None:
    from sqlalchemy.dialects import postgresql

    from app.routers.issues import IssueSearchField, _build_search_condition

    compiled = _build_search_condition("gen gaozo", IssueSearchField.all).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)

    assert "[^[:alnum:]]+" in compiled.params.values()
    assert "%gengaozo%" in compiled.params.values()


def test_issue_activity_notification_dedupe_key_shapes() -> None:
    from app.services.notifications import build_issue_activity_dedupe_key

    assert build_issue_activity_dedupe_key("comment", 12, "abc", "user-1") == "issue_activity:comment:12:abc:user:user-1"
    assert build_issue_activity_dedupe_key("status_change", 12, "evt-1", "user-1") == "issue_activity:status_change:12:evt-1:user:user-1"


def test_migration_0038_adds_issue_mention_source_index() -> None:
    """Mention rendering loads rows by source issue/comment, so that lookup must be indexed."""
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0038_add_issue_mentions_source_index.py"
    content = migration.read_text()

    assert 'revision = "0038"' in content
    assert 'down_revision = "0037"' in content
    assert "ix_issue_user_mentions_source" in content
    assert '"issue_id", "comment_id", "created_at", "id"' in content


def test_replace_issue_references_function_is_importable() -> None:
    from app.services.issues import replace_issue_references
    import inspect
    sig = inspect.signature(replace_issue_references)
    assert "comment_id" in sig.parameters
    assert "send_notifications" not in sig.parameters  # notifications always off for edits


def test_persist_issue_references_accepts_send_notifications_kwarg() -> None:
    from app.services.issues import persist_issue_references
    import inspect
    sig = inspect.signature(persist_issue_references)
    assert "send_notifications" in sig.parameters
    assert sig.parameters["send_notifications"].default is True


def test_issue_body_update_schema_exists_with_body_field() -> None:
    from app.routers.issues import IssueBodyUpdate

    assert "body" in IssueBodyUpdate.model_fields
    field = IssueBodyUpdate.model_fields["body"]
    # min_length=1, max_length=20000
    metadata = {c.__class__.__name__: c for c in (field.metadata or [])}
    assert "MinLen" in metadata or any(
        hasattr(c, "min_length") for c in (field.metadata or [])
    )


def test_issue_body_update_rejects_empty_body() -> None:
    from pydantic import ValidationError
    from app.routers.issues import IssueBodyUpdate

    try:
        IssueBodyUpdate(body="")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_issue_comment_body_update_schema_exists_with_body_field() -> None:
    from app.routers.issues import IssueCommentBodyUpdate

    assert "body" in IssueCommentBodyUpdate.model_fields
    field = IssueCommentBodyUpdate.model_fields["body"]
    metadata = {c.__class__.__name__: c for c in (field.metadata or [])}
    assert "MinLen" in metadata or any(
        hasattr(c, "min_length") for c in (field.metadata or [])
    )


def test_issue_comment_body_update_rejects_empty_body() -> None:
    from pydantic import ValidationError
    from app.routers.issues import IssueCommentBodyUpdate

    try:
        IssueCommentBodyUpdate(body="")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


@pytest.mark.asyncio
async def test_update_comment_body_returns_403_for_non_author() -> None:
    """Only the comment author may edit; other users get 403."""
    from fastapi import HTTPException
    import uuid
    from datetime import UTC, datetime
    from app.routers.issues import update_comment_body, IssueCommentBodyUpdate

    _author_id = uuid.uuid4()
    _other_id = uuid.uuid4()
    _comment_id = uuid.uuid4()

    class FakeComment:
        id = _comment_id
        issue_id = 1
        author_id = _author_id
        event_type = None
        body = "original"
        updated_at = datetime.now(UTC)

    class FakeResult:
        def scalar_one_or_none(self):
            return FakeComment()

    class FakeDb:
        async def execute(self, _):
            return FakeResult()

    class FakeUser:
        id = _other_id

    data = IssueCommentBodyUpdate(body="new body")
    try:
        await update_comment_body(
            issue_id=1,
            comment_id=_comment_id,
            data=data,
            current_user=FakeUser(),
            db=FakeDb(),
        )
        assert False, "Expected 403"
    except HTTPException as e:
        assert e.status_code == 403
