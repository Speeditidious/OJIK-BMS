"""Tests for BMS file parsers."""
import sqlite3
from pathlib import Path

import pytest

from ojikbms_client.parsers.lr2 import parse_lr2_scores
from ojikbms_client.parsers.beatoraja import (
    parse_beatoraja_score_log,
    parse_beatoraja_scores,
)


# ── LR2 Parser Tests ──────────────────────────────────────────────────────────

def _create_lr2_score_db(db_path: Path) -> None:
    """Helper to create a mock LR2 score.db."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE score (
                sha256 TEXT PRIMARY KEY,
                clear INTEGER,
                pg INTEGER,
                gr INTEGER,
                gd INTEGER,
                bd INTEGER,
                pr INTEGER,
                maxcombo INTEGER,
                minbp INTEGER,
                playtime INTEGER,
                playcount INTEGER,
                rate REAL,
                clear_db INTEGER,
                op_dp INTEGER,
                scorehash TEXT,
                complete INTEGER,
                totalnotes INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO score VALUES (
                ?,
                3, 1000, 500, 100, 50, 20,
                1200, 5, 1700000000, 10, 85.5,
                0, 0, 'abc123', 1, 800
            )
        """, ("a" * 64,))
        # Entry with 0 playcount (should be skipped)
        conn.execute("""
            INSERT INTO score VALUES (
                ?,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0.0,
                0, 0, 'xxx', 0, 0
            )
        """, ("b" * 64,))
        conn.commit()


class TestLr2Parser:
    def test_parse_lr2_scores_basic(self, tmp_path: Path) -> None:
        """parse_lr2_scores should return scores for played songs."""
        score_db = tmp_path / "score.db"
        _create_lr2_score_db(score_db)

        scores, courses, stats = parse_lr2_scores(str(score_db))

        assert len(scores) == 1  # Only 1 with playcount > 0
        assert len(courses) == 0
        assert stats.db_total == 2
        assert stats.query_result_count == 1
        assert stats.parsed == 1
        assert stats.skipped_hash == 0
        assert stats.parsed_courses == 0
        score = scores[0]

        assert score["fumen_sha256"] == "a" * 64
        assert score["client_type"] == "lr2"
        assert score["clear_type"] == 4  # Normal Clear (LR2 DB 3 → internal 4)
        assert score["play_count"] == 10
        assert score["max_combo"] == 1200
        assert score["min_bp"] == 5
        assert score["judgments"]["perfect"] == 1000
        assert score["judgments"]["great"] == 500

    def test_parse_lr2_scores_notes_field(self, tmp_path: Path) -> None:
        """parse_lr2_scores should include notes from totalnotes column."""
        score_db = tmp_path / "score.db"
        _create_lr2_score_db(score_db)

        scores, _, _ = parse_lr2_scores(str(score_db))
        assert scores[0]["notes"] == 800

    def test_parse_lr2_scores_file_not_found(self) -> None:
        """parse_lr2_scores should raise FileNotFoundError for missing DB."""
        with pytest.raises(FileNotFoundError):
            parse_lr2_scores("/nonexistent/score.db")


# ── Beatoraja Parser Tests ─────────────────────────────────────────────────────

def _create_beatoraja_score_db(data_dir: Path) -> None:
    """Helper to create a mock Beatoraja score.db."""
    score_db = data_dir / "score.db"
    with sqlite3.connect(str(score_db)) as conn:
        conn.execute("""
            CREATE TABLE score (
                sha256 TEXT NOT NULL,
                mode INTEGER NOT NULL,
                player INTEGER NOT NULL,
                clear INTEGER,
                ep INTEGER, lp INTEGER,
                eg INTEGER, lg INTEGER,
                egd INTEGER, lgd INTEGER,
                ebd INTEGER, lbd INTEGER,
                epr INTEGER, lpr INTEGER,
                ems INTEGER,
                maxcombo INTEGER,
                minbp INTEGER,
                playcount INTEGER,
                clearcount INTEGER,
                failcount INTEGER,
                rank INTEGER,
                exscore INTEGER,
                option INTEGER,
                assist INTEGER,
                date INTEGER,
                url TEXT,
                notes INTEGER,
                scorehash TEXT,
                PRIMARY KEY (sha256, mode, player)
            )
        """)
        conn.execute("""
            INSERT INTO score VALUES (
                ?, 0, 0,
                3,
                500, 500,
                200, 200,
                50, 50,
                10, 10,
                5, 5, 2,
                1000, 3,
                15, 10, 5,
                0, 1400,
                0, 0,
                1700000000, NULL, 1000, NULL
            )
        """, ("c" * 64,))
        conn.commit()


