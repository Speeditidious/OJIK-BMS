"""Tests for fumen list search/sort SQL construction."""

import uuid
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.routers.fumens import (
    _build_field_condition,
    _build_score_agg_subquery,
    _build_sort_col,
)


def _sql(expr: sa.ClauseElement) -> str:
    return str(expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_score_search_conditions_use_display_aggregate_columns() -> None:
    """Score filters should match the aggregate values displayed in the list."""
    score_agg = sa.table(
        "score_agg",
        sa.column("best_min_bp"),
        sa.column("best_exscore"),
        sa.column("total_plays"),
    )
    user = SimpleNamespace(id=uuid.uuid4())

    bp_sql = _sql(_build_field_condition("bp", "<=10", user, score_agg))
    score_sql = _sql(_build_field_condition("score", "2000", user, score_agg))
    plays_sql = _sql(_build_field_condition("plays", ">=5", user, score_agg))

    assert "score_agg.best_min_bp <= 10.0" in bp_sql
    assert "score_agg.best_exscore = 2000.0" in score_sql
    assert "score_agg.total_plays >= 5.0" in plays_sql
    assert "user_scores" not in bp_sql


def test_score_aggregate_is_keyed_by_fumen_identity() -> None:
    """The aggregate subquery should merge md5-only LR2 rows into each fumen row."""
    sql = _sql(_build_score_agg_subquery(uuid.uuid4()).select())

    assert "FROM fumens LEFT OUTER JOIN user_scores" in sql
    assert "user_scores.fumen_sha256 = fumens.sha256" in sql
    assert "user_scores.fumen_md5 = fumens.md5" in sql
    assert "user_scores.fumen_sha256 IS NULL" in sql
    assert "GROUP BY fumens.sha256, fumens.md5" in sql


def test_level_sort_strips_non_numeric_prefixes_before_cast() -> None:
    """Level sorting should not fail on labels such as ★1 or sl1."""
    sql = _sql(_build_sort_col("level", "asc", None))

    assert "substring" in sql
    assert "NULLS LAST" in sql
