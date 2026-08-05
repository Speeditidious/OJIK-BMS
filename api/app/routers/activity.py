"""Public site-wide user activity endpoints: recent-sync feed and 30-day leaderboard.

Unlike `analysis.py` (personal-user-scoped, auth-required throughout), this router
is site-wide and public: `/activity/recent` requires no auth at all, and
`/activity/ranking` only uses auth optionally (to resolve the caller's own rank).
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.score import UserActivityRanking, UserSyncEvent
from app.models.user import User

router = APIRouter(prefix="/activity", tags=["activity"])

_WINDOW_DAYS = 30
_RANKING_METRICS = {"attendance", "plays", "notes_hit"}

# Cap on how many multiples of `page_size + 1` we're willing to fetch from the DB
# in one request while filtering out empty-`updated_client_types` rows in Python
# (see `_fetch_recent_page` docstring for why this filter isn't done in SQL).
_MAX_RAW_FETCH_MULTIPLIER = 8


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class RecentActivityItem(BaseModel):
    id: str
    user_id: str
    username: str
    avatar_url: str | None
    is_admin: bool
    synced_at: str
    sync_date: str  # "YYYY-MM-DD"
    updated_client_types: list[str]


class RecentActivityResponse(BaseModel):
    items: list[RecentActivityItem]
    window_days: int
    next_cursor: str | None
    has_next_page: bool


class RankingItem(BaseModel):
    rank: int
    user_id: str
    username: str
    avatar_url: str | None
    value: int


class MyRank(BaseModel):
    rank: int
    value: int


class ActivityRankingResponse(BaseModel):
    metric: str
    window_start: str | None
    window_end: str | None
    computed_at: str | None
    items: list[RankingItem]
    my_rank: MyRank | None
    next_rank_after: int | None
    has_next_page: bool


# ---------------------------------------------------------------------------
# Cursor encode/decode
#
# No existing cursor-pagination precedent in this codebase — this establishes
# the pattern: a base64url-encoded compact JSON object carrying the last row's
# sort key, `(synced_at, id)`.
# ---------------------------------------------------------------------------

def _encode_cursor(synced_at: datetime, id_: uuid.UUID) -> str:
    """Encode a keyset-pagination cursor from the last row of a page."""
    payload = json.dumps({"synced_at": synced_at.isoformat(), "id": str(id_)}).encode()
    return base64.urlsafe_b64encode(payload).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a cursor produced by `_encode_cursor`; raises 400 on malformed input."""
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["synced_at"]), uuid.UUID(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


# ---------------------------------------------------------------------------
# /activity/recent
# ---------------------------------------------------------------------------

async def _fetch_recent_page(
    db: AsyncSession,
    cursor_synced_at: datetime | None,
    cursor_id: uuid.UUID | None,
    page_size: int,
) -> list[tuple[UserSyncEvent, str, str | None, bool]]:
    """Fetch up to `page_size + 1` in-window sync events with non-empty updates.

    Ordering is keyset pagination on `(synced_at DESC, id DESC)`.

    Two portability notes (no precedent for either in this codebase, verified
    against the SQLite test backend used by this repo's test suite):

    - Tuple comparison `(synced_at, id) < (cursor_synced_at, cursor_id)` is
      expressed as `or_(synced_at < x, and_(synced_at == x, id < y))` rather
      than `sqlalchemy.tuple_(...)`, because it's the form most portable across
      backends and is straightforward to verify against SQLite directly.
    - Filtering out rows with an empty `updated_client_types` JSON array is done
      in Python, not SQL. Postgres exposes `jsonb_array_length` (for `jsonb`
      columns) while SQLite exposes `json_array_length`; a single expression
      that is verified correct on both without a live Postgres instance to test
      against isn't available here, so per the task brief's documented
      fallback, the empty-array filter runs after fetching. To keep pagination
      correct despite this, we over-fetch in growing batches (capped) until we
      have `page_size + 1` qualifying rows or run out of underlying rows.
    """
    window_start = datetime.now(UTC) - timedelta(days=_WINDOW_DAYS)
    multiplier = 1
    filtered: list[tuple[UserSyncEvent, str, str | None, bool]] = []

    while True:
        raw_limit = (page_size + 1) * multiplier
        query = (
            select(UserSyncEvent, User.username, User.avatar_url, User.is_admin)
            .join(User, User.id == UserSyncEvent.user_id)
            .where(UserSyncEvent.synced_at >= window_start)
        )
        if cursor_synced_at is not None and cursor_id is not None:
            query = query.where(
                or_(
                    UserSyncEvent.synced_at < cursor_synced_at,
                    and_(
                        UserSyncEvent.synced_at == cursor_synced_at,
                        UserSyncEvent.id < cursor_id,
                    ),
                )
            )
        query = query.order_by(
            UserSyncEvent.synced_at.desc(), UserSyncEvent.id.desc()
        ).limit(raw_limit)

        rows = (await db.execute(query)).all()
        filtered = [row for row in rows if row[0].updated_client_types]

        if len(filtered) >= page_size + 1 or len(rows) < raw_limit or multiplier >= _MAX_RAW_FETCH_MULTIPLIER:
            return filtered
        multiplier *= 2


@router.get("/recent", response_model=RecentActivityResponse)
async def get_recent_activity(
    page_size: int = Query(10, ge=10, le=50),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RecentActivityResponse:
    """Public feed of recent syncs (last 30 days) that actually changed something.

    No authentication required. Events with an empty `updated_client_types`
    (i.e. a sync that found nothing new) are excluded from the feed.
    """
    cursor_synced_at: datetime | None = None
    cursor_id: uuid.UUID | None = None
    if cursor is not None:
        cursor_synced_at, cursor_id = _decode_cursor(cursor)

    rows = await _fetch_recent_page(db, cursor_synced_at, cursor_id, page_size)

    has_next_page = len(rows) > page_size
    page_rows = rows[:page_size]

    items = [
        RecentActivityItem(
            id=str(event.id),
            user_id=str(event.user_id),
            username=username,
            avatar_url=avatar_url,
            is_admin=is_admin,
            synced_at=event.synced_at.isoformat(),
            sync_date=event.synced_at.date().isoformat(),
            updated_client_types=list(event.updated_client_types or []),
        )
        for event, username, avatar_url, is_admin in page_rows
    ]

    next_cursor: str | None = None
    if has_next_page and page_rows:
        last_event = page_rows[-1][0]
        next_cursor = _encode_cursor(last_event.synced_at, last_event.id)

    return RecentActivityResponse(
        items=items,
        window_days=_WINDOW_DAYS,
        next_cursor=next_cursor,
        has_next_page=has_next_page,
    )


# ---------------------------------------------------------------------------
# /activity/ranking
# ---------------------------------------------------------------------------

@router.get("/ranking", response_model=ActivityRankingResponse)
async def get_activity_ranking(
    metric: str = Query(...),
    page_size: int = Query(10, ge=10, le=50),
    rank_after: int = Query(0, ge=0),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ActivityRankingResponse:
    """Paginated 30-day activity leaderboard for one metric.

    `metric` must be one of `attendance`, `plays`, `notes_hit`. If the
    precomputed snapshot for this metric has no rows yet (not computed yet),
    this returns 200 with empty `items` and null window/computed_at fields —
    the frontend is expected to show a "computing" state, not treat this as
    an error.
    """
    if metric not in _RANKING_METRICS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown metric")

    meta_row = (
        await db.execute(
            select(
                UserActivityRanking.window_start,
                UserActivityRanking.window_end,
                UserActivityRanking.computed_at,
            )
            .where(UserActivityRanking.metric == metric)
            .limit(1)
        )
    ).first()

    if meta_row is None:
        return ActivityRankingResponse(
            metric=metric,
            window_start=None,
            window_end=None,
            computed_at=None,
            items=[],
            my_rank=None,
            next_rank_after=None,
            has_next_page=False,
        )

    window_start, window_end, computed_at = meta_row

    page_result = await db.execute(
        select(UserActivityRanking, User.username, User.avatar_url)
        .join(User, User.id == UserActivityRanking.user_id)
        .where(UserActivityRanking.metric == metric, UserActivityRanking.rank > rank_after)
        .order_by(UserActivityRanking.rank.asc())
        .limit(page_size + 1)
    )
    rows = page_result.all()

    has_next_page = len(rows) > page_size
    page_rows = rows[:page_size]

    items = [
        RankingItem(
            rank=ranking.rank,
            user_id=str(ranking.user_id),
            username=username,
            avatar_url=avatar_url,
            value=ranking.value,
        )
        for ranking, username, avatar_url in page_rows
    ]

    next_rank_after: int | None = None
    if has_next_page and page_rows:
        next_rank_after = page_rows[-1][0].rank

    my_rank: MyRank | None = None
    if current_user is not None:
        my_row = (
            await db.execute(
                select(UserActivityRanking.rank, UserActivityRanking.value).where(
                    UserActivityRanking.metric == metric,
                    UserActivityRanking.user_id == current_user.id,
                )
            )
        ).first()
        if my_row is not None:
            my_rank = MyRank(rank=my_row.rank, value=my_row.value)

    return ActivityRankingResponse(
        metric=metric,
        window_start=window_start.isoformat() if window_start else None,
        window_end=window_end.isoformat() if window_end else None,
        computed_at=computed_at.isoformat() if computed_at else None,
        items=items,
        my_rank=my_rank,
        next_rank_after=next_rank_after,
        has_next_page=has_next_page,
    )
