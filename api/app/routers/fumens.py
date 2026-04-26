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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    get_current_admin,
    get_current_user,
    get_current_user_optional,
)
from app.models.fumen import Fumen, UserFumenTag
from app.models.score import UserScore
from app.models.user import User
from app.services.fumen_user_scores import (
    TableFumenScore,
    UserTagRead,
    fetch_user_score_map,
    fetch_user_tag_map,
)
from app.utils.numeric_filter import numeric_clause, parse_length_to_ms
from app.utils.score_enums import (
    ARRANGEMENT_KANJI_REV,
    BEA_ARRANGEMENT_NAMES,
    CLEAR_TYPE_VALUES,
    LR2_ARRANGEMENT_NAMES,
    RANK_VALUES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fumens", tags=["fumens"])


class FumenRead(BaseModel):
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
    model_config = ConfigDict(from_attributes=True)


FumenSearchField = Literal[
    "title_artist", "title", "artist", "level",
    "bpm", "notes", "length",
    "clear", "bp", "rate", "rank", "score", "plays", "option", "env",
]

_SCORE_FIELDS = frozenset({"clear", "bp", "rate", "rank", "score", "plays", "option", "env"})
_AGG_SCORE_FIELDS = frozenset({"clear", "bp", "rate", "rank", "score", "plays"})


class FumenListItem(FumenRead):
    """FumenRead + per-user enrichment."""

    user_score: TableFumenScore | None = None
    user_tags: list[UserTagRead] = []


class FumenListResponse(BaseModel):
    items: list[FumenListItem]
    total: int
    page: int
    limit: int


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
        UserScore.fumen_hash_others.is_(None),
        or_(
            UserScore.fumen_sha256 == Fumen.sha256,
            and_(
                UserScore.fumen_md5 == Fumen.md5,
                UserScore.fumen_sha256.is_(None),
            ),
        ),
    )
    return (
        select(
            Fumen.sha256.label("fumen_sha256"),
            Fumen.md5.label("fumen_md5"),
            func.max(display_clear).label("best_clear_type"),
            func.max(UserScore.exscore).label("best_exscore"),
            func.min(UserScore.min_bp).label("best_min_bp"),
            func.max(UserScore.rate).label("best_rate"),
            func.max(rank_order).label("rank_order"),
            func.sum(UserScore.play_count).label("total_plays"),
        )
        .select_from(Fumen)
        .outerjoin(UserScore, score_join_cond)
        .group_by(Fumen.sha256, Fumen.md5)
        .subquery("score_agg")
    )


def _score_agg_join_cond(score_agg: Any) -> Any:
    return or_(
        Fumen.sha256 == score_agg.c.fumen_sha256,
        and_(
            Fumen.sha256.is_(None),
            score_agg.c.fumen_sha256.is_(None),
            Fumen.md5 == score_agg.c.fumen_md5,
        ),
    )


