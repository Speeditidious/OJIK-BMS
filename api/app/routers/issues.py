"""Public issue endpoints: list, create, comment, search, and admin status management."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.issue import Issue, IssueComment, IssueTag, IssueUserMention
from app.models.user import User
from app.routers.auth import build_discord_avatar_url
from app.schemas import Pagination

router = APIRouter(prefix="/issues", tags=["issues"])


# ── Enums ──────────────────────────────────────────────────────────────────────

class IssueStatus(StrEnum):
    open = "open"
    work_in_progress = "work_in_progress"
    completed = "completed"
    not_planned = "not_planned"


# Statuses where any authenticated user can still post comments.
_COMMENTABLE_STATUSES: frozenset[str] = frozenset({"open", "work_in_progress"})


class IssueSearchField(StrEnum):
    all = "all"
    title = "title"
    body = "body"


class IssueSortKey(StrEnum):
    last_activity = "last_activity"
    created = "created"


# ── Schemas ────────────────────────────────────────────────────────────────────

class IssueTagRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    name_en: str | None = None
    name_ja: str | None = None
    color: str | None = None
    content_hint: str | None = None
    display_order: int = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class IssueAuthorRead(BaseModel):
    id: str
    username: str
    avatar_url: str | None = None
    is_admin: bool = False


class IssueMentionRead(BaseModel):
    source_text: str
    user: IssueAuthorRead


class IssueRead(BaseModel):
    id: int
    tag: IssueTagRead
    status: IssueStatus
    title: str
    body: str
    author: IssueAuthorRead
    comment_count: int
    last_activity_at: datetime
    closed_at: datetime | None = None
    closed_by: IssueAuthorRead | None = None
    is_pinned: bool = False
    pinned_at: datetime | None = None
    pinned_by: IssueAuthorRead | None = None
    mentions: list[IssueMentionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueCreate(BaseModel):
    tag_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)


class IssueCommentRead(BaseModel):
    id: uuid.UUID
    issue_id: int
    author: IssueAuthorRead
    body: str | None
    created_at: datetime
    updated_at: datetime
    event_type: str | None = None
    event_payload: dict | None = None
    mentions: list[IssueMentionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IssueCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class IssueStatusUpdate(BaseModel):
    status: IssueStatus


class IssuePinUpdate(BaseModel):
    is_pinned: bool


class UserSearchResult(BaseModel):
    id: str
    username: str
    avatar_url: str | None = None


class IssueSearchResult(BaseModel):
    id: int
    title: str
    status: IssueStatus


# ── Helpers ────────────────────────────────────────────────────────────────────

def _issue_load_options():
    """Standard eager-load options for fetching an Issue with author info filled in."""
    return (
        selectinload(Issue.author).selectinload(User.oauth_accounts),
        selectinload(Issue.tag),
        selectinload(Issue.closed_by).selectinload(User.oauth_accounts),
        selectinload(Issue.pinned_by).selectinload(User.oauth_accounts),
    )


def _comment_load_options():
    """Standard eager-load options for fetching IssueComment with author info filled in."""
    return (
        selectinload(IssueComment.author).selectinload(User.oauth_accounts),
    )


def _resolve_user_avatar(user: User) -> str | None:
    """Resolve a user's effective avatar URL from their loaded OAuth accounts.

    Mirrors `routers/users._resolve_avatar`: custom upload wins, otherwise we fall
    back to the Discord avatar stored on the user's oauth_accounts row. Callers
    must `selectinload(User.oauth_accounts)` to avoid an extra query per user.
    """
    if user.avatar_url:
        return user.avatar_url
    for oauth in user.oauth_accounts:
        avatar_hash = getattr(oauth, "discord_avatar_hash", None)
        if oauth.provider == "discord" and (avatar_hash or oauth.discord_avatar_url):
            return (
                build_discord_avatar_url(getattr(oauth, "provider_account_id", ""), avatar_hash)
                or oauth.discord_avatar_url
            )
    return None


def _user_to_author(user: User) -> IssueAuthorRead:
    return IssueAuthorRead(
        id=str(user.id),
        username=user.username,
        avatar_url=_resolve_user_avatar(user),
        is_admin=bool(user.is_admin),
    )


MentionSourceKey = tuple[int, uuid.UUID | None]


async def _load_issue_mentions(
    db: AsyncSession,
    *,
    issue_ids: list[int],
    include_issue_body: bool = False,
    comment_ids: list[uuid.UUID] | None = None,
) -> dict[MentionSourceKey, list[IssueMentionRead]]:
    """Load resolved user mentions for issue bodies and/or comments in one query."""
    if not issue_ids:
        return {}

    source_filters = []
    if include_issue_body:
        source_filters.append(IssueUserMention.comment_id.is_(None))
    if comment_ids:
        source_filters.append(IssueUserMention.comment_id.in_(comment_ids))
    if not source_filters:
        return {}

    result = await db.execute(
        select(IssueUserMention)
        .options(selectinload(IssueUserMention.mentioned_user).selectinload(User.oauth_accounts))
        .where(
            IssueUserMention.issue_id.in_(issue_ids),
            or_(*source_filters),
        )
        .order_by(IssueUserMention.created_at, IssueUserMention.id)
    )

    mentions_by_source: dict[MentionSourceKey, list[IssueMentionRead]] = {}
    for mention in result.scalars().all():
        key = (mention.issue_id, mention.comment_id)
        mentions_by_source.setdefault(key, []).append(
            IssueMentionRead(
                source_text=mention.source_text,
                user=_user_to_author(mention.mentioned_user),
            )
        )
    return mentions_by_source


def _issue_to_read(issue: Issue, mentions: list[IssueMentionRead] | None = None) -> IssueRead:
    return IssueRead(
        id=issue.id,
        tag=IssueTagRead.model_validate(issue.tag),
        status=IssueStatus(issue.status),
        title=issue.title,
        body=issue.body,
        author=_user_to_author(issue.author),
        comment_count=issue.comment_count,
        last_activity_at=issue.last_activity_at,
        closed_at=issue.closed_at,
        closed_by=_user_to_author(issue.closed_by) if issue.closed_by else None,
        is_pinned=issue.is_pinned,
        pinned_at=issue.pinned_at,
        pinned_by=_user_to_author(issue.pinned_by) if issue.pinned_by else None,
        mentions=mentions or [],
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _comment_to_read(comment: IssueComment, mentions: list[IssueMentionRead] | None = None) -> IssueCommentRead:
    return IssueCommentRead(
        id=comment.id,
        issue_id=comment.issue_id,
        author=_user_to_author(comment.author),
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        event_type=comment.event_type,
        event_payload=comment.event_payload,
        mentions=mentions or [],
    )


async def _resolve_tag_filter(db: AsyncSession, tag: str) -> uuid.UUID | None:
    """Resolve a tag query param (UUID or slug) to a tag_id, or None if not found."""
    try:
        return uuid.UUID(tag)
    except ValueError:
        result = await db.execute(select(IssueTag).where(IssueTag.slug == tag))
        tag_obj = result.scalar_one_or_none()
        return tag_obj.id if tag_obj else None


def _normalize_issue_search_keyword(q: str) -> str:
    """Normalize a search keyword for whitespace-insensitive substring matching."""
    return "".join(q.lower().split())


def _issue_search_text_expression(search_field: IssueSearchField):
    """Return the issue text expression searched by the selected field."""
    if search_field == IssueSearchField.title:
        return func.coalesce(Issue.title, "")
    if search_field == IssueSearchField.body:
        return func.coalesce(Issue.body, "")
    return func.coalesce(Issue.title, "") + text("' '") + func.coalesce(Issue.body, "")


def _build_search_condition(q: str, search_field: IssueSearchField):
    """Build PostgreSQL search condition with FTS plus whitespace-insensitive substring fallback."""
    search_text = _issue_search_text_expression(search_field)
    fts_condition = func.to_tsvector("simple", search_text).op("@@")(
        func.plainto_tsquery("simple", q)
    )
    normalized_keyword = _normalize_issue_search_keyword(q)
    if not normalized_keyword:
        return fts_condition

    normalized_text = func.regexp_replace(func.lower(search_text), r"\s+", "", "g")
    return or_(fts_condition, normalized_text.like(f"%{normalized_keyword}%"))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/tags", response_model=list[IssueTagRead])
async def list_issue_tags(db: AsyncSession = Depends(get_db)) -> list[IssueTagRead]:
    """List active issue tags ordered by display_order."""
    result = await db.execute(
        select(IssueTag)
        .where(IssueTag.is_active.is_(True))
        .order_by(IssueTag.display_order, IssueTag.name)
    )
    tags = result.scalars().all()
    return [IssueTagRead.model_validate(t) for t in tags]


@router.get("/search/users", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(default="", min_length=0),
    db: AsyncSession = Depends(get_db),
) -> list[UserSearchResult]:
    """Username prefix autocomplete for @mentions. Returns up to 10 matches."""
    if not q:
        return []
    result = await db.execute(
        select(User)
        .where(func.lower(User.username).like(func.lower(q) + "%"))
        .order_by(User.username)
        .limit(10)
    )
    users = result.scalars().all()
    return [UserSearchResult(id=str(u.id), username=u.username, avatar_url=u.avatar_url) for u in users]


@router.get("/search/issues", response_model=list[IssueSearchResult])
async def search_issues(
    q: str = Query(default="", min_length=0),
    db: AsyncSession = Depends(get_db),
) -> list[IssueSearchResult]:
    """Issue title search / numeric ID lookup for #references. Returns up to 10 matches."""
    if not q:
        return []

    q_stripped = q.lstrip("#").strip()
    if q_stripped.isdigit():
        result = await db.execute(select(Issue).where(Issue.id == int(q_stripped)).limit(10))
        issues = result.scalars().all()
    else:
        result = await db.execute(
            select(Issue)
            .where(_build_search_condition(q, IssueSearchField.title))
            .order_by(Issue.id.desc())
            .limit(10)
        )
        issues = result.scalars().all()

    return [IssueSearchResult(id=i.id, title=i.title, status=IssueStatus(i.status)) for i in issues]


