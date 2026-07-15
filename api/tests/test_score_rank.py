from app.utils.score_rank import rank_from_exscore


def test_rank_from_exscore_returns_max_for_perfect_exscore() -> None:
    assert rank_from_exscore(2000, 1000) == "MAX"


def test_rank_from_exscore_keeps_max_minus_below_perfect_exscore() -> None:
    assert rank_from_exscore(1999, 1000) == "MAX-"