def _score_exists_cond(user_id: _uuid.UUID, cond: Any) -> Any:
    """EXISTS subquery: fumens that have a user_score row matching `cond`."""
    return exists(
        select(literal(1)).select_from(UserScore).where(
            UserScore.user_id == user_id,
            UserScore.fumen_hash_others.is_(None),
            or_(
                UserScore.fumen_sha256 == Fumen.sha256,
                and_(
                    UserScore.fumen_md5 == Fumen.md5,
                    UserScore.fumen_sha256.is_(None),
                ),
            ),
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
        return Fumen.table_entries.contains([{"level": level_q}])
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


def _build_sort_col(sort_by: str, sort_dir: str, score_agg: Any) -> Any:
    asc_dir = sort_dir == "asc"

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
        return col.asc().nullslast() if asc_dir else col.desc().nullslast()

    if sort_by == "level":
        level_expr = sa.text("CAST(substring(table_entries->0->>'level' from '[0-9]+(?:\\.[0-9]+)?') AS NUMERIC)")
        return sa.asc(level_expr).nullslast() if asc_dir else sa.desc(level_expr).nullslast()

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
            return col.asc().nullslast() if asc_dir else col.desc().nullslast()

    return Fumen.title.asc().nullslast()


@router.get("/", response_model=FumenListResponse)
async def list_fumens(
    field: FumenSearchField = Query("title_artist"),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    sort_by: str = Query("title"),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
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

    if q_clean and field in _SCORE_FIELDS and not current_user:
        raise HTTPException(status_code=400, detail="Authentication required for score field search")
    if sort_by in _SCORE_FIELDS and not current_user:
        raise HTTPException(status_code=400, detail="Authentication required for score field sort")

    # Optional score aggregation subquery (for sorting/filtering by score fields)
    score_agg = None
    if current_user and (sort_by in _SCORE_FIELDS or (q_clean and field in _AGG_SCORE_FIELDS)):
        score_agg = _build_score_agg_subquery(current_user.id)

    base = select(Fumen)
    count_q = select(func.count()).select_from(Fumen)

    # LEFT JOIN score_agg for sort/filter — one aggregate row per fumen, so pagination stays stable.
    if score_agg is not None:
        join_cond = _score_agg_join_cond(score_agg)
        base = base.outerjoin(score_agg, join_cond)
        count_q = count_q.outerjoin(score_agg, join_cond)

    # WHERE
    if q_clean:
        where_cond = _build_field_condition(field, q_clean, current_user, score_agg)
        if where_cond is None:
            return FumenListResponse(items=[], total=0, page=page, limit=limit)
        base = base.where(where_cond)
        count_q = count_q.where(where_cond)

    total = (await db.execute(count_q)).scalar() or 0

    # ORDER BY + tie-breaker
    order_col = _build_sort_col(sort_by, sort_dir, score_agg)
    base = base.order_by(
        order_col,
        Fumen.sha256.asc().nullslast(),
        Fumen.md5.asc().nullslast(),
    )

    base = base.limit(limit).offset((page - 1) * limit)
    fumens = list((await db.execute(base)).scalars().all())

    score_map: dict = {}
    tag_map: dict = {}
    if current_user and fumens:
        score_map = await fetch_user_score_map(db, current_user.id, fumens)
        tag_map = await fetch_user_tag_map(db, current_user.id, fumens)

    items = [
        FumenListItem(
            **FumenRead.model_validate(f).model_dump(),
            user_score=score_map.get((f.sha256, f.md5 if not f.sha256 else None)),
            user_tags=tag_map.get((f.sha256, f.md5 if not f.sha256 else None), []),
        )
        for f in fumens
    ]

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


@router.get("/{hash_value}", response_model=FumenRead)
async def get_fumen_by_hash(
    hash_value: str,
    db: AsyncSession = Depends(get_db),
) -> FumenRead:
    """Get a fumen by SHA256 (64 chars) or MD5 (32 chars) hash."""
    if len(hash_value) == 64:
        result = await db.execute(select(Fumen).where(Fumen.sha256 == hash_value))
    elif len(hash_value) == 32:
        result = await db.execute(select(Fumen).where(Fumen.md5 == hash_value))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")

    fumen = result.scalar_one_or_none()
    if fumen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fumen not found")

    return FumenRead.model_validate(fumen)


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

    def _merge_entries(a: list | None, b: list | None) -> list:
        """Merge two table_entries lists, keeping one entry per table_id."""
        seen: dict = {}
        for e in (a or []):
            seen[e.get("table_id")] = e
        for e in (b or []):
            tid = e.get("table_id")
            if tid not in seen:
                seen[tid] = e
        return list(seen.values())

    # ── Fetch md5-only rows that need a sha256 ──
    # Match rows where sha256 is absent: NULL or empty string (legacy data may store '').
    result = await db.execute(
        select(Fumen.md5, Fumen.table_entries).where(
            Fumen.md5 == sa.func.any(sa.cast(sa.literal(all_md5s, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))),
            sa.or_(Fumen.sha256.is_(None), Fumen.sha256 == ""),
        )
    )
    md5_only_rows: dict[str, list | None] = {row.md5: row.table_entries for row in result.all()}

    if md5_only_rows:
        # Check which target sha256s already exist in another row (conflict = duplicate)
        target_sha256s = [md5_to_sha256[md5] for md5 in md5_only_rows if md5 in md5_to_sha256]
        existing_sha256_rows: dict[str, Any] = {}
        if target_sha256s:
            r2 = await db.execute(
                select(Fumen.sha256, Fumen.md5, Fumen.table_entries).where(
                    Fumen.sha256 == sa.func.any(
                        sa.cast(sa.literal(target_sha256s, sa.ARRAY(sa.String)), sa.ARRAY(sa.String))
                    )
                )
            )
            for row in r2.all():
                existing_sha256_rows[row.sha256] = row

        md5s_to_update: list[str] = []
        for md5 in md5_only_rows:
            sha256 = md5_to_sha256.get(md5)
            if not sha256:
                continue
            if sha256 in existing_sha256_rows:
                # Conflict: sha256 row exists separately — merge the two rows.
                # Canonical row = sha256 row (preferred identity). Set md5 there
                # and merge table_entries, then delete the md5-only duplicate.
                sha256_row = existing_sha256_rows[sha256]
                if sha256_row.md5 is None:
                    merged_entries = _merge_entries(sha256_row.table_entries, md5_only_rows[md5])
                    await db.execute(
                        update(Fumen)
                        .where(Fumen.sha256 == sha256, Fumen.md5.is_(None))
                        .values(md5=md5, table_entries=merged_entries)
                        .execution_options(synchronize_session=False)
                    )
                from sqlalchemy import delete as sa_delete
                await db.execute(
                    sa_delete(Fumen).where(Fumen.md5 == md5, sa.or_(Fumen.sha256.is_(None), Fumen.sha256 == ""))
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
# Fumen detail sync
# ---------------------------------------------------------------------------

class KnownHashesResponse(BaseModel):
    """Response for GET /fumens/known-hashes."""

    complete_sha256: list[str]
    complete_md5: list[str]
    partial_sha256: list[str]
    partial_md5: list[str]


# Detail columns — NULL이 하나라도 있으면 "partial"
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
)

# All fillable column names (title/artist + detail)
_FILLABLE_COL_NAMES = ("title", "artist") + _DETAIL_COLS


@router.get("/known-hashes", response_model=KnownHashesResponse)
async def get_known_hashes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnownHashesResponse:
    """Return sets of known fumen hashes, split by detail completeness.

    - complete: all detail columns are non-NULL → client can skip entirely.
    - partial: at least one detail column is NULL → Beatoraja items should be sent for fill.
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
            detail_all_filled.label("is_complete"),
        )
    )
    rows = result.all()

    complete_sha256: list[str] = []
    complete_md5: list[str] = []
    partial_sha256: list[str] = []
    partial_md5: list[str] = []

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

    return KnownHashesResponse(
        complete_sha256=complete_sha256,
        complete_md5=complete_md5,
        partial_sha256=partial_sha256,
        partial_md5=partial_md5,
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
    client_type: str  # "beatoraja" or "lr2"


class FumenDetailSyncRequest(BaseModel):
    """Request body for POST /fumens/sync-details."""

    items: list[FumenDetailItem]
    supplemented_md5s: list[str] = []    # 이번 세션에서 supplement로 sha256 채워진 fumen의 md5
    supplemented_sha256s: list[str] = [] # 이번 세션에서 supplement로 md5 채워진 fumen의 sha256


class FumenDetailSyncResponse(BaseModel):
    """Response body for POST /fumens/sync-details."""

    inserted: int
    updated: int
    skipped: int
    overlap_count: int = 0  # updated 중 supplemented와 겹치는 수 (double-count 보정용)


@router.post("/sync-details", response_model=FumenDetailSyncResponse)
async def sync_fumen_details(
    body: FumenDetailSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FumenDetailSyncResponse:
    """Sync fumen detail data from client's local song DBs.

    Accepts fumen metadata items (Beatoraja first, then LR2).
    - Beatoraja items: fill NULL detail fields on existing fumens, INSERT new ones.
    - LR2 items: INSERT only if not already in DB (skip existing entirely).
    All new inserts record added_by_user_id.

    NOTE: Client should call GET /fumens/known-hashes first and only send
    items that are new or have incomplete details on the server.
    """
    if not body.items:
        return FumenDetailSyncResponse(inserted=0, updated=0, skipped=0)

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
                # LR2: always skip existing fumens
                if not already_seen:
                    skipped_count += 1
                seen_hashes.update(dedup_keys)
                continue

            # Beatoraja: determine which NULL fields to fill
            update_vals: dict[str, Any] = {}
            for col in _FILLABLE_COL_NAMES:
                current_val = getattr(existing, col)
                new_val = getattr(item, col)
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
                "title": item.title,
                "artist": item.artist,
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
                "added_by_user_id": current_user.id,
            }
            new_rows.append(row)
            if sha256:
                inserted_sha256s.add(sha256)
            if md5:
                inserted_md5s.add(md5)

    # ── Step 3: Bulk UPDATE via CASE WHEN (grouped by NULL field pattern) ──
    updated_count = 0
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

        updated_count += len(entries)

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
        updated=updated_count,
        skipped=skipped_count,
        overlap_count=overlap_count,
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
    if len(hash_value) == 64:
        result = await db.execute(select(Fumen).where(Fumen.sha256 == hash_value))
    elif len(hash_value) == 32:
        result = await db.execute(select(Fumen).where(Fumen.md5 == hash_value))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")
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
    return FumenRead.model_validate(fumen)


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
    if len(hash_value) == 64:
        condition = UserFumenTag.fumen_sha256 == hash_value
    elif len(hash_value) == 32:
        condition = (UserFumenTag.fumen_md5 == hash_value) & UserFumenTag.fumen_sha256.is_(None)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")

    result = await db.execute(
        select(UserFumenTag).where(
            UserFumenTag.user_id == current_user.id,
            condition,
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

    sha256: str | None = None
    md5: str | None = None
    if len(hash_value) == 64:
        sha256 = hash_value
    elif len(hash_value) == 32:
        md5 = hash_value
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash length")

    # display_order = 현재 태그 수 (마지막에 추가)
    count_result = await db.execute(
        select(sa.func.count()).select_from(UserFumenTag).where(
            UserFumenTag.user_id == current_user.id,
            UserFumenTag.fumen_sha256 == sha256 if sha256 else
            (UserFumenTag.fumen_md5 == md5) & UserFumenTag.fumen_sha256.is_(None),
        )
    )
    next_order = count_result.scalar() or 0

    tag = UserFumenTag(
        user_id=current_user.id,
        fumen_sha256=sha256,
        fumen_md5=md5,
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