_VALID_STATUS_VALUES: frozenset[str] = frozenset(s.value for s in IssueStatus)


_SORT_COLUMNS = {
    IssueSortKey.last_activity: Issue.last_activity_at,
    IssueSortKey.created: Issue.created_at,
}


def _issue_order_by(sort: IssueSortKey):
    """Return stable issue ordering with pinned rows first.

    Pinned issues sort among themselves by the same selected key so the chosen
    sort order remains consistent within each group.
    """
    sort_column = _SORT_COLUMNS[sort]
    return (
        Issue.is_pinned.desc(),
        sort_column.desc(),
        Issue.id.desc(),
    )


@router.get("/", response_model=Pagination[IssueRead])
async def list_issues(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
    q: str | None = Query(default=None),
    search_field: IssueSearchField = Query(default=IssueSearchField.all),
    tag: str | None = Query(default=None),
    status: str | None = Query(default="open"),
    sort: IssueSortKey = Query(default=IssueSortKey.last_activity),
    db: AsyncSession = Depends(get_db),
) -> Pagination[IssueRead]:
    """List issues with optional search, tag filter, status filter, and sort key."""
    filters: list[Any] = []

    if status and status != "all":
        if status not in _VALID_STATUS_VALUES:
            raise HTTPException(status_code=422, detail="Invalid status value.")
        filters.append(Issue.status == status)

    if tag:
        tag_id = await _resolve_tag_filter(db, tag)
        if tag_id is None:
            return Pagination(items=[], total=0, page=page, size=size, pages=0)
        filters.append(Issue.tag_id == tag_id)

    if q:
        filters.append(_build_search_condition(q, search_field))

    base_query = select(Issue).where(*filters) if filters else select(Issue)
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        base_query
        .options(*_issue_load_options())
        .order_by(*_issue_order_by(sort))
        .offset((page - 1) * size)
        .limit(size)
    )
    issues = result.scalars().all()
    pages = (total + size - 1) // size if total > 0 else 0
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[i.id for i in issues],
        include_issue_body=True,
    )

    return Pagination(
        items=[_issue_to_read(i, mentions_by_source.get((i.id, None), [])) for i in issues],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


class IssueStatusCounts(BaseModel):
    open: int = 0
    work_in_progress: int = 0
    completed: int = 0
    not_planned: int = 0


@router.get("/counts", response_model=IssueStatusCounts)
async def get_issue_counts(
    q: str | None = Query(default=None),
    search_field: IssueSearchField = Query(default=IssueSearchField.all),
    tag: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> IssueStatusCounts:
    """Return per-status issue counts, honoring the same search/tag filters as list."""
    filters: list[Any] = []

    if tag:
        tag_id = await _resolve_tag_filter(db, tag)
        if tag_id is None:
            return IssueStatusCounts()
        filters.append(Issue.tag_id == tag_id)

    if q:
        filters.append(_build_search_condition(q, search_field))

    stmt = select(Issue.status, func.count()).group_by(Issue.status)
    if filters:
        stmt = stmt.where(*filters)

    result = await db.execute(stmt)
    counts = IssueStatusCounts()
    for row_status, row_count in result.all():
        if row_status in _VALID_STATUS_VALUES:
            setattr(counts, row_status, row_count)
    return counts


@router.get("/pinned", response_model=list[IssueRead])
async def list_pinned_issues(
    size: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[IssueRead]:
    """List pinned issues for the home page discussion section."""
    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.is_pinned.is_(True))
        .order_by(Issue.pinned_at.desc().nullslast(), Issue.last_activity_at.desc(), Issue.id.desc())
        .limit(size)
    )
    issues = result.scalars().all()
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[i.id for i in issues],
        include_issue_body=True,
    )
    return [_issue_to_read(i, mentions_by_source.get((i.id, None), [])) for i in issues]


