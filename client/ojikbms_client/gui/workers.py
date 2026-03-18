"""QThread workers for OJIK BMS Client GUI.

LoginWorker: Opens the Discord OAuth URL in a browser and waits for the
             local callback to capture tokens.

SyncWorker: Runs a full or quick sync in a background thread, emitting
            progress and log signals so the UI stays responsive.
"""
import asyncio
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from ojikbms_client.parsers.lr2 import ParseStats

# Log colours — kept in sync with main_window.py constants
_PRIMARY = "#C8E6A0"
_GREEN = "#80E6A0"
_MUTED = "#8B8FA8"


class LoginWorker(QThread):
    """Worker that handles Discord OAuth login flow.

    Signals:
        url_ready(url: str): Emitted with the login URL before opening the browser.
        finished(success: bool, message: str)
    """

    url_ready = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, api_url: str) -> None:
        super().__init__()
        self._api_url = api_url

    def run(self) -> None:
        try:
            from ojikbms_client.auth import (
                find_free_port,
                get_discord_login_url,
                save_tokens,
                wait_for_oauth_callback,
            )

            port = find_free_port()
            login_url = get_discord_login_url(self._api_url, state=f"agent:{port}")
            self.url_ready.emit(login_url)
            webbrowser.open(login_url)

            result = wait_for_oauth_callback(port, timeout=120)
            if result:
                save_tokens(result["access_token"], result["refresh_token"])
                self.finished.emit(True, "로그인 성공!")
            else:
                self.finished.emit(False, "로그인 시간 초과 또는 취소됨")
        except Exception as e:
            self.finished.emit(False, str(e))


class _SyncCancelledError(Exception):
    """Raised internally when the user requests cancellation."""


