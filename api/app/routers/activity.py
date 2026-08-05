"""Public site-wide user activity endpoints: recent-sync feed and 30-day leaderboard.

Unlike `analysis.py` (personal-user-scoped, auth-required throughout), this router
is site-wide and public: `/activity/recent` requires no auth at all, and
`/activity/ranking` only uses auth optionally (to resolve the caller's own rank).
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.score import UserActivityRanking, UserSyncEvent
from app.models.user import OAuthAccount, User
from app.routers.auth import build_discord_avatar_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activity", tags=["activity"])

_WINDOW_DAYS = 30
_RANKING_RANGES = {"weekly", "monthly"}
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
    computed_at: str | None = None
    total_count: int
    page: int


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
    range: str
    metric: str
    window_start: str | None
    window_end: str | None
    computed_at: str | None
    items: list[RankingItem]
    my_rank: MyRank | None
    total_count: int
    page: int


def _isoformat_datetime(value: datetime | str | None) -> str | None:
    """Serialize DB datetime values, tolerating SQLite aggregate string results."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


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


def _recent_cache_key(page_size: int, page: int) -> str:
    """Cache key for one `/activity/recent` page: `activity:recent:{page_size}:{page}`."""
    return f"activity:recent:{page_size}:{page}"


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


def _recent_base_filters(db: AsyncSession, window_start: datetime):
    return (
        UserSyncEvent.synced_at >= window_start,
        # Deactivated/banned accounts are invisible site-wide (mirrors
        # `ranking_calculator.select_ranking_user_ids`'s `is_active IS TRUE`).
        User.is_active.is_(True),
        _non_empty_updates_expr(_dialect_name(db)),
    )


async def _fetch_recent_page(
    db: AsyncSession,
    offset: int,
    page_size: int,
) -> list[tuple[UserSyncEvent, str, str | None, str | None, str | None, str | None, bool]]:
    """Fetch exactly one offset-paginated page of in-window sync events with non-empty updates.

    Ordered newest-first on `(synced_at DESC, id DESC)`, matching `/rankings/{table_slug}`'s
    offset/limit pagination style so the frontend can render numbered page buttons.
    """
    window_start = datetime.now(UTC) - timedelta(days=_WINDOW_DAYS)

    query = (
        select(
            UserSyncEvent,
            User.username,
            User.avatar_url,
            OAuthAccount.provider_account_id,
            OAuthAccount.discord_avatar_hash,
            OAuthAccount.discord_avatar_url,
            User.is_admin,
        )
        .join(User, User.id == UserSyncEvent.user_id)
        .outerjoin(
            OAuthAccount,
            and_(OAuthAccount.user_id == User.id, OAuthAccount.provider == "discord"),
        )
        .where(*_recent_base_filters(db, window_start))
        .order_by(UserSyncEvent.synced_at.desc(), UserSyncEvent.id.desc())
        .offset(offset)
        .limit(page_size)
    )

    return (await db.execute(query)).all()


async def _fetch_recent_total(db: AsyncSession) -> int:
    """Total count of in-window, visible sync events, for page-count calculation."""
    window_start = datetime.now(UTC) - timedelta(days=_WINDOW_DAYS)
    return (
        await db.execute(
            select(func.count())
            .select_from(UserSyncEvent)
            .join(User, User.id == UserSyncEvent.user_id)
            .where(*_recent_base_filters(db, window_start))
        )
    ).scalar_one()


async def _fetch_recent_computed_at(db: AsyncSession) -> datetime | str | None:
    """Return the newest in-window visible sync event timestamp for feed metadata."""
    window_start = datetime.now(UTC) - timedelta(days=_WINDOW_DAYS)
    return (
        await db.execute(
            select(func.max(UserSyncEvent.synced_at))
            .join(User, User.id == UserSyncEvent.user_id)
            .where(
                UserSyncEvent.synced_at >= window_start,
                User.is_active.is_(True),
                _non_empty_updates_expr(_dialect_name(db)),
            )
        )
    ).scalar_one_or_none()


@router.get("/recent", response_model=RecentActivityResponse)
async def get_recent_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=10, le=50),
    db: AsyncSession = Depends(get_db),
) -> RecentActivityResponse:
    """Public feed of recent syncs (last 30 days) that actually changed something.

    No authentication required. Events with an empty `updated_client_types`
    (i.e. a sync that found nothing new) are excluded from the feed, as are
    events belonging to deactivated users.

    Offset-paginated (matches `/rankings/{table_slug}`'s `page`/`total_count`
    shape) so the frontend can render numbered page buttons rather than an
    infinite "load more" feed.

    Responses are cached in Redis for `_RECENT_CACHE_TTL_SECONDS`, keyed by
    `(page_size, page)`. The response carries no per-user data, so the cache
    is shared across all visitors.
    """
    cache_key = _recent_cache_key(page_size, page)
    cached = await _cache_get(cache_key)
    if cached is not None:
        return RecentActivityResponse(**cached)

    offset = (page - 1) * page_size
    rows = await _fetch_recent_page(db, offset, page_size)
    total_count = await _fetch_recent_total(db)

    items = [
        RecentActivityItem(
            id=str(event.id),
            user_id=str(event.user_id),
            username=username,
            avatar_url=avatar_url or build_discord_avatar_url(discord_id or "", discord_avatar_hash) or discord_avatar_url,
            is_admin=is_admin,
            synced_at=event.synced_at.isoformat(),
            sync_date=event.synced_at.date().isoformat(),
            updated_client_types=list(event.updated_client_types or []),
        )
        for event, username, avatar_url, discord_id, discord_avatar_hash, discord_avatar_url, is_admin in rows
    ]

    computed_at = await _fetch_recent_computed_at(db)
    response = RecentActivityResponse(
        items=items,
        window_days=_WINDOW_DAYS,
        computed_at=_isoformat_datetime(computed_at),
        total_count=total_count,
        page=page,
    )
    await _cache_set(cache_key, response.model_dump())
    return response


