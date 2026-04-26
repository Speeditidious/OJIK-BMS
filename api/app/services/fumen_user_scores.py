"""Shared score/tag join logic for fumen list endpoints.

Extracted from tables.py::get_table_songs so that fumens.py::list_fumens can
reuse the same aggregation path without duplicating code.
"""
from __future__ import annotations

import math
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fumen import Fumen, UserFumenTag
from app.models.score import UserScore
from app.services.clear_type_display import display_clear_type
from app.services.client_aggregation import (
    CLIENT_LABEL,
    PerClientBest,
    aggregate_source_client,
)

FumenKey = tuple[str | None, str | None]


# ── Pydantic schemas (re-exported so tables.py / fumens.py both import from here) ──

class TableFumenScore(BaseModel):
    """Per-field best scores for a fumen, derived from user_scores rows."""

    best_clear_type: int | None
    best_exscore: int | None
    rate: float | None
    rank: str | None
    best_min_bp: int | None
    source_client: str | None
    source_client_detail: dict | None
    options: dict | None = None
    client_type: str | None = None
    play_count: int | None = None


class UserTagRead(BaseModel):
    id: str
    tag: str

    model_config = ConfigDict(from_attributes=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_rate_rank(exscore: int, notes_total: int) -> tuple[float, str]:
    """Compute rate (%) and rank from exscore and notes_total."""
    max_ex = notes_total * 2
    if max_ex <= 0:
        return 0.0, "F"
    rate = math.floor(exscore / max_ex * 10000) / 100
    for rank, threshold in [("AAA", 16), ("AA", 14), ("A", 12), ("B", 10), ("C", 8), ("D", 6), ("E", 4)]:
        if exscore * 9 >= notes_total * threshold:
            return rate, rank
    return rate, "F"


# ── Public functions ───────────────────────────────────────────────────────────

async def fetch_user_score_map(
    db: AsyncSession,
    user_id: uuid.UUID,
    fumens: list[Fumen],
) -> dict[FumenKey, TableFumenScore]:
    """Build per-fumen aggregated best user scores for a list of fumens.

    Mirrors the logic inlined in tables.py::get_table_songs (score aggregation
    section). Handles LR2 sha256=NULL rows per CLAUDE.md "Fumen hash lookups".
    """
    if not fumens:
        return {}

    sha256_list = [f.sha256 for f in fumens if f.sha256]
    md5_list = [f.md5 for f in fumens if f.md5 and not f.sha256]
    md5_for_sha256_fumens = [f.md5 for f in fumens if f.sha256 and f.md5]
    md5_to_key: dict[str, FumenKey] = {
        f.md5: (f.sha256, None)
        for f in fumens
        if f.sha256 and f.md5
    }

    score_conditions = []
    if sha256_list:
        score_conditions.append(UserScore.fumen_sha256.in_(sha256_list))
    if md5_list:
        score_conditions.append(
            (UserScore.fumen_md5.in_(md5_list)) & UserScore.fumen_sha256.is_(None)
        )
    if md5_for_sha256_fumens:
        score_conditions.append(
            (UserScore.fumen_md5.in_(md5_for_sha256_fumens)) & UserScore.fumen_sha256.is_(None)
        )

    if not score_conditions:
        return {}

    combined = score_conditions[0]
    for c in score_conditions[1:]:
        combined = combined | c

    score_rows_result = await db.execute(
        select(UserScore).where(
            UserScore.user_id == user_id,
            UserScore.fumen_hash_others.is_(None),
            combined,
        ).order_by(UserScore.recorded_at.desc().nullslast())
    )
    score_rows = score_rows_result.scalars().all()

    notes_map: dict[FumenKey, int | None] = {
        (f.sha256, f.md5 if not f.sha256 else None): f.notes_total
        for f in fumens
    }

    per_fumen_client: dict[FumenKey, dict[str, dict[str, Any]]] = {}
    for s in score_rows:
        if s.fumen_sha256 is None and s.fumen_md5 and s.fumen_md5 in md5_to_key:
            key = md5_to_key[s.fumen_md5]
        else:
            key = (s.fumen_sha256, s.fumen_md5 if not s.fumen_sha256 else None)

        per_client = per_fumen_client.setdefault(key, {})
        ct = s.client_type
        if ct not in per_client:
            per_client[ct] = {
                "clear_type": None, "exscore": None, "rate": None,
                "rank": None, "min_bp": None, "options": None, "play_count": None,
            }
        entry = per_client[ct]
        if s.clear_type is not None and (entry["clear_type"] is None or s.clear_type > entry["clear_type"]):
            entry["clear_type"] = s.clear_type
            entry["options"] = s.options
        if s.exscore is not None and (entry["exscore"] is None or s.exscore > entry["exscore"]):
            entry["exscore"] = s.exscore
            entry["rate"] = s.rate
            entry["rank"] = s.rank
        if s.min_bp is not None and (entry["min_bp"] is None or s.min_bp < entry["min_bp"]):
            entry["min_bp"] = s.min_bp
        if s.play_count is not None:
            entry["play_count"] = (entry["play_count"] or 0) + s.play_count

    score_map: dict[FumenKey, TableFumenScore] = {}
    for key, per_client in per_fumen_client.items():
        raw: dict[str, Any] = {
            "clear_type": None, "exscore": None, "rate": None, "rank": None,
            "min_bp": None, "options": None, "best_client_type": None, "play_count": None,
        }
        for ct, entry in per_client.items():
            client_label = CLIENT_LABEL.get(ct, ct.upper())
            if entry["clear_type"] is not None and (raw["clear_type"] is None or entry["clear_type"] > raw["clear_type"]):
                raw["clear_type"] = entry["clear_type"]
                raw["options"] = entry["options"]
                raw["best_client_type"] = ct
            if entry["exscore"] is not None and (raw["exscore"] is None or entry["exscore"] > raw["exscore"]):
                raw["exscore"] = entry["exscore"]
                raw["rate"] = entry["rate"]
                raw["rank"] = entry["rank"]
            if entry["min_bp"] is not None and (raw["min_bp"] is None or entry["min_bp"] < raw["min_bp"]):
                raw["min_bp"] = entry["min_bp"]
            raw["play_count"] = (raw["play_count"] or 0) + (entry["play_count"] or 0)
            _ = client_label  # used implicitly via raw["best_client_type"]

        source_client, source_client_detail = aggregate_source_client(
            PerClientBest(
                client_type=ct,
                clear_type=entry["clear_type"],
                exscore=entry["exscore"],
                rate=entry["rate"],
                rank=entry["rank"],
                min_bp=entry["min_bp"],
            )
            for ct, entry in per_client.items()
        )

        rate = raw["rate"]
        rank = raw["rank"]
        if (rate is None or rank is None) and raw["exscore"] is not None:
            nt = notes_map.get(key)
            if nt:
                rate, rank = _compute_rate_rank(raw["exscore"], nt)

        clear_type = display_clear_type(raw["clear_type"], exscore=raw["exscore"], rate=rate)

        score_map[key] = TableFumenScore(
            best_clear_type=clear_type,
            best_exscore=raw["exscore"],
            rate=rate,
            rank=rank,
            best_min_bp=raw["min_bp"],
            source_client=source_client,
            source_client_detail=source_client_detail,
            options=raw["options"],
            client_type=raw["best_client_type"],
            play_count=raw["play_count"] or None,
        )

    return score_map


async def fetch_user_tag_map(
    db: AsyncSession,
    user_id: uuid.UUID,
    fumens: list[Fumen],
) -> dict[FumenKey, list[UserTagRead]]:
    """Build per-fumen user tag lists for a list of fumens."""
    if not fumens:
        return {}

    sha256_list_tags = [f.sha256 for f in fumens if f.sha256]
    md5_list_tags = [f.md5 for f in fumens if f.md5 and not f.sha256]

    tag_conditions = []
    if sha256_list_tags:
        tag_conditions.append(UserFumenTag.fumen_sha256.in_(sha256_list_tags))
    if md5_list_tags:
        tag_conditions.append(
            (UserFumenTag.fumen_md5.in_(md5_list_tags)) & UserFumenTag.fumen_sha256.is_(None)
        )

    if not tag_conditions:
        return {}

    combined_tag = tag_conditions[0]
    for c in tag_conditions[1:]:
        combined_tag = combined_tag | c

    tag_rows_result = await db.execute(
        select(UserFumenTag).where(
            UserFumenTag.user_id == user_id,
            combined_tag,
        )
    )

    tag_map: dict[FumenKey, list[UserTagRead]] = {}
    for tag in tag_rows_result.scalars().all():
        t_key: FumenKey = (tag.fumen_sha256, tag.fumen_md5 if not tag.fumen_sha256 else None)
        tag_map.setdefault(t_key, []).append(UserTagRead(id=str(tag.id), tag=tag.tag))

    return tag_map
