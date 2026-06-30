"""Course note-count helpers."""

from __future__ import annotations

from typing import Any


def course_notes_total(
    course: Any,
    notes_by_md5: dict[str, int | None],
    notes_by_sha256: dict[str, int | None],
) -> int | None:
    """Return the sum of member fumen notes for a course when every member is known."""
    sha256_list = list(getattr(course, "sha256_list", None) or [])
    if sha256_list and all(sha256_list):
        values = [notes_by_sha256.get(str(sha256)) for sha256 in sha256_list]
        if values and all(value is not None for value in values):
            return sum(int(value or 0) for value in values)

    md5_list = list(getattr(course, "md5_list", None) or [])
    values = [notes_by_md5.get(str(md5)) for md5 in md5_list if md5]
    if values and len(values) == len([md5 for md5 in md5_list if md5]) and all(value is not None for value in values):
        return sum(int(value or 0) for value in values)
    return None
