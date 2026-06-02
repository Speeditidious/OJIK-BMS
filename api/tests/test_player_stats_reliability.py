"""Tests for the player_stats_reliability module.

Tests both the pure-Python helper (is_lr2_stats_unreliable) and the
SQLAlchemy expression builder (lr2_stats_unreliable_sql).
"""

import pytest
from sqlalchemy.dialects import postgresql

from app.models.score import UserPlayerStats
from app.services.player_stats_reliability import (
    LR2_MIN_SECONDS_PER_PLAY,
    is_lr2_stats_unreliable,
    lr2_stats_unreliable_sql,
)


# ---------------------------------------------------------------------------
# Pure-Python helper
# ---------------------------------------------------------------------------

class TestIsLr2StatsUnreliable:
    """Tests for is_lr2_stats_unreliable."""

    def test_corrupted_build_playtime_zero(self):
        """LR2ALT bug: playtime=0 with non-zero playcount → unreliable."""
        assert is_lr2_stats_unreliable("lr2", playcount=28286, playtime=0) is True

    def test_healthy_lr2(self):
        """Normal LR2 record with reasonable playtime → reliable."""
        assert is_lr2_stats_unreliable("lr2", playcount=22184, playtime=2214681) is False

    def test_boundary_just_below_threshold(self):
        """playtime=99 < 10*10=100 → unreliable."""
        assert is_lr2_stats_unreliable("lr2", playcount=10, playtime=99) is True

    def test_boundary_at_threshold(self):
        """playtime=100 is NOT < 10*10=100 → reliable."""
        assert is_lr2_stats_unreliable("lr2", playcount=10, playtime=100) is False

    def test_empty_baseline_playcount_zero(self):
        """playcount=0 — predicate requires playcount > 0 → reliable."""
        assert is_lr2_stats_unreliable("lr2", playcount=0, playtime=0) is False

    def test_playtime_none(self):
        """playtime=None — predicate requires playtime IS NOT NULL → reliable."""
        assert is_lr2_stats_unreliable("lr2", playcount=50, playtime=None) is False

    def test_beatoraja_low_ratio(self):
        """Beatoraja client — predicate only fires for lr2 → reliable."""
        assert is_lr2_stats_unreliable("beatoraja", playcount=100, playtime=0) is False


# ---------------------------------------------------------------------------
# Constant sanity check
# ---------------------------------------------------------------------------

def test_constant_value():
    """LR2_MIN_SECONDS_PER_PLAY must be 10."""
    assert LR2_MIN_SECONDS_PER_PLAY == 10


# ---------------------------------------------------------------------------
# SQLAlchemy expression
# ---------------------------------------------------------------------------

def _compile_sql(expr) -> str:
    """Compile a SQLAlchemy clause to a SQL string (PostgreSQL dialect)."""
    compiled = expr.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


class TestLr2StatsUnreliableSql:
    """Tests for lr2_stats_unreliable_sql."""

    def setup_method(self):
        self.sql = _compile_sql(lr2_stats_unreliable_sql(UserPlayerStats))

    def test_contains_client_type_lr2(self):
        """SQL must filter on client_type = 'lr2'."""
        assert "lr2" in self.sql

    def test_contains_playtime(self):
        """SQL must reference playtime column."""
        assert "playtime" in self.sql

    def test_contains_playcount(self):
        """SQL must reference playcount column."""
        assert "playcount" in self.sql

    def test_contains_min_seconds_constant(self):
        """SQL must embed the threshold constant (10)."""
        assert "10" in self.sql

    def test_is_and_expression(self):
        """The expression must be a conjunction (AND)."""
        # Multiple conditions → SQL contains AND
        assert " AND " in self.sql.upper()

    def test_returns_sqlalchemy_clause(self):
        """lr2_stats_unreliable_sql must return a SQLAlchemy clause element."""
        from sqlalchemy.sql.elements import ClauseElement
        expr = lr2_stats_unreliable_sql(UserPlayerStats)
        assert isinstance(expr, ClauseElement)
