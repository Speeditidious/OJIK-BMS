"""Tests for the issue domain: models, services, and API endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path


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


def test_migration_0038_adds_issue_mention_source_index() -> None:
    """Mention rendering loads rows by source issue/comment, so that lookup must be indexed."""
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "0038_add_issue_mentions_source_index.py"
    content = migration.read_text()

    assert 'revision = "0038"' in content
    assert 'down_revision = "0037"' in content
    assert "ix_issue_user_mentions_source" in content
    assert '"issue_id", "comment_id", "created_at", "id"' in content
