"""BMS difficulty table fetcher and parser.

Supports two source formats:
  1. HTML page with <meta name="bmstable" content="header_url"> tag
  2. Direct header.json URL

The parsed result is normalized to:
  {
    "header": { ...original header.json fields },
    "songs": [ {level, md5, sha256, title, artist, url, url_diff, name_diff, ...}, ... ],
    "level_order": ["sl0", "sl1", ...],  # ordered level list
    "courses": [ {name, md5_list}, ... ]  # parsed from header course/grade fields
  }
"""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# Base directory for local table cache
TABLES_DIR = Path(__file__).parent.parent.parent / "difficulty_tables"


class _MetaTagParser(HTMLParser):
    """Minimal HTML parser: extracts <meta name="bmstable" content="...">."""

    def __init__(self) -> None:
        super().__init__()
        self.bmstable_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attrs_dict: dict[str, str] = {k.lower(): (v or "") for k, v in attrs}
        if attrs_dict.get("name", "").lower() == "bmstable":
            self.bmstable_url = attrs_dict.get("content")


def _make_absolute(url: str, base_url: str) -> str:
    """Resolve a potentially relative URL against a base URL."""
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)


def _derive_level_order(songs: list[dict]) -> list[str]:
    """Build an ordered, de-duplicated level list from song data.

    Tries to sort numerically where possible (sl0 < sl1 < sl10),
    otherwise falls back to the original insertion order.
    """
    seen: dict[str, int] = {}
    for song in songs:
        level = str(song.get("level", "")).strip()
        if level and level not in seen:
            seen[level] = len(seen)

    def _sort_key(lvl: str) -> tuple[str, int]:
        m = re.match(r"^(.*?)(\d+)$", lvl)
        if m:
            return (m.group(1), int(m.group(2)))
        return (lvl, 0)

    return sorted(seen.keys(), key=_sort_key)


def _parse_courses_from_header(header: dict) -> list[dict[str, Any]]:
    """Extract course entries from header.json course/grade fields.

    Returns a list of {name: str, md5_list: [str, ...]} dicts.
    """
    courses: list[dict[str, Any]] = []

    raw_grade: list[dict] = header.get("grade") or []
    for entry in raw_grade:
        name = entry.get("name") or ""
        md5s = entry.get("md5") or []
        if name and md5s:
            courses.append({"name": name, "md5_list": md5s})

    raw_course: list[Any] = header.get("course") or []
    for item in raw_course:
        # course can be a list of lists
        if isinstance(item, list):
            for entry in item:
                name = entry.get("name") or ""
                md5s = entry.get("md5") or []
                if name and md5s:
                    courses.append({"name": name, "md5_list": md5s})
        elif isinstance(item, dict):
            name = item.get("name") or ""
            md5s = item.get("md5") or []
            if name and md5s:
                courses.append({"name": name, "md5_list": md5s})

    return courses


def _normalize(header: dict, raw_songs: list[dict]) -> dict:
    """Normalize raw header + song list into the canonical stored format."""
    songs: list[dict] = []
    for song in raw_songs:
        normalized: dict[str, Any] = {
            "level": str(song.get("level", "")).strip(),
            "md5": (song.get("md5") or song.get("md5hash") or "").lower(),
            "sha256": (song.get("sha256") or song.get("sha256hash") or "").lower(),
            "title": song.get("title") or song.get("title_yomigana") or "",
            "artist": song.get("artist") or "",
            "url": song.get("url") or "",
            "url_diff": song.get("url_diff") or "",
            "name_diff": song.get("name_diff") or "",
        }
        # Pass through any extra fields
        for k, v in song.items():
            if k not in normalized:
                normalized[k] = v
        songs.append(normalized)

    level_order = header.get("level_order") or _derive_level_order(songs)
    courses = _parse_courses_from_header(header)

    return {
        "header": header,
        "songs": songs,
        "level_order": level_order,
        "courses": courses,
        "symbol": header.get("symbol") or None,
    }


