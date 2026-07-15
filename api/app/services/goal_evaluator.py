"""Goal evaluation service — baseline computation, target validation, and
achievement matching for the goal/quest system (plan §3, Task 8).

Shared by `api/app/routers/goals.py` (creation-time validation, Task 9) and
`api/app/routers/sync.py` (post-sync achievement detection, Task 10). This
module owns all DB access and pure-logic rules for goals; the routers only
orchestrate calls into it.

Design notes (see plan §3.2/§3.3 for the full rationale):
- Baselines are computed **per metric independently** — a user's best clear
  and best rate may come from different attempts, and each target metric is
  validated independently anyway. Do not collapse this into a single "best
  row" selection (that solves a different problem: picking one row to
  *display*, e.g. `pick_best_per_client`-style helpers elsewhere).
- Achievement matching is batch-oriented and uses a conditional, atomic
  `UPDATE ... WHERE status='active' ... RETURNING` so that re-running the
  same candidate list (e.g. a sync retry) never double-transitions a goal.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.goal import UserGoal
from app.models.score import UserScore
from app.services.ranking_calculator import RANK_ORDER

# Position lookup for RANK_ORDER; a rank not in this table (or None) is
# treated as sitting below "F", i.e. position -1.
RANK_INDEX: dict[str, int] = {rank: index for index, rank in enumerate(RANK_ORDER)}


# ── Baseline ──────────────────────────────────────────────────────────────

@dataclass
class GoalBaseline:
    """Per-metric best-ever values for a user on a chart or course.

    Each field is derived independently from whatever rows exist — they are
    not guaranteed to come from the same `user_scores` row.
    """

    clear_type: int | None   # None = no play (treat as clear_type 0/"NOPLAY" for comparisons)
    min_bp: int | None       # None = no BP data
    rank: str | None         # None = no rank (treat as below "F" for comparisons)
    rate: float | None       # None = no rate (treat as 0 for comparisons)


def _aggregate_baseline(rows) -> GoalBaseline:
    """Reduce a list of (clear_type, min_bp, rank, rate) row tuples to a
    per-metric-independent :class:`GoalBaseline`."""
    clear_values = [row.clear_type for row in rows if row.clear_type is not None]
    bp_values = [row.min_bp for row in rows if row.min_bp is not None]
    rank_values = [row.rank for row in rows if row.rank in RANK_INDEX]
    rate_values = [row.rate for row in rows if row.rate is not None]

    best_rank = max(rank_values, key=lambda r: RANK_INDEX[r]) if rank_values else None

    return GoalBaseline(
        clear_type=max(clear_values) if clear_values else None,
        min_bp=min(bp_values) if bp_values else None,
        rank=best_rank,
        rate=max(rate_values) if rate_values else None,
    )


def _chart_hash_condition(fumen_sha256: str | None, fumen_md5: str | None):
    """Dual sha256/md5 lookup per CLAUDE.md's "Fumen hash lookups" rule:
    match sha256-identified rows, plus md5-only (LR2) rows for the same
    chart. Never skip a row just because sha256 IS NULL.
    """
    if fumen_sha256 and fumen_md5:
        return or_(
            UserScore.fumen_sha256 == fumen_sha256,
            and_(UserScore.fumen_md5 == fumen_md5, UserScore.fumen_sha256.is_(None)),
        )
    if fumen_sha256:
        return UserScore.fumen_sha256 == fumen_sha256
    if fumen_md5:
        return UserScore.fumen_md5 == fumen_md5
    return None


async def compute_chart_baseline(
    db: AsyncSession,
    user_id: uuid.UUID,
    client_type: str,
    fumen_sha256: str | None,
    fumen_md5: str | None,
) -> GoalBaseline:
    """Best-ever per-metric baseline for a single chart, scoped to one
    client_type. Returns an all-``None`` baseline if no rows match.
    """
    condition = _chart_hash_condition(fumen_sha256, fumen_md5)
    if condition is None:
        return GoalBaseline(None, None, None, None)

    result = await db.execute(
        select(
            UserScore.clear_type,
            UserScore.min_bp,
            UserScore.rank,
            UserScore.rate,
        ).where(
            UserScore.user_id == user_id,
            UserScore.client_type == client_type,
            UserScore.fumen_hash_others.is_(None),
            condition,
        )
    )
    return _aggregate_baseline(result.all())


def _course_hash_condition(course: Course, client_type: str):
    """Build the `user_scores.fumen_hash_others` match condition for a course,
    mirroring `score_row_detail.match_course_from_hash` exactly (reversed:
    given the course, find the score rows that would have matched it).

    - lr2: the score's `fumen_hash_others` is a combined LR2 stage hash that
      *ends with* "".join(md5_list) — course_hash.endswith(joined) in the
      reference implementation.
    - beatoraja: the score's `fumen_hash_others` *equals* "".join(sha256_list)
      exactly.

    All values in the relevant list must be present (non-empty); otherwise
    there is no well-defined expected hash for this client_type and this
    returns ``None`` (caller should treat as "no matching rows").
    """
    if client_type == "lr2":
        values = list(course.md5_list or [])
        if not values or not all(values):
            return None
        joined = "".join(values)
        # "%" / "_" are not valid hex-hash characters, so no LIKE-escaping needed.
        return UserScore.fumen_hash_others.like(f"%{joined}")
    if client_type == "beatoraja":
        values = list(course.sha256_list or [])
        if not values or not all(values):
            return None
        joined = "".join(values)
        return UserScore.fumen_hash_others == joined
    return None


async def compute_course_baseline(
    db: AsyncSession,
    user_id: uuid.UUID,
    client_type: str,
    course_id: uuid.UUID,
) -> GoalBaseline:
    """Best-ever per-metric baseline for a course, scoped to one client_type.
    Returns an all-``None`` baseline if the course doesn't exist, has no
    hash-list data for this client_type, or no rows match.
    """
    course = await db.get(Course, course_id)
    if course is None:
        return GoalBaseline(None, None, None, None)

    condition = _course_hash_condition(course, client_type)
    if condition is None:
        return GoalBaseline(None, None, None, None)

    result = await db.execute(
        select(
            UserScore.clear_type,
            UserScore.min_bp,
            UserScore.rank,
            UserScore.rate,
        ).where(
            UserScore.user_id == user_id,
            UserScore.client_type == client_type,
            condition,
        )
    )
    return _aggregate_baseline(result.all())


# ── Target validation (pure, no DB access) ──────────────────────────────────

@dataclass
class GoalValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    improved_metrics: list[str] = field(default_factory=list)


def validate_goal_target(
    baseline: GoalBaseline,
    *,
    target_clear_type: int | None = None,
    target_min_bp: int | None = None,
    target_rank: str | None = None,
    target_rate: float | None = None,
) -> GoalValidationResult:
    """Validate a candidate goal target against the user's baseline (plan
    §3.2). Only metrics that are non-``None`` in the target are judged — an
    omitted metric is neither forbidden nor counted as an improvement.

    Overall ``ok`` requires: no selected metric regresses vs. baseline, AND
    at least one selected metric is a genuine improvement. This naturally
    rejects "nothing selected" and "NOPLAY-only" goals without a special
    case — see the report for verification that this falls out of the
    general rule.
    """
    errors: list[str] = []
    improved: list[str] = []
    selected = False

    if target_clear_type is not None:
        selected = True
        base_clear = baseline.clear_type or 0
        if target_clear_type < base_clear:
            errors.append("clear_type_worse")
        elif target_clear_type > base_clear:
            improved.append("clear_type")

    if target_min_bp is not None:
        selected = True
        if baseline.min_bp is not None:
            if target_min_bp > baseline.min_bp:
                errors.append("min_bp_worse")
            elif target_min_bp < baseline.min_bp:
                improved.append("min_bp")
        # else: no baseline BP data at all. Any target_min_bp is allowed (not
        # forbidden), but we do NOT count it as a scored "improvement" here —
        # judgment call: the plan doesn't require this edge case explicitly,
        # and treating "some BP goal when there was none" as an automatic
        # improvement would let a goal be created (and satisfied) with *only*
        # this metric selected and no way to have "regressed" from a baseline
        # that doesn't exist. See report for discussion.

    if target_rank is not None:
        selected = True
        base_rank_pos = RANK_INDEX.get(baseline.rank, -1) if baseline.rank else -1
        target_rank_pos = RANK_INDEX.get(target_rank)
        if target_rank_pos is None:
            errors.append("invalid_rank")
        elif target_rank_pos < base_rank_pos:
            errors.append("rank_worse")
        elif target_rank_pos > base_rank_pos:
            improved.append("rank")

    if target_rate is not None:
        selected = True
        base_rate = baseline.rate or 0.0
        if target_rate < base_rate:
            errors.append("rate_worse")
        elif target_rate > base_rate:
            improved.append("rate")

    if not selected:
        errors.append("no_metric_selected")
    elif not errors and not improved:
        errors.append("no_improvement")

    ok = selected and not errors and len(improved) > 0
    return GoalValidationResult(ok=ok, errors=errors, improved_metrics=improved)


# ── Achievement matching (batch, DB-touching) ───────────────────────────────

@dataclass
class GoalAchievementCandidate:
    user_id: uuid.UUID
    client_type: str
    goal_type: str            # "chart" | "course"
    fumen_sha256: str | None  # chart candidates only
    fumen_md5: str | None     # chart candidates only
    course_id: uuid.UUID | None  # course candidates only
    clear_type: int | None
    min_bp: int | None
    rank: str | None
    rate: float | None
    recorded_at: datetime | None  # the record's own recorded_at — becomes achieved_recorded_at


def _candidate_identity_condition(candidate: GoalAchievementCandidate):
    """Build the SQL condition selecting active goals whose identity matches
    this candidate, using the indexed (user_id, client_type, hash/course_id)
    columns from Task 7's migration."""
    if candidate.goal_type == "chart":
        hash_conditions = []
        if candidate.fumen_sha256:
            hash_conditions.append(UserGoal.fumen_sha256 == candidate.fumen_sha256)
        if candidate.fumen_md5:
            hash_conditions.append(UserGoal.fumen_md5 == candidate.fumen_md5)
        if not hash_conditions:
            return None
        return and_(
            UserGoal.goal_type == "chart",
            UserGoal.user_id == candidate.user_id,
            UserGoal.client_type == candidate.client_type,
            or_(*hash_conditions),
        )
    if candidate.goal_type == "course":
        if candidate.course_id is None:
            return None
        return and_(
            UserGoal.goal_type == "course",
            UserGoal.user_id == candidate.user_id,
            UserGoal.client_type == candidate.client_type,
            UserGoal.course_id == candidate.course_id,
        )
    return None


