"""Beatoraja score database parser.

Beatoraja uses SQLite databases located in the data/ directory:
- data/score.db       : Current best scores (score table)
- data/scorelog.db    : Score history (scorelog table)

score.db schema (may vary by version):
    CREATE TABLE score (
        sha256      TEXT NOT NULL,
        mode        INTEGER NOT NULL,    -- 0=SP, 1=DP
        player      INTEGER NOT NULL,    -- 0=1P, 1=2P
        clear       INTEGER,
        ep          INTEGER,             -- PGreat (exact perfect)
        lp          INTEGER,             -- Great (late perfect)
        eg          INTEGER,             -- Great (early great)
        lg          INTEGER,             -- Great (late great)
        egd         INTEGER,             -- Good
        lgd         INTEGER,             -- Good
        ebd         INTEGER,             -- Bad
        lbd         INTEGER,             -- Bad
        epr         INTEGER,             -- Poor
        lpr         INTEGER,             -- Poor
        ems         INTEGER,             -- Miss
        maxcombo    INTEGER,
        minbp       INTEGER,
        playcount   INTEGER,
        clearcount  INTEGER,
        failcount   INTEGER,
        rank        INTEGER,
        exscore     INTEGER,
        option      INTEGER,
        assist      INTEGER,
        date        INTEGER,             -- Unix timestamp
        url         TEXT,
        notes       INTEGER,
        PRIMARY KEY (sha256, mode, player)
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


# Beatoraja arrangement (note layout) enum — from Beatoraja open source (option column)
BEATORAJA_ARRANGEMENT = {
    0: "NORMAL",
    1: "MIRROR",
    2: "RANDOM",
    3: "R-RANDOM",
    4: "S-RANDOM",
    5: "SPIRAL",
    6: "H-RANDOM",
    7: "ALL-SCRATCH",
    8: "EX-RAN",
    9: "EX-S-RAN",
}

# Beatoraja clear type mapping (DB value → internal clear type)
# Internal types: 0=NO PLAY, 1=FAILED, 2=ASSIST, 3=EASY, 4=NORMAL,
#                 5=HARD, 6=EXHARD, 7=FC, 8=PERFECT, 9=MAX
BEATORAJA_CLEAR_TYPE = {
    0: 0,   # No Play
    1: 1,   # Failed
    2: 1,   # No-score failed state → treat as Failed
    3: 2,   # Assist Clear
    4: 3,   # Easy Clear
    5: 4,   # Normal Clear
    6: 5,   # Hard Clear
    7: 6,   # Ex Hard Clear
    8: 7,   # Full Combo
    9: 8,   # Perfect (all greats, ignoring empty poor)
    10: 9,  # MAX (all PGreats, ignoring empty poor) — may not appear in practice
}

# Candidate column names for each judgment field across Beatoraja versions
_JUDGMENT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "ep": ("ep", "epg", "eperfect", "exactperfect", "pgreat"),   # actual: epg
    "lp": ("lp", "lpg", "lperfect", "lateperfect"),              # actual: lpg
    "eg": ("eg", "egr", "egreat", "earlygreat"),                  # actual: egr
    "lg": ("lg", "lgr", "lgreat", "lategreat"),                   # actual: lgr
    "egd": ("egd", "egood", "earlygood"),
    "lgd": ("lgd", "lgood", "lategood"),
    "ebd": ("ebd", "ebad", "earlybad"),
    "lbd": ("lbd", "lbad", "latebad"),
    "epr": ("epr", "epoor", "earlypoor"),
    "lpr": ("lpr", "lpoor", "latepoor"),
    "ems": ("ems", "emiss", "miss"),
    "lms": ("lms",),  # late miss — read separately and summed into "miss" judgments
    "maxcombo": ("maxcombo", "max_combo", "combo"),
    "minbp": ("minbp", "min_bp"),
    "playcount": ("playcount", "play_count"),
    "exscore": ("exscore", "ex_score", "score"),
    "date": ("date", "timestamp", "last_play"),
    "notes": ("notes", "total_notes", "totalnotes"),
    "clearcount": ("clearcount", "clear_count"),
    "arrangement": ("option",),
    "seed": ("seed",),
    "random_raw": ("random",),
}


def _decode_beatoraja_options(arrangement_val: int, random_raw: int, seed: int) -> dict:
    """Decode Beatoraja play options from raw DB integers.

    Args:
        arrangement_val: option column value (arrangement enum index).
        random_raw: random column value (purpose unknown; stored as raw).
        seed: seed column value (-1 means unused).

    Returns:
        Dict with arrangement, seed, and random_raw keys.
    """
    arr = BEATORAJA_ARRANGEMENT.get(arrangement_val, f"UNKNOWN({arrangement_val})")
    return {
        "arrangement": arr,
        "arrangement_2p": None,
        "arrangement_raw": arrangement_val,
        "history_raw": None,
        "seed": seed if seed != -1 else None,
        "random_raw": random_raw,
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


def parse_beatoraja_scores(
    data_dir: str,
    mode: int = 0,   # 0=SP, 1=DP
    player: int = 0,  # 0=1P, 1=2P
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], ParseStats]:
    """
    Parse Beatoraja score.db and return single-song scores, course records, and parse statistics.

    Args:
        data_dir: Path to the Beatoraja data directory (containing score.db).
        mode: Game mode (0=SP, 1=DP).
        player: Player slot (0=1P, 1=2P).

    Returns:
        Tuple of (score list, course list, ParseStats).
        Score list matches ScoreSyncItem schema; course list matches CourseSyncItem schema.

    Raises:
        FileNotFoundError: If score.db does not exist.
        ValueError: If the database schema is unrecognized.
    """
    data_path = Path(data_dir)
    score_db = data_path / "score.db"

    if not score_db.exists():
        raise FileNotFoundError(f"Beatoraja score.db not found: {score_db}")

    scores: list[dict[str, Any]] = []
    courses: list[dict[str, Any]] = []
    stats = ParseStats()

    with sqlite3.connect(str(score_db)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        available = _get_columns(cursor, "score")
        if not available:
            raise ValueError(
                f"Table 'score' not found in {score_db}. "
                f"Tables: {_list_tables(cursor)}"
            )

        if "sha256" not in available:
            raise ValueError(
                f"Cannot find sha256 column in Beatoraja score table. "
                f"Available columns: {sorted(available)}"
            )

        # Resolve optional judgment columns; missing ones default to 0
        cols = {key: _resolve_col(available, cands) for key, cands in _JUDGMENT_CANDIDATES.items()}

        # Build SELECT for only existing columns
        select_cols = ["sha256", "clear"]
        for col in cols.values():
            if col and col not in select_cols:
                select_cols.append(col)

        playcount_col = cols["playcount"] or "playcount"
        has_mode = "mode" in available
        has_player = "player" in available

        where_parts = []
        params: list[Any] = []
        if has_mode:
            where_parts.append("mode = ?")
            params.append(mode)
        if has_player:
            where_parts.append("player = ?")
            params.append(player)
        if cols["playcount"] and cols["playcount"] in available:
            where_parts.append(f"{cols['playcount']} > 0")

        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Count total rows before any filter
        cursor.execute("SELECT COUNT(*) FROM score")
        stats.db_total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT {', '.join(select_cols)} FROM score {where}",
            params,
        )

        rows = cursor.fetchall()
        stats.query_result_count = len(rows)

        for row in rows:
            def _int(col: str | None) -> int:
                return int(row[col]) if col and row[col] is not None else 0

            sha256 = (row["sha256"] or "").strip().replace("\x00", "").lower()
            if not sha256:
                stats.skipped_hash += 1
                continue

            if len(sha256) > 64:
                # Course (multi-song) record.
                # Beatoraja format: N×64-char SHA256 hashes concatenated.
                song_sha256s = [
                    sha256[i : i + 64]
                    for i in range(0, len(sha256), 64)
                    if len(sha256[i : i + 64]) == 64
                ]
                if not song_sha256s:
                    stats.skipped_hash += 1
                    continue

                played_at_c = None
                date_col_c = cols["date"]
                if date_col_c and row[date_col_c]:
                    try:
                        played_at_c = datetime.fromtimestamp(
                            row[date_col_c], tz=timezone.utc
                        ).isoformat()
                    except (ValueError, OSError):
                        pass

                clear_val_c = int(row["clear"]) if row["clear"] is not None else 0
                exscore_c = _int(cols["exscore"])
                notes_c = _int(cols["notes"])
                score_rate_c = None
                if exscore_c and notes_c:
                    max_ex = notes_c * 2
                    if max_ex > 0:
                        score_rate_c = exscore_c / max_ex

                courses.append({
                    "course_hash": sha256,
                    "client_type": "beatoraja",
                    "clear_type": BEATORAJA_CLEAR_TYPE.get(clear_val_c, 0),
                    "score_rate": score_rate_c,
                    "max_combo": _int(cols["maxcombo"]) or None,
                    "min_bp": _int(cols["minbp"]) or None,
                    "play_count": _int(cols["playcount"]),
                    "clear_count": _int(cols["clearcount"]),
                    "played_at": played_at_c,
                    "song_hashes": [
                        {"song_md5": None, "song_sha256": s}
                        for s in song_sha256s
                    ],
                })
                stats.parsed_courses += 1
                continue

            if len(sha256) != 64:
                stats.skipped_hash += 1
                continue

            played_at = None
            date_col = cols["date"]
            if date_col and row[date_col]:
                try:
                    played_at = datetime.fromtimestamp(
                        row[date_col], tz=timezone.utc
                    ).isoformat()
                except (ValueError, OSError):
                    pass

            ep = _int(cols["ep"])
            lp = _int(cols["lp"])
            eg = _int(cols["eg"])
            lg = _int(cols["lg"])

            # Calculate score rate from exscore and notes.
            # Fall back to computing exscore from judgment counts if the column is absent.
            score_rate = None
            exscore = _int(cols["exscore"])
            if not exscore:
                exscore = 2 * (ep + lp) + (eg + lg)
            notes = _int(cols["notes"])
            if exscore and notes:
                max_exscore = notes * 2  # PGreat=2, Great=1
                if max_exscore > 0:
                    score_rate = exscore / max_exscore

            judgments = {
                "pgreat": ep + lp,
                "great": eg + lg,
                "good": _int(cols["egd"]) + _int(cols["lgd"]),
                "bad": _int(cols["ebd"]) + _int(cols["lbd"]),
                "poor": _int(cols["epr"]) + _int(cols["lpr"]),
                "miss": _int(cols["ems"]) + _int(cols["lms"]),
                "exscore": exscore,
            }

            clear_val = int(row["clear"]) if row["clear"] is not None else 0

            arrangement_col = cols["arrangement"]
            seed_col = cols["seed"]
            random_raw_col = cols["random_raw"]
            arrangement_val = int(row[arrangement_col]) if arrangement_col and row[arrangement_col] is not None else 0
            seed_val = int(row[seed_col]) if seed_col and row[seed_col] is not None else -1
            random_raw_val = int(row[random_raw_col]) if random_raw_col and row[random_raw_col] is not None else 0

            scores.append({
                "song_sha256": sha256,
                "client_type": "beatoraja",
                "clear_type": BEATORAJA_CLEAR_TYPE.get(clear_val, 0),
                "score_rate": score_rate,
                "max_combo": _int(cols["maxcombo"]) or None,
                "min_bp": _int(cols["minbp"]) or None,
                "judgments": judgments,
                "play_count": _int(cols["playcount"]),
                "clear_count": _int(cols["clearcount"]),
                "played_at": played_at,
                "options": _decode_beatoraja_options(arrangement_val, random_raw_val, seed_val),
            })

    stats.parsed = len(scores)
    return scores, courses, stats


def parse_beatoraja_player_stats(data_dir: str, player: int = 0) -> dict[str, int] | None:
    """Read cumulative totals from Beatoraja player table (most recent row).

    Args:
        data_dir: Path to the Beatoraja data directory (containing score.db).
        player: Player slot (0=1P, 1=2P).

    Returns:
        Dict with total_notes_hit and total_play_count, or None if table absent.
    """
    data_path = Path(data_dir)
    score_db = data_path / "score.db"
    if not score_db.exists():
        return None

    try:
        with sqlite3.connect(str(score_db)) as conn:
            cursor = conn.cursor()

            # Check if player table exists
            cursor.execute("PRAGMA table_info(player)")
            columns = {row[1] for row in cursor.fetchall()}
            if not columns:
                return None

            # Resolve judgment columns (Beatoraja uses epg/lpg/egr/lgr etc.)
            hit_col_candidates = [
                ("ep", ("epg", "ep")),
                ("lp", ("lpg", "lp")),
                ("eg", ("egr", "eg")),
                ("lg", ("lgr", "lg")),
                ("egd", ("egd",)),
                ("lgd", ("lgd",)),
                ("ebd", ("ebd",)),
                ("lbd", ("lbd",)),
                # epr/lpr (Poor) and ems/lms (Miss) are excluded: key was not pressed
                # within the note's timing window, so they do not count as notes hit.
            ]
            resolved_hit_cols = [
                _resolve_col(columns, cands)
                for _, cands in hit_col_candidates
            ]
            resolved_hit_cols = [c for c in resolved_hit_cols if c]

            if not resolved_hit_cols:
                return None

            date_col = _resolve_col(columns, ("date", "timestamp"))
            pc_col = _resolve_col(columns, ("playcount", "play_count"))
            has_player_col = "player" in columns

            select_parts = resolved_hit_cols[:]
            if pc_col:
                select_parts.append(pc_col)

            where_parts = []
            params = []
            if has_player_col:
                where_parts.append("player = ?")
                params.append(player)

            where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
            order = f"ORDER BY {date_col} DESC LIMIT 1" if date_col else "LIMIT 1"

            cursor.execute(
                f"SELECT {', '.join(select_parts)} FROM player {where} {order}",
                params,
            )
            row = cursor.fetchone()
            if row is None:
                return None

            col_index = {col: i for i, col in enumerate(select_parts)}
            total_notes_hit = sum(
                int(row[col_index[c]] or 0) for c in resolved_hit_cols
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


def _list_tables(cursor: sqlite3.Cursor) -> list[str]:
    """Return list of table names in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]


