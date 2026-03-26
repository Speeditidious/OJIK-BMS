"""Tests for BMS file parsers."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ojikbms_client.parsers.lr2 import parse_lr2_scores
from ojikbms_client.parsers.beatoraja import parse_beatoraja_scores


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
                1700000000, NULL, 1000
            )
        """, ("c" * 64,))
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

    def test_parse_beatoraja_scores_file_not_found(self, tmp_path: Path) -> None:
        """parse_beatoraja_scores should raise FileNotFoundError for missing DB."""
        with pytest.raises(FileNotFoundError):
            parse_beatoraja_scores(str(tmp_path))  # score.db doesn't exist
