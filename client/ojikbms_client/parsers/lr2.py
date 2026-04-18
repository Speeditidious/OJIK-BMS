"""LR2 score database parser.

LR2 uses SQLite databases:
- LR2files/LR2song.db  : Song metadata (SHA256, title, artist, etc.)
- LR2files/score/score.db : Player scores

Score table schema (score.db):
    CREATE TABLE score (
        sha256       TEXT PRIMARY KEY,
        clear        INTEGER,   -- 0=No Play, 1=Failed, 2=Easy Clear, ...
        pg           INTEGER,   -- PGreat count
        gr           INTEGER,   -- Great count
        gd           INTEGER,   -- Good count
        bd           INTEGER,   -- Bad count
        pr           INTEGER,   -- Poor count
        maxcombo     INTEGER,
        minbp        INTEGER,
        playtime     INTEGER,   -- Unix timestamp of last play
        playcount    INTEGER,
        rate         REAL,      -- Score rate (0.0 - 1.0)
        clear_db     INTEGER,
        op_dp        INTEGER,
        scorehash    TEXT,
        complete     INTEGER
    )
"""
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ParseStats:
    """Counters collected during a single parser run."""

    db_total: int = 0           # Total rows in score table (no filter)
    query_result_count: int = 0  # Rows returned after WHERE clause
    skipped_hash: int = 0       # Rows dropped due to missing/invalid hash
    parsed_courses: int = 0     # Course (multi-song) records extracted for sync
    parsed: int = 0             # Single-song rows successfully converted to score dicts

    @property
    def skipped_filter(self) -> int:
        """Rows excluded by the playcount/mode/player WHERE clause."""
        return self.db_total - self.query_result_count

    @property
    def effective_total(self) -> int:
        """Total rows excluding intentionally-skipped records (none for LR2)."""
        return self.db_total

    @property
    def skipped_lr2(self) -> int:
        """LR2 has no LR2-import exclusions."""
        return 0


# LR2 arrangement (note layout) enum — shared between 1P and 2P nibbles
LR2_ARRANGEMENT = {
    0: "NORMAL",
    1: "MIRROR",
    2: "RANDOM",
    3: "S-RANDOM",
    4: "H-RANDOM",
    5: "ALL-SCRATCH",
}

# LR2 clear type mapping (DB value → internal clear type)
# Internal types: 0=NO PLAY, 1=FAILED, 3=EASY, 4=NORMAL, 5=HARD, 7=FC
# LR2 has no ASSIST (2), EXHARD (6), PERFECT (8), or MAX (9) grades.
LR2_CLEAR_TYPE = {
    0: 0,   # No Play
    1: 1,   # Failed
    2: 3,   # Easy Clear  (LR2 DB 2 → internal 3)
    3: 4,   # Normal Clear
    4: 5,   # Hard Clear
    5: 7,   # Full Combo  (LR2 DB 5 → internal 7)
    # Types 6 and 7 removed — no evidence in LR2 DB; LR2 has no PERFECT/MAX grades
}

# Candidate column names for the song hash column across LR2 versions
# LR2 score.db stores MD5 (32 chars) in this column, not SHA256
_HASH_CANDIDATES = ("sha256", "hash", "SHA256", "Hash")

# Candidate column names for judgment counts across LR2 versions
_JUDGMENT_CANDIDATES = {
    "pg": ("pg", "pgreat", "p_great", "perfect"),  # LR2 actual column: "perfect"
    "gr": ("gr", "great"),
    "gd": ("gd", "good"),
    "bd": ("bd", "bad"),
    "pr": ("pr", "poor"),
    "maxcombo": ("maxcombo", "max_combo", "combo"),
    "minbp": ("minbp", "min_bp"),
    "playtime": ("playtime", "play_time", "date", "last_play"),
    "playcount": ("playcount", "play_count"),
    "rate": ("rate", "score_rate"),
    "clear": ("clear", "clear_type"),
    "op_best": ("op_best", "opbest"),
    "op_history": ("op_history", "ophistory"),
    "rseed": ("rseed", "random_seed", "seed"),
    "clearcount": ("clearcount", "clear_count"),
    "scorehash": ("scorehash",),
    "totalnotes": ("totalnotes", "total_notes", "notes"),
}