class SyncWorker(QThread):
    """Worker that runs a full or quick BMS sync in a background thread.

    Signals:
        progress(current: int, total: int, filename: str)
        log(message: str)
        finished(result: dict)
        error(message: str)
        cancelled()
    """

    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        *,
        lr2_db_path: str | None,
        beatoraja_db_dir: str | None,
        bms_folders: list[str],
        quick: bool = False,
    ) -> None:
        """
        Args:
            lr2_db_path: Path to LR2 score.db.
            beatoraja_db_dir: Path to Beatoraja data directory.
            bms_folders: List of BMS folder paths.
            quick: If True, skip BMS scan entirely — only parse score DBs and sync.
        """
        super().__init__()
        self._lr2_db_path = lr2_db_path
        self._beatoraja_db_dir = beatoraja_db_dir
        self._bms_folders = bms_folders
        self._quick = quick
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation. The worker will stop at the next checkpoint."""
        self._cancelled = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self.log.emit(msg)

    def _log_parse_summary(self, label: str, stats: "ParseStats") -> None:
        """Emit a coloured parse summary to the log widget."""
        total_processed = stats.parsed + stats.parsed_courses
        self._log(
            f'[INFO] <span style="color:{_PRIMARY};font-weight:bold;">{label} 파싱 완료'
            f" ({total_processed:,}/{stats.db_total:,})</span>"
        )
        if stats.skipped_filter > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{_MUTED};">○ 미플레이/필터 제외: {stats.skipped_filter:,}개'
                f" &nbsp;<small>— 정상 동작 (플레이 기록 없는 차분 포함)</small></span>"
            )
        if stats.skipped_hash > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:#E6C880;font-weight:bold;">⚠ 해시 오류: {stats.skipped_hash:,}개'
                f"</span>"
                f'<span style="color:#E6C880;"> &nbsp;<small>— 주의: 해시 없음 또는 길이 불일치'
                f" (sync 불가, DB 손상 가능성)</small></span>"
            )

    def _parse_lr2(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (scores, courses, player_stats)."""
        if not self._lr2_db_path:
            return [], [], []
        self.progress.emit(0, 0, "LR2 score.db 파싱 중...")
        self._log("[INFO] LR2 score.db 파싱 중...")
        from ojikbms_client.parsers.lr2 import parse_lr2_player_stats, parse_lr2_scores
        scores, courses, parse_stats = parse_lr2_scores(self._lr2_db_path)
        player_data = parse_lr2_player_stats(self._lr2_db_path)
        self._log_parse_summary("LR2", parse_stats)
        player_stats = [{"client_type": "lr2", **player_data}] if player_data else []
        return scores, courses, player_stats

    def _parse_beatoraja(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (scores, courses, player_stats, score_log)."""
        if not self._beatoraja_db_dir:
            return [], [], [], []
        self.progress.emit(0, 0, "Beatoraja score.db 파싱 중...")
        self._log("[INFO] Beatoraja score.db 파싱 중...")
        from ojikbms_client.parsers.beatoraja import (
            parse_beatoraja_player_stats,
            parse_beatoraja_score_log,
            parse_beatoraja_scores,
        )
        from ojikbms_client.sync import _convert_score_log
        scores, courses, parse_stats = parse_beatoraja_scores(self._beatoraja_db_dir)
        player_data = parse_beatoraja_player_stats(self._beatoraja_db_dir)
        self._log_parse_summary("Beatoraja", parse_stats)
        raw_log = parse_beatoraja_score_log(self._beatoraja_db_dir)
        score_log = _convert_score_log(raw_log)
        self._log(f"[INFO] Beatoraja: scorelog.db {len(raw_log):,}개 이력 파싱 완료")
        player_stats = [{"client_type": "beatoraja", **player_data}] if player_data else []
        return scores, courses, player_stats, score_log

    def _scan_bms(self) -> list[dict[str, Any]]:
        """Run BMS scan with cache, emitting progress signals."""
        if not self._bms_folders:
            return []

        from ojikbms_client.parsers.bms_scanner import scan_bms_folders
        from ojikbms_client.scan_cache import load_cache, save_cache

        cache = load_cache()
        cached_count = len(cache.get("files", {})) if cache else 0
        self._log(f"[INFO] BMS 파일 폴더 스캔 시작... (캐시 되어있는 차분: {cached_count:,}개)")
        # Emit immediately so the label switches before the first throttled callback fires
        self.progress.emit(0, 0, "BMS 파일 폴더 스캔 중...")

        def _cb(current: int, total: int, filename: str) -> None:
            if self._cancelled:
                raise _SyncCancelledError()
            self.progress.emit(current, total, filename)

        owned_songs, new_entries, scan_stats = scan_bms_folders(
            self._bms_folders,
            show_progress=False,
            cache=cache,
            progress_callback=_cb,
            log_callback=self._log,
        )

        merged = {**cache.get("files", {}), **new_entries}
        save_cache(merged, owned_songs)
        newly_hashed = len(new_entries)
        total_found = len(owned_songs) + scan_stats["skipped_empty"] + scan_stats["error_count"]
        self._log(
            f'[INFO] <span style="color:{_PRIMARY};font-weight:bold;">BMS 파일 폴더 스캔 완료'
            f" ({len(owned_songs):,}/{total_found:,})</span>"
        )
        cached_reused = len(owned_songs) - newly_hashed
        if cached_reused > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{_MUTED};">○ 캐시 재사용: {cached_reused:,}개'
                f" &nbsp;<small>— 정상 동작 (변경 없는 파일은 재해싱 생략)</small></span>"
            )
        if scan_stats["skipped_empty"] > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{_MUTED};">○ 빈 파일 제외: {scan_stats["skipped_empty"]:,}개'
                f" &nbsp;<small>— 정상 동작 (0바이트 파일)</small></span>"
            )
        return owned_songs

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            all_scores: list[dict[str, Any]] = []
            all_courses: list[dict[str, Any]] = []
            all_player_stats: list[dict[str, Any]] = []
            all_owned_songs: list[dict[str, Any]] = []
            all_score_log: list[dict[str, Any]] = []

            # Parse score DBs — run LR2 and Beatoraja concurrently (both are I/O-bound)
            with ThreadPoolExecutor(max_workers=2) as _pool:
                _lr2_fut = _pool.submit(self._parse_lr2)
                _bea_fut = _pool.submit(self._parse_beatoraja)

                try:
                    scores, courses, pstats = _lr2_fut.result()
                    all_scores.extend(scores)
                    all_courses.extend(courses)
                    all_player_stats.extend(pstats)
                except Exception as e:
                    self._log(f"[ERROR] LR2 파싱 오류: {e}")

                try:
                    scores, courses, pstats, score_log = _bea_fut.result()
                    all_scores.extend(scores)
                    all_courses.extend(courses)
                    all_player_stats.extend(pstats)
                    all_score_log.extend(score_log)
                except Exception as e:
                    self._log(f"[ERROR] Beatoraja 파싱 오류: {e}")

            if self._cancelled:
                raise _SyncCancelledError()

            # BMS folder scan — skipped entirely in quick mode
            if not self._quick and self._bms_folders:
                owned_songs = self._scan_bms()
                all_owned_songs.extend(owned_songs)

            if self._cancelled:
                raise _SyncCancelledError()

            if not all_scores and not all_courses and not all_owned_songs and not all_player_stats and not all_score_log:
                self._log("[WARN] 동기화할 데이터가 없습니다.")
                self.finished.emit({"synced_scores": 0, "synced_songs": 0, "synced_courses": 0, "synced_score_log": 0, "errors": []})
                return

            self._log("[INFO] 서버에 동기화 중...")
            self.progress.emit(0, 0, "서버 동기화 준비 중...")
            from ojikbms_client.sync import sync_scores

            def _sync_progress(current: int, total: int) -> None:
                self.progress.emit(current, total, "서버에 업로드 중...")

            sent_songs = len(all_owned_songs)
            result = asyncio.run(sync_scores(all_scores, all_owned_songs, all_player_stats, all_courses, all_score_log, progress_callback=_sync_progress))
            updated_scores_count = result.get('updated_scores', 0)
            total_records = result['synced_scores'] + result.get('synced_courses', 0)
            synced_songs = result.get('synced_songs', 0)

            # Main highlight line — always show updated score count
            self._log(
                f'[INFO] <span style="color:{_GREEN};font-weight:bold;">동기화 완료'
                f" — 갱신된 기록: {updated_scores_count:,}개</span>"
            )

            # Full sync: new/removed diff sub-line
            if not self._quick and sent_songs > 0:
                new_songs = result.get('new_songs', 0)
                removed_songs = result.get('removed_songs', 0)
                self._log(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;"
                    f'<span style="color:{_MUTED};">○ 신규 차분: {new_songs:,}개'
                    f" / 제거된 차분: {removed_songs:,}개</span>"
                )

            # Stats sub-line
            if not self._quick:
                self._log(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;"
                    f'<span style="color:{_MUTED};">○ 기록 총 {total_records:,}개'
                    f" / 차분 총 {synced_songs:,}개</span>"
                )
            else:
                self._log(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;"
                    f'<span style="color:{_MUTED};">○ 기록 총 {total_records:,}개</span>'
                )

            # Duplicate diff exclusion sub-line (full sync only)
            if not self._quick and sent_songs > 0 and synced_songs < sent_songs:
                dupes = sent_songs - synced_songs
                self._log(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;"
                    f'<span style="color:{_MUTED};">○ 중복된 차분 데이터 제외: {dupes:,}개'
                    f" &nbsp;<small>— 정상 동작 (MD5/SHA256 동일 파일)</small></span>"
                )
            if result.get("errors"):
                for err in result["errors"][:5]:
                    self._log(f"[WARN] {err}")

            self.finished.emit(result)

        except _SyncCancelledError:
            self._log("[INFO] 동기화가 취소되었습니다.")
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(str(e))
