"""Helpers for deriving source-client badges from per-client best fields."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.services.clear_type_display import display_clear_type

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


def _client_label(client_type: str) -> str:
    """Return the short client label used by dashboard responses."""
    return CLIENT_LABEL.get(client_type, client_type.upper())


def aggregate_source_client(
    per_client_entries: Iterable[PerClientBest],
) -> tuple[str | None, dict[str, str] | None]:
    """Return `(source_client, source_client_detail)` for a chart row."""
    entries = [entry for entry in per_client_entries if entry.client_type]
    if not entries:
        return (None, None)

    best_clear = max(
        (
            display_clear_type(entry.clear_type, exscore=entry.exscore, rate=entry.rate)
            for entry in entries
            if entry.clear_type is not None
        ),
        default=None,
    )
    best_exscore = max(
        (entry.exscore for entry in entries if entry.exscore is not None),
        default=None,
    )
    best_min_bp = min(
        (entry.min_bp for entry in entries if entry.min_bp is not None),
        default=None,
    )

    if best_clear is None and best_exscore is None and best_min_bp is None:
        return (None, None)

    def is_dominant(entry: PerClientBest) -> bool:
        matches_best = False

        if best_clear is not None and entry.clear_type is not None:
            display_clear = display_clear_type(entry.clear_type, exscore=entry.exscore, rate=entry.rate)
            if display_clear is None or display_clear < best_clear:
                return False
            matches_best = matches_best or display_clear == best_clear
        if best_exscore is not None and entry.exscore is not None:
            if entry.exscore < best_exscore:
                return False
            matches_best = matches_best or entry.exscore == best_exscore
        if best_min_bp is not None and entry.min_bp is not None:
            if entry.min_bp > best_min_bp:
                return False
            matches_best = matches_best or entry.min_bp == best_min_bp

        return matches_best

    winner_labels = {
        _client_label(entry.client_type)
        for entry in entries
        if is_dominant(entry)
    }
    if len(winner_labels) == 1:
        return (next(iter(winner_labels)), None)

    detail = {
        "clear_type": next(
            (
                _client_label(entry.client_type)
                for entry in entries
                if (
                    best_clear is not None
                    and display_clear_type(entry.clear_type, exscore=entry.exscore, rate=entry.rate) == best_clear
                )
            ),
            None,
        ),
        "exscore": next(
            (
                _client_label(entry.client_type)
                for entry in entries
                if best_exscore is not None and entry.exscore == best_exscore
            ),
            None,
        ),
        "min_bp": next(
            (
                _client_label(entry.client_type)
                for entry in entries
                if best_min_bp is not None and entry.min_bp == best_min_bp
            ),
            None,
        ),
    }
    return ("MIX", {key: value for key, value in detail.items() if value is not None})