@router.get("/{issue_id}", response_model=IssueRead)
async def get_issue(issue_id: int, db: AsyncSession = Depends(get_db)) -> IssueRead:
    """Get a single issue by ID."""
    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[issue.id],
        include_issue_body=True,
    )
    return _issue_to_read(issue, mentions_by_source.get((issue.id, None), []))


@router.post("/", response_model=IssueRead, status_code=201)
async def create_issue(
    data: IssueCreate,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IssueRead:
    """Create a new issue. Requires authentication."""
    from app.services.issues import persist_issue_references

    tag_result = await db.execute(
        select(IssueTag).where(IssueTag.id == data.tag_id, IssueTag.is_active.is_(True))
    )
    tag = tag_result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=422, detail="Tag not found or inactive.")

    now = datetime.now(UTC)
    issue = Issue(
        author_id=current_user.id,
        tag_id=data.tag_id,
        title=data.title,
        body=data.body,
        status="open",
        last_activity_at=now,
    )
    db.add(issue)
    await db.flush()

    await persist_issue_references(
        db,
        issue_id=issue.id,
        issue_title=issue.title,
        comment_id=None,
        body=data.body,
        actor_user_id=current_user.id,
        actor_username=current_user.username,
    )
    await db.commit()
    await db.refresh(issue)

    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue.id)
    )
    issue = result.scalar_one()
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[issue.id],
        include_issue_body=True,
    )
    return _issue_to_read(issue, mentions_by_source.get((issue.id, None), []))


