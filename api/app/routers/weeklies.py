"""Public read endpoints for the Weekly feature."""

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.difficulty_table import DifficultyTable
from app.models.fumen import Fumen
from app.models.user import OAuthAccount, User
from app.models.weekly import Weekly, WeeklyFumen
from app.routers.auth import build_discord_avatar_url
from app.services.clear_type_display import display_clear_type
from app.services.dan_decoration import resolve_dan_decorations_for_tables
from app.services.weekly_config import WeeklyConfigError, load_weekly_config
from app.services.weekly_period import period_for_offset
from app.services.weekly_records import (
    UserRecord,
    evaluate_user_records,
    fetch_fumen_candidate_user_ids,
    fetch_fumen_score_rows,
)

router = APIRouter(prefix="/weeklies", tags=["weeklies"])


# ── response models ────────────────────────────────────────────────────────────

class RangeDisplay(BaseModel):
    text: str  # pre-formatted display line, e.g. "★24 ~ ★25" or "▼24"


class BracketMeta(BaseModel):
    key: str
    group: str | None
    order: int
    color: str
    has_current: bool
    display_ranges: list[RangeDisplay]


class CategoryMeta(BaseModel):
    key: str
    name: str
    order: int
    brackets: list[BracketMeta]


class WeeklyRolloverInfo(BaseModel):
    timezone: str
    day_of_week: str
    hour: int
    minute: int
    description: str


class RecordSnapshotModel(BaseModel):
    clear_type: int | None
    exscore: int | None
    rate: float | None
    rank: str | None
    min_bp: int | None
    effective_ts: str | None


class RecordImprovementModel(BaseModel):
    is_first_record: bool
    clear_type_changed: bool
    exscore_delta: int | None
    min_bp_delta: int | None
    rate_delta: float | None
    rank_changed: bool
    previous: RecordSnapshotModel | None
    current: RecordSnapshotModel


class MyRecord(BaseModel):
    dan_decoration: dict | None = None
    score_id: str | None
    clear_type: int | None
    exscore: int | None
    rate: float | None
    rank: str | None
    min_bp: int | None
    play_count: int | None
    options: dict | None
    client_type: str | None
    improved: bool
    improvement: RecordImprovementModel | None


class WeeklyFumenItem(BaseModel):
    fumen_id: str
    slot: int
    table_symbol: str | None
    level: str
    title: str | None
    artist: str | None
    sha256: str | None
    md5: str | None
    my_record: MyRecord | None


class WeeklyDetail(BaseModel):
    weekly_id: str
    category_key: str
    bracket_key: str
    bracket_group: str | None
    color: str
    period_start: str
    period_end: str
    is_current: bool
    fumens: list[WeeklyFumenItem]


class PlayerRecord(BaseModel):
    user_id: str
    username: str
    avatar_url: str | None
    dan_decoration: dict | None
    score_id: str | None
    clear_type: int | None
    exscore: int | None
    rate: float | None
    rank: str | None
    min_bp: int | None
    play_count: int | None
    options: dict | None
    client_type: str | None
    improved: bool
    improvement: RecordImprovementModel | None


class WeeklyFumenRecords(BaseModel):
    weekly_id: str
    fumen_id: str
    records: list[PlayerRecord]
    next_offset: int | None


# ── helpers ────────────────────────────────────────────────────────────────────

def _settings():
    return load_weekly_config().settings


def _resolve_period(offset: int):
    s = _settings()
    now = datetime.now(UTC)
    return period_for_offset(
        now, offset, s.rollover_day_of_week, s.rollover_hour, s.rollover_minute, s.timezone
    )


def _snapshot_model(snapshot) -> RecordSnapshotModel:
    return RecordSnapshotModel(
        clear_type=snapshot.clear_type,
        exscore=snapshot.exscore,
        rate=snapshot.rate,
        rank=snapshot.rank,
        min_bp=snapshot.min_bp,
        effective_ts=snapshot.effective_ts.isoformat() if snapshot.effective_ts else None,
    )


def _improvement_model(rec: UserRecord) -> RecordImprovementModel | None:
    if not rec.improved:
        return None
    return RecordImprovementModel(
        is_first_record=rec.improvement.is_first_record,
        clear_type_changed=rec.improvement.clear_type_changed,
        exscore_delta=rec.improvement.exscore_delta,
        min_bp_delta=rec.improvement.min_bp_delta,
        rate_delta=rec.improvement.rate_delta,
        rank_changed=rec.improvement.rank_changed,
        previous=_snapshot_model(rec.baseline) if rec.baseline else None,
        current=_snapshot_model(rec.weekly_best),
    )


