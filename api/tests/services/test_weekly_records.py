from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import uuid

from app.services.weekly_records import CANDIDATE_SORT_KEYS, evaluate_user_records


START = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
END = START + timedelta(days=7)


def _row(clear_type, exscore, ts, play_count=1, min_bp=None, rate=None, rank=None):
    return SimpleNamespace(
        clear_type=clear_type, exscore=exscore, min_bp=min_bp, rate=rate, rank=rank,
        play_count=play_count, client_type="beatoraja",
        id=None,
        options=None,
        recorded_at=ts, synced_at=ts,
    )


def test_user_played_in_window_with_improvement_is_flagged():
    rows = {
        "u1": [
            _row(2, 1000, START - timedelta(days=10)),
            _row(4, 1200, START + timedelta(days=1)),
        ]
    }
    result = evaluate_user_records(rows, START, END)
    assert "u1" in result
    rec = result["u1"]
    assert rec.improved is True
    assert rec.best_clear_type == 4
    assert rec.best_exscore == 1200
    assert rec.baseline is not None
    assert rec.baseline.exscore == 1000
    assert rec.weekly_best.exscore == 1200
    assert rec.improvement.exscore_delta == 200


def test_user_played_in_window_without_improvement_not_flagged():
    rows = {
        "u1": [
            _row(5, 1500, START - timedelta(days=10)),
            _row(3, 1100, START + timedelta(days=1)),
        ]
    }
    result = evaluate_user_records(rows, START, END)
    rec = result["u1"]
    assert rec.improved is False
    assert rec.best_clear_type == 5
    assert rec.best_exscore == 1500
    assert rec.improvement.has_changes is False


def test_lower_clear_type_with_higher_exscore_shows_only_exscore_delta():
    rows = {
        "u1": [
            _row(5, 1500, START - timedelta(days=10)),
            _row(3, 1700, START + timedelta(days=1)),
        ]
    }
    result = evaluate_user_records(rows, START, END)
    rec = result["u1"]
    assert rec.improved is True
    assert rec.improvement.clear_type_changed is False
    assert rec.improvement.exscore_delta == 200


def test_baseline_is_latest_pre_window_record_not_pre_window_best():
    rows = {
        "u1": [
            _row(5, 1600, START - timedelta(days=30)),
            _row(4, 1500, START - timedelta(days=1)),
            _row(4, 1550, START + timedelta(days=1)),
        ]
    }
    result = evaluate_user_records(rows, START, END)
    rec = result["u1"]
    assert rec.baseline is not None
    assert rec.baseline.clear_type == 4
    assert rec.baseline.exscore == 1500
    assert rec.improvement.exscore_delta == 50


def test_user_not_played_in_window_is_excluded():
    rows = {
        "u1": [
            _row(5, 1500, START - timedelta(days=10)),
        ]
    }
    result = evaluate_user_records(rows, START, END)
    assert "u1" not in result


def test_first_ever_record_in_window_is_improvement():
    rows = {"u1": [_row(2, 800, START + timedelta(days=2))]}
    result = evaluate_user_records(rows, START, END)
    assert result["u1"].improved is True
    assert result["u1"].improvement.is_first_record is True


def test_bp_rate_rank_improvements_are_reported():
    rows = {
        "u1": [
            _row(3, 1200, START - timedelta(days=1), min_bp=40, rate=0.70, rank="A"),
            _row(3, 1200, START + timedelta(days=1), min_bp=25, rate=0.735, rank="AA"),
        ]
    }
    result = evaluate_user_records(rows, START, END)
    rec = result["u1"]
    assert rec.improved is True
    assert rec.improvement.min_bp_delta == -15
    assert rec.improvement.rate_delta is not None
    assert abs(rec.improvement.rate_delta - 0.035) < 1e-9
    assert rec.improvement.rank_changed is True


def test_user_record_carries_score_id_options_client_type_play_count():
    """UserRecord exposes best_row's score_id/options/client_type/play_count for the row + detail."""
    import uuid
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from app.services.weekly_records import evaluate_user_records

    start = datetime(2026, 6, 9, tzinfo=timezone.utc)
    end   = datetime(2026, 6, 16, tzinfo=timezone.utc)

    sid = uuid.uuid4()
    score = SimpleNamespace(
        id=sid,
        user_id="u1",
        clear_type=5,
        exscore=1800,
        min_bp=10,
        rate=0.98,
        rank="AA",
        play_count=7,
        options={"op_best": 12},
        client_type="lr2",
        recorded_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        synced_at=None,
    )
    result = evaluate_user_records({"u1": [score]}, start, end)

    rec = result["u1"]
    assert rec.best_score_id == str(sid)
    assert rec.best_play_count == 7
    assert rec.best_options == {"op_best": 12}
    assert rec.best_client_type == "lr2"


def test_user_record_separates_display_best_from_weekly_detail_record():
    """Detail rows should open the score achieved during the weekly period."""
    older_best_id = uuid.uuid4()
    weekly_id = uuid.uuid4()
    rows = {
        "u1": [
            SimpleNamespace(
                id=older_best_id,
                clear_type=6,
                exscore=1900,
                min_bp=10,
                rate=0.95,
                rank="AAA",
                play_count=20,
                options={"op": "old-best"},
                client_type="beatoraja",
                recorded_at=START - timedelta(days=3),
                synced_at=None,
            ),
            SimpleNamespace(
                id=weekly_id,
                clear_type=5,
                exscore=1850,
                min_bp=12,
                rate=0.925,
                rank="AA",
                play_count=8,
                options={"op": "weekly-lr2"},
                client_type="lr2",
                recorded_at=START + timedelta(days=2),
                synced_at=None,
            ),
        ]
    }

    rec = evaluate_user_records(rows, START, END)["u1"]

    assert rec.best_score_id == str(older_best_id)
    assert rec.best_clear_type == 6
    assert rec.weekly_score_id == str(weekly_id)
    assert rec.weekly_client_type == "lr2"
    assert rec.weekly_options == {"op": "weekly-lr2"}


def test_candidate_sort_keys_include_bp():
    """Weekly record pages should expose BP as a server-side sort key."""
    assert "bp" in CANDIDATE_SORT_KEYS