def _insert_beatoraja_score_row(
    data_dir: Path,
    *,
    sha256: str,
    mode: int,
    player: int = 0,
    clear: int = 3,
    ep: int = 500,
    lp: int = 500,
    eg: int = 200,
    lg: int = 200,
    egd: int = 50,
    lgd: int = 50,
    ebd: int = 10,
    lbd: int = 10,
    epr: int = 5,
    lpr: int = 5,
    ems: int = 2,
    maxcombo: int = 1000,
    minbp: int = 3,
    playcount: int = 15,
    clearcount: int = 10,
    failcount: int = 5,
    rank: int = 0,
    exscore: int = 1400,
    option: int = 0,
    assist: int = 0,
    date: int = 1700000000,
    notes: int = 1000,
    scorehash: str | None = None,
) -> None:
    """Insert one row into a mock Beatoraja score.db."""
    score_db = data_dir / "score.db"
    with sqlite3.connect(str(score_db)) as conn:
        conn.execute(
            """
            INSERT INTO score (
                sha256, mode, player, clear,
                ep, lp, eg, lg, egd, lgd, ebd, lbd, epr, lpr, ems,
                maxcombo, minbp, playcount, clearcount, failcount,
                rank, exscore, option, assist, date, url, notes, scorehash
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, NULL, ?, ?
            )
            """,
            (
                sha256, mode, player, clear,
                ep, lp, eg, lg, egd, lgd, ebd, lbd, epr, lpr, ems,
                maxcombo, minbp, playcount, clearcount, failcount,
                rank, exscore, option, assist, date, notes, scorehash,
            ),
        )
        conn.commit()


def _create_beatoraja_scorelog_db(data_dir: Path) -> None:
    """Helper to create a mock Beatoraja scorelog.db."""
    scorelog_db = data_dir / "scorelog.db"
    with sqlite3.connect(str(scorelog_db)) as conn:
        conn.execute("""
            CREATE TABLE scorelog (
                sha256 TEXT NOT NULL,
                mode INTEGER NOT NULL,
                player INTEGER NOT NULL,
                clear INTEGER,
                oldclear INTEGER,
                score INTEGER,
                oldscore INTEGER,
                combo INTEGER,
                oldcombo INTEGER,
                minbp INTEGER,
                oldminbp INTEGER,
                date INTEGER
            )
        """)
        conn.commit()


def _insert_beatoraja_scorelog_row(
    data_dir: Path,
    *,
    sha256: str,
    mode: int,
    player: int = 0,
    clear: int = 3,
    score: int = 1400,
    combo: int = 1000,
    minbp: int = 3,
    date: int = 1700000000,
) -> None:
    """Insert one row into a mock Beatoraja scorelog.db."""
    scorelog_db = data_dir / "scorelog.db"
    with sqlite3.connect(str(scorelog_db)) as conn:
        conn.execute(
            """
            INSERT INTO scorelog (
                sha256, mode, player, clear, oldclear,
                score, oldscore, combo, oldcombo, minbp, oldminbp, date
            ) VALUES (?, ?, ?, ?, 0, ?, 0, ?, 0, ?, 0, ?)
            """,
            (sha256, mode, player, clear, score, combo, minbp, date),
        )
        conn.commit()