def parse_beatoraja_score_log(
    data_dir: str,
    mode: int = 0,
    player: int = 0,
    since_timestamp: int | None = None,
) -> list[dict[str, Any]]:
    """
    Parse Beatoraja scorelog.db for score history.

    Args:
        data_dir: Path to the Beatoraja data directory.
        mode: Game mode (0=SP, 1=DP).
        player: Player slot (0=1P, 1=2P).
        since_timestamp: Only return entries after this Unix timestamp.

    Returns:
        List of score history dicts.
    """
    data_path = Path(data_dir)
    scorelog_db = data_path / "scorelog.db"

    if not scorelog_db.exists():
        return []

    history: list[dict[str, Any]] = []

    with sqlite3.connect(str(scorelog_db)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        available = _get_columns(cursor, "scorelog")
        if not available:
            return []

        has_mode = "mode" in available
        has_player = "player" in available

        where_parts = []
        params: list[Any] = []
        if has_mode:
            where_parts.append("mode = ?")
            params.append(mode)
        if has_player:
            where_parts.append("player = ?")
            params.append(player)
        if since_timestamp is not None:
            where_parts.append("date > ?")
            params.append(since_timestamp)

        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Resolve actual column names for scorelog (differ from score.db)
        score_col = "score" if "score" in available else "exscore"
        combo_col = "combo" if "combo" in available else "maxcombo"

        cursor.execute(
            f"SELECT sha256, clear, {score_col}, {combo_col}, minbp, date "
            f"FROM scorelog {where} ORDER BY date ASC",
            params,
        )

        for row in cursor.fetchall():
            sha256 = row["sha256"]
            if not sha256:
                continue

            played_at = None
            if row["date"]:
                try:
                    played_at = datetime.fromtimestamp(
                        row["date"], tz=timezone.utc
                    ).isoformat()
                except (ValueError, OSError):
                    pass

            history.append({
                "sha256": sha256,
                "clear_type": BEATORAJA_CLEAR_TYPE.get(row["clear"] or 0, 0),
                "exscore": row[score_col],
                "max_combo": row[combo_col],
                "min_bp": row["minbp"],
                "played_at": played_at,
            })

    return history
