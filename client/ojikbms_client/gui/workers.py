"""QThread workers for OJIK BMS Client GUI.

LoginWorker: Opens the Discord OAuth URL in a browser and waits for the
             local callback to capture tokens.

SyncWorker: Runs a sync in a background thread, emitting
            progress and log signals so the UI stays responsive.
"""
from __future__ import annotations

import asyncio
import enum
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from ojikbms_client.parsers.lr2 import ParseStats

# Log colours — kept in sync with main_window.py constants
_PRIMARY = "#C8E6A0"
_GREEN = "#80E6A0"
_MUTED = "#8B8FA8"


class SyncMode(enum.Enum):
    """Which databases to sync."""

    QUICK = "quick"  # score / scorelog only
    FULL = "full"    # score / scorelog + song DB (hash supplementation)


class ClientFilter(enum.Enum):
    """Which game clients to include in this sync run."""

    ALL = "all"
    LR2_ONLY = "lr2"
    BEA_ONLY = "beatoraja"


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
    """Worker that runs a BMS sync in a background thread.

    Signals:
        progress(current: int, total: int, label: str)
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
        beatoraja_songdata_db_path: str | None = None,
        beatoraja_songinfo_db_path: str | None = None,
        lr2_song_db_path: str | None = None,
        mode: SyncMode = SyncMode.QUICK,
        client_filter: ClientFilter = ClientFilter.ALL,
    ) -> None:
        super().__init__()
        self._lr2_db_path = lr2_db_path
        self._beatoraja_db_dir = beatoraja_db_dir
        self._beatoraja_songdata_db_path = beatoraja_songdata_db_path
        self._beatoraja_songinfo_db_path = beatoraja_songinfo_db_path
        self._lr2_song_db_path = lr2_song_db_path
        self._mode = mode
        self._client_filter = client_filter
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation. The worker will stop at the next checkpoint."""
        self._cancelled = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self.log.emit(msg)

    def _log_parse_summary(self, label: str, stats: ParseStats) -> None:
        total_processed = stats.parsed + stats.parsed_courses
        self._log(
            f'[INFO] <span style="color:{_PRIMARY};font-weight:bold;">{label} 처리 완료'
            f" ({total_processed:,}/{stats.effective_total:,})</span>"
        )
        if stats.skipped_filter > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{_MUTED};">미플레이/필터 제외: {stats.skipped_filter:,}개'
                f" &nbsp;- 정상 동작 (플레이 기록 없는 차분 포함)</span>"
            )
        if stats.skipped_lr2 > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{_MUTED};">LR2 기록 제외: {stats.skipped_lr2:,}개'
                f" &nbsp;- 정상 동작 (LR2에서 임포트된 기록. Beatoraja 기록 아님)</span>"
            )
        if stats.skipped_hash > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:#E6C880;font-weight:bold;">⚠ 해시 오류: {stats.skipped_hash:,}개</span>'
                f' <span style="color:#E6C880;">&nbsp;- 주의: 해시 없음 또는 길이 불일치'
                f" (sync 불가, DB 손상 가능성)</span>"
            )

    def _log_db_recognition(
        self,
        label: str,
        path: str | None,
        required_for_quick: bool = False,
        required_for_full: bool = False,
    ) -> bool:
        """Log whether a DB path was recognized, return True if usable.

        - Empty path: silent (not an error, user simply hasn't configured it).
        - Path set but file/dir missing: warning if required for current mode.
        """
        if not path:
            return False

        exists = Path(path).exists()
        if exists:
            return True

        # Path is configured but doesn't exist on disk
        needs = (required_for_quick and self._mode == SyncMode.QUICK) or \
                (required_for_full and self._mode == SyncMode.FULL)
        if needs:
            self._log(
                f"[WARN] {label}: 경로가 설정되어 있지만 파일/폴더를 찾을 수 없습니다. "
                f"경로를 다시 확인해주세요. ({path})"
            )
        return False

    def _log_recognition_summary(
        self,
        lr2_ok: bool,
        bea_ok: bool,
        bea_songdata_ok: bool,
    ) -> None:
        """Emit recognition summary for global sync runs (ALL filter)."""
        if self._client_filter != ClientFilter.ALL:
            return  # per-client buttons don't need the combined summary

        if lr2_ok:
            self._log(f'[INFO] LR2 기록 DB 인식됨: <span style="color:{_MUTED};">{self._lr2_db_path}</span>')
        elif self._lr2_db_path:
            pass  # already warned above if missing
        else:
            self._log(f'[INFO] <span style="color:{_MUTED};">LR2 DB: 경로 없음 (동기화 건너뜀)</span>')

        if bea_ok:
            self._log(f'[INFO] Beatoraja 기록 DB 인식됨: <span style="color:{_MUTED};">{self._beatoraja_db_dir}</span>')
        elif self._beatoraja_db_dir:
            pass
        else:
            self._log(f'[INFO] <span style="color:{_MUTED};">Beatoraja DB: 경로 없음 (동기화 건너뜀)</span>')

        if self._mode == SyncMode.FULL:
            if bea_ok and not bea_songdata_ok:
                self._log(
                    "[WARN] Beatoraja 전체 동기화: songdata.db 경로가 설정되지 않았거나 "
                    "파일을 찾을 수 없습니다. 해시 보강을 건너뜁니다."
                )

    def _check_beatoraja_completeness(self) -> None:
        """Warn when Beatoraja score folder is set but scorelog.db is missing."""
        if not self._beatoraja_db_dir:
            return
        bdir = Path(self._beatoraja_db_dir)
        if bdir.exists() and not (bdir / "scorelog.db").exists():
            self._log(
                "[WARN] Beatoraja: scorelog.db를 찾을 수 없습니다. "
                "폴더 경로를 다시 확인해주세요."
            )

    def _parse_lr2(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (scores, player_stats). Courses are included in scores."""
        if not self._lr2_db_path:
            return [], []
        self.progress.emit(0, 0, "LR2 &lt;username&gt;.db 처리 중...")
        self._log("[INFO] LR2 &lt;username&gt;.db 처리 중...")
        from ojikbms_client.parsers.lr2 import parse_lr2_player_stats, parse_lr2_scores
        scores, courses, parse_stats = parse_lr2_scores(self._lr2_db_path)
        player_data = parse_lr2_player_stats(self._lr2_db_path)
        self._log_parse_summary("LR2 플레이 기록", parse_stats)
        player_stats = [{"client_type": "lr2", **player_data}] if player_data else []
        return scores + courses, player_stats

    def _parse_beatoraja(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (scores, player_stats). Courses and scorelog entries included."""
        if not self._beatoraja_db_dir:
            return [], []
        self.progress.emit(0, 0, "Beatoraja score.db 및 scorelog.db 처리 중...")
        self._log("[INFO] Beatoraja score.db 및 scorelog.db 처리 중...")
        from ojikbms_client.parsers.beatoraja import (
            parse_beatoraja_player_stats,
            parse_beatoraja_score_log,
            parse_beatoraja_scores,
        )
        scores, courses, parse_stats = parse_beatoraja_scores(self._beatoraja_db_dir)
        player_data = parse_beatoraja_player_stats(self._beatoraja_db_dir)
        self._log_parse_summary("Beatoraja score.db", parse_stats)
        raw_log, log_stats = parse_beatoraja_score_log(self._beatoraja_db_dir)
        self._log(
            f'[INFO] <span style="color:{_PRIMARY};font-weight:bold;">Beatoraja scorelog.db 처리 완료'
            f" ({log_stats.parsed:,}/{log_stats.total_queried:,})</span>"
        )
        if log_stats.skipped_duplicate > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{_MUTED};">score.db 중복 제외: {log_stats.skipped_duplicate:,}개'
                f" &nbsp;- 정상 동작 (현재 최고 기록과 동일한 항목)</span>"
            )
        if log_stats.skipped_hash > 0:
            self._log(
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f'<span style="color:#E6C880;font-weight:bold;">⚠ 해시 오류: {log_stats.skipped_hash:,}개</span>'
                f' <span style="color:#E6C880;">&nbsp;- 주의: 해시 없음 또는 길이 불일치</span>'
            )
        player_stats = [{"client_type": "beatoraja", **player_data}] if player_data else []
        return scores + courses + raw_log, player_stats

    _SUPPLEMENT_BATCH = 5000  # Keep well below asyncpg's 32767-param limit

    def _run_hash_supplement(self, songdata_db_path: str) -> list[dict[str, Any]]:
        """Parse songdata.db, send hash supplements to the server, and return parsed items for reuse."""
        self.progress.emit(0, 0, "songdata.db 처리 중...")
        self._log("[INFO] Beatoraja songdata.db 처리 중...")
        from ojikbms_client.parsers.beatoraja import parse_beatoraja_songdata
        items = parse_beatoraja_songdata(songdata_db_path)
        if not items:
            self._log(f'[INFO] <span style="color:{_MUTED};">songdata.db: 유효한 항목 없음 (건너뜀)</span>')
            return []

        all_pairs = [{"md5": it["md5"], "sha256": it["sha256"]} for it in items]
        total = len(all_pairs)
        batches = [all_pairs[i:i + self._SUPPLEMENT_BATCH] for i in range(0, total, self._SUPPLEMENT_BATCH)]
        self._log(
            f"[INFO] songdata.db: {total:,}개 항목 처리 완료. "
            f"서버에 전송 중..."
        )

        from ojikbms_client.config import get_api_url
        api_url = get_api_url()

        total_supplemented = 0
        total_courses_updated = 0
        for idx, batch in enumerate(batches, 1):
            self.progress.emit(idx, len(batches), f"해시 보강 중... ({idx}/{len(batches)})")
            payload = {"client_type": "beatoraja", "items": batch}
            result = asyncio.run(self._post_supplement(api_url, payload))
            total_supplemented += result.get("supplemented", 0)
            total_courses_updated += result.get("courses_updated", 0)

        self._log(
            f'[INFO] <span style="color:{_GREEN};font-weight:bold;">'
            f"songdata.db 서버에 전송 완료</span>"
        )
        return items

    def _run_fumen_detail_sync(
        self,
        songdata_items: list[dict[str, Any]],
    ) -> None:
        """Build fumen detail items from local DBs and sync to server.

        Pre-fetches known hashes from server to minimize transfer volume:
        - complete hashes: skip entirely (all detail fields already filled)
        - partial hashes: send Beatoraja items only (to fill NULL fields)
        - unknown hashes: send all (new INSERT)
        """
        include_bea = self._client_filter in (ClientFilter.ALL, ClientFilter.BEA_ONLY)
        include_lr2 = self._client_filter in (ClientFilter.ALL, ClientFilter.LR2_ONLY)

        # ── Pre-fetch known hashes from server ──
        self.progress.emit(0, 0, "서버 기존 차분 해시 확인 중...")
        from ojikbms_client.sync import fetch_known_hashes
        known = asyncio.run(fetch_known_hashes())

        complete_sha256: set[str] = known["complete_sha256"]
        complete_md5: set[str] = known["complete_md5"]
        partial_md5: set[str] = known["partial_md5"]
        # "exists" = complete ∪ partial (for LR2 skip logic — md5 only, LR2 has no sha256)
        exists_md5 = complete_md5 | partial_md5

        all_items: list[dict[str, Any]] = []
        skipped_complete = 0

        # ── Beatoraja: songdata + songinfo merge ──
        if include_bea and songdata_items:
            self.progress.emit(0, 0, "차분 상세 정보 준비 중 (Beatoraja)...")

            songinfo_map: dict[str, dict] = {}
            if self._beatoraja_songinfo_db_path and Path(self._beatoraja_songinfo_db_path).exists():
                from ojikbms_client.parsers.beatoraja import parse_beatoraja_songinfo
                songinfo_map = parse_beatoraja_songinfo(self._beatoraja_songinfo_db_path)

            for sd in songdata_items:
                sha256 = sd.get("sha256", "").lower()
                md5 = sd.get("md5", "").lower()
                if not sha256 and not md5:
                    continue

                if (sha256 and sha256 in complete_sha256) or (
                    not sha256 and md5 and md5 in complete_md5
                ):
                    skipped_complete += 1
                    continue

                _title = sd.get("title") or ""
                _subtitle = sd.get("subtitle") or ""
                _artist = sd.get("artist") or ""
                _subartist = sd.get("subartist") or ""
                item: dict[str, Any] = {
                    "sha256": sha256 or None,
                    "md5": md5 or None,
                    "title": (_title + " " + _subtitle).strip() or None,
                    "artist": (_artist + " " + _subartist).strip() or None,
                    "client_type": "beatoraja",
                }

                if sd.get("minbpm") is not None:
                    item["bpm_min"] = float(sd["minbpm"])
                if sd.get("maxbpm") is not None:
                    item["bpm_max"] = float(sd["maxbpm"])
                if sd.get("notes") is not None:
                    item["notes_total"] = int(sd["notes"])
                if sd.get("length") is not None:
                    item["length"] = int(sd["length"])

                si = songinfo_map.get(sha256, {})
                if si.get("mainbpm") is not None:
                    item["bpm_main"] = float(si["mainbpm"])
                if si.get("n") is not None:
                    item["notes_n"] = int(si["n"])
                if si.get("ln") is not None:
                    item["notes_ln"] = int(si["ln"])
                if si.get("s") is not None:
                    item["notes_s"] = int(si["s"])
                if si.get("ls") is not None:
                    item["notes_ls"] = int(si["ls"])
                if si.get("total") is not None:
                    item["total"] = int(si["total"])

                all_items.append(item)

            self._log(
                f'[INFO] <span style="color:{_PRIMARY};font-weight:bold;">'
                f"Beatoraja 차분 상세 정보: {len(all_items):,}개 항목 준비 완료</span>"
            )

        # ── LR2: song.db ──
        lr2_added = 0
        lr2_skipped = 0
        if include_lr2 and self._lr2_song_db_path and Path(self._lr2_song_db_path).exists():
            self.progress.emit(0, 0, "차분 상세 정보 준비 중 (LR2)...")
            from ojikbms_client.parsers.lr2 import parse_lr2_songdata
            lr2_items = parse_lr2_songdata(self._lr2_song_db_path)
            for sd in lr2_items:
                md5 = sd.get("md5", "").lower()
                if not md5:
                    continue

                if md5 in exists_md5:
                    lr2_skipped += 1
                    continue

                item = {
                    "md5": md5,
                    "title": sd.get("title"),
                    "artist": sd.get("artist"),
                    "client_type": "lr2",
                }
                if sd.get("bpm_min") is not None:
                    item["bpm_min"] = sd["bpm_min"]
                if sd.get("bpm_max") is not None:
                    item["bpm_max"] = sd["bpm_max"]
                all_items.append(item)
                lr2_added += 1

            self._log(
                f'[INFO] <span style="color:{_PRIMARY};font-weight:bold;">'
                f"LR2 차분 상세 정보: {lr2_added:,}개 항목 준비 완료</span>"
            )

        if not all_items:
            self._log(
                f'[INFO] <span style="color:{_MUTED};">'
                f"차분 상세 정보: 전송할 신규/보강 항목 없음</span>"
            )
            return

        # ── Deduplicate before sending ──
        # Items are sent in multiple batch requests; seen_hashes on the server
        # resets per request. Deduplicate here so each fumen appears only once.
        # Beatoraja items come first and take priority (richer detail fields).
        _seen_sha256: set[str] = set()
        _seen_md5: set[str] = set()
        deduped_items: list[dict[str, Any]] = []
        for _item in all_items:
            _s = (_item.get("sha256") or "").lower()
            _m = (_item.get("md5") or "").lower()
            if (_s and _s in _seen_sha256) or (_m and _m in _seen_md5):
                continue
            deduped_items.append(_item)
            if _s:
                _seen_sha256.add(_s)
            if _m:
                _seen_md5.add(_m)
        all_items = deduped_items

        # ── Send to server ──
        self.progress.emit(0, 0, "차분 상세 정보 서버 전송 중...")
        from ojikbms_client.sync import sync_fumen_details

        def _progress(current: int, total: int) -> None:
            self.progress.emit(current, total, f"차분 상세 정보 전송 중... ({current}/{total})")

        result = asyncio.run(sync_fumen_details(all_items, progress_callback=_progress))

        self._log(
            f'[INFO] <span style="color:{_GREEN};font-weight:bold;">'
            f"차분 상세 정보 동기화 완료</span>"
            f' <span style="color:{_MUTED};">- 신규 {result["inserted"]:,}개, '
            f'보강 {result["updated"]:,}개, 이미 존재한 데이터 {result["skipped"]:,}개</span>'
        )

    @staticmethod
    async def _post_supplement(api_url: str, payload: dict) -> dict:
        import httpx

        from ojikbms_client.auth import make_authenticated_request
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await make_authenticated_request(
                client, "POST", f"{api_url}/fumens/supplement",
                api_url=api_url, json=payload,
            )
            if response.status_code == 200:
                return response.json()
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            all_scores: list[dict[str, Any]] = []
            all_player_stats: list[dict[str, Any]] = []

            include_lr2 = self._client_filter in (ClientFilter.ALL, ClientFilter.LR2_ONLY)
            include_bea = self._client_filter in (ClientFilter.ALL, ClientFilter.BEA_ONLY)

            # --- Recognition checks ---
            lr2_ok = include_lr2 and self._log_db_recognition(
                "LR2 기록 DB", self._lr2_db_path, required_for_quick=True, required_for_full=True
            )
            bea_ok = include_bea and self._log_db_recognition(
                "Beatoraja 기록 DB 폴더", self._beatoraja_db_dir, required_for_quick=True, required_for_full=True
            )
            bea_songdata_ok = (
                include_bea and
                self._mode == SyncMode.FULL and
                self._log_db_recognition(
                    "Beatoraja songdata.db", self._beatoraja_songdata_db_path, required_for_full=True
                )
            )

            if include_bea and bea_ok:
                self._check_beatoraja_completeness()

            self._log_recognition_summary(lr2_ok, bea_ok, bea_songdata_ok)

            # --- Full sync: hash supplementation + fumen detail sync ---
            songdata_items: list[dict] = []
            if self._mode == SyncMode.FULL and bea_songdata_ok and self._beatoraja_songdata_db_path:
                try:
                    songdata_items = self._run_hash_supplement(self._beatoraja_songdata_db_path)
                except Exception as e:
                    self._log(f"[WARN] 해시 보강 오류: {e}")

            if self._mode == SyncMode.FULL:
                try:
                    self._run_fumen_detail_sync(songdata_items)
                except Exception as e:
                    self._log(f"[WARN] 차분 상세 정보 동기화 오류: {e}")

            if self._cancelled:
                raise _SyncCancelledError()

            # --- Parse score DBs ---
            with ThreadPoolExecutor(max_workers=2) as _pool:
                lr2_fut = _pool.submit(self._parse_lr2) if lr2_ok else None
                bea_fut = _pool.submit(self._parse_beatoraja) if bea_ok else None

                if lr2_fut:
                    try:
                        scores, pstats = lr2_fut.result()
                        all_scores.extend(scores)
                        all_player_stats.extend(pstats)
                    except Exception as e:
                        self._log(f"[ERROR] LR2 파싱 오류: {e}")

                if bea_fut:
                    try:
                        scores, pstats = bea_fut.result()
                        all_scores.extend(scores)
                        all_player_stats.extend(pstats)
                    except Exception as e:
                        self._log(f"[ERROR] Beatoraja 파싱 오류: {e}")

            if self._cancelled:
                raise _SyncCancelledError()

            # --- Sync scores ---
            if all_scores or all_player_stats:
                self._log("[INFO] 서버에 동기화 중...")
                self.progress.emit(0, 0, "서버 동기화 준비 중...")
                from ojikbms_client.sync import sync_scores

                def _sync_progress(current: int, total: int) -> None:
                    self.progress.emit(current, total, "서버에 업로드 중...")

                result = asyncio.run(sync_scores(all_scores, all_player_stats, progress_callback=_sync_progress))
                inserted_records = result["inserted_scores"]

                from ojikbms_client.sync import fetch_today_improvement_count
                improvement_count = asyncio.run(fetch_today_improvement_count())

                if improvement_count is not None:
                    self._log(
                        f'[INFO] <span style="color:{_GREEN};font-weight:bold;">동기화 완료</span>'
                        f' <span style="color:#888;">- 신규 기록 {inserted_records:,}건</span>'
                        f' <span style="color:{_GREEN};font-weight:bold;">- 기록 갱신 {improvement_count:,}건</span>'
                    )
                else:
                    self._log(
                        f'[INFO] <span style="color:{_GREEN};font-weight:bold;">동기화 완료</span>'
                        f' <span style="color:#888;">- 신규 기록 {inserted_records:,}건</span>'
                    )

                if result.get("errors"):
                    for err in result["errors"][:5]:
                        self._log(f"[WARN] {err}")
            else:
                self._log("[WARN] 동기화할 데이터가 없습니다.")
                result = {"synced_scores": 0, "errors": []}

            if self._cancelled:
                raise _SyncCancelledError()

            self.finished.emit(result)

        except _SyncCancelledError:
            self._log("[INFO] 동기화가 취소되었습니다.")
            self.cancelled.emit()
        except Exception as e:
            import traceback
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
