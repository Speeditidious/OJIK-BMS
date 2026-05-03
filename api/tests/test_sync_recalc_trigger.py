"""Tests for sync-triggered ranking recalculation gating."""

from app.routers.sync import SyncRequest, _should_enqueue_ranking_recalculation


def test_sync_request_defaults_to_final_batch_for_legacy_clients() -> None:
    """Clients that do not send batching metadata should keep previous behavior."""
    payload = SyncRequest(scores=[], player_stats=[])

    assert payload.is_final_batch is True


def test_ranking_recalc_only_triggers_for_final_batches_with_changes() -> None:
    """Intermediate sync batches should not enqueue expensive ranking recalculation."""
    assert not _should_enqueue_ranking_recalculation(
        SyncRequest(scores=[], player_stats=[], is_final_batch=False),
        synced_scores=10,
        inserted_scores=0,
    )
    assert not _should_enqueue_ranking_recalculation(
        SyncRequest(scores=[], player_stats=[], is_final_batch=True),
        synced_scores=0,
        inserted_scores=0,
    )
    assert _should_enqueue_ranking_recalculation(
        SyncRequest(scores=[], player_stats=[], is_final_batch=True),
        synced_scores=0,
        inserted_scores=1,
    )
    assert _should_enqueue_ranking_recalculation(
        SyncRequest(
            scores=[],
            player_stats=[],
            is_final_batch=True,
            has_previous_score_changes=True,
        ),
        synced_scores=0,
        inserted_scores=0,
    )
