"""User goal (quest) endpoints — HTTP CRUD layer over Task 7's `UserGoal`
model and Task 8's `goal_evaluator.py` service.

Achievement transitions (status active -> achieved) are never performed
here — that is Task 10's sync-time job (`goal_evaluator.evaluate_and_mark_achieved`).
This router only creates, lists, soft-deletes, and reports on goals.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.course import Course
from app.models.difficulty_table import DifficultyTable
from app.models.fumen import Fumen, FumenTableEntry
from app.models.goal import UserGoal
from app.models.score import UserPlayerStats
from app.models.user import User
from app.services.goal_evaluator import (
    GoalBaseline,
    compute_chart_baseline,
    compute_course_baseline,
    validate_goal_target,
)
from app.services.ranking_calculator import CLEAR_TYPE_TO_LAMP_NAME
from app.services.ranking_calculator import _song_rating as _rate_chart
from app.services.ranking_config import get_ranking_config

router = APIRouter(prefix="/goals", tags=["goals"])


# ── Request schema ───────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    """Creatable fields for a new goal (plan §3.7)."""

    goal_type: Literal["chart", "course"]
    client_type: str
    table_slug: str | None = None
    fumen_sha256: str | None = None
    fumen_md5: str | None = None
    course_id: uuid.UUID | None = None
    target_clear_type: int | None = None
    target_min_bp: int | None = None
    target_rank: str | None = None
    target_rate: float | None = None
    comment: str | None = None


# ── Fumen / course metadata resolution helpers ──────────────────────────────

async def _resolve_fumen(
    db: AsyncSession, fumen_sha256: str | None, fumen_md5: str | None
) -> Fumen | None:
    """Look up the canonical `Fumen` row for a chart target.

    Dual sha256/md5 lookup per CLAUDE.md's "Fumen hash lookups" rule — a
    caller may only know one of the two hashes (e.g. an LR2-only chart).
    """
    conditions = []
    if fumen_sha256:
        conditions.append(Fumen.sha256 == fumen_sha256)
    if fumen_md5:
        conditions.append(Fumen.md5 == fumen_md5)
    if not conditions:
        return None
    result = await db.execute(select(Fumen).where(or_(*conditions)))
    return result.scalars().first()


async def _resolve_level_for_table(
    db: AsyncSession, fumen_id: uuid.UUID | None, table_slug: str | None
) -> str | None:
    """Return the fumen's level within the given table_slug, or None if
    either is missing or the table/entry no longer exists (defensive —
    tables/entries can be discontinued after a goal is created)."""
    if fumen_id is None or table_slug is None:
        return None
    result = await db.execute(
        select(FumenTableEntry.level)
        .join(DifficultyTable, DifficultyTable.id == FumenTableEntry.table_id)
        .where(FumenTableEntry.fumen_id == fumen_id, DifficultyTable.slug == table_slug)
    )
    return result.scalars().first()


def _compute_projected_rating(
    *,
    table_slug: str | None,
    level: str | None,
    baseline: GoalBaseline,
    target_clear_type: int | None,
    target_min_bp: int | None,
    target_rank: str | None,
    target_rate: float | None,
) -> float | None:
    """Display-only projected rating for a chart goal target (plan §3.1/§3.2).

    Reuses `ranking_calculator._song_rating` — the same per-chart rating
    formula backing `/rankings/{slug}/calc-params` — rather than
    reimplementing the formula a third time (see Task 9 report for the
    judgment call this required: `_song_rating` is a "private" (leading
    underscore) module function, but it is the only synchronous,
    already-importable entry point for the pure per-chart formula that
    doesn't pull in ranking-aggregation machinery).

    Metrics the goal doesn't target fall back to the user's current
    baseline value, so the projection reflects "if I hit this target while
    everything else stays as it is today". Returns None whenever there
    isn't enough information to compute a meaningful value (no table_slug,
    unresolved level, ranking config not loaded, or the resulting lamp is
    NOPLAY) rather than a misleading 0.0.
    """
    if table_slug is None or level is None:
        return None
    try:
        config = get_ranking_config()
    except RuntimeError:
        return None
    table_cfg = config.get_table_by_slug(table_slug)
    if table_cfg is None or level not in table_cfg.level_weights:
        return None

    clear_type = target_clear_type if target_clear_type is not None else baseline.clear_type
    lamp = CLEAR_TYPE_TO_LAMP_NAME.get(clear_type, "NOPLAY")
    if lamp == "NOPLAY":
        return None

    rank = target_rank if target_rank is not None else (baseline.rank or "F")
    min_bp = target_min_bp if target_min_bp is not None else baseline.min_bp
    rate = target_rate if target_rate is not None else baseline.rate
    rate_01 = (rate / 100.0) if rate is not None else None

    rating = _rate_chart(
        level, lamp, rank,
        float(min_bp) if min_bp is not None else None,
        rate_01,
        table_cfg,
    )
    return round(rating, 3)


def _goal_base_dict(goal: UserGoal) -> dict[str, Any]:
    """Fields present on every goal response, independent of metadata lookups."""
    return {
        "goal_id": str(goal.goal_id),
        "goal_type": goal.goal_type,
        "client_type": goal.client_type,
        "table_slug": goal.table_slug,
        "fumen_sha256": goal.fumen_sha256,
        "fumen_md5": goal.fumen_md5,
        "course_id": str(goal.course_id) if goal.course_id else None,
        "target_clear_type": goal.target_clear_type,
        "target_min_bp": goal.target_min_bp,
        "target_rank": goal.target_rank,
        "target_rate": goal.target_rate,
        "projected_rating": goal.projected_rating,
        "comment": goal.comment,
        "status": goal.status,
        "created_at": goal.created_at.isoformat() if goal.created_at else None,
        "achieved_at": goal.achieved_at.isoformat() if goal.achieved_at else None,
        "achieved_recorded_at": (
            goal.achieved_recorded_at.isoformat() if goal.achieved_recorded_at else None
        ),
        "baseline_snapshot": goal.baseline_snapshot,
    }


async def _enrich_goal(goal: UserGoal, db: AsyncSession) -> dict[str, Any]:
    """Attach display metadata (title/artist/level or course name/dan_title).

    Defensive: if the referenced Fumen/Course/DifficultyTable was deleted or
    renamed after the goal was created, the metadata fields are simply left
    null rather than raising — goals can outlive their source data.
    """
    body = _goal_base_dict(goal)
    body.update({"title": None, "artist": None, "level": None, "course_name": None, "dan_title": None})

    if goal.goal_type == "chart":
        fumen = await _resolve_fumen(db, goal.fumen_sha256, goal.fumen_md5)
        if fumen is not None:
            body["title"] = fumen.title
            body["artist"] = fumen.artist
            body["level"] = await _resolve_level_for_table(db, fumen.fumen_id, goal.table_slug)
    elif goal.goal_type == "course" and goal.course_id is not None:
        course = await db.get(Course, goal.course_id)
        if course is not None:
            body["course_name"] = course.name
            body["dan_title"] = course.dan_title

    return body


async def _resolve_default_client_type(user_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Return the user's most-recently-synced client_type (plan §3.2's
    "기본 구동기 = 유저의 가장 최근 동기화 client_type"), or None if the user has
    never synced. No existing endpoint exposes this single field (checked
    `users.py`'s `_resolve_last_synced_at`, which only resolves a timestamp,
    not which client produced it) — see Task 9 report for the judgment call
    to surface it as a field on this list response rather than a dedicated
    endpoint, matching the `user_player_stats` query pattern used at
    `analysis.py:467`.
    """
    result = await db.execute(
        select(UserPlayerStats.client_type)
        .where(UserPlayerStats.user_id == user_id)
        .order_by(UserPlayerStats.synced_at.desc())
        .limit(1)
    )
    return result.scalars().first()


