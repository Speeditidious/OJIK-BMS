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
from datetime import datetime, timezone
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
}


def _decode_lr2_options(op_best: int, op_history: int, rseed: int | None) -> dict:
    """Decode LR2 play options from raw DB integers.

    Args:
        op_best: op_best column value. Tens digit encodes the arrangement
            (e.g. 3=NORMAL, 10=MIRROR, 21=RANDOM, 31=S-RANDOM). Units digit
            encodes the gauge type (0=GROOVE, 1=SURVIVAL, etc.).
        op_history: op_history column value. Statistical analysis shows bit N
            correlates with the gauge type history (units digit of op_best),
            NOT arrangement history. Stored as a raw bitmask only.
        rseed: rseed column value (random seed; None if column absent).

    Returns:
        Dict with arrangement, arrangement_2p, arrangement_raw, history_raw, seed keys.
    """
    arr_index = op_best // 10  # tens digit = arrangement
    arr_1p = LR2_ARRANGEMENT.get(arr_index, f"UNKNOWN({arr_index})")

    return {
        "arrangement": arr_1p,
        "arrangement_2p": None,  # 2P arrangement not encoded in op_best (units digit unknown)
        "arrangement_raw": op_best,
        "history_raw": op_history,  # raw bitmask: encodes gauge type history, NOT arrangement
        "seed": rseed if rseed else None,
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

            raw_hash = (row[sha256_col] or "").strip().replace("\x00", "")
            if not raw_hash:
                stats.skipped_hash += 1
                continue

            if len(raw_hash) > 64:
                # Course (multi-song) record.
                # LR2 format: 32-char header + N×32-char MD5 (one per song).
                songs_part = raw_hash[32:]
                song_md5s = [
                    songs_part[i : i + 32]
                    for i in range(0, len(songs_part), 32)
                    if len(songs_part[i : i + 32]) == 32
                ]
                if not song_md5s:
                    stats.skipped_hash += 1
                    continue

                played_at_c = None
                playtime_col = cols["playtime"]
                if playtime_col and row[playtime_col]:
                    try:
                        played_at_c = datetime.fromtimestamp(
                            row[playtime_col], tz=timezone.utc
                        ).isoformat()
                    except (ValueError, OSError):
                        pass

                score_rate_c = row[cols["rate"]] if cols["rate"] else None
                if score_rate_c is not None and score_rate_c > 1.0:
                    score_rate_c = score_rate_c / 100.0

                clear_col_c = cols["clear"]
                clear_val_c = int(row[clear_col_c]) if clear_col_c and row[clear_col_c] is not None else 0

                courses.append({
                    "course_hash": songs_part.lower(),
                    "client_type": "lr2",
                    "clear_type": LR2_CLEAR_TYPE.get(clear_val_c, 0),
                    "score_rate": score_rate_c,
                    "max_combo": _int(cols["maxcombo"]) or None,
                    "min_bp": _int(cols["minbp"]) or None,
                    "play_count": _int(cols["playcount"]),
                    "clear_count": _int(cols["clearcount"]),
                    "played_at": played_at_c,
                    "song_hashes": [
                        {"song_md5": md5.lower(), "song_sha256": None}
                        for md5 in song_md5s
                    ],
                })
                stats.parsed_courses += 1
                continue

            if len(raw_hash) not in (32, 64):
                stats.skipped_hash += 1
                continue

            # LR2 score.db stores MD5 (32 chars); SHA256 (64 chars) is rare
            # Normalize to lowercase to ensure consistent matching in the DB
            song_md5: str | None = None
            song_sha256: str | None = None
            if len(raw_hash) == 32:
                song_md5 = raw_hash.lower()
            else:
                song_sha256 = raw_hash.lower()

            played_at = None
            playtime_col = cols["playtime"]
            if playtime_col and row[playtime_col]:
                try:
                    played_at = datetime.fromtimestamp(
                        row[playtime_col], tz=timezone.utc
                    ).isoformat()
                except (ValueError, OSError):
                    pass

            score_rate = row[cols["rate"]] if cols["rate"] else None
            if score_rate is not None and score_rate > 1.0:
                score_rate = score_rate / 100.0

            judgments = {
                "pgreat": _int(cols["pg"]),
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

            _clear_type = LR2_CLEAR_TYPE.get(clear_val, 0)
            if _clear_type == 7:  # FC → check for PERFECT / MAX
                if judgments["good"] == 0 and judgments["bad"] == 0:
                    _clear_type = 8  # PERFECT
                    if judgments["great"] == 0:
                        _clear_type = 9  # MAX

            scores.append({
                "song_md5": song_md5,
                "song_sha256": song_sha256,
                "client_type": "lr2",
                "clear_type": _clear_type,
                "score_rate": score_rate,
                "max_combo": _int(cols["maxcombo"]) or None,
                "min_bp": _int(cols["minbp"]) or None,
                "judgments": judgments,
                "play_count": _int(cols["playcount"]),
                "clear_count": _int(cols["clearcount"]),
                "played_at": played_at,
                "options": _decode_lr2_options(op_best, op_history, rseed),
            })

    stats.parsed = len(scores)
    return scores, courses, stats


def _list_tables(cursor: sqlite3.Cursor) -> list[str]:
    """Return list of table names in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]


def parse_lr2_player_stats(score_db_path: str) -> dict[str, int] | None:
    """Read cumulative totals from LR2 player table.

    Args:
        score_db_path: Path to the LR2 score.db file.

    Returns:
        Dict with total_notes_hit and total_play_count, or None if table absent.
    """
    db_path = Path(score_db_path)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()

            # Check if player table exists
            cursor.execute("PRAGMA table_info(player)")
            columns = {row[1] for row in cursor.fetchall()}
            if not columns:
                return None

            # Resolve judgment columns
            pg_col = _resolve_col(columns, ("perfect", "pg", "pgreat", "p_great"))
            gr_col = _resolve_col(columns, ("great", "gr"))
            gd_col = _resolve_col(columns, ("good", "gd"))
            bd_col = _resolve_col(columns, ("bad", "bd"))
            pc_col = _resolve_col(columns, ("playcount", "play_count"))

            if not any([pg_col, gr_col, gd_col, bd_col]):
                return None

            hit_cols = [c for c in [pg_col, gr_col, gd_col, bd_col] if c]
            select_parts = hit_cols[:]
            if pc_col:
                select_parts.append(pc_col)

            cursor.execute(f"SELECT {', '.join(select_parts)} FROM player LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                return None

            col_index = {col: i for i, col in enumerate(select_parts)}
            total_notes_hit = sum(
                int(row[col_index[c]] or 0) for c in hit_cols
            )

            total_play_count = None
            if pc_col and pc_col in col_index:
                val = row[col_index[pc_col]]
                if val is not None:
                    total_play_count = int(val)

            return {
                "total_notes_hit": total_notes_hit,
                "total_play_count": total_play_count,
            }
    except Exception:
        return None