def _decode_lr2_options(op_best: int, op_history: int, rseed: int | None) -> dict:
    """Return LR2 play options as raw DB integers.

    Args:
        op_best: op_best column value (raw int; tens digit = arrangement, units = gauge).
        op_history: op_history column value (raw bitmask).
        rseed: rseed column value (random seed; None if column absent).

    Returns:
        Dict with op_best, op_history, rseed raw int keys.
    """
    return {
        "op_best": op_best,
        "op_history": op_history,
        "rseed": rseed,
    }


def _get_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    """Return the set of column names for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _resolve_col(available: set[str], candidates: tuple[str, ...]) -> str | None:
    """Return the first candidate column name that exists in the table."""
    for name in candidates:
        if name in available:
            return name
    return None


def parse_lr2_scores(
    score_db_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], ParseStats]:
    """
    Parse LR2 score.db and return single-song scores, course records, and parse statistics.

    Args:
        score_db_path: Path to the LR2 score.db file.

    Returns:
        Tuple of (score list, course list, ParseStats).
        Score list matches ScoreSyncItem schema; course list matches CourseSyncItem schema.

    Raises:
        FileNotFoundError: If the database file does not exist.
        ValueError: If the database schema is unrecognized.
    """
    db_path = Path(score_db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"LR2 score DB not found: {db_path}")

    scores: list[dict[str, Any]] = []
    courses: list[dict[str, Any]] = []
    stats = ParseStats()

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        available = _get_columns(cursor, "score")
        if not available:
            raise ValueError(
                f"Table 'score' not found in {db_path}. "
                f"Tables: {_list_tables(cursor)}"
            )

        # Resolve hash column (stores MD5 in most LR2 versions, rarely SHA256)
        sha256_col = _resolve_col(available, _HASH_CANDIDATES)
        if sha256_col is None:
            raise ValueError(
                f"Cannot find hash column in LR2 score table. "
                f"Available columns: {sorted(available)}"
            )

        # Resolve optional columns with fallback to None
        cols = {key: _resolve_col(available, cands) for key, cands in _JUDGMENT_CANDIDATES.items()}

        # Build SELECT for only existing columns
        select_cols = [sha256_col]
        for col in cols.values():
            if col and col not in select_cols:
                select_cols.append(col)

        playcount_col = cols["playcount"]
        where = f"WHERE {playcount_col} > 0" if playcount_col else ""

        # Count total rows before any filter
        cursor.execute("SELECT COUNT(*) FROM score")
        stats.db_total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT {', '.join(select_cols)} FROM score {where}"
        )

        rows = cursor.fetchall()
        stats.query_result_count = len(rows)

        for row in rows:
            def _int(col: str | None) -> int:
                return int(row[col]) if col and row[col] is not None else 0

            def _int_or_none(col: str | None) -> int | None:
                """Like _int but returns None instead of 0 for missing/null columns.
                Use this for fields where 0 is a meaningful value (e.g. min_bp=0 for perfect play)."""
                if not col or row[col] is None:
                    return None
                return int(row[col])

            raw_hash = (row[sha256_col] or "").strip().replace("\x00", "")
            if not raw_hash:
                stats.skipped_hash += 1
                continue

            if len(raw_hash) > 64:
                # Course (multi-song) record.
                # LR2 format: 32-char header + N×32-char MD5 (one per song).
                # Preserve the full raw_hash verbatim — the 32-char header is
                # part of LR2's original identifier; stripping it loses information.
                # Extract song MD5s from the suffix only for the song_hashes payload.
                song_md5s = [
                    raw_hash[i : i + 32]
                    for i in range(32, len(raw_hash), 32)
                    if len(raw_hash[i : i + 32]) == 32
                ]
                if not song_md5s:
                    stats.skipped_hash += 1
                    continue

                played_at_c = None
                playtime_col = cols["playtime"]
                if playtime_col and row[playtime_col] is not None:
                    ts = int(row[playtime_col])
                    if ts > 0:
                        try:
                            played_at_c = datetime.fromtimestamp(ts, tz=UTC).isoformat()
                        except (ValueError, OSError):
                            pass

                clear_col_c = cols["clear"]
                clear_val_c = int(row[clear_col_c]) if clear_col_c and row[clear_col_c] is not None else 0

                scorehash_col_c = cols.get("scorehash")
                scorehash_c = None
                if scorehash_col_c and row[scorehash_col_c]:
                    scorehash_c = str(row[scorehash_col_c]).strip() or None

                judgments_c = {
                    "perfect": _int(cols["pg"]),
                    "great": _int(cols["gr"]),
                    "good": _int(cols["gd"]),
                    "bad": _int(cols["bd"]),
                    "poor": _int(cols["pr"]),
                }
                op_best_c = _int(cols["op_best"])
                op_history_c = _int(cols["op_history"])
                rseed_col_c = cols["rseed"]
                rseed_c = int(row[rseed_col_c]) if rseed_col_c and row[rseed_col_c] is not None else None

                courses.append({
                    "fumen_hash_others": raw_hash,
                    "client_type": "lr2",
                    "scorehash": scorehash_c,
                    "clear_type": LR2_CLEAR_TYPE.get(clear_val_c, 0),
                    "notes": _int(cols["totalnotes"]) or None,
                    "max_combo": _int(cols["maxcombo"]) or None,
                    "min_bp": _int_or_none(cols["minbp"]),
                    "judgments": judgments_c,
                    "play_count": _int(cols["playcount"]),
                    "clear_count": _int(cols["clearcount"]),
                    "recorded_at": played_at_c,
                    "options": _decode_lr2_options(op_best_c, op_history_c, rseed_c),
                    "song_hashes": [
                        {"song_md5": md5, "song_sha256": None}
                        for md5 in song_md5s
                    ],
                })
                stats.parsed_courses += 1
                continue

            if len(raw_hash) not in (32, 64):
                stats.skipped_hash += 1
                continue

            # LR2 score.db stores MD5 (32 chars); SHA256 (64 chars) is rare
            song_md5: str | None = None
            song_sha256: str | None = None
            if len(raw_hash) == 32:
                song_md5 = raw_hash
            else:
                song_sha256 = raw_hash

            played_at = None
            playtime_col = cols["playtime"]
            if playtime_col and row[playtime_col] is not None:
                ts = int(row[playtime_col])
                if ts > 0:
                    try:
                        played_at = datetime.fromtimestamp(ts, tz=UTC).isoformat()
                    except (ValueError, OSError):
                        pass

            judgments = {
                "perfect": _int(cols["pg"]),
                "great": _int(cols["gr"]),
                "good": _int(cols["gd"]),
                "bad": _int(cols["bd"]),
                "poor": _int(cols["pr"]),
            }

            clear_col = cols["clear"]
            clear_val = int(row[clear_col]) if clear_col and row[clear_col] is not None else 0

            op_best = _int(cols["op_best"])
            op_history = _int(cols["op_history"])
            rseed_col = cols["rseed"]
            rseed = int(row[rseed_col]) if rseed_col and row[rseed_col] is not None else None

            scorehash_col = cols.get("scorehash")
            scorehash = None
            if scorehash_col and row[scorehash_col]:
                scorehash = str(row[scorehash_col]).strip() or None

            _clear_type = LR2_CLEAR_TYPE.get(clear_val, 0)
            if _clear_type == 7:  # FC → check for PERFECT / MAX
                if judgments["good"] == 0 and judgments["bad"] == 0:
                    _clear_type = 8  # PERFECT
                    if judgments["great"] == 0:
                        _clear_type = 9  # MAX

            scores.append({
                "fumen_md5": song_md5,
                "fumen_sha256": song_sha256,
                "scorehash": scorehash,
                "client_type": "lr2",
                "clear_type": _clear_type,
                "notes": _int(cols["totalnotes"]) or None,
                "max_combo": _int(cols["maxcombo"]) or None,
                "min_bp": _int_or_none(cols["minbp"]),
                "judgments": judgments,
                "play_count": _int(cols["playcount"]),
                "clear_count": _int(cols["clearcount"]),
                "recorded_at": played_at,
                "options": _decode_lr2_options(op_best, op_history, rseed),
            })

    stats.parsed = len(scores)
    return scores, courses, stats


def _list_tables(cursor: sqlite3.Cursor) -> list[str]:
    """Return list of table names in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]


