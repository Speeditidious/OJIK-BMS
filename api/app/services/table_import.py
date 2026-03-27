"""Shared helpers for difficulty table import: fumen upsert, course sync."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _build_artist(item: dict) -> str:
    """Build artist string, appending obj name_diff if present and not a URL."""
    artist = item.get("artist") or ""
    name_diff = item.get("name_diff") or ""
    if name_diff and " / obj: " not in artist and not name_diff.startswith(("http:/", "https:/")):
        artist = f"{artist} / obj: {name_diff}"
    return artist


async def upsert_fumens(db: AsyncSession, table_id: uuid.UUID, songs: list[dict]) -> set[str]:
    """Upsert fumen rows and return the set of hash keys seen in this sync.

    Hash key format: "sha256:<hash>" or "md5:<hash>".

    For each song:
      - Looks up existing fumen by sha256 (priority) or md5.
      - Inserts if not found.
      - Updates table_entries, artist, file_url, file_url_diff if found.
      - table_entries entry for this table_id is replaced/appended.
    """
    from sqlalchemy import select, update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.fumen import Fumen

    seen_keys: set[str] = set()
    # New fumens collected for a single bulk INSERT at the end, avoiding the
    # ORM flush sort that crashes on nullable composite PKs (None < str).
    new_fumen_rows: list[dict] = []

    for item in songs:
        sha256_raw = (item.get("sha256") or "").strip().lower()
        md5_raw = (item.get("md5") or "").strip().lower()
        # Reject values that exceed column length constraints (VARCHAR 64/32).
        # Dirty data sometimes puts a sha256 in the md5 field or has trailing whitespace.
        sha256 = sha256_raw if len(sha256_raw) <= 64 else None
        md5 = md5_raw if len(md5_raw) <= 32 else None
        if not sha256 and not md5:
            continue

        level = str(item.get("level", "")).strip()
        new_entry = {"table_id": str(table_id), "level": level}
        artist = _build_artist(item)
        file_url = item.get("url") or None
        file_url_diff = item.get("url_diff") or None

        hash_key = f"sha256:{sha256}" if sha256 else f"md5:{md5}"
        seen_keys.add(hash_key)

        # Look up existing fumen.
        # sha256 takes priority. If not found by sha256, fall back to md5 — the
        # same chart may exist as {sha256=None, md5=Y} while we now have sha256 too.
        # This prevents duplicate rows when only one hash side was known at first insert.
        existing = None
        if sha256:
            result = await db.execute(select(Fumen).where(Fumen.sha256 == sha256))
            existing = result.scalar_one_or_none()
        if existing is None and md5:
            result = await db.execute(select(Fumen).where(Fumen.md5 == md5))
            existing = result.scalar_one_or_none()

        if existing is None:
            new_fumen_rows.append({
                "sha256": sha256,
                "md5": md5,
                "title": item.get("title") or None,
                "artist": artist or None,
                "file_url": file_url,
                "file_url_diff": file_url_diff,
                "table_entries": [new_entry],
            })
        else:
            entries: list[dict] = list(existing.table_entries or [])
            replaced = False
            table_id_str = str(table_id)
            for i, e in enumerate(entries):
                if e.get("table_id") == table_id_str:
                    entries[i] = new_entry
                    replaced = True
                    break
            if not replaced:
                entries.append(new_entry)

            update_vals: dict = {"table_entries": entries}
            if artist:
                update_vals["artist"] = artist
            if file_url:
                update_vals["file_url"] = file_url
            if file_url_diff:
                update_vals["file_url_diff"] = file_url_diff

            # Use core UPDATE to bypass ORM flush sort (nullable composite PK
            # makes sorted(key=q.key) fail with None < str TypeError).
            # Use the existing row's hash to locate the row — the item's sha256/md5
            # may differ from what was stored (e.g. found via md5 fallback).
            where = Fumen.sha256 == existing.sha256 if existing.sha256 else Fumen.md5 == existing.md5
            await db.execute(
                update(Fumen)
                .where(where)
                .values(**update_vals)
                .execution_options(synchronize_session=False)
            )

    # Bulk-insert new fumens via core INSERT to bypass ORM PK sort (which fails
    # when both sha256 and md5 can be None and Python can't compare None < str).
    # Batch to stay under PostgreSQL's 65535 bind-parameter limit (7 cols/row).
    if new_fumen_rows:
        cols_per_row = 7
        batch_size = 65535 // cols_per_row  # 9362
        for i in range(0, len(new_fumen_rows), batch_size):
            batch = new_fumen_rows[i : i + batch_size]
            await db.execute(
                pg_insert(Fumen).values(batch).on_conflict_do_nothing()
            )

    await db.flush()
    return seen_keys


async def remove_stale_entries(db: AsyncSession, table_id: uuid.UUID, seen_keys: set[str]) -> int:
    """Remove table_id from table_entries of fumens no longer in the table.

    Returns the count of fumens whose entries were pruned.
    """
    from sqlalchemy import select, update

    from app.models.fumen import Fumen

    table_id_str = str(table_id)
    result = await db.execute(
        select(Fumen).where(
            Fumen.table_entries.contains([{"table_id": table_id_str}])
        )
    )
    fumens = result.scalars().all()

    removed = 0
    for fumen in fumens:
        hash_key = f"sha256:{fumen.sha256}" if fumen.sha256 else f"md5:{fumen.md5}"
        md5_key = f"md5:{fumen.md5}" if fumen.md5 else None
        if hash_key in seen_keys or (md5_key and md5_key in seen_keys):
            continue
        entries = [e for e in (fumen.table_entries or []) if e.get("table_id") != table_id_str]
        # Use core UPDATE to bypass ORM flush sort — nullable composite PK (sha256, md5)
        # causes FlushError when sha256 is NULL.
        where = Fumen.sha256 == fumen.sha256 if fumen.sha256 else Fumen.md5 == fumen.md5
        await db.execute(
            update(Fumen)
            .where(where)
            .values(table_entries=entries)
            .execution_options(synchronize_session=False)
        )
        removed += 1

    return removed


async def _build_sha256_list(db: AsyncSession, md5_list: list) -> list:
    """Build a sha256 list parallel to md5_list by querying the fumens table.

    Each position corresponds to the same position in md5_list.
    Positions where sha256 is unknown are set to None.
    """
    from sqlalchemy import select

    from app.models.fumen import Fumen

    non_null_md5s = [m for m in md5_list if m]
    if not non_null_md5s:
        return [None] * len(md5_list)

    result = await db.execute(
        select(Fumen.md5, Fumen.sha256).where(
            Fumen.md5.in_(non_null_md5s),
            Fumen.sha256.isnot(None),
        )
    )
    md5_to_sha256: dict[str, str] = {row.md5: row.sha256 for row in result.all()}
    return [md5_to_sha256.get(m) if m else None for m in md5_list]


async def upsert_courses(db: AsyncSession, table_id: uuid.UUID, courses: list[dict[str, Any]]) -> None:
    """Sync course rows from header.json course/grade fields.

    - Existing courses for table_id: update md5_list, is_active=True.
    - New courses: insert.
    - Disappeared courses: is_active=False (soft-delete).
    - After upsert, fills sha256_list for each course from the fumens table.
    """
    from sqlalchemy import select

    from app.models.course import Course

    result = await db.execute(
        select(Course).where(Course.source_table_id == table_id)
    )
    existing_courses: dict[str, Course] = {c.name: c for c in result.scalars().all()}

    seen_names: set[str] = set()
    for course_data in courses:
        name = course_data["name"]
        md5_list = course_data["md5_list"]
        seen_names.add(name)

        if name in existing_courses:
            c = existing_courses[name]
            c.md5_list = md5_list
            c.is_active = True
            c.synced_at = datetime.now(UTC)
        else:
            new_course = Course(
                name=name,
                source_table_id=table_id,
                md5_list=md5_list,
                is_active=True,
                dan_title="",
                synced_at=datetime.now(UTC),
            )
            db.add(new_course)
            existing_courses[name] = new_course

    for name, course in existing_courses.items():
        if name not in seen_names:
            course.is_active = False

    await db.flush()

    # Fill sha256_list for courses that were inserted or updated this run.
    for name in seen_names:
        course = existing_courses.get(name)
        if course is None:
            continue
        course.sha256_list = await _build_sha256_list(db, course.md5_list or [])

    await db.flush()
