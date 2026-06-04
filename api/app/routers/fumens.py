"""Fumen (BMS chart) list and detail endpoints."""
from __future__ import annotations

import logging
import re
import uuid as _uuid
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, case, exists, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    get_current_admin,
    get_current_user,
    get_current_user_optional,
)
from app.models.fumen import (
    Fumen,
    FumenPlayPopularity,
    FumenPopularityWindow,
    FumenTableEntry,
    UserFumenTag,
)
from app.models.score import UserScore
from app.models.user import User
from app.services.fumen_user_scores import (
    TableFumenScore,
    UserTagRead,
    fetch_user_score_map,
    fetch_user_tag_map,
)
from app.services.level_display_preferences import (
    resolve_non_regular_hidden_levels,
    resolve_visible_table_ids,
)
from app.utils.numeric_filter import numeric_clause, parse_length_to_ms
from app.utils.score_enums import (
    ARRANGEMENT_KANJI_REV,
    BEA_ARRANGEMENT_NAMES,
    CLEAR_TYPE_VALUES,
    LR2_ARRANGEMENT_NAMES,
    RANK_VALUES,
)
from app.utils.text_normalization import normalize_display_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fumens", tags=["fumens"])


class FumenRead(BaseModel):
    fumen_id: _uuid.UUID
    md5: str | None
    sha256: str | None
    title: str | None
    artist: str | None
    bpm_min: float | None = None
    bpm_max: float | None = None
    bpm_main: float | None = None
    notes_total: int | None = None
    total: int | None = None
    notes_n: int | None = None
    notes_ln: int | None = None
    notes_s: int | None = None
    notes_ls: int | None = None
    length: int | None = None
    youtube_url: str | None
    file_url: str | None
    file_url_diff: str | None
    table_entries: list | None
    played_user_count: int = 0
    total_play_count: int = 0
    model_config = ConfigDict(from_attributes=True)


FumenSearchField = Literal[
    "title_artist", "title", "artist", "level",
    "bpm", "notes", "length",
    "clear", "bp", "rate", "rank", "score", "plays", "option", "env",
]
FumenSearchMode = Literal["basic", "regex"]

_SCORE_FIELDS = frozenset({"clear", "bp", "rate", "rank", "score", "plays", "option", "env"})
_AGG_SCORE_FIELDS = frozenset({"clear", "bp", "rate", "rank", "score", "plays"})
_SCORE_SORT_FIELDS = frozenset({"clear", "bp", "rate", "rank", "score"})
_TEXT_SEARCH_FIELDS = frozenset({"title_artist", "title", "artist"})


class FumenListItem(FumenRead):
    """FumenRead + per-user enrichment."""

    user_score: TableFumenScore | None = None
    user_tags: list[UserTagRead] = []


class FumenListResponse(BaseModel):
    items: list[FumenListItem]
    total: int
    page: int
    limit: int


class PopularFumenRead(BaseModel):
    rank: int
    fumen_id: _uuid.UUID
    title: str | None
    artist: str | None
    sha256: str | None
    md5: str | None
    played_user_count: int
    play_count: int


class PopularFumensResponse(BaseModel):
    as_of: str | None
    items: list[PopularFumenRead]


def _entry_visible(table_id: _uuid.UUID, visible_table_ids: set[_uuid.UUID] | None) -> bool:
    """Return whether a table entry should be included for the current viewer."""
    return visible_table_ids is None or table_id in visible_table_ids


async def _table_entries_map(
    db: AsyncSession,
    fumen_ids: list[_uuid.UUID],
    visible_table_ids: set[_uuid.UUID] | None = None,
    non_regular_hidden: dict[_uuid.UUID, set[str]] | None = None,
) -> dict[_uuid.UUID, list[dict[str, str]]]:
    """Return legacy-shaped table_entries arrays for API compatibility."""
    if not fumen_ids:
        return {}
    if visible_table_ids is not None and not visible_table_ids:
        return {fid: [] for fid in fumen_ids}
    query = (
        select(FumenTableEntry.fumen_id, FumenTableEntry.table_id, FumenTableEntry.level)
        .where(FumenTableEntry.fumen_id.in_(fumen_ids))
    )
    if visible_table_ids is not None:
        query = query.where(FumenTableEntry.table_id.in_(visible_table_ids))
    result = await db.execute(query)
    out: dict[_uuid.UUID, list[dict[str, str]]] = {fid: [] for fid in fumen_ids}
    for fumen_id, table_id, level in result.all():
        if non_regular_hidden and level in non_regular_hidden.get(table_id, set()):
            continue
        out.setdefault(fumen_id, []).append({"table_id": str(table_id), "level": level})
    return out


async def _fumen_read(
    db: AsyncSession,
    fumen: Fumen,
    visible_table_ids: set[_uuid.UUID] | None = None,
    non_regular_hidden: dict[_uuid.UUID, set[str]] | None = None,
) -> FumenRead:
    entries = await _table_entries_map(db, [fumen.fumen_id], visible_table_ids, non_regular_hidden)
    return FumenRead(
        fumen_id=fumen.fumen_id,
        md5=fumen.md5,
        sha256=fumen.sha256,
        title=fumen.title,
        artist=fumen.artist,
        bpm_min=fumen.bpm_min,
        bpm_max=fumen.bpm_max,
        bpm_main=fumen.bpm_main,
        notes_total=fumen.notes_total,
        total=fumen.total,
        notes_n=fumen.notes_n,
        notes_ln=fumen.notes_ln,
        notes_s=fumen.notes_s,
        notes_ls=fumen.notes_ls,
        length=fumen.length,
        youtube_url=fumen.youtube_url,
        file_url=fumen.file_url,
        file_url_diff=fumen.file_url_diff,
        table_entries=entries.get(fumen.fumen_id, []),
    )


def _build_score_agg_subquery(user_id: _uuid.UUID) -> Any:
    display_clear = case(
        (
            and_(
                UserScore.clear_type == 9,
                UserScore.exscore == 0,
            ),
            7,
        ),
        (
            and_(
                UserScore.clear_type == 9,
                UserScore.rate.isnot(None),
                UserScore.rate != 100.0,
            ),
            8,
        ),
        else_=UserScore.clear_type,
    )
    rank_order = case(
        {"MAX": 10, "AAA": 9, "AA": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2},
        value=UserScore.rank,
        else_=1,
    )
    score_join_cond = and_(
        UserScore.user_id == user_id,
        UserScore.fumen_id == Fumen.fumen_id,
    )
    return (
        select(
            Fumen.fumen_id.label("fumen_id"),
            func.max(display_clear).label("best_clear_type"),
            func.max(UserScore.exscore).label("best_exscore"),
            func.min(UserScore.min_bp).label("best_min_bp"),
            func.max(UserScore.rate).label("best_rate"),
            func.max(rank_order).label("rank_order"),
            func.sum(UserScore.play_count).label("total_plays"),
        )
        .select_from(Fumen)
        .outerjoin(UserScore, score_join_cond)
        .group_by(Fumen.fumen_id)
        .subquery("score_agg")
    )


