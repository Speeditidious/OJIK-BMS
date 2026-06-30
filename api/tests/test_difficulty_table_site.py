"""Tests for DifficultyTable.site field: response serialization and config sync semantics."""
import uuid

import pytest

from app.models.difficulty_table import DifficultyTable
from app.routers.tables import DifficultyTableRead, _representative_site_url
from app.services.table_sync import _MISSING, site_from_config


# ── URL validator helper ──────────────────────────────────────────────────────


def test_representative_site_url_accepts_https() -> None:
    assert _representative_site_url("https://stellabms.xyz/") == "https://stellabms.xyz/"


def test_representative_site_url_accepts_http() -> None:
    assert _representative_site_url("http://example.com/table") == "http://example.com/table"


def test_representative_site_url_trims_whitespace() -> None:
    assert _representative_site_url("  https://site.example/table  ") == "https://site.example/table"


def test_representative_site_url_rejects_empty() -> None:
    assert _representative_site_url("") is None


def test_representative_site_url_rejects_none() -> None:
    assert _representative_site_url(None) is None


def test_representative_site_url_rejects_plain_text() -> None:
    assert _representative_site_url("stellaverse") is None


def test_representative_site_url_rejects_ftp() -> None:
    assert _representative_site_url("ftp://example.com") is None


# ── Response serialization ────────────────────────────────────────────────────


def _make_table(site: str | None) -> DifficultyTable:
    return DifficultyTable(
        id=uuid.uuid4(),
        name="Test Table",
        symbol="TT",
        slug="test-table",
        source_url="https://example.com/header.json",
        site=site,
        is_default=True,
    )


def test_from_orm_exposes_valid_representative_site_url() -> None:
    item = DifficultyTableRead.from_orm_with_count(_make_table(" https://site.example/table "), 12)

    assert item.site == " https://site.example/table "
    assert item.representative_site_url == "https://site.example/table"
    assert item.song_count == 12


def test_from_orm_hides_blank_site() -> None:
    item = DifficultyTableRead.from_orm_with_count(_make_table(""))

    assert item.site == ""
    assert item.representative_site_url is None


def test_from_orm_hides_non_url_text() -> None:
    item = DifficultyTableRead.from_orm_with_count(_make_table("stellaverse"))

    assert item.representative_site_url is None


def test_from_orm_hides_null_site() -> None:
    item = DifficultyTableRead.from_orm_with_count(_make_table(None))

    assert item.site is None
    assert item.representative_site_url is None


def test_from_orm_none_count_when_omitted() -> None:
    item = DifficultyTableRead.from_orm_with_count(_make_table(None))

    assert item.song_count is None


# ── Config sync helper ────────────────────────────────────────────────────────


def test_site_from_config_returns_missing_when_key_absent() -> None:
    result = site_from_config({"slug": "sl", "url": "https://example.com/header.json"})

    assert result is _MISSING


def test_site_from_config_returns_trimmed_url_when_present() -> None:
    result = site_from_config({"site": " https://representative.example "})

    assert result == "https://representative.example"


def test_site_from_config_returns_empty_string_when_explicitly_empty() -> None:
    result = site_from_config({"site": ""})

    assert result == ""


def test_site_from_config_returns_empty_string_for_none_value() -> None:
    result = site_from_config({"site": None})

    assert result == ""
