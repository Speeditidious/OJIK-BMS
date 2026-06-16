"""Text normalization helpers for persisted display metadata."""

from __future__ import annotations

from html import unescape


def normalize_display_text(value: str | None) -> str | None:
    """Return display text with common HTML entities decoded.

    Some BMS table JSON and local song DB rows contain HTML-escaped metadata
    such as ``&quot;``. Decode at persistence boundaries so search, sorting, and
    admin inspection all use the literal title/artist text.
    """
    if value is None:
        return None
    normalized = value
    for _ in range(3):
        decoded = unescape(normalized)
        if decoded == normalized:
            break
        normalized = decoded
    return normalized


def normalize_loose_search_text(value: str | None) -> str:
    """Return lowercase text with punctuation and whitespace removed for search."""
    return "".join(ch for ch in (value or "").casefold() if ch.isalnum())


def loose_text_matches(value: str | None, query: str | None) -> bool:
    """Return whether normalized value contains the normalized query."""
    normalized_query = normalize_loose_search_text(query)
    if not normalized_query:
        return True
    return normalized_query in normalize_loose_search_text(value)
