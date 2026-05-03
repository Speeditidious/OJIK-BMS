import re
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_update import ClientUpdateAnnouncement


class ReleaseTarget(NamedTuple):
    """Desktop client release target tuple."""

    target_os: str
    arch: str
    channel: str
    installer_kind: str


_SEMVER_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-.](?P<pre>[0-9A-Za-z.-]+))?(?:\+.*)?$"
)


async def get_latest_visible_update(
    db: AsyncSession,
    current_version: str | None,
    target: ReleaseTarget,
) -> ClientUpdateAnnouncement | None:
    """Return the highest visible release newer than *current_version*."""
    rows = await list_visible_updates(db, target)
    current = _parse_version(current_version or "0.0.0")
    candidates = [
        row
        for row in rows
        if _parse_version(row.version) > current
        and _is_supported_bridge(current_version, row.min_supported_version)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: _parse_version(row.version))


async def get_latest_visible_release(
    db: AsyncSession,
    target: ReleaseTarget,
) -> ClientUpdateAnnouncement | None:
    """Return the highest visible release for a download page."""
    rows = await list_visible_updates(db, target)
    if not rows:
        return None
    return max(rows, key=lambda row: _parse_version(row.version))


async def list_visible_updates(
    db: AsyncSession,
    target: ReleaseTarget,
) -> list[ClientUpdateAnnouncement]:
    """List published update rows visible now for a release target."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(ClientUpdateAnnouncement)
        .where(
            ClientUpdateAnnouncement.channel == target.channel,
            ClientUpdateAnnouncement.target_os == target.target_os,
            ClientUpdateAnnouncement.arch == target.arch,
            ClientUpdateAnnouncement.installer_kind == target.installer_kind,
            ClientUpdateAnnouncement.is_published.is_(True),
            (
                (ClientUpdateAnnouncement.publish_after.is_(None))
                | (ClientUpdateAnnouncement.publish_after <= now)
            ),
        )
    )
    return list(result.scalars().all())


def published_at_for(row: ClientUpdateAnnouncement) -> datetime:
    """Return the public publish timestamp for API responses."""
    return row.published_at or row.publish_after or row.created_at


def _is_supported_bridge(current_version: str | None, min_supported_version: str | None) -> bool:
    if not current_version or not min_supported_version:
        return True
    return _parse_version(current_version) >= _parse_version(min_supported_version)


def _parse_version(version: str) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]]:
    """Parse a small semver subset into a sortable tuple.

    Stable releases sort after prereleases with the same major/minor/patch.
    Unknown formats sort as 0.0.0 prereleases so a bad row never wins over a
    correctly formatted release.
    """
    match = _SEMVER_RE.match((version or "").strip())
    if not match:
        return (0, 0, 0, 0, ((1, version),))

    pre = match.group("pre")
    pre_rank = 1 if pre is None else 0
    pre_parts: tuple[tuple[int, int | str], ...] = tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in pre.split(".")
    ) if pre else ()
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        pre_rank,
        pre_parts,
    )
