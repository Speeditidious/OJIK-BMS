"""Server synchronization logic for the OJIK agent."""
import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ojikbms_client.auth import make_authenticated_request
from ojikbms_client.config import get_api_url, is_local_url, update_last_synced_at

console = Console()


def _make_client(**kwargs: Any) -> httpx.AsyncClient:
    """Create an AsyncClient, disabling SSL verification for local URLs."""
    api_url = get_api_url()
    if is_local_url(api_url):
        kwargs.setdefault("verify", False)
    return httpx.AsyncClient(**kwargs)

BATCH_SIZE = 500  # Number of scores to sync per batch


async def sync_scores(
    scores: list[dict[str, Any]],
    player_stats: list[dict[str, Any]] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Sync scores and player stats to the server in batches.

    Args:
        scores: List of score dicts matching ScoreSyncItem schema.
        player_stats: List of player stat dicts from the player table.

    Returns:
        Summary dict with synced_scores, errors.
    """
    api_url = get_api_url()
    player_stats = player_stats or []

    total_synced_scores = 0
    total_inserted_scores = 0
    all_errors: list[str] = []

    any_batch_succeeded = False

    async with _make_client(timeout=300.0) as client:
        # Build score batches — skip if no scores
        score_batches = (
            [scores[i : i + BATCH_SIZE] for i in range(0, len(scores), BATCH_SIZE)]
            if scores
            else []
        )

        # If there are player_stats but no score batches, send in a single empty batch
        if not score_batches and player_stats:
            score_batches = [[]]

        total_batches = len(score_batches)
        for batch_idx, score_batch in enumerate(score_batches, 1):
            # Include player_stats only in the first batch
            stats_batch = player_stats if batch_idx == 1 else []

            payload = {
                "scores": score_batch,
                "player_stats": stats_batch,
            }

            response = await make_authenticated_request(
                client,
                "POST",
                f"{api_url}/sync/",
                api_url=api_url,
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                total_synced_scores += data.get("synced_scores", 0)
                total_inserted_scores += data.get("inserted_scores", 0)
                all_errors.extend(data.get("errors", []))
                any_batch_succeeded = True
                if progress_callback:
                    progress_callback(batch_idx, total_batches)
            else:
                all_errors.append(
                    f"Batch {batch_idx} failed: HTTP {response.status_code} - {response.text[:200]}"
                )

    # Update last synced timestamp if at least one batch succeeded
    if any_batch_succeeded:
        update_last_synced_at()

    return {
        "synced_scores": total_synced_scores,
        "inserted_scores": total_inserted_scores,
        "errors": all_errors,
    }


async def fetch_today_improvement_count() -> int | None:
    """Fetch today's improvement count (actual score improvements) from the analysis API.

    Returns:
        Number of improved fumen records today, or None on failure.
    """
    api_url = get_api_url()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    async with _make_client(timeout=10.0) as client:
        response = await make_authenticated_request(
            client,
            "GET",
            f"{api_url}/analysis/recent-updates",
            api_url=api_url,
            params={"date": today, "limit": 1},
        )

        if response.status_code == 200:
            day_summary = response.json().get("day_summary") or {}
            return day_summary.get("total_updates")

    return None


async def fetch_known_hashes() -> dict[str, set[str]]:
    """Fetch known fumen hash sets from the server for client-side pre-filtering.

    Returns:
        Dict with keys: complete_sha256, complete_md5, partial_sha256, partial_md5.
        Each value is a set of lowercase hash strings.
        Returns empty sets on error.
    """
    api_url = get_api_url()
    try:
        async with _make_client(timeout=60.0) as client:
            response = await make_authenticated_request(
                client,
                "GET",
                f"{api_url}/fumens/known-hashes",
                api_url=api_url,
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "complete_sha256": set(data.get("complete_sha256", [])),
                    "complete_md5": set(data.get("complete_md5", [])),
                    "partial_sha256": set(data.get("partial_sha256", [])),
                    "partial_md5": set(data.get("partial_md5", [])),
                }
    except Exception:
        pass
    return {
        "complete_sha256": set(),
        "complete_md5": set(),
        "partial_sha256": set(),
        "partial_md5": set(),
    }


async def sync_fumen_details(
    items: list[dict[str, Any]],
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Sync fumen detail data to the server in batches.

    NOTE: items should already be filtered by the caller using known_hashes
    (items that are 'complete' on the server should be excluded before calling).

    Args:
        items: List of fumen detail dicts matching FumenDetailItem schema.
        progress_callback: Optional (current_batch, total_batches) callback.

    Returns:
        Summary dict with inserted, updated, skipped, errors.
    """
    api_url = get_api_url()
    # 15 columns per row × 1024 rows = 15,360 params < asyncpg's 32767 limit
    batch_size = 1024
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    all_errors: list[str] = []

    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)] if items else []

    async with _make_client(timeout=300.0) as client:
        for batch_idx, batch in enumerate(batches, 1):
            payload = {"items": batch}
            response = await make_authenticated_request(
                client,
                "POST",
                f"{api_url}/fumens/sync-details",
                api_url=api_url,
                json=payload,
            )
            if response.status_code == 200:
                data = response.json()
                total_inserted += data.get("inserted", 0)
                total_updated += data.get("updated", 0)
                total_skipped += data.get("skipped", 0)
                if progress_callback:
                    progress_callback(batch_idx, len(batches))
            else:
                all_errors.append(
                    f"Batch {batch_idx} failed: HTTP {response.status_code} - {response.text[:200]}"
                )

    return {
        "inserted": total_inserted,
        "updated": total_updated,
        "skipped": total_skipped,
        "errors": all_errors,
    }


