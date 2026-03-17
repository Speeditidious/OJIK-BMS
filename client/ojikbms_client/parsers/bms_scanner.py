"""BMS file scanner with MD5/SHA256 hashing and header metadata extraction.

Scans BMS folders for .bms, .bme, .bml, and .bmson files,
computing MD5 and SHA256 hashes and extracting chart metadata (title, artist, etc.).
"""
import hashlib
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

console = Console()

BMS_EXTENSIONS = {".bms", ".bme", ".bml", ".bmson", ".pms"}
HASH_BUFFER_SIZE = 65536  # 64 KB read chunks
# SHA256 of empty string — skip zero-byte files
_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
# I/O-bound workload: more threads than CPU cores is beneficial on /mnt/c/ paths
HASH_WORKERS = min(16, (os.cpu_count() or 4) * 2)
# Emit at most one progress update per this many files to avoid saturating the Qt event queue.
# At 100K files: 1000 emits instead of 100K.
_PROGRESS_EMIT_INTERVAL = 100

# Maximum bytes to buffer for header parsing (BMS headers are always in the first few KB)
_HEADER_LIMIT = 8192
# BMS header field regex: matches lines like "#TITLE My Song"
_HEADER_RE = re.compile(r"^#([A-Za-z0-9_]+)\s+(.*)", re.MULTILINE)
# Fields we want to extract from BMS headers
_WANTED_FIELDS = frozenset({"title", "artist", "subtitle", "subartist", "bpm"})
# Encodings to try in order (Japanese/Korean BMS files are usually CP932 or CP949)
_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "cp949", "latin-1")


def _parse_bms_header(data: bytes) -> dict[str, Any]:
    """
    Extract metadata fields from raw BMS file bytes.

    Tries multiple encodings and reads only the first _HEADER_LIMIT bytes.
    Returns a dict with any subset of: title, artist, subtitle, bpm.
    """
    text = None
    for enc in _ENCODINGS:
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if text is None:
        return {}

    result: dict[str, Any] = {}
    for m in _HEADER_RE.finditer(text):
        key = m.group(1).lower()
        if key in _WANTED_FIELDS and key not in result:
            result[key] = m.group(2).strip()
        if len(result) == len(_WANTED_FIELDS):
            break

    if "bpm" in result:
        try:
            result["bpm"] = float(result["bpm"])
        except ValueError:
            result.pop("bpm")

    return result


def _scan_bms_file(file_path: Path) -> tuple[str, str, dict[str, Any]]:
    """
    Compute MD5/SHA256 hashes and extract BMS header metadata in a single file read.

    Args:
        file_path: Path to the BMS file.

    Returns:
        Tuple of (md5_hex, sha256_hex, metadata_dict).
        metadata_dict contains title, artist, subtitle, bpm (as available).
    """
    md5_h = hashlib.md5()
    sha256_h = hashlib.sha256()
    header_buf = bytearray()
    header_done = False

    with file_path.open("rb") as f:
        while chunk := f.read(HASH_BUFFER_SIZE):
            md5_h.update(chunk)
            sha256_h.update(chunk)
            if not header_done:
                remaining = _HEADER_LIMIT - len(header_buf)
                header_buf.extend(chunk[:remaining])
                if len(header_buf) >= _HEADER_LIMIT:
                    header_done = True

    meta: dict[str, Any] = {}
    if file_path.suffix.lower() != ".bmson":
        meta = _parse_bms_header(bytes(header_buf))

    return md5_h.hexdigest(), sha256_h.hexdigest(), meta


def compute_file_hashes(file_path: Path) -> tuple[str, str]:
    """
    Compute MD5 and SHA256 hashes for a file.

    Args:
        file_path: Path to the file.

    Returns:
        Tuple of (md5_hex, sha256_hex).
    """
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    with file_path.open("rb") as f:
        while chunk := f.read(HASH_BUFFER_SIZE):
            md5.update(chunk)
            sha256.update(chunk)

    return md5.hexdigest(), sha256.hexdigest()