def _candidate_matches_goal_identity(candidate: GoalAchievementCandidate, goal: UserGoal) -> bool:
    """Python-side re-check that a fetched goal really corresponds to this
    candidate's identity (the SQL condition above already narrows to this,
    but a single batched query can return goals for other candidates too)."""
    if goal.goal_type != candidate.goal_type:
        return False
    if goal.user_id != candidate.user_id or goal.client_type != candidate.client_type:
        return False
    if candidate.goal_type == "chart":
        return (
            (candidate.fumen_sha256 is not None and candidate.fumen_sha256 == goal.fumen_sha256)
            or (candidate.fumen_md5 is not None and candidate.fumen_md5 == goal.fumen_md5)
        )
    if candidate.goal_type == "course":
        return candidate.course_id is not None and candidate.course_id == goal.course_id
    return False


def _candidate_satisfies_targets(candidate: GoalAchievementCandidate, goal: UserGoal) -> bool:
    """Whether the candidate's own values (not baseline) satisfy all of the
    goal's non-null target_* fields — same directional comparisons as
    `validate_goal_target`, but against the actual achieved value."""
    if goal.target_clear_type is not None:
        if candidate.clear_type is None or candidate.clear_type < goal.target_clear_type:
            return False
    if goal.target_min_bp is not None:
        if candidate.min_bp is None or candidate.min_bp > goal.target_min_bp:
            return False
    if goal.target_rank is not None:
        candidate_pos = RANK_INDEX.get(candidate.rank, -1) if candidate.rank else -1
        target_pos = RANK_INDEX.get(goal.target_rank, -1)
        if candidate_pos < target_pos:
            return False
    if goal.target_rate is not None:
        if candidate.rate is None or candidate.rate < goal.target_rate:
            return False
    return True