class TestBeatorajaParser:
    def test_parse_beatoraja_scores_basic(self, tmp_path: Path) -> None:
        """parse_beatoraja_scores should return scores for played songs."""
        _create_beatoraja_score_db(tmp_path)

        scores, courses, stats = parse_beatoraja_scores(str(tmp_path))

        assert len(scores) == 1
        assert len(courses) == 0
        assert stats.db_total == 1
        assert stats.query_result_count == 1
        assert stats.parsed == 1
        assert stats.skipped_hash == 0
        assert stats.parsed_courses == 0
        score = scores[0]

        assert score["fumen_sha256"] == "c" * 64
        assert score["client_type"] == "beatoraja"
        assert score["clear_type"] == 2  # Assist Clear (Beatoraja DB 3 → internal 2)
        assert score["play_count"] == 15
        assert score["max_combo"] == 1000
        assert score["min_bp"] == 3
        assert score["judgments"]["epg"] == 500  # ep (early perfect)
        assert score["judgments"]["lpg"] == 500  # lp (late perfect)

    def test_parse_beatoraja_scores_notes_field(self, tmp_path: Path) -> None:
        """parse_beatoraja_scores should forward notes count for server-side rate computation."""
        _create_beatoraja_score_db(tmp_path)

        scores, _, _ = parse_beatoraja_scores(str(tmp_path))
        score = scores[0]

        # notes column value is 1000
        assert score["notes"] == 1000

    def test_parse_beatoraja_scores_includes_nonstandard_mode_course(self, tmp_path: Path) -> None:
        """Course rows with non-standard raw mode values should bypass the SP/DP filter."""
        _create_beatoraja_score_db(tmp_path)
        course_hash = ("d" * 64) + ("e" * 64) + ("f" * 64) + ("g" * 64)
        _insert_beatoraja_score_row(
            tmp_path,
            sha256=course_hash,
            mode=10000,
            clear=5,
            maxcombo=399,
            minbp=676,
            playcount=17,
            clearcount=1,
            date=1755002698,
            notes=12966,
            scorehash="035230ad8fcad0e1ac1bdc27b1b1e050bc0d17c492e615b6a8ba9bbe38255d64f9f",
        )
        _insert_beatoraja_score_row(
            tmp_path,
            sha256="h" * 64,
            mode=1,
            clear=7,
            maxcombo=1200,
            minbp=1,
            playcount=20,
            clearcount=20,
            date=1755002700,
            notes=1400,
            scorehash="different-mode-single",
        )

        scores, courses, stats = parse_beatoraja_scores(str(tmp_path))

        assert len(scores) == 1
        assert len(courses) == 1
        assert stats.db_total == 3
        assert stats.query_result_count == 2
        assert stats.parsed == 1
        assert stats.parsed_courses == 1

        course = courses[0]
        assert course["fumen_hash_others"] == course_hash
        assert course["scorehash"] == "035230ad8fcad0e1ac1bdc27b1b1e050bc0d17c492e615b6a8ba9bbe38255d64f9f"
        assert course["play_count"] == 17
        assert course["clear_count"] == 1
        assert course["notes"] == 12966
        assert course["options"]["mode"] == 10000
        assert [song["song_sha256"] for song in course["song_hashes"]] == [
            "d" * 64,
            "e" * 64,
            "f" * 64,
            "g" * 64,
        ]

        assert all(score["fumen_sha256"] != "h" * 64 for score in scores)

    def test_parse_beatoraja_score_log_includes_nonstandard_mode_course(self, tmp_path: Path) -> None:
        """scorelog course rows with non-standard raw mode values should be parsed."""
        _create_beatoraja_scorelog_db(tmp_path)
        course_hash = ("i" * 64) + ("j" * 64) + ("k" * 64) + ("l" * 64)
        _insert_beatoraja_scorelog_row(
            tmp_path,
            sha256="m" * 64,
            mode=0,
            clear=4,
            score=1500,
            combo=900,
            minbp=10,
            date=1700000001,
        )
        _insert_beatoraja_scorelog_row(
            tmp_path,
            sha256=course_hash,
            mode=10000,
            clear=5,
            score=12966,
            combo=399,
            minbp=676,
            date=1755002698,
        )
        _insert_beatoraja_scorelog_row(
            tmp_path,
            sha256="n" * 64,
            mode=1,
            clear=7,
            score=1800,
            combo=1200,
            minbp=2,
            date=1700000002,
        )

        history, stats = parse_beatoraja_score_log(str(tmp_path))

        assert len(history) == 2
        assert stats.total_queried == 2
        assert stats.parsed == 1
        assert stats.parsed_courses == 1

        course = next(item for item in history if item.get("fumen_hash_others"))
        assert course["fumen_hash_others"] == course_hash
        assert course["clear_type"] == 4
        assert course["exscore"] == 12966
        assert course["max_combo"] == 399
        assert course["min_bp"] == 676
        assert all(item.get("fumen_sha256") != "n" * 64 for item in history)

    def test_parse_beatoraja_score_log_skips_nonstandard_mode_course_duplicates(self, tmp_path: Path) -> None:
        """Duplicate checks should also see non-standard-mode course rows from score.db."""
        _create_beatoraja_score_db(tmp_path)
        _create_beatoraja_scorelog_db(tmp_path)
        course_hash = ("o" * 64) + ("p" * 64) + ("q" * 64) + ("r" * 64)
        duplicate_date = 1755002698
        _insert_beatoraja_score_row(
            tmp_path,
            sha256=course_hash,
            mode=10000,
            clear=5,
            maxcombo=399,
            minbp=676,
            playcount=17,
            clearcount=1,
            date=duplicate_date,
            notes=12966,
            scorehash="duplicate-course",
        )
        _insert_beatoraja_scorelog_row(
            tmp_path,
            sha256=course_hash,
            mode=10000,
            clear=5,
            score=12966,
            combo=399,
            minbp=676,
            date=duplicate_date,
        )

        history, stats = parse_beatoraja_score_log(str(tmp_path))

        assert history == []
        assert stats.total_queried == 1
        assert stats.skipped_duplicate == 1

    def test_parse_beatoraja_scores_file_not_found(self, tmp_path: Path) -> None:
        """parse_beatoraja_scores should raise FileNotFoundError for missing DB."""
        with pytest.raises(FileNotFoundError):
            parse_beatoraja_scores(str(tmp_path))  # score.db doesn't exist
