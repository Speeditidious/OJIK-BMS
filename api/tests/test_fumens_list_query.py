"""Tests for fumen list search/sort SQL construction."""

import uuid
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.routers.fumens import (
    _basic_text_filter,
    _basic_text_match_bucket,
    _basic_text_precision_filter,
    _build_field_condition,
    _build_score_agg_subquery,
    _build_sort_cols,
    _build_text_search_sort_cols,
    _normalize_search_text,
    _regex_text_condition,
)


def _sql(expr: sa.ClauseElement) -> str:
    return str(expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _sqls(exprs: list[sa.ClauseElement]) -> list[str]:
    return [_sql(expr) for expr in exprs]


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
    """The aggregate subquery should join scores by normalized fumen_id."""
    sql = _sql(_build_score_agg_subquery(uuid.uuid4()).select())

    assert "FROM fumens LEFT OUTER JOIN user_scores" in sql
    assert "user_scores.fumen_id = fumens.fumen_id" in sql
    assert "GROUP BY fumens.fumen_id" in sql


def test_level_sort_strips_non_numeric_prefixes_before_cast() -> None:
    """Level sorting should use normalized fumen_table_entries."""
    sql = _sql(_build_sort_cols("level", "asc", None)[0])

    assert "fumen_table_entries" in sql
    assert "fumen_table_entries.fumen_id = fumens.fumen_id" in sql
    assert "NULLS LAST" in sql


def test_title_sort_places_dummy_titles_last_for_ascending() -> None:
    """Title ascending should put dummy title rows after regular rows."""
    bucket_sql, title_sql = _sqls(_build_sort_cols("title", "asc", None))

    assert "CASE WHEN" in bucket_sql
    assert "btrim(fumens.title) = '>> ??? <<'" in bucket_sql
    assert "btrim(fumens.title) ~ '^[가-힣]'" in bucket_sql
    assert bucket_sql.endswith("ASC")
    assert title_sql == "fumens.title ASC NULLS LAST"


def test_title_sort_places_dummy_titles_last_for_descending() -> None:
    """Title descending should reverse title order but keep dummy rows last."""
    bucket_sql, title_sql = _sqls(_build_sort_cols("title", "desc", None))

    assert bucket_sql.endswith("ASC")
    assert title_sql == "fumens.title DESC NULLS LAST"


def test_artist_sort_uses_title_for_dummy_bucket() -> None:
    """Artist sorting should still identify dummy rows by title only."""
    bucket_sql, artist_sql = _sqls(_build_sort_cols("artist", "asc", None))

    assert "btrim(fumens.title)" in bucket_sql
    assert "btrim(fumens.artist)" not in bucket_sql
    assert artist_sql == "fumens.artist ASC NULLS LAST"


def test_basic_text_filter_uses_normalized_sargable_candidate_predicate() -> None:
    filter_sql = _sql(_basic_text_filter("title", "g e n"))
    precision_sql = _sql(_basic_text_precision_filter("title", "g e n"))

    assert "regexp_replace(lower(coalesce(fumens.title" in filter_sql
    assert "'[^[:alnum:]]+'" in filter_sql
    assert "LIKE '%%gen%%'" in filter_sql
    assert "CASE WHEN" in precision_sql
    assert "< 99" in precision_sql


def test_basic_text_bucket_excludes_normalized_infix_matches() -> None:
    bucket_sql = _sql(_basic_text_match_bucket("title", "Air"))

    assert "lower(coalesce(fumens.title" in bucket_sql
    assert "~ '(^|[^[:alnum:]])air([^[:alnum:]]|$)'" in bucket_sql
    assert "LIKE 'air%%' ESCAPE '\\\\'" in bucket_sql
    assert "LIKE 'air%%'" in bucket_sql
    assert "ELSE 99" in bucket_sql


def test_title_artist_bucket_offsets_artist_below_title() -> None:
    bucket_sql = _sql(_basic_text_match_bucket("title_artist", "Air"))

    assert "least(" in bucket_sql.lower()
    assert "THEN 0" in bucket_sql
    assert "THEN 10" in bucket_sql


def test_basic_text_search_uses_popularity_after_requested_sort() -> None:
    order_sql = _sqls(_build_text_search_sort_cols("title_artist", "Air", "title", "asc", None))

    title_index = next(i for i, sql in enumerate(order_sql) if sql == "fumens.title ASC NULLS LAST")
    popularity_index = next(i for i, sql in enumerate(order_sql) if "fumen_play_popularity.played_user_count DESC" in sql)

    assert order_sql[0].startswith("least(")
    assert title_index < popularity_index


def test_regex_text_search_uses_popularity_after_requested_sort() -> None:
    order_sql = _sqls(_build_text_search_sort_cols("title_artist", None, "title", "asc", None))

    title_index = next(i for i, sql in enumerate(order_sql) if sql == "fumens.title ASC NULLS LAST")
    popularity_index = next(i for i, sql in enumerate(order_sql) if "fumen_play_popularity.played_user_count DESC" in sql)

    assert title_index < popularity_index


def test_normalize_search_text_strips_symbols_and_whitespace() -> None:
    assert _normalize_search_text("[ g e n_g a o z o! ]") == "gengaozo"


def test_regex_condition_uses_lower_raw_text_regex_operator() -> None:
    regex_sql = _sql(_regex_text_condition("title_artist", "^Air"))

    assert "lower(coalesce(fumens.title" in regex_sql
    assert " ~ '^air'" in regex_sql
    assert "lower(coalesce(fumens.artist" in regex_sql


def test_regex_rejects_non_text_field_and_long_query() -> None:
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as non_text:
        _regex_text_condition("level", "^Air")
    assert non_text.value.status_code == 400

    with pytest.raises(HTTPException) as too_long:
        _regex_text_condition("title", "a" * 121)
    assert too_long.value.status_code == 400