def _score_agg_join_cond(score_agg: Any) -> Any:
    return Fumen.fumen_id == score_agg.c.fumen_id


def _score_exists_cond(user_id: _uuid.UUID, cond: Any) -> Any:
    """EXISTS subquery: fumens that have a user_score row matching `cond`."""
    return exists(
        select(literal(1)).select_from(UserScore).where(
            UserScore.user_id == user_id,
            UserScore.fumen_id == Fumen.fumen_id,
            cond,
        )
    )


def _build_field_condition(
    field: str, q: str, user: User | None, score_agg: Any | None = None
) -> Any | None:
    """Return SQLAlchemy WHERE clause for the given search field and query string.

    Returns None on parse failure — caller treats it as empty result.
    Raises HTTPException(400) if score field is requested without auth (caller checks first).
    """
    if field == "title_artist":
        return or_(Fumen.title.ilike(f"%{q}%"), Fumen.artist.ilike(f"%{q}%"))
    if field == "title":
        return Fumen.title.ilike(f"%{q}%")
    if field == "artist":
        return Fumen.artist.ilike(f"%{q}%")
    if field == "level":
        level_q = re.sub(r"^[^\w\d.]+", "", q)
        return exists(
            select(literal(1)).select_from(FumenTableEntry).where(
                FumenTableEntry.fumen_id == Fumen.fumen_id,
                FumenTableEntry.level == level_q,
            )
        )
    if field == "bpm":
        return numeric_clause(Fumen.bpm_main, q)
    if field == "notes":
        return numeric_clause(Fumen.notes_total, q)
    if field == "length":
        return numeric_clause(Fumen.length, parse_length_to_ms(q))

    # Score fields — user must be authenticated (caller validates before calling)
    if user is None:
        return None

    if field == "clear":
        ct = CLEAR_TYPE_VALUES.get(q.upper())
        if ct is None:
            return None
        if score_agg is not None:
            return score_agg.c.best_clear_type == ct
        return _score_exists_cond(user.id, UserScore.clear_type == ct)

    if field == "bp":
        cond = numeric_clause(score_agg.c.best_min_bp if score_agg is not None else UserScore.min_bp, q)
        if score_agg is not None:
            return cond
        return _score_exists_cond(user.id, cond) if cond is not None else None

    if field == "rate":
        cond = numeric_clause(score_agg.c.best_rate if score_agg is not None else UserScore.rate, q)
        if score_agg is not None:
            return cond
        return _score_exists_cond(user.id, cond) if cond is not None else None

    if field == "rank":
        if q.upper() not in RANK_VALUES:
            return None
        if score_agg is not None:
            rank_value = {"MAX": 10, "AAA": 9, "AA": 8, "A": 7, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2}[q.upper()]
            return score_agg.c.rank_order == rank_value
        return _score_exists_cond(user.id, UserScore.rank == q.upper())

    if field == "score":
        cond = numeric_clause(score_agg.c.best_exscore if score_agg is not None else UserScore.exscore, q)
        if score_agg is not None:
            return cond
        return _score_exists_cond(user.id, cond) if cond is not None else None

    if field == "plays":
        cond = numeric_clause(score_agg.c.total_plays if score_agg is not None else UserScore.play_count, q)
        if score_agg is not None:
            return cond
        return _score_exists_cond(user.id, cond) if cond is not None else None

    if field == "env":
        client_map = {"LR": "lr2", "BR": "beatoraja"}
        ct = client_map.get(q.upper())
        if ct is None:
            return None
        return _score_exists_cond(user.id, UserScore.client_type == ct)

    if field == "option":
        arr_name = ARRANGEMENT_KANJI_REV.get(q)
        if arr_name is None:
            return None
        sub_conds = []
        if arr_name in LR2_ARRANGEMENT_NAMES:
            idx = LR2_ARRANGEMENT_NAMES.index(arr_name)
            sub_conds.append(and_(
                UserScore.client_type == "lr2",
                sa.cast(UserScore.options["op_best"].astext, sa.Integer).between(idx * 10, idx * 10 + 9),
            ))
        if arr_name in BEA_ARRANGEMENT_NAMES:
            idx = BEA_ARRANGEMENT_NAMES.index(arr_name)
            sub_conds.append(and_(
                UserScore.client_type == "beatoraja",
                sa.cast(UserScore.options["option"].astext, sa.Integer) == idx,
            ))
        if not sub_conds:
            return None
        return _score_exists_cond(user.id, or_(*sub_conds))

    return None


def _escape_regex_literal(value: str) -> str:
    """Return a regex-safe literal for server-generated search patterns."""
    return re.escape(value)


def _word_boundary_regex(q: str) -> str:
    """Build a PostgreSQL regex matching q near non-alphanumeric boundaries."""
    escaped = _escape_regex_literal(q)
    return rf"(^|[^[:alnum:]]){escaped}([^[:alnum:]]|$)"


def _normalize_search_text(value: str) -> str:
    """Strip non-alphanumerics and lowercase to mirror the SQL norm expression."""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _norm_expr(col: Any) -> Any:
    """SQL normalized expression matching `_normalize_search_text`."""
    return func.regexp_replace(func.lower(func.coalesce(col, "")), "[^[:alnum:]]+", "", "g")


