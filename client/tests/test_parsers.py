"""Tests for BMS file parsers."""
import hashlib
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ojikbms_client.parsers.bms_scanner import compute_file_hashes, scan_bms_folders
from ojikbms_client.parsers.lr2 import parse_lr2_scores
from ojikbms_client.parsers.beatoraja import parse_beatoraja_scores


# ── BMS Scanner Tests ─────────────────────────────────────────────────────────

class TestBmsScanner:
    def test_compute_file_hashes(self, tmp_path: Path) -> None:
        """compute_file_hashes should return correct MD5 and SHA256."""
        test_content = b"#TITLE Test Song\n#ARTIST Test Artist\n"
        test_file = tmp_path / "test.bms"
        test_file.write_bytes(test_content)

        expected_md5 = hashlib.md5(test_content).hexdigest()
        expected_sha256 = hashlib.sha256(test_content).hexdigest()

        md5, sha256 = compute_file_hashes(test_file)

        assert md5 == expected_md5
        assert sha256 == expected_sha256
        assert len(md5) == 32
        assert len(sha256) == 64

    def test_scan_bms_folders_finds_bms_extensions(self, tmp_path: Path) -> None:
        """scan_bms_folders should find .bms, .bme, .bml, .bmson files."""
        # Create test BMS files with different extensions
        (tmp_path / "song1.bms").write_bytes(b"#TITLE Song 1")
        (tmp_path / "song2.bme").write_bytes(b"#TITLE Song 2")
        (tmp_path / "song3.bml").write_bytes(b"#TITLE Song 3")
        (tmp_path / "song4.bmson").write_bytes(b'{"info": {}}')
        (tmp_path / "not_a_bms.txt").write_bytes(b"ignore me")

        results, _ = scan_bms_folders([str(tmp_path)], show_progress=False)

        assert len(results) == 4
        for result in results:
            assert "song_md5" in result
            assert "song_sha256" in result
            assert len(result["song_md5"]) == 32
            assert len(result["song_sha256"]) == 64

    def test_scan_bms_folders_recursive(self, tmp_path: Path) -> None:
        """scan_bms_folders should recursively scan subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.bms").write_bytes(b"#TITLE Root")
        (subdir / "sub.bms").write_bytes(b"#TITLE Sub")

        results, _ = scan_bms_folders([str(tmp_path)], show_progress=False)
        assert len(results) == 2

    def test_scan_nonexistent_folder(self) -> None:
        """scan_bms_folders should handle nonexistent folders gracefully."""
        results, entries = scan_bms_folders(["/nonexistent/path/to/bms"], show_progress=False)
        assert results == []
        assert entries == {}

    def test_scan_empty_folder(self, tmp_path: Path) -> None:
        """scan_bms_folders should return empty list for folders with no BMS files."""
        (tmp_path / "readme.txt").write_bytes(b"not a bms file")
        results, _ = scan_bms_folders([str(tmp_path)], show_progress=False)
        assert results == []


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
                complete INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO score VALUES (
                ?,
                3, 1000, 500, 100, 50, 20,
                1200, 5, 1700000000, 10, 85.5,
                0, 0, 'abc123', 1
            )
        """, ("a" * 64,))
        # Entry with 0 playcount (should be skipped)
        conn.execute("""
            INSERT INTO score VALUES (
                ?,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0.0,
                0, 0, 'xxx', 0
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

        assert score["song_sha256"] == "a" * 64
        assert score["client_type"] == "lr2"
        assert score["clear_type"] == 4  # Normal Clear (LR2 DB 3 → internal 4)
        assert score["play_count"] == 10
        assert score["max_combo"] == 1200
        assert score["min_bp"] == 5
        assert score["judgments"]["pgreat"] == 1000
        assert score["judgments"]["great"] == 500

    def test_parse_lr2_scores_file_not_found(self) -> None:
        """parse_lr2_scores should raise FileNotFoundError for missing DB."""
        with pytest.raises(FileNotFoundError):
            parse_lr2_scores("/nonexistent/score.db")

    def test_parse_lr2_scores_score_rate_normalized(self, tmp_path: Path) -> None:
        """parse_lr2_scores should normalize score_rate to 0-1 range."""
        score_db = tmp_path / "score.db"
        _create_lr2_score_db(score_db)

        scores, _, _ = parse_lr2_scores(str(score_db))
        assert scores[0]["score_rate"] is not None
        # rate=85.5 → normalized to 0.855
        assert abs(scores[0]["score_rate"] - 0.855) < 0.001


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

        assert score["song_sha256"] == "c" * 64
        assert score["client_type"] == "beatoraja"
        assert score["clear_type"] == 2  # Assist Clear (Beatoraja DB 3 → internal 2)
        assert score["play_count"] == 15
        assert score["max_combo"] == 1000
        assert score["min_bp"] == 3
        assert score["judgments"]["pgreat"] == 1000  # ep + lp = 500 + 500
        assert score["judgments"]["exscore"] == 1400

    def test_parse_beatoraja_scores_score_rate_calculated(self, tmp_path: Path) -> None:
        """parse_beatoraja_scores should calculate score_rate from exscore/notes."""
        _create_beatoraja_score_db(tmp_path)

        scores, _, _ = parse_beatoraja_scores(str(tmp_path))
        score = scores[0]

        # exscore=1400, notes=1000, max_exscore=2000 → rate=0.7
        assert score["score_rate"] is not None
        assert abs(score["score_rate"] - 0.7) < 0.001

    def test_parse_beatoraja_scores_file_not_found(self, tmp_path: Path) -> None:
        """parse_beatoraja_scores should raise FileNotFoundError for missing DB."""
        with pytest.raises(FileNotFoundError):
            parse_beatoraja_scores(str(tmp_path))  # score.db doesn't exist
