"""Beatoraja score database parser.

Note: rows where scorehash == 'LR2' in score.db are skipped entirely.

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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ParseStats:
    """Counters collected during a single parser run."""

    db_total: int = 0           # Total rows in score table (no filter)
    query_result_count: int = 0  # Rows returned after WHERE clause
    skipped_hash: int = 0       # Rows dropped due to missing/invalid hash
    skipped_lr2: int = 0        # Rows intentionally skipped (LR2-imported records, not real Beatoraja scores)
    parsed_courses: int = 0     # Course (multi-song) records extracted for sync
    parsed: int = 0             # Single-song rows successfully converted to score dicts

    @property
    def skipped_filter(self) -> int:
        """Rows excluded by the playcount/mode/player WHERE clause."""
        return self.db_total - self.query_result_count

    @property
    def effective_total(self) -> int:
        """Total rows excluding intentionally-skipped LR2 imports."""
        return self.db_total - self.skipped_lr2


@dataclass
class ScoreLogStats:
    """Counters collected during a single scorelog parser run."""

    total_queried: int = 0      # Rows returned after WHERE clause
    skipped_hash: int = 0       # Rows dropped due to missing/invalid sha256 (empty or len < 64)
    skipped_duplicate: int = 0  # Rows skipped as duplicates of score.db entries
    parsed: int = 0             # Single-song rows successfully added to history
    parsed_courses: int = 0     # Course rows (sha256 len > 64) added to history


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
    "lms": ("lms",),  # late miss
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
    "scorehash": ("scorehash",),
}


def _decode_beatoraja_options(mode_val: int, arrangement_val: int, seed: int, random_raw: int) -> dict:
    """Return Beatoraja play options as raw DB integers.

    Args:
        mode_val: mode column value (0=SP, 1=DP).
        arrangement_val: option column value (raw int, arrangement enum index).
        seed: seed column value (-1 means unused).
        random_raw: random column value (raw int).

    Returns:
        Dict with mode, option, seed, random raw int keys.
    """
    return {
        "mode": mode_val,
        "option": arrangement_val,
        "seed": seed,
        "random": random_raw,
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
        # Always include scorehash if present
        if "scorehash" in available:
            select_cols.append("scorehash")
        for col in cols.values():
            if col and col not in select_cols:
                select_cols.append(col)

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

            def _int_or_none(col: str | None) -> int | None:
                """Like _int but returns None instead of 0 for missing/null columns.
                Use this for fields where 0 is a meaningful value (e.g. min_bp=0 for perfect play)."""
                if not col or row[col] is None:
                    return None
                return int(row[col])

            sha256 = (row["sha256"] or "").strip().replace("\x00", "").lower()
            if not sha256:
                stats.skipped_hash += 1
                continue

            # Skip rows where scorehash == 'LR2' (Beatoraja marks LR2-imported scores this way).
            # These are not real Beatoraja scores — counted separately, not as hash errors.
            raw_scorehash = row["scorehash"] if "scorehash" in select_cols else None
            if raw_scorehash and str(raw_scorehash).strip().upper() == "LR2":
                stats.skipped_lr2 += 1
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
                            row[date_col_c], tz=UTC
                        ).isoformat()
                    except (ValueError, OSError):
                        pass

                clear_val_c = int(row["clear"]) if row["clear"] is not None else 0
                notes_c = _int(cols["notes"])

                scorehash_c = None
                if raw_scorehash and str(raw_scorehash).strip().upper() != "LR2":
                    scorehash_c = str(raw_scorehash).strip() or None

                judgments_c = {
                    "epg": _int(cols["ep"]),
                    "lpg": _int(cols["lp"]),
                    "egr": _int(cols["eg"]),
                    "lgr": _int(cols["lg"]),
                    "egd": _int(cols["egd"]),
                    "lgd": _int(cols["lgd"]),
                    "ebd": _int(cols["ebd"]),
                    "lbd": _int(cols["lbd"]),
                    "epr": _int(cols["epr"]),
                    "lpr": _int(cols["lpr"]),
                    "ems": _int(cols["ems"]),
                    "lms": _int(cols["lms"]),
                }
                arrangement_col_c = cols["arrangement"]
                seed_col_c = cols["seed"]
                random_raw_col_c = cols["random_raw"]
                arrangement_val_c = int(row[arrangement_col_c]) if arrangement_col_c and row[arrangement_col_c] is not None else 0
                seed_val_c = int(row[seed_col_c]) if seed_col_c and row[seed_col_c] is not None else -1
                random_raw_val_c = int(row[random_raw_col_c]) if random_raw_col_c and row[random_raw_col_c] is not None else 0

                courses.append({
                    "fumen_hash_others": sha256,
                    "client_type": "beatoraja",
                    "scorehash": scorehash_c,
                    "clear_type": BEATORAJA_CLEAR_TYPE.get(clear_val_c, 0),
                    "notes": notes_c or None,
                    "max_combo": _int(cols["maxcombo"]) or None,
                    "min_bp": _int_or_none(cols["minbp"]),
                    "judgments": judgments_c,
                    "play_count": _int(cols["playcount"]),
                    "clear_count": _int(cols["clearcount"]),
                    "recorded_at": played_at_c,
                    "options": _decode_beatoraja_options(mode, arrangement_val_c, seed_val_c, random_raw_val_c),
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
                        row[date_col], tz=UTC
                    ).isoformat()
                except (ValueError, OSError):
                    pass

            ep = _int(cols["ep"])
            lp = _int(cols["lp"])
            eg = _int(cols["eg"])
            lg = _int(cols["lg"])

            notes = _int(cols["notes"])

            # Raw judgment keys (Beatoraja-native)
            judgments = {
                "epg": ep,
                "lpg": lp,
                "egr": eg,
                "lgr": lg,
                "egd": _int(cols["egd"]),
                "lgd": _int(cols["lgd"]),
                "ebd": _int(cols["ebd"]),
                "lbd": _int(cols["lbd"]),
                "epr": _int(cols["epr"]),
                "lpr": _int(cols["lpr"]),
                "ems": _int(cols["ems"]),
                "lms": _int(cols["lms"]),
            }

            clear_val = int(row["clear"]) if row["clear"] is not None else 0

            arrangement_col = cols["arrangement"]
            seed_col = cols["seed"]
            random_raw_col = cols["random_raw"]
            arrangement_val = int(row[arrangement_col]) if arrangement_col and row[arrangement_col] is not None else 0
            seed_val = int(row[seed_col]) if seed_col and row[seed_col] is not None else -1
            random_raw_val = int(row[random_raw_col]) if random_raw_col and row[random_raw_col] is not None else 0

            # Extract scorehash; skip if it is 'LR2' (already filtered above for whole rows,
            # but double-check here for safety)
            scorehash_val = None
            if raw_scorehash:
                sh = str(raw_scorehash).strip()
                if sh and sh.upper() != "LR2":
                    scorehash_val = sh

            scores.append({
                "fumen_sha256": sha256,
                "scorehash": scorehash_val,
                "client_type": "beatoraja",
                "clear_type": BEATORAJA_CLEAR_TYPE.get(clear_val, 0),
                "notes": notes or None,
                "max_combo": _int(cols["maxcombo"]) or None,
                "min_bp": _int_or_none(cols["minbp"]),
                "judgments": judgments,
                "play_count": _int(cols["playcount"]),
                "clear_count": _int(cols["clearcount"]),
                "recorded_at": played_at,
                "options": _decode_beatoraja_options(mode, arrangement_val, seed_val, random_raw_val),
            })

    stats.parsed = len(scores)
    return scores, courses, stats


def parse_beatoraja_player_stats(data_dir: str, player: int = 0) -> dict | None:
    """Read cumulative totals from Beatoraja player table (most recent row).

    Args:
        data_dir: Path to the Beatoraja data directory (containing score.db).
        player: Player slot (0=1P, 1=2P).

    Returns:
        Dict with playcount, clearcount, playtime, and judgments (raw counts),
        or None if player table is absent.
    """
    data_path = Path(data_dir)
    score_db = data_path / "score.db"
    if not score_db.exists():
        return None

    try:
        with sqlite3.connect(str(score_db)) as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(player)")
            columns = {row[1] for row in cursor.fetchall()}
            if not columns:
                return None

            # All judgment field candidates for Beatoraja player table
            judgment_candidates = [
                ("epg", ("epg", "ep")),
                ("lpg", ("lpg", "lp")),
                ("egr", ("egr", "eg")),
                ("lgr", ("lgr", "lg")),
                ("egd", ("egd",)),
                ("lgd", ("lgd",)),
                ("ebd", ("ebd",)),
                ("lbd", ("lbd",)),
                ("epr", ("epr",)),
                ("lpr", ("lpr",)),
                ("ems", ("ems",)),
                ("lms", ("lms",)),
            ]
            resolved_judgment = [
                (key, _resolve_col(columns, cands))
                for key, cands in judgment_candidates
            ]
            resolved_judgment = [(k, c) for k, c in resolved_judgment if c]

            if not resolved_judgment:
                return None

            date_col = _resolve_col(columns, ("date", "timestamp"))
            pc_col   = _resolve_col(columns, ("playcount", "play_count"))
            cc_col   = _resolve_col(columns, ("clear", "clearcount", "clear_count"))
            pt_col   = _resolve_col(columns, ("playtime", "play_time"))
            has_player_col = "player" in columns

            select_parts = list(dict.fromkeys(
                [c for _, c in resolved_judgment]
                + [c for c in [pc_col, cc_col, pt_col] if c]
            ))

            where_parts: list[str] = []
            params: list[Any] = []
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

            def _val(col: str | None) -> int | None:
                if col and col in col_index:
                    v = row[col_index[col]]
                    return int(v) if v is not None else None
                return None

            judgments = {}
            for key, col in resolved_judgment:
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


def _list_tables(cursor: sqlite3.Cursor) -> list[str]:
    """Return list of table names in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]


