"""Public site-wide user activity endpoints: recent-sync feed and 30-day leaderboard.

Unlike `analysis.py` (personal-user-scoped, auth-required throughout), this router
is site-wide and public: `/activity/recent` requires no auth at all, and
`/activity/ranking` only uses auth optionally (to resolve the caller's own rank).
"""
from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.score import UserActivityRanking, UserSyncEvent
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activity", tags=["activity"])

_WINDOW_DAYS = 30
_RANKING_METRICS = {"attendance", "plays", "notes_hit"}

#: TTL for the `/activity/recent` response cache. Short on purpose: this is the
#: home page's default tab, hit by every visitor, but the feed must still feel
#: near-live.
_RECENT_CACHE_TTL_SECONDS = 30


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

# ---------------------------------------------------------------------------
# Redis response cache for /activity/recent
#
# `/activity/recent` is the home page's default tab and is fully public (no
# auth, no per-user variation), so an identical response can safely be shared
# across all visitors for a short TTL. Redis is otherwise only used here as the
# Celery broker/backend, so there's no existing HTTP-cache helper to reuse;
# this is deliberately kept minimal and local rather than generalized.
#
# Every cache operation fails open: any Redis error is logged once at WARNING
# and the request proceeds against the database.
# ---------------------------------------------------------------------------

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis | None:
    """Return a lazily-created Redis client, or None if one can't be constructed.

    Construction is non-blocking (redis-py connects lazily on first command),
    so an unreachable Redis surfaces as an error at get/set time, not here.
    """
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as exc:  # pragma: no cover - malformed REDIS_URL only
            logger.warning("activity cache: could not create Redis client: %s", exc)
            return None
    return _redis_client


def _recent_cache_key(page_size: int, cursor: str | None) -> str:
    """Cache key for one `/activity/recent` page: `activity:recent:{page_size}:{cursor}`."""
    return f"activity:recent:{page_size}:{cursor or ''}"


async def _cache_get(key: str) -> dict | None:
    """Read a cached JSON payload, returning None on miss or any Redis failure."""
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception as exc:
        logger.warning("activity cache: Redis GET failed (%s), serving uncached", exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        # Corrupt/legacy payload — treat as a miss rather than failing the request.
        return None


async def _cache_set(key: str, payload: dict) -> None:
    """Store a JSON payload under `key` with the short TTL; silent on Redis failure."""
    client = _get_redis()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(payload), ex=_RECENT_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("activity cache: Redis SET failed (%s), continuing uncached", exc)


def _dialect_name(db: AsyncSession) -> str:
    """Return the bound dialect's name, defaulting to postgresql (mirrors `fumen_popularity.py`)."""
    bind = db.get_bind()
    return bind.dialect.name if bind is not None else "postgresql"


def _non_empty_updates_expr(dialect_name: str):
    """SQL predicate for `updated_client_types` being a non-empty JSON array.

    Dialect-branched because the JSON array-length function differs: Postgres
    exposes `jsonb_array_length` for `jsonb` columns, SQLite exposes
    `json_array_length`. Following the same `_utc_date_expr` dialect-branching
    convention already used in `app/services/fumen_popularity.py`.

    Emitting this as SQL (rather than filtering in Python) is what lets the
    Postgres planner match the partial index
    `ix_user_sync_events_updated_synced_at_id`, whose predicate is exactly
    `jsonb_array_length(updated_client_types) > 0`.
    """
    column = UserSyncEvent.updated_client_types
    if dialect_name == "sqlite":
        return func.json_array_length(column) > 0
    return func.jsonb_array_length(column) > 0


async def _fetch_recent_page(
    db: AsyncSession,
    cursor_synced_at: datetime | None,
    cursor_id: uuid.UUID | None,
    page_size: int,
) -> list[tuple[UserSyncEvent, str, str | None, bool]]:
    """Fetch up to `page_size + 1` in-window sync events with non-empty updates.

    Ordering is keyset pagination on `(synced_at DESC, id DESC)`.

    Tuple comparison `(synced_at, id) < (cursor_synced_at, cursor_id)` is
    expressed as `or_(synced_at < x, and_(synced_at == x, id < y))` rather than
    `sqlalchemy.tuple_(...)`, because it's the form most portable across
    backends and is straightforward to verify against SQLite directly.

    Both the empty-`updated_client_types` filter and the `is_active` filter are
    applied in SQL, so `limit(page_size + 1)` is exact: `has_next_page` is
    always accurate and no over-fetching is needed.
    """
    window_start = datetime.now(UTC) - timedelta(days=_WINDOW_DAYS)

    query = (
        select(UserSyncEvent, User.username, User.avatar_url, User.is_admin)
        .join(User, User.id == UserSyncEvent.user_id)
        .where(
            UserSyncEvent.synced_at >= window_start,
            # Deactivated/banned accounts are invisible site-wide (mirrors
            # `ranking_calculator.select_ranking_user_ids`'s `is_active IS TRUE`).
            User.is_active.is_(True),
            _non_empty_updates_expr(_dialect_name(db)),
        )
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
    ).limit(page_size + 1)

    return (await db.execute(query)).all()


@router.get("/recent", response_model=RecentActivityResponse)
async def get_recent_activity(
    page_size: int = Query(10, ge=10, le=50),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RecentActivityResponse:
    """Public feed of recent syncs (last 30 days) that actually changed something.

    No authentication required. Events with an empty `updated_client_types`
    (i.e. a sync that found nothing new) are excluded from the feed, as are
    events belonging to deactivated users.

    Responses are cached in Redis for `_RECENT_CACHE_TTL_SECONDS`, keyed by
    `(page_size, cursor)`. The response carries no per-user data, so the cache
    is shared across all visitors.
    """
    cache_key = _recent_cache_key(page_size, cursor)
    cached = await _cache_get(cache_key)
    if cached is not None:
        return RecentActivityResponse(**cached)

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

    response = RecentActivityResponse(
        items=items,
        window_days=_WINDOW_DAYS,
        next_cursor=next_cursor,
        has_next_page=has_next_page,
    )
    await _cache_set(cache_key, response.model_dump())
    return response


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
        .where(
            UserActivityRanking.metric == metric,
            UserActivityRanking.rank > rank_after,
            # Defense in depth: `activity_ranking.py` already excludes inactive
            # users when building the snapshot, but a user deactivated between
            # two snapshot rebuilds must not remain visible on the leaderboard.
            User.is_active.is_(True),
        )
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

    # Deliberately not filtered on `current_user.is_active`: this is the caller
    # looking up their own row, not a public listing. In practice a deactivated
    # user has no snapshot row (the rebuild excludes them), so this resolves to
    # None on its own once the next rebuild runs.
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