# ---------------------------------------------------------------------------
# /activity/ranking
# ---------------------------------------------------------------------------

@router.get("/ranking", response_model=ActivityRankingResponse)
async def get_activity_ranking(
    range: str = Query("monthly"),
    metric: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=10, le=50),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ActivityRankingResponse:
    """Paginated weekly/monthly activity leaderboard for one metric.

    `range` must be `weekly` or `monthly`; `metric` must be one of
    `attendance`, `plays`, `notes_hit`. If the precomputed snapshot has no rows
    yet (not computed yet), this returns 200 with empty `items` and null
    window/computed_at fields — the frontend is expected to show a "computing"
    state, not treat this as an error.

    Offset-paginated (matches `/rankings/{table_slug}`'s `page`/`total_count`
    shape) so the frontend can render numbered page buttons rather than an
    infinite "load more" feed.
    """
    if range not in _RANKING_RANGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown range")
    if metric not in _RANKING_METRICS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown metric")

    meta_row = (
        await db.execute(
            select(
                UserActivityRanking.window_start,
                UserActivityRanking.window_end,
                UserActivityRanking.computed_at,
            )
            .where(
                UserActivityRanking.range == range,
                UserActivityRanking.metric == metric,
            )
            .limit(1)
        )
    ).first()

    if meta_row is None:
        return ActivityRankingResponse(
            range=range,
            metric=metric,
            window_start=None,
            window_end=None,
            computed_at=None,
            items=[],
            my_rank=None,
            total_count=0,
            page=page,
        )

    window_start, window_end, computed_at = meta_row

    # Defense in depth: `activity_ranking.py` already excludes inactive users
    # when building the snapshot, but a user deactivated between two snapshot
    # rebuilds must not remain visible on the leaderboard.
    base_filters = (
        UserActivityRanking.metric == metric,
        UserActivityRanking.range == range,
        User.is_active.is_(True),
    )

    total_count = (
        await db.execute(
            select(func.count())
            .select_from(UserActivityRanking)
            .join(User, User.id == UserActivityRanking.user_id)
            .where(*base_filters)
        )
    ).scalar_one()

    offset = (page - 1) * page_size
    page_result = await db.execute(
        select(
            UserActivityRanking,
            User.username,
            User.avatar_url,
            OAuthAccount.provider_account_id,
            OAuthAccount.discord_avatar_hash,
            OAuthAccount.discord_avatar_url,
        )
        .join(User, User.id == UserActivityRanking.user_id)
        .outerjoin(
            OAuthAccount,
            and_(OAuthAccount.user_id == User.id, OAuthAccount.provider == "discord"),
        )
        .where(*base_filters)
        .order_by(UserActivityRanking.rank.asc())
        .offset(offset)
        .limit(page_size)
    )
    rows = page_result.all()

    items = [
        RankingItem(
            rank=ranking.rank,
            user_id=str(ranking.user_id),
            username=username,
            avatar_url=avatar_url or build_discord_avatar_url(discord_id or "", discord_avatar_hash) or discord_avatar_url,
            value=ranking.value,
        )
        for ranking, username, avatar_url, discord_id, discord_avatar_hash, discord_avatar_url in rows
    ]

    # Deliberately not filtered on `current_user.is_active`: this is the caller
    # looking up their own row, not a public listing. In practice a deactivated
    # user has no snapshot row (the rebuild excludes them), so this resolves to
    # None on its own once the next rebuild runs.
    my_rank: MyRank | None = None
    if current_user is not None:
        my_row = (
            await db.execute(
                select(UserActivityRanking.rank, UserActivityRanking.value).where(
                    UserActivityRanking.range == range,
                    UserActivityRanking.metric == metric,
                    UserActivityRanking.user_id == current_user.id,
                )
            )
        ).first()
        if my_row is not None:
            my_rank = MyRank(rank=my_row.rank, value=my_row.value)

    return ActivityRankingResponse(
        range=range,
        metric=metric,
        window_start=window_start.isoformat() if window_start else None,
        window_end=window_end.isoformat() if window_end else None,
        computed_at=computed_at.isoformat() if computed_at else None,
        items=items,
        my_rank=my_rank,
        total_count=total_count,
        page=page,
    )
