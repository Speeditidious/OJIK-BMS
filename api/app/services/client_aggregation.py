"""Helpers for deriving source-client badges from per-client best fields."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

CLIENT_LABEL = {
    "lr2": "LR",
    "beatoraja": "BR",
}


@dataclass
class PerClientBest:
    """Best fields accumulated for one client on one chart."""

    client_type: str
    clear_type: int | None = None
    exscore: int | None = None
    rate: float | None = None
    rank: str | None = None
    min_bp: int | None = None


def aggregate_source_client(
    per_client_entries: Iterable[PerClientBest],
) -> tuple[str | None, dict[str, str] | None]:
    """Return `(source_client, source_client_detail)` for a chart row."""
    entries = [entry for entry in per_client_entries if entry.client_type]
    if not entries:
        return (None, None)

    raw: dict[str, object | None] = {
        "clear_type": None,
        "clear_type_client": None,
        "exscore": None,
        "exscore_client": None,
        "min_bp": None,
        "min_bp_client": None,
    }

    for entry in entries:
        label = CLIENT_LABEL.get(entry.client_type, entry.client_type.upper())
        if entry.clear_type is not None and (
            raw["clear_type"] is None or entry.clear_type > raw["clear_type"]
        ):
            raw["clear_type"] = entry.clear_type
            raw["clear_type_client"] = label
        if entry.exscore is not None and (
            raw["exscore"] is None or entry.exscore > raw["exscore"]
        ):
            raw["exscore"] = entry.exscore
            raw["exscore_client"] = label
        if entry.min_bp is not None and (
            raw["min_bp"] is None or entry.min_bp < raw["min_bp"]
        ):
            raw["min_bp"] = entry.min_bp
            raw["min_bp_client"] = label

    for entry in entries:
        label = CLIENT_LABEL.get(entry.client_type, entry.client_type.upper())
        clear_ok = raw["clear_type"] is None or entry.clear_type == raw["clear_type"]
        score_ok = raw["exscore"] is None or entry.exscore == raw["exscore"]
        bp_ok = raw["min_bp"] is None or entry.min_bp == raw["min_bp"]
        if clear_ok and score_ok and bp_ok:
            return (label, None)

    clients = {
        value
        for key, value in raw.items()
        if key.endswith("_client") and isinstance(value, str) and value
    }
    if len(clients) > 1:
        return (
            "MIX",
            {
                "clear_type": raw["clear_type_client"],
                "exscore": raw["exscore_client"],
                "min_bp": raw["min_bp_client"],
            },
        )
    if len(clients) == 1:
        return (next(iter(clients)), None)
    return (None, None)