def parse_lr2_player_stats(score_db_path: str) -> dict | None:
    """Read cumulative totals from LR2 player table.

    Args:
        score_db_path: Path to the LR2 score.db file.

    Returns:
        Dict with playcount, clearcount, playtime, and judgments (raw counts),
        or None if player table is absent.
    """
    db_path = Path(score_db_path)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(player)")
            columns = {row[1] for row in cursor.fetchall()}
            if not columns:
                return None

            pg_col  = _resolve_col(columns, ("perfect", "pg", "pgreat", "p_great"))
            gr_col  = _resolve_col(columns, ("great", "gr"))
            gd_col  = _resolve_col(columns, ("good", "gd"))
            bd_col  = _resolve_col(columns, ("bad", "bd"))
            pr_col  = _resolve_col(columns, ("poor", "pr"))
            pc_col  = _resolve_col(columns, ("playcount", "play_count"))
            cc_col  = _resolve_col(columns, ("clear", "clearcount", "clear_count"))
            pt_col  = _resolve_col(columns, ("playtime", "play_time"))

            judgment_cols = [c for c in [pg_col, gr_col, gd_col, bd_col, pr_col] if c]
            if not judgment_cols:
                return None

            select_parts = list(dict.fromkeys(
                judgment_cols
                + [c for c in [pc_col, cc_col, pt_col] if c]
            ))

            cursor.execute(f"SELECT {', '.join(select_parts)} FROM player LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                return None

            col_index = {col: i for i, col in enumerate(select_parts)}

            def _val(col: str | None) -> int | None:
                if col and col in col_index:
                    v = row[col_index[col]]
                    return int(v) if v is not None else None
                return None

            judgments = {}
            for key, col in [
                ("perfect", pg_col),
                ("great",   gr_col),
                ("good",    gd_col),
                ("bad",     bd_col),
                ("poor",    pr_col),
            ]:
                v = _val(col)
                if v is not None:
                    judgments[key] = v

            return {
                "playcount":  _val(pc_col),
                "clearcount": _val(cc_col),
                "playtime":   _val(pt_col),
                "judgments":  judgments or None,
            }
    except Exception:
        return None


def parse_lr2_songdata(db_path: str) -> list[dict[str, Any]]:
    """Parse LR2 song.db (LR2song.db) and return song metadata items.

    Each returned dict contains: md5, title, artist, bpm_min, bpm_max.
    Only rows with valid 32-char MD5 hashes are returned.
    Does NOT extract karinotes (LR2 counts LN as 2, server counts as 1 → incompatible).

    Args:
        db_path: Full path to LR2song.db.

    Returns:
        List of dicts. Returns [] on error or if file does not exist.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return []

    items: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(str(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='song'")
            if not cursor.fetchone():
                return []

            cursor.execute("PRAGMA table_info(song)")
            columns = {row[1] for row in cursor.fetchall()}

            hash_col = None
            for candidate in ("hash", "sha256", "Hash"):
                if candidate in columns:
                    hash_col = candidate
                    break
            if not hash_col:
                return []

            title_col = "title" if "title" in columns else None
            subtitle_col = "subtitle" if "subtitle" in columns else None
            artist_col = "artist" if "artist" in columns else None
            subartist_col = "subartist" if "subartist" in columns else None
            minbpm_col = "minbpm" if "minbpm" in columns else None
            maxbpm_col = "maxbpm" if "maxbpm" in columns else None

            select_parts = [hash_col]
            for col in (title_col, subtitle_col, artist_col, subartist_col, minbpm_col, maxbpm_col):
                if col:
                    select_parts.append(col)

            cursor.execute(
                f"SELECT {', '.join(select_parts)} FROM song "
                f"WHERE {hash_col} IS NOT NULL AND {hash_col} != ''"
            )

            for row in cursor.fetchall():
                hash_val = row[hash_col]
                if not hash_val or len(hash_val) != 32:
                    continue

                item: dict[str, Any] = {"md5": hash_val}
                if title_col:
                    _title = row[title_col] or ""
                    _subtitle = (row[subtitle_col] or "") if subtitle_col else ""
                    item["title"] = (_title + " " + _subtitle).strip() or None
                if artist_col:
                    _artist = row[artist_col] or ""
                    _subartist = (row[subartist_col] or "") if subartist_col else ""
                    item["artist"] = (_artist + " " + _subartist).strip() or None
                if minbpm_col and row[minbpm_col] is not None:
                    item["bpm_min"] = float(row[minbpm_col])
                if maxbpm_col and row[maxbpm_col] is not None:
                    item["bpm_max"] = float(row[maxbpm_col])
                items.append(item)

    except Exception:
        return []

    return items


