"""Server synchronization logic for the OJIK agent."""
import asyncio
from collections.abc import Callable
from typing import Any

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ojikbms_client.auth import make_authenticated_request
from ojikbms_client.config import get_api_url, update_last_synced_at

console = Console()

BATCH_SIZE = 2000  # Number of scores to sync per batch


async def sync_scores(
    scores: list[dict[str, Any]],
    owned_songs: list[dict[str, Any]] | None = None,
    player_stats: list[dict[str, Any]] | None = None,
    courses: list[dict[str, Any]] | None = None,
    score_log: list[dict[str, Any]] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Sync scores, courses, owned songs, player stats, and score history to the server in batches.

    Args:
        scores: List of score dicts matching ScoreSyncItem schema.
        owned_songs: List of owned song dicts matching OwnedSongItem schema.
        player_stats: List of player stat dicts from the player table.
        courses: List of course dicts matching CourseSyncItem schema.
        score_log: List of Beatoraja scorelog entries for history backfill.

    Returns:
        Summary dict with synced_scores, synced_songs, synced_courses, synced_score_log, errors.
    """
    api_url = get_api_url()
    owned_songs = owned_songs or []
    player_stats = player_stats or []
    courses = courses or []
    score_log = score_log or []

    total_synced_scores = 0
    total_synced_songs = 0
    total_synced_courses = 0
    total_synced_score_log = 0
    all_errors: list[str] = []

    any_batch_succeeded = False

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Build score batches — skip if no scores
        score_batches = (
            [scores[i : i + BATCH_SIZE] for i in range(0, len(scores), BATCH_SIZE)]
            if scores
            else []
        )

        # If there are owned songs/player_stats/courses/score_log but no score batches, send in a single empty batch
        if not score_batches and (owned_songs or player_stats or courses or score_log):
            score_batches = [[]]

        total_batches = len(score_batches)
        for batch_idx, score_batch in enumerate(score_batches, 1):
            # Include owned_songs, player_stats, courses, and score_log only in the first batch
            songs_batch = owned_songs if batch_idx == 1 else []
            stats_batch = player_stats if batch_idx == 1 else []
            courses_batch = courses if batch_idx == 1 else []
            score_log_batch = score_log if batch_idx == 1 else []

            payload = {
                "scores": score_batch,
                "owned_songs": songs_batch,
                "player_stats": stats_batch,
                "courses": courses_batch,
                "score_log": score_log_batch,
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
                total_synced_songs += data.get("synced_songs", 0)
                total_synced_courses += data.get("synced_courses", 0)
                total_synced_score_log += data.get("synced_score_log", 0)
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
        "synced_songs": total_synced_songs,
        "synced_courses": total_synced_courses,
        "synced_score_log": total_synced_score_log,
        "errors": all_errors,
    }


async def get_sync_status() -> dict[str, Any] | None:
    """Get the current sync status from the server."""
    api_url = get_api_url()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await make_authenticated_request(
            client,
            "GET",
            f"{api_url}/sync/status",
            api_url=api_url,
        )

        if response.status_code == 200:
            return response.json()

    return None


def _convert_score_log(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert parse_beatoraja_score_log output to ScoreLogItem-compatible dicts."""
    result = []
    for entry in raw:
        sha256 = entry.get("sha256", "")
        played_at = entry.get("played_at")
        if not sha256 or len(sha256) != 64 or not played_at:
            continue
        result.append({
            "song_sha256": sha256,
            "client_type": "beatoraja",
            "clear_type": entry.get("clear_type"),
            "max_combo": entry.get("max_combo"),
            "min_bp": entry.get("min_bp"),
            "played_at": played_at,
        })
    return result


def run_full_sync(
    lr2_db_path: str | None = None,
    beatoraja_db_dir: str | None = None,
    bms_folders: list[str] | None = None,
) -> None:
    """
    Run a full synchronization: parse local DBs and sync to server.

    Args:
        lr2_db_path: Path to LR2 score.db file.
        beatoraja_db_dir: Path to Beatoraja data directory.
        bms_folders: List of BMS folder paths to scan.
    """
    all_scores: list[dict[str, Any]] = []
    all_courses: list[dict[str, Any]] = []
    all_owned_songs: list[dict[str, Any]] = []
    all_player_stats: list[dict[str, Any]] = []
    all_score_log: list[dict[str, Any]] = []

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
                all_courses.extend(lr2_courses)

                lr2_stats = parse_lr2_player_stats(lr2_db_path)
                if lr2_stats:
                    all_player_stats.append({"client_type": "lr2", **lr2_stats})

                progress.update(task, description=f"LR2: {len(lr2_scores)}개 스코어 파싱 완료")
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
                all_courses.extend(bea_courses)

                bea_stats = parse_beatoraja_player_stats(beatoraja_db_dir)
                if bea_stats:
                    all_player_stats.append({"client_type": "beatoraja", **bea_stats})

                bea_log = parse_beatoraja_score_log(beatoraja_db_dir)
                all_score_log.extend(_convert_score_log(bea_log))

                progress.update(task, description=f"Beatoraja: {len(bea_scores)}개 스코어, {len(bea_log)}개 기록 이력 파싱 완료")
            except Exception as e:
                console.print(f"[red]Beatoraja 파싱 오류: {e}[/red]")

        if bms_folders:
            task = progress.add_task("BMS 파일 폴더 스캔 중...", total=None)
            try:
                from ojikbms_client.parsers.bms_scanner import scan_bms_folders
                from ojikbms_client.scan_cache import (
                    load_cache,
                    save_cache,
                )
                cache = load_cache()
                owned_songs, new_entries, _ = scan_bms_folders(bms_folders, cache=cache)
                all_owned_songs.extend(owned_songs)
                # Merge new entries with existing cache and persist
                merged = {**cache.get("files", {}), **new_entries}
                save_cache(merged, owned_songs)
                progress.update(task, description=f"BMS 폴더: {len(owned_songs)}개 파일 발견")
            except Exception as e:
                console.print(f"[red]BMS 폴더 스캔 오류: {e}[/red]")

        if not all_scores and not all_owned_songs and not all_player_stats:
            console.print("[yellow]동기화할 데이터가 없습니다.[/yellow]")
            return

        task = progress.add_task("서버에 동기화 중...", total=None)
        result = asyncio.run(sync_scores(all_scores, all_owned_songs, all_player_stats, all_courses, all_score_log))
        progress.update(task, description="동기화 완료")

    total_records = result['synced_scores'] + result.get('synced_courses', 0)
    console.print(
        f"\n[green]동기화 완료:[/green] "
        f"기록 {total_records}개, "
        f"차분 {result['synced_songs']}개"
    )

    if result["errors"]:
        console.print(f"[yellow]경고: {len(result['errors'])}개 오류 발생[/yellow]")
        for err in result["errors"][:5]:
            console.print(f"  - {err}")