def parse_beatoraja_songdata(db_path: str) -> list[dict[str, Any]]:
    """Parse Beatoraja songdata.db and return song metadata items.

    Each returned dict currently contains at minimum 'md5' and 'sha256' when
    both are present and non-empty. Additional fields (title, artist, bpm, etc.)
    are included as-is for forward compatibility — callers decide which fields
    to use.

    Only rows where both md5 and sha256 are non-empty are returned (rows
    lacking either hash cannot contribute to hash supplementation).

    Args:
        db_path: Full path to songdata.db.

    Returns:
        List of dicts with at least {'md5': str, 'sha256': str, ...}.
        Returns [] on error or if the file does not exist.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return []

    # Beatoraja songdata.db table candidates (varies slightly by version)
    table_candidates = ("song", "musics", "music")
    # Column name candidates for each key field
    md5_candidates = ("md5",)
    sha256_candidates = ("sha256",)

    items: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(str(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find the song table
            tables = _list_tables(cursor)
            table = next((t for t in table_candidates if t in tables), None)
            if table is None:
                return []

            columns = _get_columns(cursor, table)
            md5_col = _resolve_col(columns, md5_candidates)
            sha256_col = _resolve_col(columns, sha256_candidates)
            if not md5_col or not sha256_col:
                return []

            # Collect all available extra columns for forward compatibility
            extra_cols = sorted(
                c for c in columns
                if c not in {md5_col, sha256_col}
            )
            select_cols = ", ".join([sha256_col, md5_col] + extra_cols)

            cursor.execute(
                f"SELECT {select_cols} FROM {table} "
                f"WHERE {sha256_col} != '' AND {sha256_col} IS NOT NULL "
                f"  AND {md5_col}    != '' AND {md5_col}    IS NOT NULL"
            )

            for row in cursor.fetchall():
                sha256_val = row[sha256_col]
                md5_val    = row[md5_col]
                # Basic sanity check on hash lengths
                if not sha256_val or len(sha256_val) != 64:
                    continue
                if not md5_val or len(md5_val) != 32:
                    continue

                item: dict[str, Any] = {
                    "sha256": sha256_val.lower(),
                    "md5":    md5_val.lower(),
                }
                for col in extra_cols:
                    item[col] = row[col]
                items.append(item)

    except Exception:
        return []

    return items


def parse_beatoraja_songinfo(db_path: str) -> dict[str, dict[str, Any]]:
    """Parse Beatoraja songinfo.db and return note analysis data keyed by sha256.

    Args:
        db_path: Full path to songinfo.db.

    Returns:
        Dict mapping sha256 (lowercase) to {n, ln, s, ls, total, mainbpm}.
        Returns {} on error or if the file does not exist.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return {}

    result: dict[str, dict[str, Any]] = {}
    try:
        with sqlite3.connect(str(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            columns = _get_columns(cursor, "information")
            if not columns:
                return {}

            sha256_col = _resolve_col(columns, ("sha256",))
            if not sha256_col:
                return {}

            n_col = _resolve_col(columns, ("n",))
            ln_col = _resolve_col(columns, ("ln",))
            s_col = _resolve_col(columns, ("s",))
            ls_col = _resolve_col(columns, ("ls",))
            total_col = _resolve_col(columns, ("total",))
            mainbpm_col = _resolve_col(columns, ("mainbpm",))

            select_parts = [sha256_col]
            for col in (n_col, ln_col, s_col, ls_col, total_col, mainbpm_col):
                if col:
                    select_parts.append(col)

            cursor.execute(
                f"SELECT {', '.join(select_parts)} FROM information "
                f"WHERE {sha256_col} IS NOT NULL AND {sha256_col} != ''"
            )

            for row in cursor.fetchall():
                sha256_val = row[sha256_col]
                if not sha256_val or len(sha256_val) != 64:
                    continue
                key = sha256_val.lower()
                entry: dict[str, Any] = {}
                if n_col:
                    entry["n"] = row[n_col]
                if ln_col:
                    entry["ln"] = row[ln_col]
                if s_col:
                    entry["s"] = row[s_col]
                if ls_col:
                    entry["ls"] = row[ls_col]
                if total_col:
                    entry["total"] = row[total_col]
                if mainbpm_col:
                    entry["mainbpm"] = row[mainbpm_col]
                result[key] = entry

    except Exception:
        return {}

    return result


def parse_beatoraja_score_log(
    data_dir: str,
    mode: int = 0,
    player: int = 0,
    since_timestamp: int | None = None,
) -> tuple[list[dict[str, Any]], ScoreLogStats]:
    """
    Parse Beatoraja scorelog.db for score history.

    scorelog.db records best-score improvements only (not every play).
    Columns extracted: sha256, clear, score (exscore), combo (maxcombo), minbp, date.
    old* columns (oldclear, oldscore, oldcombo, oldminbp) are intentionally excluded —
    only the new (improved) values are used.

    Entries whose (sha256, date) pair already exists in score.db are skipped to
    avoid uploading the same record twice.

    Args:
        data_dir: Path to the Beatoraja data directory.
        mode: Game mode (0=SP, 1=DP).
        player: Player slot (0=1P, 1=2P).
        since_timestamp: Only return entries after this Unix timestamp.

    Returns:
        Tuple of (history list, ScoreLogStats).
        History list contains score dicts compatible with ScoreSyncItem schema.
    """
    data_path = Path(data_dir)
    scorelog_db = data_path / "scorelog.db"

    if not scorelog_db.exists():
        return [], ScoreLogStats()

    # Build (sha256, date) set from score.db to skip duplicate entries.
    # score.db stores the current best per sha256; scorelog.db may contain
    # the same (sha256, date) row representing that best score.
    score_db_pairs: set[tuple[str, int]] = set()
    score_db = data_path / "score.db"
    if score_db.exists():
        with sqlite3.connect(str(score_db)) as score_conn:
            score_cursor = score_conn.cursor()
            score_cursor.execute("PRAGMA table_info(score)")
            score_cols = {row[1] for row in score_cursor.fetchall()}
            if "sha256" in score_cols and "date" in score_cols:
                where_parts_s: list[str] = []
                params_s: list[Any] = []
                if "mode" in score_cols:
                    where_parts_s.append("mode = ?")
                    params_s.append(mode)
                if "player" in score_cols:
                    where_parts_s.append("player = ?")
                    params_s.append(player)
                where_s = ("WHERE " + " AND ".join(where_parts_s)) if where_parts_s else ""
                score_cursor.execute(
                    f"SELECT sha256, date FROM score {where_s}",
                    params_s,
                )
                for s_row in score_cursor.fetchall():
                    if s_row[0] and s_row[1] is not None:
                        score_db_pairs.add((s_row[0].strip().lower(), int(s_row[1])))

    history: list[dict[str, Any]] = []
    stats = ScoreLogStats()

    with sqlite3.connect(str(scorelog_db)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        available = _get_columns(cursor, "scorelog")
        if not available:
            return []

        has_mode = "mode" in available
        has_player = "player" in available

        where_parts: list[str] = []
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

        # Resolve column names that vary across Beatoraja versions.
        # scorelog has no scorehash column — do not attempt to read one.
        # old* columns (oldclear, oldscore, oldcombo, oldminbp) are present but
        # intentionally excluded; only the current (improved) values are synced.
        score_col = "score" if "score" in available else "exscore"
        combo_col = "combo" if "combo" in available else "maxcombo"

        cursor.execute(
            f"SELECT sha256, clear, {score_col}, {combo_col}, minbp, date "
            f"FROM scorelog {where} ORDER BY date ASC",
            params,
        )

        rows = cursor.fetchall()
        stats.total_queried = len(rows)

        for row in rows:
            sha256 = (row["sha256"] or "").strip().lower()
            if not sha256 or len(sha256) < 64:
                stats.skipped_hash += 1
                continue

            date_unix = row["date"]

            # Skip entries already present in score.db (same sha256 + date).
            if date_unix is not None and (sha256, int(date_unix)) in score_db_pairs:
                stats.skipped_duplicate += 1
                continue

            played_at = None
            if date_unix:
                try:
                    played_at = datetime.fromtimestamp(
                        date_unix, tz=UTC
                    ).isoformat()
                except (ValueError, OSError):
                    pass

            if len(sha256) > 64:
                # Course record — concatenated N×64-char SHA256 hashes.
                # scorelog.db lacks scorehash, notes, play_count, clear_count —
                # those fields are omitted (server treats them as optional).
                history.append({
                    "fumen_hash_others": sha256,
                    "scorehash": None,
                    "client_type": "beatoraja",
                    "clear_type": BEATORAJA_CLEAR_TYPE.get(row["clear"] or 0, 0),
                    "max_combo": row[combo_col],
                    "min_bp": row["minbp"],
                    "exscore": row[score_col],
                    "recorded_at": played_at,
                    "song_hashes": [],
                })
                stats.parsed_courses += 1
                continue

            history.append({
                "fumen_sha256": sha256,
                # scorelog.db has no scorehash column — set to None so the server
                # performs a plain INSERT without deduplication on scorehash.
                "scorehash": None,
                "client_type": "beatoraja",
                "clear_type": BEATORAJA_CLEAR_TYPE.get(row["clear"] or 0, 0),
                "exscore": row[score_col],
                "max_combo": row[combo_col],
                "min_bp": row["minbp"],
                "recorded_at": played_at,
            })
            stats.parsed += 1

    return history, stats