@router.get("/{issue_id}/comments", response_model=Pagination[IssueCommentRead])
async def list_comments(
    issue_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Pagination[IssueCommentRead]:
    """List comments for an issue, ordered chronologically."""
    issue_result = await db.execute(select(Issue.id).where(Issue.id == issue_id))
    if issue_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Issue not found.")

    count_result = await db.execute(
        select(func.count()).where(IssueComment.issue_id == issue_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(IssueComment)
        .options(*_comment_load_options())
        .where(IssueComment.issue_id == issue_id)
        .order_by(IssueComment.created_at, IssueComment.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    comments = result.scalars().all()
    pages = (total + size - 1) // size if total > 0 else 0
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[issue_id],
        comment_ids=[c.id for c in comments],
    )

    return Pagination(
        items=[_comment_to_read(c, mentions_by_source.get((c.issue_id, c.id), [])) for c in comments],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post("/{issue_id}/comments", response_model=IssueCommentRead, status_code=201)
async def create_comment(
    issue_id: int,
    data: IssueCommentCreate,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IssueCommentRead:
    """Add a comment to an open issue. Requires authentication."""
    from app.services.issues import persist_issue_references

    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status not in _COMMENTABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Cannot comment on a closed issue.")

    now = datetime.now(UTC)
    comment = IssueComment(
        issue_id=issue_id,
        author_id=current_user.id,
        body=data.body,
    )
    db.add(comment)
    await db.flush()

    await db.execute(
        update(Issue)
        .where(Issue.id == issue_id)
        .values(comment_count=Issue.comment_count + 1, last_activity_at=now)
    )

    await persist_issue_references(
        db,
        issue_id=issue_id,
        issue_title=issue.title,
        comment_id=comment.id,
        body=data.body,
        actor_user_id=current_user.id,
        actor_username=current_user.username,
    )

    from app.services.notifications import create_issue_activity_notification

    await create_issue_activity_notification(
        db,
        issue_id=issue_id,
        issue_title=issue.title,
        target_user_id=issue.author_id,
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        activity_type="comment",
        source_id=str(comment.id),
        metadata={"comment_id": str(comment.id)},
    )
    await db.commit()
    await db.refresh(comment)

    result = await db.execute(
        select(IssueComment)
        .options(*_comment_load_options())
        .where(IssueComment.id == comment.id)
    )
    comment = result.scalar_one()
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[issue_id],
        comment_ids=[comment.id],
    )
    return _comment_to_read(comment, mentions_by_source.get((comment.issue_id, comment.id), []))


@router.patch("/{issue_id}/status", response_model=IssueRead)
async def update_issue_status(
    issue_id: int,
    data: IssueStatusUpdate,
    current_admin: Any = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> IssueRead:
    """Update issue status (admin only).

    Transitions into 'open' or 'work_in_progress' clear closed_at/closed_by — those
    are open states where any user may still comment. 'completed' and 'not_planned'
    record the closing admin and timestamp.
    """
    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")

    previous_status = issue.status
    new_status = data.status.value
    if previous_status == new_status:
        return _issue_to_read(issue)

    now = datetime.now(UTC)
    issue.status = new_status
    issue.last_activity_at = now
    if new_status in _COMMENTABLE_STATUSES:
        issue.closed_at = None
        issue.closed_by_id = None
    else:
        issue.closed_at = now
        issue.closed_by_id = current_admin.id

    # System event row appears in the comment timeline but does not count toward
    # comment_count and carries no body.
    status_event = IssueComment(
        issue_id=issue_id,
        author_id=current_admin.id,
        body=None,
        event_type="status_change",
        event_payload={"from": previous_status, "to": new_status},
    )
    db.add(status_event)
    await db.flush()

    from app.services.notifications import create_issue_activity_notification

    await create_issue_activity_notification(
        db,
        issue_id=issue_id,
        issue_title=issue.title,
        target_user_id=issue.author_id,
        actor_user_id=current_admin.id,
        actor_username=current_admin.username,
        activity_type="status_change",
        source_id=str(status_event.id),
        metadata={"from": previous_status, "to": new_status, "event_id": str(status_event.id)},
    )

    await db.commit()
    await db.refresh(issue)

    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue_id)
    )
    issue = result.scalar_one()
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[issue.id],
        include_issue_body=True,
    )
    return _issue_to_read(issue, mentions_by_source.get((issue.id, None), []))


@router.patch("/{issue_id}/pin", response_model=IssueRead)
async def update_issue_pin(
    issue_id: int,
    data: IssuePinUpdate,
    current_admin: Any = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> IssueRead:
    """Pin or unpin an issue as an admin-only discussion highlight."""
    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")

    if issue.is_pinned == data.is_pinned:
        return _issue_to_read(issue)

    now = datetime.now(UTC)
    issue.is_pinned = data.is_pinned
    issue.pinned_at = now if data.is_pinned else None
    issue.pinned_by_id = current_admin.id if data.is_pinned else None
    issue.last_activity_at = now

    pin_event = IssueComment(
        issue_id=issue_id,
        author_id=current_admin.id,
        body=None,
        event_type="pin_change",
        event_payload={"is_pinned": data.is_pinned},
    )
    db.add(pin_event)
    await db.flush()

    from app.services.notifications import create_issue_activity_notification

    await create_issue_activity_notification(
        db,
        issue_id=issue_id,
        issue_title=issue.title,
        target_user_id=issue.author_id,
        actor_user_id=current_admin.id,
        actor_username=current_admin.username,
        activity_type="pin_change",
        source_id=str(pin_event.id),
        metadata={"is_pinned": data.is_pinned, "event_id": str(pin_event.id)},
    )

    await db.commit()

    result = await db.execute(
        select(Issue)
        .options(*_issue_load_options())
        .where(Issue.id == issue_id)
    )
    issue = result.scalar_one()
    mentions_by_source = await _load_issue_mentions(
        db,
        issue_ids=[issue.id],
        include_issue_body=True,
    )
    return _issue_to_read(issue, mentions_by_source.get((issue.id, None), []))