def _like_escape(value: str) -> str:
    """Escape LIKE metacharacters in raw query text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _column_bucket(col: Any, q_lower: str, q_norm: str, offset: int) -> Any:
    """Relevance bucket for one column; lower is better."""
    raw = func.lower(func.coalesce(col, ""))
    norm = _norm_expr(col)
    boundary = _word_boundary_regex(q_lower)
    prefix = _like_escape(q_lower) + "%"
    return case(
        (raw == q_lower, offset + 0),
        (raw.op("~")(boundary), offset + 1),
        (raw.like(prefix, escape="\\"), offset + 2),
        (norm == q_norm, offset + 3),
        (norm.like(q_norm + "%"), offset + 4),
        else_=99,
    )


def _basic_text_match_bucket(field: str, q: str) -> Any:
    q_lower = q.lower()
    q_norm = _normalize_search_text(q)
    if field == "title":
        return _column_bucket(Fumen.title, q_lower, q_norm, 0)
    if field == "artist":
        return _column_bucket(Fumen.artist, q_lower, q_norm, 0)
    return func.least(
        _column_bucket(Fumen.title, q_lower, q_norm, 0),
        _column_bucket(Fumen.artist, q_lower, q_norm, 10),
    )


def _basic_text_filter(field: str, q: str) -> Any:
    """Sargable normalized candidate predicate for basic text search."""
    q_norm = _normalize_search_text(q)
    if not q_norm:
        return sa.false()
    contains = "%" + q_norm + "%"
    title_hit = _norm_expr(Fumen.title).like(contains)
    artist_hit = _norm_expr(Fumen.artist).like(contains)
    if field == "title":
        return title_hit
    if field == "artist":
        return artist_hit
    return or_(title_hit, artist_hit)


def _basic_text_precision_filter(field: str, q: str) -> Any:
    """Exclude candidates that only matched as normalized infix."""
    return _basic_text_match_bucket(field, q) < 99


def _regex_text_condition(field: str, q: str) -> Any:
    if field not in _TEXT_SEARCH_FIELDS:
        raise HTTPException(status_code=400, detail="Regex search is only available for title and artist fields")
    if len(q) > 120:
        raise HTTPException(status_code=400, detail="Regex query is too long")
    if not q.strip():
        raise HTTPException(status_code=400, detail="Regex query is empty")
    q_lower = q.lower()
    title = func.lower(func.coalesce(Fumen.title, ""))
    artist = func.lower(func.coalesce(Fumen.artist, ""))
    if field == "title":
        return title.op("~")(q_lower)
    if field == "artist":
        return artist.op("~")(q_lower)
    return or_(title.op("~")(q_lower), artist.op("~")(q_lower))


def _db_error_sqlstate(exc: DBAPIError) -> str | None:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _dummy_title_bucket() -> Any:
    stripped_title = func.btrim(Fumen.title)
    is_dummy_title = or_(
        stripped_title == ">> ??? <<",
        stripped_title.op("~")(r"^[가-힣]"),
    )
    return case((is_dummy_title, 1), else_=0).asc()


def _build_sort_cols(sort_by: str, sort_dir: str, score_agg: Any | None) -> list[Any]:
    asc_dir = sort_dir == "asc"
    if sort_by == "players":
        col = FumenPlayPopularity.played_user_count
        return [col.asc().nullslast() if asc_dir else col.desc().nullslast()]
    if sort_by == "plays":
        col = FumenPlayPopularity.total_play_count
        return [col.asc().nullslast() if asc_dir else col.desc().nullslast()]

    fumen_col_map: dict[str, Any] = {
        "title": Fumen.title,
        "artist": Fumen.artist,
        "title_artist": Fumen.title,
        "bpm": Fumen.bpm_main,
        "notes": Fumen.notes_total,
        "length": Fumen.length,
    }
    if sort_by in fumen_col_map:
        col = fumen_col_map[sort_by]
        sort_col = col.asc().nullslast() if asc_dir else col.desc().nullslast()
        if sort_by in {"title", "artist", "title_artist"}:
            return [_dummy_title_bucket(), sort_col]
        return [sort_col]

    if sort_by == "level":
        level_expr = (
            select(func.min(FumenTableEntry.level))
            .where(FumenTableEntry.fumen_id == Fumen.fumen_id)
            .scalar_subquery()
        )
        return [level_expr.asc().nullslast() if asc_dir else level_expr.desc().nullslast()]

    if score_agg is not None:
        score_col_map: dict[str, Any] = {
            "clear": score_agg.c.best_clear_type,
            "score": score_agg.c.best_exscore,
            "bp": score_agg.c.best_min_bp,
            "rate": score_agg.c.best_rate,
            "rank": score_agg.c.rank_order,
            "plays": score_agg.c.total_plays,
        }
        if sort_by in score_col_map:
            col = score_col_map[sort_by]
            return [col.asc().nullslast() if asc_dir else col.desc().nullslast()]

    return [_dummy_title_bucket(), Fumen.title.asc().nullslast()]


def _build_text_search_sort_cols(
    field: str,
    q: str | None,
    sort_by: str,
    sort_dir: str,
    score_agg: Any | None,
) -> list[Any]:
    """Return text-search ordering with popularity as the last semantic tiebreaker."""
    cols: list[Any] = []
    if q is not None:
        cols.append(_basic_text_match_bucket(field, q).asc())
    cols.extend(_build_sort_cols(sort_by, sort_dir, score_agg))
    cols.append(FumenPlayPopularity.played_user_count.desc().nullslast())
    return cols


@router.get("/", response_model=FumenListResponse)
async def list_fumens(
    field: FumenSearchField = Query("title_artist"),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    sort_by: str = Query("title"),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    search_mode: FumenSearchMode = Query("basic"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> FumenListResponse:
    """List all fumens with optional filtering, server-side sorting, and pagination.

    Authentication is required when `field` or `sort_by` is a score-based field
    (clear, bp, rate, rank, score, plays, option, env).

    **Breaking change** (2026-04-26): replaced the old `title`/`artist`/`offset`
    params with `field`/`q`/`page`/`sort_by`/`sort_dir`.
    """
    q_clean = q.strip() if q else ""

    if search_mode == "regex" and field not in _TEXT_SEARCH_FIELDS:
        raise HTTPException(status_code=400, detail="Regex search is only available for title and artist fields")
    if q_clean and field in _SCORE_FIELDS and not current_user:
        raise HTTPException(status_code=400, detail="Authentication required for score field search")
    if sort_by in _SCORE_SORT_FIELDS and not current_user:
        raise HTTPException(status_code=400, detail="Authentication required for score field sort")

    # Optional score aggregation subquery (for sorting/filtering by score fields)
    score_agg = None
    if current_user and (sort_by in _SCORE_SORT_FIELDS or (q_clean and field in _AGG_SCORE_FIELDS)):
        score_agg = _build_score_agg_subquery(current_user.id)

    base = select(
        Fumen,
        func.coalesce(FumenPlayPopularity.played_user_count, 0).label("played_user_count"),
        func.coalesce(FumenPlayPopularity.total_play_count, 0).label("total_play_count"),
    ).outerjoin(FumenPlayPopularity, Fumen.fumen_id == FumenPlayPopularity.fumen_id)
    count_q = select(func.count()).select_from(Fumen)

    # LEFT JOIN score_agg for sort/filter — one aggregate row per fumen, so pagination stays stable.
    if score_agg is not None:
        join_cond = _score_agg_join_cond(score_agg)
        base = base.outerjoin(score_agg, join_cond)
        count_q = count_q.outerjoin(score_agg, join_cond)

    # WHERE
    if q_clean and field in _TEXT_SEARCH_FIELDS and search_mode == "basic":
        candidate_filter = _basic_text_filter(field, q_clean)
        precision_filter = _basic_text_precision_filter(field, q_clean)
        base = base.where(candidate_filter, precision_filter)
        count_q = count_q.where(candidate_filter, precision_filter)
    elif q_clean and field in _TEXT_SEARCH_FIELDS and search_mode == "regex":
        regex_filter = _regex_text_condition(field, q_clean)
        base = base.where(regex_filter)
        count_q = count_q.where(regex_filter)
    elif q_clean:
        where_cond = _build_field_condition(field, q_clean, current_user, score_agg)
        if where_cond is None:
            return FumenListResponse(items=[], total=0, page=page, limit=limit)
        base = base.where(where_cond)
        count_q = count_q.where(where_cond)

    if search_mode == "regex" and q_clean:
        await db.execute(sa.text("SET LOCAL statement_timeout = '3000'"))

    try:
        total = (await db.execute(count_q)).scalar() or 0
    except DBAPIError as exc:
        await db.rollback()
        sqlstate = _db_error_sqlstate(exc)
        if sqlstate == "2201B":
            raise HTTPException(status_code=400, detail="Invalid regular expression") from exc
        if sqlstate == "57014":
            raise HTTPException(status_code=400, detail="Regex search timed out; narrow the pattern") from exc
        raise

    # ORDER BY + tie-breaker
    if q_clean and field in _TEXT_SEARCH_FIELDS and search_mode == "basic":
        base = base.order_by(
            *_build_text_search_sort_cols(field, q_clean, sort_by, sort_dir, score_agg),
            Fumen.sha256.asc().nullslast(),
            Fumen.md5.asc().nullslast(),
        )
    elif q_clean and field in _TEXT_SEARCH_FIELDS and search_mode == "regex":
        base = base.order_by(
            *_build_text_search_sort_cols(field, None, sort_by, sort_dir, score_agg),
            Fumen.sha256.asc().nullslast(),
            Fumen.md5.asc().nullslast(),
        )
    else:
        base = base.order_by(
            *_build_sort_cols(sort_by, sort_dir, score_agg),
            Fumen.sha256.asc().nullslast(),
            Fumen.md5.asc().nullslast(),
        )

    base = base.limit(limit).offset((page - 1) * limit)
    try:
        rows = list((await db.execute(base)).all())
    except DBAPIError as exc:
        await db.rollback()
        sqlstate = _db_error_sqlstate(exc)
        if sqlstate == "2201B":
            raise HTTPException(status_code=400, detail="Invalid regular expression") from exc
        if sqlstate == "57014":
            raise HTTPException(status_code=400, detail="Regex search timed out; narrow the pattern") from exc
        raise
    fumens = [row[0] for row in rows]
    popularity_by_id = {
        row[0].fumen_id: (int(row.played_user_count or 0), int(row.total_play_count or 0))
        for row in rows
    }

    score_map: dict = {}
    tag_map: dict = {}
    if current_user and fumens:
        score_map = await fetch_user_score_map(db, current_user.id, fumens)
        tag_map = await fetch_user_tag_map(db, current_user.id, fumens)

    visible_table_ids = await resolve_visible_table_ids(db, current_user)
    non_regular_hidden = await resolve_non_regular_hidden_levels(db, current_user)
    entries_map = await _table_entries_map(db, [f.fumen_id for f in fumens], visible_table_ids, non_regular_hidden)
    items = []
    for f in fumens:
        played_user_count, total_play_count = popularity_by_id.get(f.fumen_id, (0, 0))
        item = FumenListItem(
            fumen_id=f.fumen_id,
            md5=f.md5,
            sha256=f.sha256,
            title=f.title,
            artist=f.artist,
            bpm_min=f.bpm_min,
            bpm_max=f.bpm_max,
            bpm_main=f.bpm_main,
            notes_total=f.notes_total,
            total=f.total,
            notes_n=f.notes_n,
            notes_ln=f.notes_ln,
            notes_s=f.notes_s,
            notes_ls=f.notes_ls,
            length=f.length,
            youtube_url=f.youtube_url,
            file_url=f.file_url,
            file_url_diff=f.file_url_diff,
            table_entries=entries_map.get(f.fumen_id, []),
            played_user_count=played_user_count,
            total_play_count=total_play_count,
            user_score=score_map.get(f.fumen_id),
            user_tags=tag_map.get(f.fumen_id, []),
        )
        items.append(item)

    return FumenListResponse(items=items, total=total, page=page, limit=limit)


# GET /my-tags must be registered before /{hash_value} to avoid path capture.
class TagRead(BaseModel):
    id: str
    tag: str

    model_config = ConfigDict(from_attributes=True)


class TagCreateRequest(BaseModel):
    tag: str


@router.get("/my-tags", response_model=list[str])
async def get_my_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Get distinct tags used by the current user (for autocomplete)."""
    result = await db.execute(
        select(UserFumenTag.tag)
        .where(UserFumenTag.user_id == current_user.id)
        .distinct()
        .order_by(UserFumenTag.tag)
    )
    return [row[0] for row in result.all()]


