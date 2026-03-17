"""BMS scan cache — mtime+size based hash cache for fast re-sync.

Cache file: ~/.ojik/scan_cache.json
Schema version: 1
"""
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ojikbms_client.config import CONFIG_DIR

CACHE_FILE = CONFIG_DIR / "scan_cache.json"
CACHE_VERSION = 1


def load_cache() -> dict[str, Any]:
    """Load scan cache from disk.

    Returns:
        Cache dict with 'files', 'owned_songs_snapshot', 'updated_at'.
        Returns empty cache on missing/corrupt file.
    """
    if not CACHE_FILE.exists():
        return _empty_cache()

    try:
        with CACHE_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CACHE_VERSION:
            return _empty_cache()
        return data
    except (json.JSONDecodeError, OSError, KeyError):
        return _empty_cache()


def save_cache(
    file_entries: dict[str, dict[str, Any]],
    owned_songs_snapshot: list[dict[str, Any]],
) -> None:
    """Save scan cache to disk.

    Args:
        file_entries: Mapping of absolute file path → {mtime, size, md5, sha256}.
        owned_songs_snapshot: List of owned song dicts (song_md5, song_sha256, …).
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "version": CACHE_VERSION,
        "files": file_entries,
        "owned_songs_snapshot": owned_songs_snapshot,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def get_cached_hashes(
    cache: dict[str, Any],
    file_path: Path,
) -> tuple[str, str] | None:
    """Return (md5, sha256) from cache if mtime+size match, else None.

    Args:
        cache: Cache dict returned by load_cache().
        file_path: Absolute path to the BMS file.

    Returns:
        (md5_hex, sha256_hex) if cache hit, None if stale/missing.
    """
    key = str(file_path)
    entry = cache.get("files", {}).get(key)
    if entry is None:
        return None

    try:
        stat = file_path.stat()
    except OSError:
        return None

    if entry.get("mtime") == stat.st_mtime and entry.get("size") == stat.st_size:
        md5 = entry.get("md5")
        sha256 = entry.get("sha256")
        if md5 and sha256:
            return md5, sha256

    return None


def build_cache_entry(file_path: Path, md5: str, sha256: str) -> dict[str, Any]:
    """Build a cache entry dict for a scanned file.

    Args:
        file_path: Absolute path to the BMS file.
        md5: MD5 hex digest.
        sha256: SHA256 hex digest.

    Returns:
        Dict with mtime, size, md5, sha256.
    """
    try:
        stat = file_path.stat()
        return {
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "md5": md5,
            "sha256": sha256,
        }
    except OSError:
        return {"mtime": 0.0, "size": 0, "md5": md5, "sha256": sha256}


def get_owned_songs_snapshot(cache: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the cached owned_songs_snapshot, empty list if missing."""
    return cache.get("owned_songs_snapshot", [])


def has_valid_cache(cache: dict[str, Any]) -> bool:
    """Return True if the cache contains at least one file entry."""
    return bool(cache.get("files"))


def _empty_cache() -> dict[str, Any]:
    return {
        "version": CACHE_VERSION,
        "files": {},
        "owned_songs_snapshot": [],
        "updated_at": None,
    }


def clear_cache() -> None:
    """Delete the scan cache file."""
    try:
        if CACHE_FILE.exists():
            os.remove(CACHE_FILE)
    except OSError:
        pass