# ── GET /goals/ ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_goals(
    goal_status: Literal["active", "achieved"] = Query(default="active", alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List the current user's own goals, filtered by status (default active)."""
    result = await db.execute(
        select(UserGoal)
        .where(
            UserGoal.user_id == current_user.id,
            UserGoal.deleted_at.is_(None),
            UserGoal.status == goal_status,
        )
        .order_by(UserGoal.created_at.desc())
    )
    goals = result.scalars().all()

    goal_dicts = [await _enrich_goal(goal, db) for goal in goals]
    default_client_type = await _resolve_default_client_type(current_user.id, db)

    return {"goals": goal_dicts, "default_client_type": default_client_type}


# ── POST /goals/ ─────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new goal after validating the target improves on the user's
    baseline (Task 8's `validate_goal_target`) and doesn't duplicate an
    existing active goal for the same target."""
    fumen: Fumen | None = None
    course: Course | None = None

    if body.goal_type == "chart":
        if not body.fumen_sha256 and not body.fumen_md5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chart goal requires fumen_sha256 or fumen_md5",
            )
        fumen = await _resolve_fumen(db, body.fumen_sha256, body.fumen_md5)
        # Prefer the canonical Fumen row's hashes (covers both sha256 and
        # md5) so the stored goal matches achievement candidates from either
        # client, but fall back to whatever the caller supplied if the
        # fumen isn't registered yet.
        resolved_sha256 = fumen.sha256 if fumen is not None else body.fumen_sha256
        resolved_md5 = fumen.md5 if fumen is not None else body.fumen_md5

        baseline = await compute_chart_baseline(
            db, current_user.id, body.client_type, body.fumen_sha256, body.fumen_md5
        )
    else:
        if body.course_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="course goal requires course_id",
            )
        course = await db.get(Course, body.course_id)
        resolved_sha256 = None
        resolved_md5 = None
        baseline = await compute_course_baseline(db, current_user.id, body.client_type, body.course_id)

    validation = validate_goal_target(
        baseline,
        target_clear_type=body.target_clear_type,
        target_min_bp=body.target_min_bp,
        target_rank=body.target_rank,
        target_rate=body.target_rate,
    )
    if not validation.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": validation.errors, "improved_metrics": validation.improved_metrics},
        )

    # Application-level duplicate-active-goal check (friendlier than a raw
    # DB constraint violation) — mirrors the partial unique indexes exactly
    # (COALESCE(...,'') pairing for chart, plain equality for course).
    dup_query = select(UserGoal.goal_id).where(
        UserGoal.user_id == current_user.id,
        UserGoal.client_type == body.client_type,
        UserGoal.goal_type == body.goal_type,
        UserGoal.status == "active",
        UserGoal.deleted_at.is_(None),
    )
    if body.goal_type == "chart":
        dup_query = dup_query.where(
            UserGoal.table_slug == body.table_slug,
            (UserGoal.fumen_sha256 == resolved_sha256) if resolved_sha256 else UserGoal.fumen_sha256.is_(None),
            (UserGoal.fumen_md5 == resolved_md5) if resolved_md5 else UserGoal.fumen_md5.is_(None),
        )
    else:
        dup_query = dup_query.where(UserGoal.course_id == body.course_id)

    if (await db.execute(dup_query)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active goal already exists for this target",
        )

    level = None
    if body.goal_type == "chart" and fumen is not None:
        level = await _resolve_level_for_table(db, fumen.fumen_id, body.table_slug)

    projected_rating = None
    if body.goal_type == "chart":
        projected_rating = _compute_projected_rating(
            table_slug=body.table_slug,
            level=level,
            baseline=baseline,
            target_clear_type=body.target_clear_type,
            target_min_bp=body.target_min_bp,
            target_rank=body.target_rank,
            target_rate=body.target_rate,
        )

    goal = UserGoal(
        goal_id=uuid.uuid4(),
        user_id=current_user.id,
        goal_type=body.goal_type,
        client_type=body.client_type,
        table_slug=body.table_slug if body.goal_type == "chart" else None,
        fumen_sha256=resolved_sha256,
        fumen_md5=resolved_md5,
        course_id=body.course_id if body.goal_type == "course" else None,
        course_md5_list=(course.md5_list if course is not None else None),
        target_clear_type=body.target_clear_type,
        target_min_bp=body.target_min_bp,
        target_rank=body.target_rank,
        target_rate=body.target_rate,
        projected_rating=projected_rating,
        comment=body.comment,
        status="active",
        baseline_snapshot=asdict(baseline),
    )
    db.add(goal)
    try:
        await db.commit()
    except IntegrityError:
        # Backstop for a race between the pre-check above and the insert
        # (e.g. two concurrent requests) — the partial unique index still
        # protects correctness; convert its raw violation into the same
        # friendly 409 the pre-check would have returned.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active goal already exists for this target",
        ) from None
    await db.refresh(goal)

    return await _enrich_goal(goal, db)


# ── DELETE /goals/{goal_id} ──────────────────────────────────────────────────

@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a goal (active or achieved) owned by the current user.

    Sets `deleted_at` rather than physically deleting the row per plan
    §3.7's last bullet — goals remain available for audit/history.
    """
    result = await db.execute(
        select(UserGoal).where(
            UserGoal.goal_id == goal_id,
            UserGoal.user_id == current_user.id,
            UserGoal.deleted_at.is_(None),
        )
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    goal.deleted_at = datetime.now(UTC)
    await db.commit()


# ── GET /goals/achievements ──────────────────────────────────────────────────

@router.get("/achievements")
async def list_goal_achievements(
    date: date = Query(..., description="YYYY-MM-DD, matched against achieved_recorded_at's date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return goals achieved on the given calendar date (Task 15's DayStatSheet
    "goals achieved that day" section).

    Uses `func.date(...)` rather than `cast(..., Date)` — both Postgres and
    SQLite provide a `date()` function that extracts the calendar date from
    a timestamp/text value; `CAST(... AS DATE)` is unreliable on SQLite
    because "DATE" isn't a recognized type-affinity keyword there, so the
    cast falls back to NUMERIC affinity and silently mis-parses the value.
    """
    result = await db.execute(
        select(UserGoal)
        .where(
            UserGoal.user_id == current_user.id,
            UserGoal.deleted_at.is_(None),
            UserGoal.status == "achieved",
            func.date(UserGoal.achieved_recorded_at) == date.isoformat(),
        )
        .order_by(UserGoal.achieved_recorded_at.desc())
    )
    goals = result.scalars().all()

    return {"goals": [await _enrich_goal(goal, db) for goal in goals]}