def _weekly_dan_table_slugs(category_key: str, bracket_key: str) -> list[str]:
    category_dan_tables = {
        "5aery": ["5aery"],
        "stellaverse": ["satellite", "stella"],
        "balgwang": ["balgwang", "new_balgwang", "overjoy"],
    }
    if category_key in category_dan_tables:
        return category_dan_tables[category_key]

    try:
        bracket = load_weekly_config().category(category_key).bracket(bracket_key)
    except WeeklyConfigError:
        return []
    return list(dict.fromkeys(selector.table for selector in bracket.selectors))


def _weekly_avatar_url(
    user_avatar_url: str | None,
    discord_id: str | None,
    discord_avatar_hash: str | None,
    discord_avatar_url: str | None,
) -> str | None:
    """Return custom avatar first, then Discord avatar fallback."""
    if user_avatar_url:
        return user_avatar_url
    return build_discord_avatar_url(discord_id or "", discord_avatar_hash) or discord_avatar_url


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/rollover-info", response_model=WeeklyRolloverInfo)
async def get_rollover_info() -> WeeklyRolloverInfo:
    """Return the weekly rollover schedule (timezone, day, time)."""
    s = _settings()
    dow_ko = {
        "mon": "월요일", "tue": "화요일", "wed": "수요일",
        "thu": "목요일", "fri": "금요일", "sat": "토요일", "sun": "일요일",
    }
    dow_label = dow_ko.get(s.rollover_day_of_week, s.rollover_day_of_week)
    tz_label = s.timezone.replace("Asia/Seoul", "KST")
    description = f"매주 {dow_label} {s.rollover_hour:02d}:{s.rollover_minute:02d} {tz_label} 갱신"
    return WeeklyRolloverInfo(
        timezone=s.timezone,
        day_of_week=s.rollover_day_of_week,
        hour=s.rollover_hour,
        minute=s.rollover_minute,
        description=description,
    )


@router.get("/categories", response_model=list[CategoryMeta])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryMeta]:
    cfg = load_weekly_config()
    cur_start, _ = _resolve_period(0)

    existing_result = await db.execute(
        select(Weekly.category_key, Weekly.bracket_key).where(Weekly.period_start == cur_start)
    )
    existing = {(r.category_key, r.bracket_key) for r in existing_result.all()}

    all_slugs = {s.table for c in cfg.categories for b in c.brackets for s in b.selectors}
    sym_result = await db.execute(
        select(DifficultyTable.slug, DifficultyTable.symbol).where(DifficultyTable.slug.in_(all_slugs))
    )
    slug_to_symbol: dict[str, str | None] = {r.slug: r.symbol for r in sym_result.all()}

    def _build_display_ranges(b) -> list[RangeDisplay]:
        def clean_lv(lv: str) -> str:
            return re.sub(r"^LEVEL\s+", "", lv, flags=re.IGNORECASE).strip()

        def to_num(lv: str) -> float | None:
            try:
                return float(re.sub(r"[^\d.]", "", lv))
            except ValueError:
                return None

        # ── Pass 1: collect all level_range selectors into groups keyed by (lv0, lv1) ──
        # range_syms[key] = ordered list of symbols that share this exact range
        range_syms: dict[tuple[str, str], list[str]] = {}
        for s in b.selectors:
            if not s.level_range:
                continue
            sym = slug_to_symbol.get(s.table) or ""
            lv0, lv1 = clean_lv(s.level_range[0]), clean_lv(s.level_range[1])
            key = (lv0, lv1)
            range_syms.setdefault(key, [])
            if sym not in range_syms[key]:
                range_syms[key].append(sym)

        # ── Pass 2: override start symbol for a range if a `levels` selector
        #    pinpoints exactly its lower bound (e.g. new_balgwang levels=["24"] within ★24~25)
        range_start_override: dict[tuple[str, str], str] = {}
        for s in b.selectors:
            if not s.levels:
                continue
            sym = slug_to_symbol.get(s.table) or ""
            for lv in s.levels:
                lv_c = clean_lv(lv)
                n = to_num(lv_c)
                if n is None:
                    continue
                for (lv0, lv1), syms in range_syms.items():
                    lo, hi = to_num(lv0), to_num(lv1)
                    if lo is None or hi is None:
                        continue
                    if lo <= n <= hi and sym not in syms:
                        # this single level is covered by the range but from a different table
                        if abs(n - lo) < 0.001:
                            range_start_override[(lv0, lv1)] = sym

        # ── Pass 3: build display lines ──
        result: list[RangeDisplay] = []
        for (lv0, lv1), syms in range_syms.items():
            start_sym = range_start_override.get((lv0, lv1))

            if len(syms) == 0:
                result.append(RangeDisplay(text=f"{lv0} ~ {lv1}"))
            elif len(syms) == 1:
                sym = syms[0]
                if start_sym and start_sym != sym:
                    # e.g. ▼24 ~ ★25  (subset table covers the start of this range)
                    result.append(RangeDisplay(text=f"{start_sym}{lv0} ~ {sym}{lv1}"))
                else:
                    # e.g. ★★0 ~ 3  (single table, no symbol repeat at end)
                    result.append(RangeDisplay(text=f"{sym}{lv0} ~ {lv1}"))
            else:
                # Multiple tables share the exact same range.
                # Convention: last-added symbol (typically the "easier" variant) at start,
                # first symbol at end.  e.g. syms=["★","▼"] → ▼21 ~ ★23
                result.append(RangeDisplay(text=f"{syms[-1]}{lv0} ~ {syms[0]}{lv1}"))

        return result

    out: list[CategoryMeta] = []
    for c in cfg.categories:
        out.append(
            CategoryMeta(
                key=c.key, name=c.name, order=c.order,
                brackets=[
                    BracketMeta(
                        key=b.key, group=b.group, order=b.order, color=b.color,
                        has_current=(c.key, b.key) in existing,
                        display_ranges=_build_display_ranges(b),
                    )
                    for b in c.brackets
                ],
            )
        )
    return out


