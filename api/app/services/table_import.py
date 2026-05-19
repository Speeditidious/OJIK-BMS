"""Shared helpers for difficulty table import: fumen upsert, course sync."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.utils.text_normalization import normalize_display_text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _build_artist(item: dict) -> str:
    """Build artist string, appending obj name_diff if present and not a URL."""
    artist = normalize_display_text(item.get("artist") or "") or ""
    name_diff = normalize_display_text(item.get("name_diff") or "") or ""
    if name_diff and " / obj: " not in artist and not name_diff.startswith(("http:/", "https:/")):
        artist = f"{artist} / obj: {name_diff}"
    return artist


async def upsert_fumens(db: AsyncSession, table_id: uuid.UUID, songs: list[dict]) -> set[uuid.UUID]:
    """Upsert fumen rows and table membership entries for one difficulty table.

    Returns the set of ``fumen_id`` values seen in this import. Membership is
    stored in ``fumen_table_entries`` so two table imports never rewrite the
    same JSONB column and cannot drop each other's entries.
    """
    from sqlalchemy import or_, select, text, update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.fumen import Fumen, FumenTableEntry

    normalized = _normalize_song_rows(songs)
    if not normalized:
        return set()

    sha256s = sorted({row["sha256"] for row in normalized if row["sha256"]})
    md5s = sorted({row["md5"] for row in normalized if row["md5"]})

    existing_rows = []
    conditions = []
    if sha256s:
        conditions.append(Fumen.sha256.in_(sha256s))
    if md5s:
        conditions.append(Fumen.md5.in_(md5s))
    if conditions:
        result = await db.execute(select(Fumen).where(or_(*conditions)))
        existing_rows = list(result.scalars().all())

    by_sha: dict[str, Fumen] = {f.sha256: f for f in existing_rows if f.sha256}
    by_md5: dict[str, Fumen] = {f.md5: f for f in existing_rows if f.md5}

    # If the same chart exists as both a sha256 row and an md5-only row, fold
    # the md5-only row into the sha256 row before adding the new table entry.
    for row in normalized:
        sha256 = row["sha256"]
        md5 = row["md5"]
        if not sha256 or not md5:
            continue
        sha_row = by_sha.get(sha256)
        md5_row = by_md5.get(md5)
        if sha_row is not None and md5_row is not None and sha_row.fumen_id != md5_row.fumen_id:
            await _merge_duplicate_fumen(db, canonical=sha_row, duplicate=md5_row)
            by_md5[md5] = sha_row

    # Promote md5-only rows when a later table gives us the sha256 for the same
    # md5. This avoids creating duplicate fumen rows because uq_fumens_md5 only
    # applies while sha256 IS NULL.
    promoted_ids: set[uuid.UUID] = set()
    for row in normalized:
        sha256 = row["sha256"]
        md5 = row["md5"]
        if not sha256 or not md5 or sha256 in by_sha or md5 not in by_md5:
            continue
        existing = by_md5[md5]
        if existing.sha256 and existing.sha256 != sha256:
            continue
        update_vals = _metadata_update_values(row)
        update_vals["sha256"] = sha256
        await db.execute(
            update(Fumen)
            .where(Fumen.fumen_id == existing.fumen_id)
            .values(**update_vals)
            .execution_options(synchronize_session=False)
        )
        existing.sha256 = sha256
        by_sha[sha256] = existing
        promoted_ids.add(existing.fumen_id)

    sha_rows = [_fumen_insert_values(row) for row in normalized if row["sha256"] and row["sha256"] not in by_sha]
    if sha_rows:
        await db.execute(
            pg_insert(Fumen)
            .values(sha_rows)
            .on_conflict_do_update(
                index_elements=[Fumen.sha256],
                index_where=Fumen.sha256.isnot(None),
                set_={
                    "md5": text("COALESCE(EXCLUDED.md5, fumens.md5)"),
                    "title": text("COALESCE(EXCLUDED.title, fumens.title)"),
                    "artist": text("COALESCE(EXCLUDED.artist, fumens.artist)"),
                    "file_url": text("COALESCE(EXCLUDED.file_url, fumens.file_url)"),
                    "file_url_diff": text("COALESCE(EXCLUDED.file_url_diff, fumens.file_url_diff)"),
                    "updated_at": text("now()"),
                },
            )
        )

    md5_rows = [
        _fumen_insert_values(row)
        for row in normalized
        if not row["sha256"] and row["md5"] and row["md5"] not in by_md5
    ]
    if md5_rows:
        await db.execute(
            pg_insert(Fumen)
            .values(md5_rows)
            .on_conflict_do_update(
                index_elements=[Fumen.md5],
                index_where=text("md5 IS NOT NULL AND sha256 IS NULL"),
                set_={
                    "title": text("COALESCE(EXCLUDED.title, fumens.title)"),
                    "artist": text("COALESCE(EXCLUDED.artist, fumens.artist)"),
                    "file_url": text("COALESCE(EXCLUDED.file_url, fumens.file_url)"),
                    "file_url_diff": text("COALESCE(EXCLUDED.file_url_diff, fumens.file_url_diff)"),
                    "updated_at": text("now()"),
                },
            )
        )

    # Update metadata for rows that already existed. This is a small bounded
    # loop over touched rows, while inserts and table-entry writes stay batched.
    for row in normalized:
        existing = by_sha.get(row["sha256"]) if row["sha256"] else by_md5.get(row["md5"])
        if existing is None or existing.fumen_id in promoted_ids:
            continue
        update_vals = _metadata_update_values(row)
        if update_vals:
            await db.execute(
                update(Fumen)
                .where(Fumen.fumen_id == existing.fumen_id)
                .values(**update_vals)
                .execution_options(synchronize_session=False)
            )

    # Re-fetch touched rows so every normalized input has the canonical fumen_id.
    result = await db.execute(select(Fumen).where(or_(*conditions)))
    touched = list(result.scalars().all())
    by_sha = {f.sha256: f for f in touched if f.sha256}
    by_md5 = {f.md5: f for f in touched if f.md5}

    entry_rows: list[dict[str, Any]] = []
    seen_fumen_ids: set[uuid.UUID] = set()
    touched_sha256s: set[str] = set()
    touched_md5s: set[str] = set()
    for row in normalized:
        fumen = by_sha.get(row["sha256"]) if row["sha256"] else by_md5.get(row["md5"])
        if fumen is None:
            continue
        seen_fumen_ids.add(fumen.fumen_id)
        if fumen.sha256:
            touched_sha256s.add(fumen.sha256)
        if fumen.md5:
            touched_md5s.add(fumen.md5)
        entry_rows.append({"fumen_id": fumen.fumen_id, "table_id": table_id, "level": row["level"]})

    if entry_rows:
        await db.execute(
            pg_insert(FumenTableEntry)
            .values(entry_rows)
            .on_conflict_do_update(
                index_elements=[FumenTableEntry.fumen_id, FumenTableEntry.table_id],
                set_={"level": text("EXCLUDED.level"), "updated_at": text("now()")},
            )
        )

    await _backfill_user_scores_for_hashes(db, sha256s=touched_sha256s, md5s=touched_md5s)
    await db.flush()
    return seen_fumen_ids


async def remove_stale_entries(db: AsyncSession, table_id: uuid.UUID, seen_fumen_ids: set[uuid.UUID]) -> int:
    """Remove entries for fumens no longer present in one difficulty table.

    Returns the number of table-entry rows deleted.
    """
    from sqlalchemy import delete

    from app.models.fumen import FumenTableEntry

    stmt = delete(FumenTableEntry).where(FumenTableEntry.table_id == table_id)
    if seen_fumen_ids:
        stmt = stmt.where(FumenTableEntry.fumen_id.not_in(seen_fumen_ids))
    result = await db.execute(stmt)
    return result.rowcount or 0


def _normalize_song_rows(songs: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_sha: dict[str, dict[str, Any]] = {}
    by_md5: dict[str, dict[str, Any]] = {}

    for item in songs:
        sha256_raw = (item.get("sha256") or "").strip().lower()
        md5_raw = (item.get("md5") or "").strip().lower()
        sha256 = sha256_raw if sha256_raw and len(sha256_raw) <= 64 else None
        md5 = md5_raw if md5_raw and len(md5_raw) <= 32 else None
        if not sha256 and not md5:
            continue

        row = by_sha.get(sha256) if sha256 else None
        if row is None and md5:
            row = by_md5.get(md5)
        if row is None:
            row = {"sha256": sha256, "md5": md5}
            rows.append(row)
        elif sha256 and not row.get("sha256"):
            row["sha256"] = sha256
        elif md5 and not row.get("md5"):
            row["md5"] = md5

        row.update(
            {
                "title": normalize_display_text(item.get("title")) or None,
                "artist": _build_artist(item) or None,
                "file_url": item.get("url") or None,
                "file_url_diff": item.get("url_diff") or None,
                "level": str(item.get("level", "")).strip(),
            }
        )
        if row.get("sha256"):
            by_sha[row["sha256"]] = row
        if row.get("md5"):
            by_md5[row["md5"]] = row

    return rows


def _fumen_insert_values(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sha256": row["sha256"],
        "md5": row["md5"],
        "title": row.get("title"),
        "artist": row.get("artist"),
        "file_url": row.get("file_url"),
        "file_url_diff": row.get("file_url_diff"),
    }


def _metadata_update_values(row: dict[str, Any]) -> dict[str, Any]:
    update_vals: dict[str, Any] = {}
    for key in ("title", "artist", "file_url", "file_url_diff"):
        if row.get(key):
            update_vals[key] = row[key]
    if update_vals:
        update_vals["updated_at"] = datetime.now(UTC)
    return update_vals


async def _merge_duplicate_fumen(db: AsyncSession, *, canonical: Any, duplicate: Any) -> None:
    """Move duplicate fumen references to canonical before deleting it."""
    from sqlalchemy import text, update

    from app.models.fumen import Fumen

    canonical_id = canonical.fumen_id
    duplicate_id = duplicate.fumen_id
    await db.execute(
        update(Fumen)
        .where(Fumen.fumen_id == canonical_id)
        .values(
            md5=canonical.md5 or duplicate.md5,
            title=canonical.title or duplicate.title,
            artist=canonical.artist or duplicate.artist,
            file_url=canonical.file_url or duplicate.file_url,
            file_url_diff=canonical.file_url_diff or duplicate.file_url_diff,
            updated_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        text("""
            INSERT INTO fumen_table_entries (fumen_id, table_id, level, created_at, updated_at)
            SELECT :canonical_id, table_id, level, created_at, now()
            FROM fumen_table_entries
            WHERE fumen_id = :duplicate_id
            ON CONFLICT (fumen_id, table_id) DO NOTHING
        """),
        {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
    )
    await db.execute(
        text("""
            INSERT INTO user_fumen_tags (id, user_id, fumen_id, tag, display_order)
            SELECT gen_random_uuid(), user_id, :canonical_id, tag, display_order
            FROM user_fumen_tags
            WHERE fumen_id = :duplicate_id
            ON CONFLICT (user_id, fumen_id, tag) DO UPDATE
            SET display_order = LEAST(user_fumen_tags.display_order, EXCLUDED.display_order)
        """),
        {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
    )
    await db.execute(
        text("UPDATE user_scores SET fumen_id = :canonical_id WHERE fumen_id = :duplicate_id"),
        {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
    )
    await db.execute(text("DELETE FROM fumens WHERE fumen_id = :duplicate_id"), {"duplicate_id": duplicate_id})


async def _backfill_user_scores_for_hashes(
    db: AsyncSession,
    *,
    sha256s: set[str],
    md5s: set[str],
) -> None:
    """Fill user_scores.fumen_id for newly registered fumens touched by hashes."""
    from sqlalchemy import text

    if sha256s:
        await db.execute(
            text("""
                UPDATE user_scores us
                SET fumen_id = f.fumen_id
                FROM fumens f
                WHERE us.fumen_id IS NULL
                  AND us.fumen_hash_others IS NULL
                  AND us.fumen_sha256 = f.sha256
                  AND us.fumen_sha256 = ANY(:sha256s)
            """),
            {"sha256s": sorted(sha256s)},
        )
    if md5s:
        await db.execute(
            text("""
                UPDATE user_scores us
                SET fumen_id = f.fumen_id
                FROM fumens f
                WHERE us.fumen_id IS NULL
                  AND us.fumen_hash_others IS NULL
                  AND us.fumen_sha256 IS NULL
                  AND us.fumen_md5 = f.md5
                  AND us.fumen_md5 = ANY(:md5s)
            """),
            {"md5s": sorted(md5s)},
        )


async def _build_sha256_list(db: AsyncSession, md5_list: list) -> list:
    """Build a sha256 list parallel to md5_list.

    Queries the fumens table first (fast path), then falls back to
    user_scores for any md5 still missing a sha256. This covers cases
    where fumens.sha256 was never populated from a table header (LR2-only
    tables), but a Beatoraja user has synced a (fumen_sha256, fumen_md5)
    pair that supplies the mapping.

    Returns:
        List of same length as md5_list. Unknown positions are None.
    """
    from sqlalchemy import select

    from app.models.fumen import Fumen
    from app.models.score import UserScore

    non_null_md5s = [m for m in md5_list if m]
    if not non_null_md5s:
        return [None] * len(md5_list)

    # 1) Primary: fumens table
    fumens_result = await db.execute(
        select(Fumen.md5, Fumen.sha256).where(
            Fumen.md5.in_(non_null_md5s),
            Fumen.sha256.isnot(None),
        )
    )
    md5_to_sha256: dict[str, str] = {row.md5: row.sha256 for row in fumens_result.all()}

    # 2) Fallback: user_scores for any md5 still missing sha256
    missing = [m for m in non_null_md5s if m not in md5_to_sha256]
    if missing:
        scores_result = await db.execute(
            select(UserScore.fumen_md5, UserScore.fumen_sha256).where(
                UserScore.fumen_md5.in_(missing),
                UserScore.fumen_sha256.isnot(None),
            )
        )
        for row in scores_result.all():
            if row.fumen_md5 not in md5_to_sha256:
                md5_to_sha256[row.fumen_md5] = row.fumen_sha256

    return [md5_to_sha256.get(m) if m else None for m in md5_list]


CATEGORY_ORDER = ["layout", "ln", "gauge", "judge", "speed"]
CATEGORY_TOKENS: dict[str, list[str]] = {
    "layout": ["grade_mirror", "grade", "grade_random"],
    "ln": ["ln", "cn", "hcn"],
    "gauge": ["gauge_lr2", "gauge_5k", "gauge_7k", "gauge_9k", "gauge_24k"],
    "judge": ["no_good", "no_great"],
    "speed": ["no_speed"],
}
NEGATIVE_CATEGORIES = {"speed"}


def _hash_list_key(values: list[str | None]) -> tuple[str, ...]:
    """Return a normalized ordered hash-list key."""
    return tuple(str(value).strip().lower() for value in values if str(value).strip())


def _normalize_constraint(values: Any) -> list[str]:
    """Normalize course constraint tokens, preserving first-seen order."""
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        token = value.strip().lower()
        if token and token not in seen:
            seen.add(token)
            normalized.append(token)
    return normalized


def _normalize_hash_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def _normalize_course_payload(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    md5_list = _normalize_hash_values(raw.get("md5_list") or raw.get("md5") or [])
    sha256_list = _normalize_hash_values(
        raw.get("sha256_list") or raw.get("sha256") or raw.get("sha256hash") or []
    )
    if not name or (not md5_list and not sha256_list):
        return None
    return {
        "name": name,
        "md5_list": md5_list,
        "sha256_list": sha256_list,
        "constraint": _normalize_constraint(raw.get("constraint") or []),
    }


def _course_payload_key(course_data: dict[str, Any]) -> tuple[Any, ...]:
    md5_key = _hash_list_key(course_data.get("md5_list") or [])
    sha256_key = _hash_list_key(course_data.get("sha256_list") or [])
    hash_kind = "md5" if md5_key else "sha256"
    hash_key = md5_key if md5_key else sha256_key
    return (
        course_data["name"],
        hash_kind,
        hash_key,
        tuple(sorted(course_data.get("constraint") or [])),
    )


def _course_import_key(course: Any) -> tuple[Any, ...]:
    md5_key = _hash_list_key(course.md5_list or [])
    sha256_key = _hash_list_key(course.sha256_list or [])
    hash_kind = "md5" if md5_key else "sha256"
    hash_key = md5_key if md5_key else sha256_key
    return (
        course.name,
        hash_kind,
        hash_key,
        tuple(sorted(course.constraint or [])),
    )


def _course_legacy_match_key(course: Any) -> tuple[Any, ...]:
    md5_key = _hash_list_key(course.md5_list or [])
    sha256_key = _hash_list_key(course.sha256_list or [])
    hash_kind = "md5" if md5_key else "sha256"
    hash_key = md5_key if md5_key else sha256_key
    return (course.name, hash_kind, hash_key)


def _course_payload_legacy_match_key(course_data: dict[str, Any]) -> tuple[Any, ...]:
    md5_key = _hash_list_key(course_data.get("md5_list") or [])
    sha256_key = _hash_list_key(course_data.get("sha256_list") or [])
    hash_kind = "md5" if md5_key else "sha256"
    hash_key = md5_key if md5_key else sha256_key
    return (course_data["name"], hash_kind, hash_key)


def _group_key(course: Any) -> tuple[str, tuple[str, ...]]:
    """Return active-selection key. Names and constraints are intentionally ignored."""
    md5_key = _hash_list_key(course.md5_list or [])
    if md5_key:
        return ("md5", md5_key)
    return ("sha256", _hash_list_key(course.sha256_list or []))


def _filter_by_category(candidates: list[Any], category: str) -> list[Any]:
    tokens = CATEGORY_TOKENS[category]

    def _has(course: Any, token: str) -> bool:
        return token in (course.constraint or [])

    if category in NEGATIVE_CATEGORIES:
        without = [course for course in candidates if not _has(course, tokens[0])]
        return without if without else candidates

    has_any = [course for course in candidates if any(_has(course, token) for token in tokens)]
    if not has_any:
        return candidates
    for preferred in tokens:
        subset = [course for course in has_any if _has(course, preferred)]
        if subset:
            return subset
    return has_any


def select_active(group: list[Any]) -> Any:
    """Return the single active Course winner for one identical hash-list group."""
    if len(group) == 1:
        return group[0]

    remaining = list(group)
    for category in CATEGORY_ORDER:
        if len(remaining) == 1:
            return remaining[0]
        filtered = _filter_by_category(remaining, category)
        if filtered:
            remaining = filtered

    remaining.sort(key=lambda course: (course.name, str(course.id) if getattr(course, "id", None) else ""))
    return remaining[0]


async def _fill_sha256_lists_for_courses(db: AsyncSession, courses: list[Any]) -> None:
    """Fill active course sha256 lists with one fumens query and one score fallback query."""
    from sqlalchemy import select

    from app.models.fumen import Fumen
    from app.models.score import UserScore

    md5s = sorted(
        {
            md5
            for course in courses
            for md5 in _normalize_hash_values(course.md5_list or [])
        }
    )
    if not md5s:
        return

    fumens_result = await db.execute(
        select(Fumen.md5, Fumen.sha256).where(
            Fumen.md5.in_(md5s),
            Fumen.sha256.isnot(None),
        )
    )
    md5_to_sha256: dict[str, str] = {
        row.md5: row.sha256 for row in fumens_result.all() if row.md5 and row.sha256
    }

    missing = [md5 for md5 in md5s if md5 not in md5_to_sha256]
    if missing:
        scores_result = await db.execute(
            select(UserScore.fumen_md5, UserScore.fumen_sha256).where(
                UserScore.fumen_md5.in_(missing),
                UserScore.fumen_sha256.isnot(None),
            )
        )
        for row in scores_result.all():
            if row.fumen_md5 and row.fumen_sha256 and row.fumen_md5 not in md5_to_sha256:
                md5_to_sha256[row.fumen_md5] = row.fumen_sha256

    for course in courses:
        md5_list = _normalize_hash_values(course.md5_list or [])
        if md5_list:
            course.sha256_list = [md5_to_sha256.get(md5) for md5 in md5_list]


async def upsert_courses(
    db: AsyncSession,
    table_id: uuid.UUID,
    courses: list[dict[str, Any]],
) -> dict[str, int]:
    """Sync courses for one table, applying constraint-based active selection."""
    from sqlalchemy import select

    from app.models.course import Course

    result = await db.execute(
        select(Course).where(Course.source_table_id == table_id)
    )
    existing_rows = list(result.scalars().all())
    existing: dict[tuple[Any, ...], Course] = {}
    legacy_constraintless: dict[tuple[Any, ...], list[tuple[tuple[Any, ...], Course]]] = {}
    duplicate_existing: list[Course] = []
    for course in existing_rows:
        key = _course_import_key(course)
        if key in existing:
            duplicate_existing.append(course)
        else:
            existing[key] = course
            if not (course.constraint or []):
                legacy_constraintless.setdefault(_course_legacy_match_key(course), []).append((key, course))

    incoming_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for raw in courses:
        normalized = _normalize_course_payload(raw)
        if normalized is not None:
            incoming_by_key[_course_payload_key(normalized)] = normalized

    inserted = 0
    updated = 0
    deactivated = 0
    seen_keys: set[tuple[Any, ...]] = set()

    for key, course_data in incoming_by_key.items():
        seen_keys.add(key)
        md5_list = course_data["md5_list"]
        sha256_list_from_header = course_data["sha256_list"] or None
        course_constraint = course_data["constraint"]

        legacy_match = None
        if key not in existing:
            candidates = legacy_constraintless.get(_course_payload_legacy_match_key(course_data), [])
            while candidates:
                old_key, candidate = candidates.pop(0)
                if old_key in existing and existing[old_key] is candidate:
                    legacy_match = (old_key, candidate)
                    break

        if key in existing or legacy_match is not None:
            if legacy_match is not None:
                old_key, course = legacy_match
                existing.pop(old_key, None)
                existing[key] = course
            else:
                course = existing[key]
            course.name = course_data["name"]
            course.md5_list = md5_list
            if sha256_list_from_header or not md5_list:
                course.sha256_list = sha256_list_from_header
            course.constraint = course_constraint
            course.is_active = True
            course.synced_at = datetime.now(UTC)
            updated += 1
        else:
            course = Course(
                name=course_data["name"],
                source_table_id=table_id,
                md5_list=md5_list,
                sha256_list=sha256_list_from_header,
                constraint=course_constraint,
                is_active=True,
                dan_title="",
                synced_at=datetime.now(UTC),
            )
            db.add(course)
            existing[key] = course
            inserted += 1

    for key, course in existing.items():
        if key not in seen_keys and course.is_active:
            course.is_active = False
            deactivated += 1

    for course in duplicate_existing:
        if course.is_active:
            course.is_active = False
            deactivated += 1

    await db.flush()

    active_rows = [course for course in existing.values() if course.is_active]
    grouped: dict[tuple[str, tuple[str, ...]], list[Course]] = {}
    for course in active_rows:
        key = _group_key(course)
        if key[1]:
            grouped.setdefault(key, []).append(course)

    for group in grouped.values():
        winner = select_active(group)
        for course in group:
            if course is not winner and course.is_active:
                course.is_active = False
                deactivated += 1

    await db.flush()

    active_after_selection = [course for course in active_rows if course.is_active]
    await _fill_sha256_lists_for_courses(db, active_after_selection)
    await db.flush()

    return {
        "inserted": inserted,
        "updated": updated,
        "deactivated": deactivated,
    }