async def get_sync_status() -> dict[str, Any] | None:
    """Get the current sync status from the server."""
    api_url = get_api_url()

    async with _make_client(timeout=10.0) as client:
        response = await make_authenticated_request(
            client,
            "GET",
            f"{api_url}/sync/status",
            api_url=api_url,
        )

        if response.status_code == 200:
            return response.json()

    return None


def run_full_sync(
    lr2_db_path: str | None = None,
    beatoraja_db_dir: str | None = None,
) -> None:
    """
    Run a full synchronization: parse local DBs and sync to server.

    Args:
        lr2_db_path: Path to LR2 score.db file.
        beatoraja_db_dir: Path to Beatoraja data directory.
    """
    all_scores: list[dict[str, Any]] = []
    all_player_stats: list[dict[str, Any]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        if lr2_db_path:
            task = progress.add_task("LR2 DB 파싱 중...", total=None)
            try:
                from ojikbms_client.parsers.lr2 import (
                    parse_lr2_player_stats,
                    parse_lr2_scores,
                )
                lr2_scores, lr2_courses, _ = parse_lr2_scores(lr2_db_path)
                all_scores.extend(lr2_scores)
                all_scores.extend(lr2_courses)  # course records are now ScoreSyncItem-compatible

                lr2_stats = parse_lr2_player_stats(lr2_db_path)
                if lr2_stats:
                    all_player_stats.append({"client_type": "lr2", **lr2_stats})

                progress.update(task, description=f"LR2: {len(lr2_scores)}개 스코어, {len(lr2_courses)}개 코스 파싱 완료")
            except Exception as e:
                console.print(f"[red]LR2 파싱 오류: {e}[/red]")

        if beatoraja_db_dir:
            task = progress.add_task("Beatoraja DB 파싱 중...", total=None)
            try:
                from ojikbms_client.parsers.beatoraja import (
                    parse_beatoraja_player_stats,
                    parse_beatoraja_score_log,
                    parse_beatoraja_scores,
                )
                bea_scores, bea_courses, _ = parse_beatoraja_scores(beatoraja_db_dir)
                all_scores.extend(bea_scores)
                all_scores.extend(bea_courses)  # course records are now ScoreSyncItem-compatible

                bea_stats = parse_beatoraja_player_stats(beatoraja_db_dir)
                if bea_stats:
                    all_player_stats.append({"client_type": "beatoraja", **bea_stats})

                # Scorelog entries are now regular ScoreSyncItem-compatible dicts
                bea_log = parse_beatoraja_score_log(beatoraja_db_dir)
                all_scores.extend(bea_log)

                progress.update(task, description=f"Beatoraja: {len(bea_scores)}개 스코어, {len(bea_courses)}개 코스, {len(bea_log)}개 기록 이력 파싱 완료")
            except Exception as e:
                console.print(f"[red]Beatoraja 파싱 오류: {e}[/red]")

        if not all_scores and not all_player_stats:
            console.print("[yellow]동기화할 데이터가 없습니다.[/yellow]")
            return

        task = progress.add_task("서버에 동기화 중...", total=None)
        result = asyncio.run(sync_scores(all_scores, all_player_stats))
        improvement_count = asyncio.run(fetch_today_improvement_count())
        progress.update(task, description="동기화 완료")

    if improvement_count is not None:
        console.print(
            f"\n[bold green]기록 갱신 {improvement_count}건[/bold green]"
            f"  [dim](총 {result['synced_scores']}건 기록됨)[/dim]"
        )
    else:
        console.print(
            f"\n[green]동기화 완료:[/green] "
            f"기록 {result['synced_scores']}건"
        )

    if result["errors"]:
        console.print(f"[yellow]경고: {len(result['errors'])}개 오류 발생[/yellow]")
        for err in result["errors"][:5]:
            console.print(f"  - {err}")
