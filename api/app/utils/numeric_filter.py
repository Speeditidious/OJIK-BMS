"""Helpers for building SQLAlchemy WHERE conditions from free-text numeric input."""
from __future__ import annotations

import re
from typing import Any

_NUM = r"-?\d+(?:\.\d+)?"
_RANGE = re.compile(rf"^\s*({_NUM})\s*-\s*({_NUM})\s*$")
_GE    = re.compile(rf"^\s*>=\s*({_NUM})\s*$")
_LE    = re.compile(rf"^\s*<=\s*({_NUM})\s*$")
_GT    = re.compile(rf"^\s*>\s*({_NUM})\s*$")
_LT    = re.compile(rf"^\s*<\s*({_NUM})\s*$")
_EQ    = re.compile(rf"^\s*({_NUM})\s*$")


def numeric_clause(col: Any, raw: str) -> Any | None:
    """Return SQLAlchemy WHERE condition from a numeric filter string.

    Supports: ``120-180``, ``>=140``, ``<=180``, ``>140``, ``<180``, ``150``.
    Returns None on parse failure — caller should treat as empty result.
    """
    s = raw.strip()
    for pat, builder in [
        (_RANGE, lambda m: col.between(float(m[1]), float(m[2]))),
        (_GE,    lambda m: col >= float(m[1])),
        (_LE,    lambda m: col <= float(m[1])),
        (_GT,    lambda m: col >  float(m[1])),
        (_LT,    lambda m: col <  float(m[1])),
        (_EQ,    lambda m: col == float(m[1])),
    ]:
        m = pat.match(s)
        if m:
            return builder(m)
    return None


def parse_length_to_ms(raw: str) -> str:
    """Convert M:SS or H:MM:SS duration string to milliseconds string.

    Passes through numeric-only strings unchanged so ``numeric_clause`` can
    still handle them.
    """
    parts = raw.strip().split(":")
    if len(parts) == 1:
        return raw
    try:
        if len(parts) == 2:
            m, s = int(parts[0]), int(parts[1])
            return str((m * 60 + s) * 1000)
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return str((h * 3600 + m * 60 + s) * 1000)
    except ValueError:
        pass
    return raw
