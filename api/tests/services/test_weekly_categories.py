from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.routers import weeklies


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalarResult(self._rows)

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, weekly_rows, symbol_rows):
        self._results = [_FakeResult(weekly_rows), _FakeResult(symbol_rows)]

    async def execute(self, _statement):
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_current_categories_prefer_generated_snapshot(monkeypatch):
    period_start = datetime(2026, 8, 3, 19, 0, tzinfo=UTC)
    period_end = period_start + timedelta(days=7)
    monkeypatch.setattr(weeklies, "_resolve_period", lambda offset: (period_start, period_end))

    weekly_row = SimpleNamespace(
        category_key="balgwang",
        bracket_key="legacy",
        config_snapshot={
            "category_name": "発狂類",
            "bracket_group": None,
            "color": "#111111",
            "selectors": [{"table": "balgwang", "levels": ["1", "3"]}],
        },
        created_at=period_start,
    )
    db = _FakeSession(
        [weekly_row],
        [SimpleNamespace(slug="balgwang", symbol="★")],
    )

    categories = await weeklies.list_categories(offset=0, db=db)
    balgwang = next(category for category in categories if category.key == "balgwang")

    assert [bracket.key for bracket in balgwang.brackets] == ["legacy"]
    assert balgwang.brackets[0].display_ranges[0].text == "★1 ~ 3"