@router.get("/popular", response_model=PopularFumensResponse)
async def get_popular_fumens(
    range: str = Query("weekly"),
    limit: int = Query(10, ge=1, le=50),
    sort_by: str = Query("players"),
    db: AsyncSession = Depends(get_db),
) -> PopularFumensResponse:
    """Return cached popular fumens for weekly, monthly, or all-time ranges."""
    if range not in {"weekly", "monthly", "all_time"}:
        raise HTTPException(status_code=400, detail="Unknown popularity range")
    if sort_by not in {"players", "plays"}:
        raise HTTPException(status_code=400, detail="sort_by must be 'players' or 'plays'")

    items: list[PopularFumenRead] = []
    as_of_value = None
    if range == "all_time":
        as_of_value = (
            await db.execute(select(func.max(FumenPlayPopularity.updated_at)))
        ).scalar_one_or_none()
        primary_order = (
            FumenPlayPopularity.played_user_count.desc()
            if sort_by == "players"
            else FumenPlayPopularity.total_play_count.desc()
        )
        secondary_order = (
            FumenPlayPopularity.total_play_count.desc()
            if sort_by == "players"
            else FumenPlayPopularity.played_user_count.desc()
        )
        rows = (
            await db.execute(
                select(Fumen, FumenPlayPopularity)
                .join(FumenPlayPopularity, Fumen.fumen_id == FumenPlayPopularity.fumen_id)
                .order_by(primary_order, secondary_order, Fumen.fumen_id)
                .limit(limit)
            )
        ).all()
        for index, row in enumerate(rows, start=1):
            fumen, popularity = row
            items.append(
                PopularFumenRead(
                    rank=index,
                    fumen_id=fumen.fumen_id,
                    title=fumen.title,
                    artist=fumen.artist,
                    sha256=fumen.sha256,
                    md5=fumen.md5,
                    played_user_count=popularity.played_user_count,
                    play_count=popularity.total_play_count,
                )
            )
    else:
        as_of_value = (
            await db.execute(
                select(func.max(FumenPopularityWindow.computed_at)).where(
                    FumenPopularityWindow.window == range
                )
            )
        ).scalar_one_or_none()
        primary_order = (
            FumenPopularityWindow.played_user_count.desc()
            if sort_by == "players"
            else FumenPopularityWindow.play_count.desc()
        )
        secondary_order = (
            FumenPopularityWindow.play_count.desc()
            if sort_by == "players"
            else FumenPopularityWindow.played_user_count.desc()
        )
        rows = (
            await db.execute(
                select(Fumen, FumenPopularityWindow)
                .join(FumenPopularityWindow, Fumen.fumen_id == FumenPopularityWindow.fumen_id)
                .where(FumenPopularityWindow.window == range)
                .order_by(primary_order, secondary_order, Fumen.fumen_id)
                .limit(limit)
            )
        ).all()
        for index, row in enumerate(rows, start=1):
            fumen, popularity = row
            items.append(
                PopularFumenRead(
                    rank=index,
                    fumen_id=fumen.fumen_id,
                    title=fumen.title,
                    artist=fumen.artist,
                    sha256=fumen.sha256,
                    md5=fumen.md5,
                    played_user_count=popularity.played_user_count,
                    play_count=popularity.play_count,
                )
            )

    return PopularFumensResponse(
        as_of=as_of_value.isoformat() if as_of_value is not None else None,
        items=items,
    )