def scan_bms_folders(
    folder_paths: list[str],
    show_progress: bool = True,
    cache: dict[str, Any] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Recursively scan BMS folders, compute hashes, and extract chart metadata.

    If a cache dict is provided (from scan_cache.load_cache()), files whose
    mtime and size have not changed are not re-hashed — their cached hashes
    are reused directly.

    Args:
        folder_paths: List of folder paths to scan.
        show_progress: Whether to display a Rich progress bar (CLI mode).
        cache: Optional cache dict from scan_cache.load_cache().
        progress_callback: Optional callback(current, total, filename) for GUI.
        log_callback: Optional callback(message) for emitting log lines to GUI.

    Returns:
        Tuple of (owned_songs, new_file_entries) where new_file_entries is a
        dict mapping absolute path → {mtime, size, md5, sha256} for use with
        scan_cache.save_cache().
    """
    from ojikbms_client.scan_cache import build_cache_entry, get_cached_hashes

    def _warn(msg: str) -> None:
        console.print(f"[yellow]{msg}[/yellow]")
        if log_callback:
            log_callback(f"[WARN] {msg}")

    # Collect all BMS files first.
    # os.walk is used instead of Path.rglob so that I/O errors on individual
    # subdirectories (common on WSL2 /mnt/c/ paths) are skipped rather than
    # aborting the entire scan.
    all_files: list[Path] = []
    _discovered = 0
    for folder_str in folder_paths:
        folder = Path(folder_str)
        if not folder.exists():
            _warn(f"폴더를 찾을 수 없습니다: {folder}")
            continue

        for dirpath, _, filenames in os.walk(
            folder, onerror=lambda e: _warn(f"디렉토리 접근 불가 (건너뜀): {e}")
        ):
            for filename in filenames:
                if Path(filename).suffix.lower() in BMS_EXTENSIONS:
                    fp = Path(dirpath) / filename
                    all_files.append(fp)
                    _discovered += 1
                    if progress_callback and _discovered % _PROGRESS_EMIT_INTERVAL == 0:
                        progress_callback(_discovered, 0, "")

    # Emit the exact final count (last batch may be < _PROGRESS_EMIT_INTERVAL)
    if progress_callback and all_files:
        progress_callback(len(all_files), 0, "")

    if not all_files:
        return [], {}

    owned_songs: list[dict[str, Any]] = []
    new_file_entries: dict[str, Any] = {}
    errors: list[str] = []
    skipped_empty = 0

    total = len(all_files)

    # Partition files into cache-hit and needs-hash sets.
    # Each iteration calls fp.stat() — can be slow on WSL2 /mnt paths.
    # Emit deterministic progress so the UI shows "캐시 확인" instead of stalling.
    cached_results: list[tuple[Path, str, str]] = []
    files_to_hash: list[Path] = []

    if cache is not None:
        for i, fp in enumerate(all_files, 1):
            hit = get_cached_hashes(cache, fp)
            if hit is not None:
                cached_results.append((fp, hit[0], hit[1]))
            else:
                files_to_hash.append(fp)
            if progress_callback and (i % _PROGRESS_EMIT_INTERVAL == 0 or i == total):
                progress_callback(i, total, fp.name)
    else:
        files_to_hash = all_files

    # Carry over cache entries in bulk — avoids per-item dict lookup in the hot loop
    cached_file_entries = cache.get("files", {}) if cache is not None else {}

    # Apply cache hits (fast dict access — no progress needed, subsumed by partition above)
    for fp, md5_hex, sha256_hex in cached_results:
        if sha256_hex != _EMPTY_SHA256:
            owned_songs.append({"song_md5": md5_hex, "song_sha256": sha256_hex})
            existing = cached_file_entries.get(str(fp))
            if existing:
                new_file_entries[str(fp)] = existing
        else:
            skipped_empty += 1

    hash_total = len(files_to_hash)
    hash_done = 0

    if files_to_hash and log_callback:
        log_callback(f"[INFO] 신규 BMS 파일들 불러오는 중... ({hash_total:,}개)")

    def _hash_and_callback(fp: Path) -> tuple[Path, str, str, dict[str, Any]]:
        md5_hex, sha256_hex, meta = _scan_bms_file(fp)
        return fp, md5_hex, sha256_hex, meta

    if files_to_hash:
        with ThreadPoolExecutor(max_workers=HASH_WORKERS) as executor:
            future_to_path = {
                executor.submit(_hash_and_callback, fp): fp for fp in files_to_hash
            }

            if show_progress and not progress_callback:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task("BMS 파일 해싱 중...", total=hash_total)
                    for future in as_completed(future_to_path):
                        try:
                            fp, md5_hex, sha256_hex, meta = future.result()
                            if sha256_hex != _EMPTY_SHA256:
                                owned_songs.append({
                                    "song_md5": md5_hex,
                                    "song_sha256": sha256_hex,
                                    **meta,
                                })
                                new_file_entries[str(fp)] = build_cache_entry(fp, md5_hex, sha256_hex)
                            else:
                                skipped_empty += 1
                        except (OSError, PermissionError) as e:
                            errors.append(f"{future_to_path[future]}: {e}")
                        finally:
                            progress.advance(task)
            else:
                for future in as_completed(future_to_path):
                    try:
                        fp, md5_hex, sha256_hex, meta = future.result()
                        if sha256_hex != _EMPTY_SHA256:
                            owned_songs.append({
                                "song_md5": md5_hex,
                                "song_sha256": sha256_hex,
                                **meta,
                            })
                            new_file_entries[str(fp)] = build_cache_entry(fp, md5_hex, sha256_hex)
                        else:
                            skipped_empty += 1
                    except (OSError, PermissionError) as e:
                        errors.append(f"{future_to_path[future]}: {e}")
                    finally:
                        hash_done += 1
                        if progress_callback and (
                            hash_done % _PROGRESS_EMIT_INTERVAL == 0 or hash_done == hash_total
                        ):
                            progress_callback(hash_done, hash_total, future_to_path[future].name)

    if errors:
        _warn(f"파일 읽기 오류 {len(errors)}개 발생:")
        for err in errors[:10]:
            if log_callback:
                log_callback(f"[WARN] &nbsp;&nbsp;• {err}")
        if len(errors) > 10:
            if log_callback:
                log_callback(f"[WARN] &nbsp;&nbsp;... 외 {len(errors) - 10}개")

    return owned_songs, new_file_entries, {"skipped_empty": skipped_empty, "error_count": len(errors)}


def scan_single_file(file_path: str) -> dict[str, Any] | None:
    """
    Scan and hash a single BMS file.

    Args:
        file_path: Path to the BMS file.

    Returns:
        Dict with song_md5, song_sha256, and extracted metadata, or None if file is invalid.
    """
    path = Path(file_path)

    if not path.exists():
        return None

    if path.suffix.lower() not in BMS_EXTENSIONS:
        return None

    try:
        md5_hex, sha256_hex, meta = _scan_bms_file(path)
        return {
            "song_md5": md5_hex,
            "song_sha256": sha256_hex,
            "file_path": str(path),
            "file_name": path.name,
            **meta,
        }
    except (OSError, PermissionError):
        return None