async def fetch_table(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch and parse a BMS difficulty table from *url*.

    Args:
        url: HTML page or header.json URL.
        client: Optional pre-created httpx client (re-used for efficiency).

    Returns:
        Normalized table dict with keys: header, songs, level_order, courses.

    Raises:
        httpx.HTTPError: on network / HTTP errors.
        ValueError: if the page has no recognizable bmstable meta tag.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    try:
        req_headers: dict[str, str] = {"User-Agent": "OJIK-BMS-TableFetcher/1.0"}

        resp = await client.get(url, headers=req_headers)
        resp.raise_for_status()

        parsed = urlparse(url)
        is_json = parsed.path.endswith(".json") or "json" in resp.headers.get(
            "content-type", ""
        )

        if is_json:
            header_url = url
            header: dict = resp.json()
        else:
            parser = _MetaTagParser()
            parser.feed(resp.text)
            if not parser.bmstable_url:
                raise ValueError(f"No <meta name='bmstable'> found at {url}")
            header_url = _make_absolute(parser.bmstable_url, url)
            header_resp = await client.get(header_url, headers={"User-Agent": req_headers["User-Agent"]})
            header_resp.raise_for_status()
            header = header_resp.json()

        data_url_raw: str = header.get("data_url") or header.get("data_url_no_cache", "")
        if not data_url_raw:
            raise ValueError(f"header.json at {header_url} has no data_url field")

        data_url = _make_absolute(data_url_raw, header_url)
        data_resp = await client.get(data_url, headers={"User-Agent": req_headers["User-Agent"]})
        data_resp.raise_for_status()

        raw_songs: list[dict] = data_resp.json()
        if not isinstance(raw_songs, list):
            raise ValueError(f"data.json at {data_url} is not a JSON array")

        return _normalize(header, raw_songs)

    finally:
        if own_client:
            await client.aclose()


def save_table_to_disk(slug: str, table_data: dict) -> None:
    """Persist header.json and data.json to the local cache folder."""
    import shutil
    from datetime import datetime

    config = _load_config()
    backup_count: int = config.get("backup_count", 3)

    table_dir = TABLES_DIR / slug
    table_dir.mkdir(parents=True, exist_ok=True)

    header_path = table_dir / "header.json"
    data_path = table_dir / "data.json"

    if header_path.exists() and data_path.exists():
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = table_dir / "backups" / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(header_path, backup_dir / "header.json")
        shutil.copy2(data_path, backup_dir / "data.json")

        backups_root = table_dir / "backups"
        all_backups = sorted(backups_root.iterdir())
        for old in all_backups[:-backup_count]:
            shutil.rmtree(old, ignore_errors=True)

    header_path.write_text(
        json.dumps(table_data["header"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    data_path.write_text(
        json.dumps(table_data["songs"], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_table_from_disk(slug: str) -> dict | None:
    """Load the cached table data from disk, or return None if not cached."""
    table_dir = TABLES_DIR / slug
    header_path = table_dir / "header.json"
    data_path = table_dir / "data.json"

    if not header_path.exists() or not data_path.exists():
        return None

    header = json.loads(header_path.read_text(encoding="utf-8"))
    songs = json.loads(data_path.read_text(encoding="utf-8"))

    level_order = header.get("level_order") or _derive_level_order(songs)
    courses = _parse_courses_from_header(header)
    return {"header": header, "songs": songs, "level_order": level_order, "courses": courses}


def _load_config() -> dict:
    import tomllib
    config_path = TABLES_DIR / "config.toml"
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_default_table_configs() -> list[dict]:
    """Return the list of default table configs from config.toml."""
    return _load_config().get("default_tables", [])


def get_update_config() -> dict:
    """Return update-related settings from config.toml."""
    config = _load_config()
    return {
        "update_interval_hours": config.get("update_interval_hours", 24),
        "backup_count": config.get("backup_count", 3),
        "min_request_interval_hours": config.get("min_request_interval_hours", 6),
    }