@router.get("/by-hash/{hash_value}", response_model=FumenRead)
async def get_fumen_by_legacy_hash(
    hash_value: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> FumenRead:
    """Resolve a legacy SHA256/MD5 hash URL to the registered fumen."""
    if len(hash_value) not in {32, 64}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")
    fumen = await _get_fumen_by_hash(hash_value, db)
    visible_table_ids = await resolve_visible_table_ids(db, current_user)
    non_regular_hidden = await resolve_non_regular_hidden_levels(db, current_user)
    return await _fumen_read(db, fumen, visible_table_ids, non_regular_hidden)


# ---------------------------------------------------------------------------
# Fumen detail sync — route registrations that must come before /{hash_value}
# ---------------------------------------------------------------------------

# NOTE: /known-hashes and /sync-details are registered here (before /{hash_value})
# so that FastAPI matches them before the catch-all path parameter route.

class KnownHashesResponse(BaseModel):
    """Response for GET /fumens/known-hashes."""

    complete_sha256: list[str]
    complete_md5: list[str]
    partial_sha256: list[str]
    partial_md5: list[str]
    keymode_missing_md5: list[str] = []


# Detail columns — NULL이 하나라도 있으면 "partial"
# NOTE: keymode is intentionally excluded here — it is tracked separately via
# keymode_missing_md5 so that LR2 clients can do a targeted backfill without
# causing all existing fumens to become "partial".
_DETAIL_COLS = (
    "bpm_min", "bpm_max", "bpm_main", "notes_total", "total",
    "notes_n", "notes_ln", "notes_s", "notes_ls", "length",
)

# Columns fetched for pre-fetch (hash keys + fillable detail fields only, no table_entries JSONB)
_PREFETCH_COLS = (
    Fumen.sha256, Fumen.md5, Fumen.title, Fumen.artist,
    Fumen.bpm_min, Fumen.bpm_max, Fumen.bpm_main,
    Fumen.notes_total, Fumen.total,
    Fumen.notes_n, Fumen.notes_ln, Fumen.notes_s, Fumen.notes_ls,
    Fumen.length,
    Fumen.keymode,
)

# All fillable column names (title/artist + detail + keymode)
# keymode is added explicitly here (not via _DETAIL_COLS) so Beatoraja can fill it
# while it stays out of the complete/partial completeness check.
_FILLABLE_COL_NAMES = ("title", "artist") + _DETAIL_COLS + ("keymode",)


@router.get("/known-hashes", response_model=KnownHashesResponse)
async def get_known_hashes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnownHashesResponse:
    """Return sets of known fumen hashes, split by detail completeness.

    - complete: all detail columns are non-NULL → client can skip entirely.
    - partial: at least one detail column is NULL → Beatoraja items should be sent for fill.
    - keymode_missing_md5: md5 values of fumens with NULL keymode (separate from partial/complete).
    """
    detail_all_filled = sa.and_(
        *[getattr(Fumen, col).isnot(None) for col in _DETAIL_COLS],
        Fumen.title.isnot(None),
        Fumen.artist.isnot(None),
        Fumen.sha256.isnot(None), Fumen.sha256 != "",
        Fumen.md5.isnot(None), Fumen.md5 != "",
    )

    result = await db.execute(
        select(
            Fumen.sha256,
            Fumen.md5,
            Fumen.keymode,
            detail_all_filled.label("is_complete"),
        )
    )
    rows = result.all()

    complete_sha256: list[str] = []
    complete_md5: list[str] = []
    partial_sha256: list[str] = []
    partial_md5: list[str] = []
    keymode_missing_md5: list[str] = []

    for row in rows:
        if row.is_complete:
            if row.sha256:
                complete_sha256.append(row.sha256)
            if row.md5:
                complete_md5.append(row.md5)
        else:
            if row.sha256:
                partial_sha256.append(row.sha256)
            if row.md5:
                partial_md5.append(row.md5)
        # keymode_missing_md5 is separate from partial/complete — even a "complete"
        # fumen may have NULL keymode (added after the fumen was first synced).
        if row.keymode is None and row.md5:
            keymode_missing_md5.append(row.md5)

    return KnownHashesResponse(
        complete_sha256=complete_sha256,
        complete_md5=complete_md5,
        partial_sha256=partial_sha256,
        partial_md5=partial_md5,
        keymode_missing_md5=keymode_missing_md5,
    )


class FumenDetailItem(BaseModel):
    """A single fumen detail item from the client's local song DB."""

    md5: str | None = None
    sha256: str | None = None
    title: str | None = None
    artist: str | None = None
    bpm_min: float | None = None
    bpm_max: float | None = None
    bpm_main: float | None = None
    notes_total: int | None = None
    total: int | None = None
    notes_n: int | None = None
    notes_ln: int | None = None
    notes_s: int | None = None
    notes_ls: int | None = None
    length: int | None = None
    keymode: int | None = None
    client_type: str  # "beatoraja" or "lr2"


class FumenDetailSyncRequest(BaseModel):
    """Request body for POST /fumens/sync-details."""

    items: list[FumenDetailItem]
    supplemented_md5s: list[str] = []    # 이번 세션에서 supplement로 sha256 채워진 fumen의 md5
    supplemented_sha256s: list[str] = [] # 이번 세션에서 supplement로 md5 채워진 fumen의 sha256


class FumenDetailSyncResponse(BaseModel):
    """Response body for POST /fumens/sync-details."""

    inserted: int
    enriched: int
    skipped: int
    overlap_count: int = 0  # enriched 중 supplemented와 겹치는 수 (double-count 보정용)


@router.post("/sync-details", response_model=FumenDetailSyncResponse)
async def sync_fumen_details(
    body: FumenDetailSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FumenDetailSyncResponse:
    """Sync fumen detail data from client's local song DBs.

    Accepts fumen metadata items (Beatoraja first, then LR2).
    - Beatoraja items: fill NULL detail fields on existing fumens, INSERT new ones.
    - LR2 items: fill NULL keymode on existing fumens; INSERT if not in DB.
    All new inserts record added_by_user_id.

    NOTE: Client should call GET /fumens/known-hashes first and only send
    items that are new or have incomplete details on the server.
    LR2 items should additionally only be resent for md5s listed in keymode_missing_md5.
    """
    if not body.items:
        return FumenDetailSyncResponse(inserted=0, enriched=0, skipped=0)

    supplemented_md5_set = set(body.supplemented_md5s)
    supplemented_sha256_set = set(body.supplemented_sha256s)
    overlap_count = 0

    # ── Step 1: Bulk pre-fetch — detail columns only (no table_entries JSONB) ──
    all_sha256s = [it.sha256.lower() for it in body.items if it.sha256]
    all_md5s = [it.md5.lower() for it in body.items if it.md5]

    existing_by_sha256: dict[str, Any] = {}
    if all_sha256s:
        result = await db.execute(
            select(*_PREFETCH_COLS).where(Fumen.sha256.in_(all_sha256s))
        )
        for row in result.all():
            existing_by_sha256[row.sha256] = row

    existing_by_md5: dict[str, Any] = {}
    if all_md5s:
        result = await db.execute(
            select(*_PREFETCH_COLS).where(
                Fumen.md5.in_(all_md5s),
                # No sha256 IS NULL filter — a fumen with {sha256=X, md5=Y} must also be
                # found when querying by md5=Y, to avoid duplicate inserts.
            )
        )
        for row in result.all():
            existing_by_md5[row.md5] = row

    existing_md5_set = set(existing_by_md5.keys())

    skipped_count = 0
    # Track ALL processed fumens (insert/update/skip) by hash key.
    # A fumen is the same if sha256 OR md5 matches. Both hashes are added when known.
    seen_hashes: set[str] = set()
    new_rows: list[dict] = []

    # Track newly inserted keys so LR2 items can skip them
    inserted_sha256s: set[str] = set()
    inserted_md5s: set[str] = set()

    # Collect updates: group by NULL field pattern for bulk CASE WHEN
    # Key: frozenset of column names to update
    # Value: list of (hash_key_type, hash_value, {col: new_val})
    update_groups: dict[frozenset, list[tuple[str, str, dict]]] = {}

    # ── Step 2: Process items in order (Beatoraja first, then LR2) ──
    for item in body.items:
        sha256 = item.sha256.lower() if item.sha256 else None
        md5 = item.md5.lower() if item.md5 else None
        if not sha256 and not md5:
            # No valid hash at all — cannot identify fumen, don't count in skipped
            continue

        existing = None
        hash_key_type: str = ""
        hash_key_val: str = ""
        if sha256 and sha256 in existing_by_sha256:
            existing = existing_by_sha256[sha256]
            hash_key_type, hash_key_val = "sha256", sha256
        elif md5 and md5 in existing_md5_set:
            existing = existing_by_md5.get(md5)
            hash_key_type, hash_key_val = "md5", md5
        elif sha256 and sha256 in inserted_sha256s:
            # Intra-batch dedup: already inserted by Beatoraja in this request — not a
            # pre-existing DB row, so don't count as skipped.
            continue
        elif md5 and md5 in inserted_md5s:
            continue

        is_lr2 = item.client_type == "lr2"

        # Build all hash keys (both sha256 and md5 if present) for dedup tracking.
        # A fumen is the same if it matches on sha256 OR md5.
        dedup_keys = []
        if sha256:
            dedup_keys.append(f"sha256:{sha256}")
        if md5:
            dedup_keys.append(f"md5:{md5}")

        # Check if this fumen was already processed in this batch (via another hash or client)
        already_seen = any(k in seen_hashes for k in dedup_keys)

        if existing is not None:
            if is_lr2:
                # LR2 existing fumen: only fill keymode when server value is NULL
                if existing.keymode is None and item.keymode is not None:
                    cols_key = frozenset({"keymode"})
                    update_groups.setdefault(cols_key, []).append(
                        (hash_key_type, hash_key_val, {"keymode": item.keymode})
                    )
                    # Overlap check: fumen was hash-supplemented this session and now also
                    # gets keymode filled → double-count correction needed.
                    _is_overlap = (
                        (sha256 and sha256 in supplemented_sha256_set) or
                        (md5 and md5 in supplemented_md5_set)
                    )
                    if _is_overlap:
                        overlap_count += 1
                else:
                    if not already_seen:
                        skipped_count += 1
                seen_hashes.update(dedup_keys)
                continue

            # Beatoraja: determine which NULL fields to fill
            update_vals: dict[str, Any] = {}
            for col in _FILLABLE_COL_NAMES:
                current_val = getattr(existing, col)
                new_val = getattr(item, col)
                if col in {"title", "artist"}:
                    new_val = normalize_display_text(new_val)
                if current_val is None and new_val is not None:
                    update_vals[col] = new_val

            # Hash supplementation: fill in missing sha256/md5 from client data.
            # Only supplement the hash that was NOT used for matching (to avoid overwriting
            # the key we matched on), and only if the target hash is currently NULL.
            # Use `not existing.sha256` to catch both NULL and empty string (legacy data).
            if hash_key_type == "md5" and sha256 and not existing.sha256:
                # Collision check: ensure this sha256 isn't already used by another row.
                if sha256 not in existing_by_sha256:
                    update_vals["sha256"] = sha256
            if hash_key_type == "sha256" and md5 and not existing.md5:
                if md5 not in existing_by_md5:
                    update_vals["md5"] = md5

            if update_vals:
                cols_key = frozenset(update_vals.keys())
                update_groups.setdefault(cols_key, []).append(
                    (hash_key_type, hash_key_val, update_vals)
                )
                # Overlap check: 이번 세션에서 supplement된 fumen이 detail update도 받으면 double-count
                _is_overlap = (
                    (sha256 and sha256 in supplemented_sha256_set) or
                    (md5 and md5 in supplemented_md5_set)
                )
                if _is_overlap:
                    overlap_count += 1
            else:
                if not already_seen:
                    skipped_count += 1
            # Mark as seen regardless of update/skip — prevents LR2 double-count
            seen_hashes.update(dedup_keys)
        else:
            # New fumen — prepare for bulk INSERT
            row: dict = {
                "sha256": sha256,
                "md5": md5,
                "title": normalize_display_text(item.title),
                "artist": normalize_display_text(item.artist),
                "bpm_min": item.bpm_min,
                "bpm_max": item.bpm_max,
                "bpm_main": item.bpm_main,
                "notes_total": item.notes_total,
                "total": item.total,
                "notes_n": item.notes_n,
                "notes_ln": item.notes_ln,
                "notes_s": item.notes_s,
                "notes_ls": item.notes_ls,
                "length": item.length,
                "keymode": item.keymode,
                "added_by_user_id": current_user.id,
            }
            new_rows.append(row)
            if sha256:
                inserted_sha256s.add(sha256)
            if md5:
                inserted_md5s.add(md5)

    # ── Step 3: Bulk UPDATE via CASE WHEN (grouped by NULL field pattern) ──
    enriched_count = 0
    for cols_key, entries in update_groups.items():
        sha256_entries = [(hv, vals) for hkt, hv, vals in entries if hkt == "sha256"]
        md5_entries = [(hv, vals) for hkt, hv, vals in entries if hkt == "md5"]

        for hash_col, hash_entries in [
            (Fumen.sha256, sha256_entries),
            (Fumen.md5, md5_entries),
        ]:
            if not hash_entries:
                continue

            hash_values = [hv for hv, _ in hash_entries]
            case_values: dict[str, Any] = {}
            for col_name in cols_key:
                case_mapping = {
                    hv: vals[col_name]
                    for hv, vals in hash_entries
                    if col_name in vals
                }
                if case_mapping:
                    case_values[col_name] = sa.case(case_mapping, value=hash_col)

            if case_values:
                await db.execute(
                    update(Fumen)
                    .where(hash_col.in_(hash_values))
                    .values(**case_values)
                    .execution_options(synchronize_session=False)
                )

        enriched_count += len(entries)

    # ── Step 4: Bulk INSERT ──
    if new_rows:
        await db.execute(
            pg_insert(Fumen).values(new_rows).on_conflict_do_nothing()
        )
    inserted_count = len(new_rows)

    await db.flush()
    await db.commit()

    return FumenDetailSyncResponse(
        inserted=inserted_count,
        enriched=enriched_count,
        skipped=skipped_count,
        overlap_count=overlap_count,
    )


@router.get("/{hash_value}", response_model=FumenRead)
async def get_fumen_by_hash(
    hash_value: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> FumenRead:
    """Get a fumen by fumen_id UUID, SHA256, or MD5."""
    fumen = await _get_fumen_by_hash(hash_value, db)
    visible_table_ids = await resolve_visible_table_ids(db, current_user)
    non_regular_hidden = await resolve_non_regular_hidden_levels(db, current_user)
    return await _fumen_read(db, fumen, visible_table_ids, non_regular_hidden)


class SupplementItem(BaseModel):
    """A single fumen hash supplement item from the client.

    Currently uses md5 and sha256 for hash pairing.
    Additional fields (title, bpm, etc.) may be included in the future
    and will be passed through for forward compatibility.
    """

    md5: str | None = None
    sha256: str | None = None


class SupplementRequest(BaseModel):
    """Request body for POST /fumens/supplement."""

    client_type: str
    items: list[SupplementItem]


class SupplementResponse(BaseModel):
    """Response body for POST /fumens/supplement."""

    supplemented: int
    courses_updated: int
    supplemented_md5s: list[str] = []    # 방향 1: md5로 매치되어 sha256 채워진 fumen들의 md5
    supplemented_sha256s: list[str] = [] # 방향 2: sha256로 매치되어 md5 채워진 fumen들의 sha256


@router.post("/supplement", response_model=SupplementResponse)
async def supplement_fumen_hashes(
    body: SupplementRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupplementResponse:
    """Supplement missing md5/sha256 fields in the fumens table.

    Accepts pairs of (md5, sha256) extracted from the client's local song DB
    (e.g., Beatoraja songdata.db). For each pair:
    - If a fumen with that sha256 exists and has no md5, fills md5.
    - If a fumen with that md5 exists and has no sha256, fills sha256.

    After supplementing, recalculates sha256_list for any courses whose
    md5_list contains a newly-supplemented md5.
    """
    from app.models.course import Course
    from app.services.table_import import _build_sha256_list

    # Collect valid (md5, sha256) pairs
    pairs = [
        (item.md5.lower(), item.sha256.lower())
        for item in body.items
        if item.md5 and item.sha256
    ]
    if not pairs:
        return SupplementResponse(supplemented=0, courses_updated=0)

    all_md5s = [p[0] for p in pairs]
    all_sha256s = [p[1] for p in pairs]
    md5_to_sha256 = {p[0]: p[1] for p in pairs}
    sha256_to_md5 = {p[1]: p[0] for p in pairs}

    supplemented = 0
    newly_supplemented_md5s: set[str] = set()
    newly_supplemented_sha256s: set[str] = set()

    # ── Fetch md5-only rows that need a sha256 ──
    # Match rows where sha256 is absent: NULL or empty string (legacy data may store '').
    result = await db.execute(
        select(Fumen).where(
            Fumen.md5 == sa.func.any(sa.cast(sa.literal(all_md5s, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))),
            sa.or_(Fumen.sha256.is_(None), Fumen.sha256 == ""),
        )
    )
    md5_only_rows: dict[str, Fumen] = {row.md5: row for row in result.scalars().all() if row.md5}

    if md5_only_rows:
        # Check which target sha256s already exist in another row (conflict = duplicate)
        target_sha256s = [md5_to_sha256[md5] for md5 in md5_only_rows if md5 in md5_to_sha256]
        existing_sha256_rows: dict[str, Fumen] = {}
        if target_sha256s:
            r2 = await db.execute(
                select(Fumen).where(
                    Fumen.sha256 == sa.func.any(
                        sa.cast(sa.literal(target_sha256s, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))
                    )
                )
            )
            for row in r2.scalars().all():
                existing_sha256_rows[row.sha256] = row

        md5s_to_update: list[str] = []
        for md5, md5_only_row in md5_only_rows.items():
            sha256 = md5_to_sha256.get(md5)
            if not sha256:
                continue
            if sha256 in existing_sha256_rows:
                sha256_row = existing_sha256_rows[sha256]
                if sha256_row.md5 is None:
                    await db.execute(
                        update(Fumen)
                        .where(Fumen.fumen_id == sha256_row.fumen_id)
                        .values(md5=md5)
                        .execution_options(synchronize_session=False)
                    )
                await db.execute(
                    sa.text("""
                        INSERT INTO fumen_table_entries (fumen_id, table_id, level, created_at, updated_at)
                        SELECT :canonical_id, table_id, level, created_at, now()
                        FROM fumen_table_entries
                        WHERE fumen_id = :duplicate_id
                        ON CONFLICT (fumen_id, table_id) DO NOTHING
                    """),
                    {"canonical_id": sha256_row.fumen_id, "duplicate_id": md5_only_row.fumen_id},
                )
                await db.execute(
                    sa.text("""
                        INSERT INTO user_fumen_tags (id, user_id, fumen_id, tag, display_order)
                        SELECT gen_random_uuid(), user_id, :canonical_id, tag, display_order
                        FROM user_fumen_tags
                        WHERE fumen_id = :duplicate_id
                        ON CONFLICT (user_id, fumen_id, tag) DO UPDATE
                        SET display_order = LEAST(user_fumen_tags.display_order, EXCLUDED.display_order)
                    """),
                    {"canonical_id": sha256_row.fumen_id, "duplicate_id": md5_only_row.fumen_id},
                )
                await db.execute(
                    sa.text("UPDATE user_scores SET fumen_id = :canonical_id WHERE fumen_id = :duplicate_id"),
                    {"canonical_id": sha256_row.fumen_id, "duplicate_id": md5_only_row.fumen_id},
                )
                await db.execute(
                    sa.delete(Fumen).where(Fumen.fumen_id == md5_only_row.fumen_id)
                )
                supplemented += 1
                newly_supplemented_md5s.add(md5)
            else:
                md5s_to_update.append(md5)

        # Simple bulk UPDATE for non-conflicting rows
        if md5s_to_update:
            case_expr = sa.case(
                {md5: md5_to_sha256[md5] for md5 in md5s_to_update},
                value=Fumen.md5,
            )
            await db.execute(
                update(Fumen)
                .where(
                    Fumen.md5 == sa.func.any(sa.cast(sa.literal(md5s_to_update, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))),
                    sa.or_(Fumen.sha256.is_(None), Fumen.sha256 == ""),
                )
                .values(sha256=case_expr)
                .execution_options(synchronize_session=False)
            )
            supplemented += len(md5s_to_update)
            newly_supplemented_md5s.update(md5s_to_update)

    # ── Fill md5 where fumen has sha256 but no md5 ──
    # (rows already merged above already have md5 set, so md5 IS NULL filter is safe)
    result = await db.execute(
        select(Fumen.sha256).where(
            Fumen.sha256 == sa.func.any(sa.cast(sa.literal(all_sha256s, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))),
            Fumen.md5.is_(None),
        )
    )
    sha256s_needing_md5 = [row.sha256 for row in result.all()]
    if sha256s_needing_md5:
        case_expr = sa.case(
            {sha256: sha256_to_md5[sha256] for sha256 in sha256s_needing_md5 if sha256 in sha256_to_md5},
            value=Fumen.sha256,
        )
        await db.execute(
            update(Fumen)
            .where(
                Fumen.sha256 == sa.func.any(sa.cast(sa.literal(sha256s_needing_md5, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))),
                Fumen.md5.is_(None),
            )
            .values(md5=case_expr)
            .execution_options(synchronize_session=False)
        )
        supplemented += len(sha256s_needing_md5)
        newly_supplemented_md5s.update(
            sha256_to_md5[s] for s in sha256s_needing_md5 if s in sha256_to_md5
        )
        newly_supplemented_sha256s.update(sha256s_needing_md5)

    await db.flush()

    if newly_supplemented_md5s or newly_supplemented_sha256s:
        from app.services.table_import import _backfill_user_scores_for_hashes

        await _backfill_user_scores_for_hashes(
            db,
            sha256s=newly_supplemented_sha256s,
            md5s=newly_supplemented_md5s,
        )

    # Recalculate sha256_list for courses affected by newly supplemented md5s
    courses_updated = 0
    if newly_supplemented_md5s:
        courses_result = await db.execute(select(Course).where(Course.is_active.is_(True)))
        all_active_courses = courses_result.scalars().all()

        for course in all_active_courses:
            md5_list: list = course.md5_list or []
            if any(m in newly_supplemented_md5s for m in md5_list if m):
                course.sha256_list = await _build_sha256_list(db, md5_list)
                courses_updated += 1

        await db.flush()

    await db.commit()
    return SupplementResponse(
        supplemented=supplemented,
        courses_updated=courses_updated,
        supplemented_md5s=list(newly_supplemented_md5s),
        supplemented_sha256s=list(newly_supplemented_sha256s),
    )


# ---------------------------------------------------------------------------
# YouTube URL management (admin only)
# ---------------------------------------------------------------------------

_YOUTUBE_PATTERN = re.compile(
    r"^https?://(www\.)?youtube\.com/watch\?.*v=[\w-]+"
    r"|^https?://youtu\.be/[\w-]+"
)


class YoutubeUrlRequest(BaseModel):
    youtube_url: str | None = None


async def _get_fumen_by_hash(hash_value: str, db: AsyncSession) -> Fumen:
    # Check md5/sha256 first by length. uuid.UUID() accepts 32-char hex strings
    # without dashes, so an md5 would otherwise be mis-parsed as a fumen_id.
    if len(hash_value) == 64:
        result = await db.execute(select(Fumen).where(Fumen.sha256 == hash_value))
    elif len(hash_value) == 32:
        result = await db.execute(select(Fumen).where(Fumen.md5 == hash_value))
    else:
        try:
            fumen_uuid = _uuid.UUID(hash_value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")
        result = await db.execute(select(Fumen).where(Fumen.fumen_id == fumen_uuid))
    fumen = result.scalar_one_or_none()
    if fumen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fumen not found")
    return fumen


@router.patch("/{hash_value}/youtube-url", response_model=FumenRead)
async def update_youtube_url(
    hash_value: str,
    body: YoutubeUrlRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> FumenRead:
    """Update youtube_url for a fumen (admin only)."""
    if body.youtube_url is not None and not _YOUTUBE_PATTERN.match(body.youtube_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid YouTube URL",
        )
    fumen = await _get_fumen_by_hash(hash_value, db)
    fumen.youtube_url = body.youtube_url
    await db.commit()
    await db.refresh(fumen)
    visible_table_ids = await resolve_visible_table_ids(db, current_user)
    non_regular_hidden = await resolve_non_regular_hidden_levels(db, current_user)
    return await _fumen_read(db, fumen, visible_table_ids, non_regular_hidden)


# ---------------------------------------------------------------------------
# User fumen tags
# ---------------------------------------------------------------------------

@router.get("/{hash_value}/tags", response_model=list[TagRead])
async def get_fumen_tags(
    hash_value: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TagRead]:
    """Get current user's tags for a fumen."""
    fumen = await _get_fumen_by_hash(hash_value, db)

    result = await db.execute(
        select(UserFumenTag).where(
            UserFumenTag.user_id == current_user.id,
            UserFumenTag.fumen_id == fumen.fumen_id,
        ).order_by(UserFumenTag.display_order, UserFumenTag.tag)
    )
    tags = result.scalars().all()
    return [TagRead(id=str(t.id), tag=t.tag) for t in tags]


@router.post("/{hash_value}/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def add_fumen_tag(
    hash_value: str,
    body: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagRead:
    """Add a tag to a fumen for the current user."""
    tag_text = body.tag.strip()
    if not tag_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag cannot be empty")

    fumen = await _get_fumen_by_hash(hash_value, db)

    # display_order = 현재 태그 수 (마지막에 추가)
    count_result = await db.execute(
        select(sa.func.count()).select_from(UserFumenTag).where(
            UserFumenTag.user_id == current_user.id,
            UserFumenTag.fumen_id == fumen.fumen_id,
        )
    )
    next_order = count_result.scalar() or 0

    tag = UserFumenTag(
        user_id=current_user.id,
        fumen_id=fumen.fumen_id,
        tag=tag_text,
        display_order=next_order,
    )
    db.add(tag)
    try:
        await db.commit()
        await db.refresh(tag)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")

    return TagRead(id=str(tag.id), tag=tag.tag)


@router.delete("/{hash_value}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fumen_tag(
    hash_value: str,
    tag_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a tag from a fumen."""
    try:
        tag_uuid = _uuid.UUID(tag_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tag id")

    result = await db.execute(
        select(UserFumenTag).where(
            UserFumenTag.id == tag_uuid,
            UserFumenTag.user_id == current_user.id,
        )
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    await db.delete(tag)
    await db.commit()


class TagReorderRequest(BaseModel):
    tag_ids: list[str]


@router.put("/{hash_value}/tags/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_fumen_tags(
    hash_value: str,
    body: TagReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Reorder tags by providing an ordered list of tag UUIDs."""
    try:
        tag_uuids = [_uuid.UUID(tid) for tid in body.tag_ids]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tag id")

    result = await db.execute(
        select(UserFumenTag).where(
            UserFumenTag.id.in_(tag_uuids),
            UserFumenTag.user_id == current_user.id,
        )
    )
    tags_by_id = {t.id: t for t in result.scalars().all()}

    for order, tag_uuid in enumerate(tag_uuids):
        if tag_uuid in tags_by_id:
            tags_by_id[tag_uuid].display_order = order

    await db.commit()