@router.get("/{category_key}/{bracket_key}/periods")
async def list_periods(
    category_key: str, bracket_key: str, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    result = await db.execute(
        select(Weekly.id, Weekly.period_start, Weekly.period_end)
        .where(Weekly.category_key == category_key, Weekly.bracket_key == bracket_key)
        .order_by(Weekly.period_start.desc())
    )
    return [
        {"weekly_id": str(r.id), "period_start": r.period_start.isoformat(),
         "period_end": r.period_end.isoformat()}
        for r in result.all()
    ]


@router.get("/{category_key}/{bracket_key}", response_model=WeeklyDetail)
async def get_weekly_detail(
    category_key: str,
    bracket_key: str,
    offset: int = Query(0, le=0),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> WeeklyDetail:
    try:
        cfg = load_weekly_config()
        cfg.category(category_key).bracket(bracket_key)
    except WeeklyConfigError:
        raise HTTPException(status_code=404, detail="Unknown category/bracket")

    period_start, _ = _resolve_period(offset)
    cur_start, _ = _resolve_period(0)

    weekly_result = await db.execute(
        select(Weekly).where(
            Weekly.category_key == category_key,
            Weekly.bracket_key == bracket_key,
            Weekly.period_start == period_start,
        )
    )
    weekly = weekly_result.scalar_one_or_none()
    if weekly is None:
        raise HTTPException(status_code=404, detail="Weekly not found for this period")

    wf_result = await db.execute(
        select(
            WeeklyFumen.slot, WeeklyFumen.fumen_id, WeeklyFumen.table_symbol, WeeklyFumen.level,
            Fumen.title, Fumen.artist, Fumen.sha256, Fumen.md5,
        )
        .join(Fumen, Fumen.fumen_id == WeeklyFumen.fumen_id)
        .where(WeeklyFumen.weekly_id == weekly.id)
        .order_by(WeeklyFumen.slot)
    )
    rows = wf_result.all()
    dan_table_slugs = _weekly_dan_table_slugs(category_key, bracket_key)
    my_dan_decoration = None
    if current_user is not None:
        my_decorations = await resolve_dan_decorations_for_tables(
            db, [current_user.id], dan_table_slugs
        )
        my_dan_decoration = my_decorations.get(str(current_user.id))

    items: list[WeeklyFumenItem] = []
    for r in rows:
        my_record: MyRecord | None = None
        if current_user is not None:
            grouped = await fetch_fumen_score_rows(
                db, r.sha256, r.md5, r.fumen_id, only_user_id=current_user.id
            )
            mine = grouped.get(str(current_user.id))
            if mine:
                evaluated = evaluate_user_records(
                    {str(current_user.id): mine}, weekly.period_start, weekly.period_end
                )
                rec: UserRecord | None = evaluated.get(str(current_user.id))
                if rec is not None:
                    my_record = MyRecord(
                        dan_decoration=my_dan_decoration,
                        score_id=rec.weekly_score_id,
                        clear_type=display_clear_type(rec.best_clear_type, exscore=rec.best_exscore, rate=rec.best_rate),
                        exscore=rec.best_exscore, rate=rec.best_rate, rank=rec.best_rank,
                        min_bp=rec.best_min_bp,
                        play_count=rec.best_play_count,
                        options=rec.best_options,
                        client_type=rec.best_client_type,
                        improved=rec.improved,
                        improvement=_improvement_model(rec),
                    )
        items.append(
            WeeklyFumenItem(
                fumen_id=str(r.fumen_id), slot=r.slot, table_symbol=r.table_symbol, level=r.level,
                title=r.title, artist=r.artist, sha256=r.sha256, md5=r.md5, my_record=my_record,
            )
        )

    snap = weekly.config_snapshot or {}
    return WeeklyDetail(
        weekly_id=str(weekly.id),
        category_key=weekly.category_key,
        bracket_key=weekly.bracket_key,
        bracket_group=snap.get("bracket_group"),
        color=snap.get("color", "#888888"),
        period_start=weekly.period_start.isoformat(),
        period_end=weekly.period_end.isoformat(),
        is_current=(weekly.period_start == cur_start),
        fumens=items,
    )


@router.get("/{weekly_id}/fumen/{fumen_id}/records", response_model=WeeklyFumenRecords)
async def get_weekly_fumen_records(
    weekly_id: uuid.UUID,
    fumen_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_key: str = Query("score", pattern="^(clear|bp|rate|score|plays)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
) -> WeeklyFumenRecords:
    weekly = (await db.execute(select(Weekly).where(Weekly.id == weekly_id))).scalar_one_or_none()
    if weekly is None:
        raise HTTPException(status_code=404, detail="Weekly not found")
    wf = (
        await db.execute(
            select(WeeklyFumen).where(
                WeeklyFumen.weekly_id == weekly_id, WeeklyFumen.fumen_id == fumen_id
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Fumen not in this weekly")

    fumen = (
        await db.execute(
            select(Fumen.sha256, Fumen.md5, Fumen.fumen_id).where(Fumen.fumen_id == fumen_id)
        )
    ).first()
    if fumen is None:
        raise HTTPException(status_code=404, detail="Fumen not found")

    candidate_user_ids = await fetch_fumen_candidate_user_ids(
        db,
        fumen.sha256,
        fumen.md5,
        fumen.fumen_id,
        weekly.period_start,
        weekly.period_end,
        limit=limit + 1,
        offset=offset,
        sort_key=sort_key,
        sort_dir=sort_dir,
    )
    has_more = len(candidate_user_ids) > limit
    candidate_user_ids = candidate_user_ids[:limit]
    grouped = await fetch_fumen_score_rows(
        db,
        fumen.sha256,
        fumen.md5,
        fumen.fumen_id,
        user_ids=candidate_user_ids,
    )
    evaluated = evaluate_user_records(grouped, weekly.period_start, weekly.period_end)
    if not evaluated:
        return WeeklyFumenRecords(
            weekly_id=str(weekly_id),
            fumen_id=str(fumen_id),
            records=[],
            next_offset=(offset + limit if has_more else None),
        )

    user_ids_list = [uuid.UUID(uid) for uid in evaluated.keys()]
    users_result = await db.execute(
        select(
            User.id,
            User.username,
            User.avatar_url,
            OAuthAccount.provider_account_id,
            OAuthAccount.discord_avatar_hash,
            OAuthAccount.discord_avatar_url,
        )
        .outerjoin(
            OAuthAccount,
            (OAuthAccount.user_id == User.id) & (OAuthAccount.provider == "discord"),
        )
        .where(User.id.in_(user_ids_list))
    )
    user_map = {str(u.id): u for u in users_result.all()}
    decorations = await resolve_dan_decorations_for_tables(
        db, user_ids_list, _weekly_dan_table_slugs(weekly.category_key, weekly.bracket_key)
    )

    records: list[PlayerRecord] = []
    for user_id in candidate_user_ids:
        uid = str(user_id)
        rec = evaluated.get(uid)
        if rec is None:
            continue
        u = user_map.get(uid)
        if u is None:
            continue
        records.append(
            PlayerRecord(
                user_id=uid,
                username=u.username,
                avatar_url=_weekly_avatar_url(
                    u.avatar_url,
                    u.provider_account_id,
                    u.discord_avatar_hash,
                    u.discord_avatar_url,
                ),
                dan_decoration=decorations.get(uid),
                score_id=rec.weekly_score_id,
                clear_type=display_clear_type(rec.best_clear_type, exscore=rec.best_exscore, rate=rec.best_rate),
                exscore=rec.best_exscore, rate=rec.best_rate, rank=rec.best_rank,
                min_bp=rec.best_min_bp,
                play_count=rec.best_play_count,
                options=rec.best_options,
                client_type=rec.best_client_type,
                improved=rec.improved,
                improvement=_improvement_model(rec),
            )
        )

    return WeeklyFumenRecords(
        weekly_id=str(weekly_id),
        fumen_id=str(fumen_id),
        records=records,
        next_offset=(offset + limit if has_more else None),
    )