async def evaluate_and_mark_achieved(
    db: AsyncSession,
    candidates: list[GoalAchievementCandidate],
) -> list[uuid.UUID]:
    """Batch-match a list of newly-synced score candidates against active
    goals and atomically transition any that are fully satisfied.

    Runs a single indexed SELECT across all candidates (not one query per
    candidate — plan §3.3's O(U + G_match) requirement), then one
    conditional `UPDATE ... WHERE status='active' ... RETURNING` per goal
    that is actually satisfied. The `WHERE status='active'` guard makes this
    safe to call twice with the same candidates (e.g. a sync retry) — the
    second call is a no-op for goals already transitioned.
    """
    if not candidates:
        return []

    identity_conditions = [
        condition
        for condition in (_candidate_identity_condition(c) for c in candidates)
        if condition is not None
    ]
    if not identity_conditions:
        return []

    result = await db.execute(
        select(UserGoal).where(
            UserGoal.status == "active",
            UserGoal.deleted_at.is_(None),
            or_(*identity_conditions),
        )
    )
    goals = result.scalars().all()

    achieved_goal_ids: list[uuid.UUID] = []
    for goal in goals:
        satisfying_candidate = next(
            (
                c
                for c in candidates
                if _candidate_matches_goal_identity(c, goal) and _candidate_satisfies_targets(c, goal)
            ),
            None,
        )
        if satisfying_candidate is None:
            continue

        transition = await db.execute(
            update(UserGoal)
            .where(
                UserGoal.goal_id == goal.goal_id,
                UserGoal.status == "active",
                UserGoal.deleted_at.is_(None),
            )
            .values(
                status="achieved",
                # func.now() is dialect-aware: CURRENT_TIMESTAMP on SQLite, now() on Postgres.
                achieved_at=func.now(),
                achieved_recorded_at=satisfying_candidate.recorded_at,
            )
            .returning(UserGoal.goal_id)
        )
        row = transition.first()
        if row is not None:
            achieved_goal_ids.append(row[0])

    return achieved_goal_ids
