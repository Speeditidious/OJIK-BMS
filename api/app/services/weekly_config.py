"""Loader and schema for the Weekly feature config (api/weeklies/config.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "weeklies" / "config.toml"


class WeeklyConfigError(Exception):
    """Raised when the weekly config is missing/invalid or a key is not found."""


@dataclass(frozen=True)
class Selector:
    table: str
    level_range: tuple[str, str] | None = None
    levels: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Bracket:
    key: str
    order: int
    color: str
    pick_count: int
    selectors: tuple[Selector, ...]
    group: str | None = None


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    order: int
    brackets: tuple[Bracket, ...]

    def bracket(self, bracket_key: str) -> Bracket:
        for b in self.brackets:
            if b.key == bracket_key:
                return b
        raise WeeklyConfigError(f"Unknown bracket: {self.key}/{bracket_key}")


@dataclass(frozen=True)
class Settings:
    timezone: str
    rollover_day_of_week: str
    rollover_hour: int
    rollover_minute: int
    default_pick_count: int


@dataclass(frozen=True)
class WeeklyConfig:
    settings: Settings
    categories: tuple[Category, ...] = field(default_factory=tuple)

    def category(self, category_key: str) -> Category:
        for c in self.categories:
            if c.key == category_key:
                return c
        raise WeeklyConfigError(f"Unknown category: {category_key}")


def _parse_selector(raw: dict) -> Selector:
    table = raw.get("table")
    if not table:
        raise WeeklyConfigError(f"Selector missing 'table': {raw}")
    level_range = raw.get("level_range")
    levels = raw.get("levels")
    if not level_range and not levels:
        raise WeeklyConfigError(f"Selector for table '{table}' needs level_range or levels")
    return Selector(
        table=table,
        level_range=tuple(level_range) if level_range else None,  # type: ignore[arg-type]
        levels=tuple(levels) if levels else None,
    )


def _parse(raw: dict) -> WeeklyConfig:
    s = raw.get("settings", {})
    rollover = s.get("rollover", {})
    default_pick = int(s.get("default_pick_count", 5))
    settings = Settings(
        timezone=s.get("timezone", "Asia/Seoul"),
        rollover_day_of_week=rollover.get("day_of_week", "mon"),
        rollover_hour=int(rollover.get("hour", 4)),
        rollover_minute=int(rollover.get("minute", 0)),
        default_pick_count=default_pick,
    )

    categories: list[Category] = []
    for c in raw.get("categories", []):
        brackets: list[Bracket] = []
        for b in c.get("brackets", []):
            selectors = tuple(_parse_selector(x) for x in b.get("selectors", []))
            if not selectors:
                raise WeeklyConfigError(f"Bracket {c['key']}/{b['key']} has no selectors")
            brackets.append(
                Bracket(
                    key=b["key"],
                    order=int(b["order"]),
                    color=b.get("color", "#888888"),
                    pick_count=int(b.get("pick_count", default_pick)),
                    selectors=selectors,
                    group=b.get("group"),
                )
            )
        brackets.sort(key=lambda x: x.order)
        categories.append(
            Category(
                key=c["key"],
                name=c["name"],
                order=int(c["order"]),
                brackets=tuple(brackets),
            )
        )
    categories.sort(key=lambda x: x.order)
    return WeeklyConfig(settings=settings, categories=tuple(categories))


@lru_cache(maxsize=1)
def load_weekly_config() -> WeeklyConfig:
    """Load and cache the weekly config. Raises WeeklyConfigError if absent/invalid."""
    if not _CONFIG_PATH.exists():
        raise WeeklyConfigError(f"Weekly config not found: {_CONFIG_PATH}")
    with _CONFIG_PATH.open("rb") as fh:
        raw = tomllib.load(fh)
    return _parse(raw)
