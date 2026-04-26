"""Default difficulty table ordering helpers."""
from __future__ import annotations

from app.models.difficulty_table import DifficultyTable
from app.parsers.table_fetcher import get_default_table_configs

_ORDER_FALLBACK = 1_000_000


def _config_order_maps() -> tuple[dict[str, int], dict[str, int]]:
    """Return config-defined default table order by slug and source URL."""
    by_slug: dict[str, int] = {}
    by_url: dict[str, int] = {}
    for index, cfg in enumerate(get_default_table_configs()):
        slug = str(cfg.get("slug") or "").strip()
        url = str(cfg.get("url") or "").strip()
        if slug:
            by_slug[slug] = index
        if url:
            by_url[url] = index
    return by_slug, by_url


def _default_table_sort_index(
    table: DifficultyTable,
    by_slug: dict[str, int],
    by_url: dict[str, int],
) -> int:
    """Return the configured display index for a default difficulty table."""
    if table.slug and table.slug in by_slug:
        return by_slug[table.slug]
    if table.source_url and table.source_url in by_url:
        return by_url[table.source_url]
    if table.default_order is not None:
        return table.default_order
    return _ORDER_FALLBACK


def default_table_sort_index(table: DifficultyTable) -> int:
    """Return the configured display index for a default difficulty table."""
    by_slug, by_url = _config_order_maps()
    return _default_table_sort_index(table, by_slug, by_url)


def sort_difficulty_tables(tables: list[DifficultyTable]) -> list[DifficultyTable]:
    """Sort tables with config-defined defaults first, then custom tables by name."""
    by_slug, by_url = _config_order_maps()
    return sorted(
        tables,
        key=lambda table: (
            0 if table.is_default else 1,
            _default_table_sort_index(table, by_slug, by_url)
            if table.is_default
            else _ORDER_FALLBACK,
            table.name.casefold(),
        ),
    )
