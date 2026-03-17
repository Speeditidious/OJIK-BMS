"""OJIK BMS Client — PyQt6 main window."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QDesktopServices, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ojikbms_client.auth import clear_tokens, is_logged_in
from ojikbms_client.config import (
    load_config,
    save_config,
    set_api_url,
    set_beatoraja_db_dir,
    set_lr2_db_path,
)
from ojikbms_client.gui.workers import LoginWorker, SyncWorker

_ASSETS = Path(__file__).parent / "assets"

# ---------------------------------------------------------------------------
# Colour palette (dark, matches web app)
# ---------------------------------------------------------------------------
_BG = "#12151C"
_SURFACE = "#1E2330"
_PRIMARY = "#C8E6A0"
_ACCENT = "#C8A0E6"
_TEXT = "#E8EAF0"
_MUTED = "#8B8FA8"
_RED = "#E68080"
_GREEN = "#80E6A0"

_STYLESHEET = f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: "Segoe UI", "Malgun Gothic", "Noto Sans KR", "NanumGothic", sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    background-color: {_SURFACE};
    border: 1px solid #2E3348;
    border-radius: 6px;
    margin-top: 8px;
    padding: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: {_PRIMARY};
    font-weight: bold;
}}
QLineEdit {{
    background-color: {_BG};
    border: 1px solid #2E3348;
    border-radius: 4px;
    padding: 4px 8px;
    color: {_TEXT};
}}
QLineEdit:focus {{
    border-color: {_PRIMARY};
}}
QPushButton {{
    background-color: {_SURFACE};
    border: 1px solid #2E3348;
    border-radius: 4px;
    padding: 6px 14px;
    color: {_TEXT};
}}
QPushButton:hover {{
    background-color: #2A3040;
    border-color: {_PRIMARY};
}}
QPushButton:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QPushButton#primary {{
    background-color: #2A3820;
    border-color: {_PRIMARY};
    color: {_PRIMARY};
    font-weight: bold;
}}
QPushButton#primary:hover {{
    background-color: #344828;
}}
QPushButton#primary:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QPushButton#accent {{
    background-color: #2A2038;
    border-color: {_ACCENT};
    color: {_ACCENT};
    font-weight: bold;
}}
QPushButton#accent:hover {{
    background-color: #342848;
}}
QPushButton#accent:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QPushButton#discord {{
    background-color: #3C4370;
    border-color: #5865F2;
    color: #FFFFFF;
    font-weight: bold;
    padding: 8px 18px;
}}
QPushButton#discord:hover {{
    background-color: #4752C4;
    border-color: #7289DA;
}}
QPushButton#discord:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QPushButton#danger {{
    border-color: {_RED};
    color: {_RED};
}}
QPushButton#danger:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QTextEdit {{
    background-color: {_BG};
    border: 1px solid #2E3348;
    border-radius: 4px;
    font-family: "Consolas", "D2Coding", monospace;
    font-size: 12px;
    color: {_TEXT};
}}
QProgressBar {{
    background-color: {_BG};
    border: 1px solid #2E3348;
    border-radius: 4px;
    text-align: center;
    color: {_TEXT};
}}
QProgressBar::chunk {{
    background-color: {_PRIMARY};
    border-radius: 3px;
}}
QListWidget {{
    background-color: {_BG};
    border: 1px solid #2E3348;
    border-radius: 4px;
}}
QListWidget::item {{
    padding: 2px 4px;
}}
QListWidget::item:selected {{
    background-color: {_SURFACE};
}}
QScrollArea {{
    border: none;
}}
QSplitter::handle {{
    background-color: #2E3348;
    height: 2px;
}}
QSplitter::handle:hover {{
    background-color: {_PRIMARY};
}}
"""


class MainWindow(QWidget):
    """OJIK BMS Client main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OJIK BMS Client")
        self.setWindowIcon(QIcon(str(_ASSETS / "ojikbms_logo.png")))
        self.setMinimumSize(600, 400)
        self.resize(640, 860)
        self.setStyleSheet(_STYLESHEET)

        self._worker: SyncWorker | None = None
        self._login_worker: LoginWorker | None = None
        self._advanced_visible = False

        self._build_ui()
        self._load_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(16, 16, 16, 16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self._make_header())
        top_layout.addWidget(self._make_auth_section())
        top_layout.addWidget(self._make_settings_section())
        top_layout.addWidget(self._make_sync_section())
        top_layout.addStretch()

        scroll.setWidget(top_widget)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(scroll)
        splitter.addWidget(self._make_progress_section())
        splitter.setStretchFactor(0, 0)  # top: fixed on resize
        splitter.setStretchFactor(1, 1)  # bottom: log expands on resize
        splitter.setSizes([640, 160])    # initial ratio: top 640px, log 160px

        root.addWidget(splitter, 1)

    def _make_header(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)

        logo_label = QLabel()
        logo_pixmap = QPixmap(str(_ASSETS / "ojikbms_logo.png")).scaled(
            32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        logo_label.setPixmap(logo_pixmap)
        row.addWidget(logo_label)

        title = QLabel("OJIK BMS Client")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_PRIMARY};")
        row.addWidget(title)
        row.addStretch()

        self._login_badge = QLabel("로그아웃 상태")
        self._login_badge.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        row.addWidget(self._login_badge)
        return w

    def _make_auth_section(self) -> QGroupBox:
        box = QGroupBox("Discord 로그인")
        self._auth_box = box
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(box)

        self._login_status_label = QLabel("로그인되지 않았습니다.")
        self._login_status_label.setStyleSheet(f"color: {_MUTED};")
        row.addWidget(self._login_status_label)
        row.addStretch()

        self._login_btn = QPushButton("  Discord 로그인")
        self._login_btn.setObjectName("discord")
        self._login_btn.setIcon(QIcon(str(_ASSETS / "discord_icon.png")))
        self._login_btn.setIconSize(QSize(22, 22))
        self._login_btn.clicked.connect(self._on_login)
        row.addWidget(self._login_btn)

        self._logout_btn = QPushButton("로그아웃")
        self._logout_btn.setObjectName("danger")
        self._logout_btn.clicked.connect(self._on_logout)
        row.addWidget(self._logout_btn)

        return box

    def _make_settings_section(self) -> QGroupBox:
        box = QGroupBox("설정")
        self._settings_box = box
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        # LR2 score.db
        layout.addWidget(QLabel("LR2 기록 데이터베이스 (<username>.db)"))
        lr2_row = QHBoxLayout()
        self._lr2_edit = QLineEdit()
        self._lr2_edit.setPlaceholderText("LR2 <username>.db 경로...")
        self._lr2_edit.setReadOnly(True)
        lr2_row.addWidget(self._lr2_edit)
        lr2_browse = QPushButton("찾아보기")
        lr2_browse.clicked.connect(self._browse_lr2)
        lr2_row.addWidget(lr2_browse)
        layout.addLayout(lr2_row)

        # Beatoraja dir
        layout.addWidget(QLabel("Beatoraja 기록 데이터베이스 폴더 (player/player1/)"))
        bea_row = QHBoxLayout()
        self._bea_edit = QLineEdit()
        self._bea_edit.setPlaceholderText("Beatoraja score.db, scorelog.db 있는 폴더 경로...")
        self._bea_edit.setReadOnly(True)
        bea_row.addWidget(self._bea_edit)
        bea_browse = QPushButton("찾아보기")
        bea_browse.clicked.connect(self._browse_beatoraja)
        bea_row.addWidget(bea_browse)
        layout.addLayout(bea_row)

        # BMS folders
        layout.addWidget(QLabel("BMS 곡, 차분 파일 폴더 (최상위 폴더 하나만 해도 ok)"))
        self._folder_list = QListWidget()
        self._folder_list.setFixedHeight(80)
        layout.addWidget(self._folder_list)

        folder_btns = QHBoxLayout()
        add_folder_btn = QPushButton("+ 폴더 추가")
        add_folder_btn.clicked.connect(self._add_bms_folder)
        folder_btns.addWidget(add_folder_btn)
        remove_folder_btn = QPushButton("선택 제거")
        remove_folder_btn.setObjectName("danger")
        remove_folder_btn.clicked.connect(self._remove_bms_folder)
        folder_btns.addWidget(remove_folder_btn)
        folder_btns.addStretch()
        layout.addLayout(folder_btns)

        # Advanced (collapsible)
        self._adv_toggle = QToolButton()
        self._adv_toggle.setText("▶ 고급 설정")
        self._adv_toggle.setStyleSheet(f"color: {_MUTED}; background: transparent; border: none;")
        self._adv_toggle.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._adv_toggle)

        self._adv_widget = QWidget()
        adv_layout = QHBoxLayout(self._adv_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.addWidget(QLabel("API URL"))
        self._api_url_edit = QLineEdit()
        self._api_url_edit.setPlaceholderText("http://localhost:8000")
        self._api_url_edit.editingFinished.connect(self._save_api_url)
        adv_layout.addWidget(self._api_url_edit)
        self._adv_widget.setVisible(False)
        layout.addWidget(self._adv_widget)

        return box

    def _make_sync_section(self) -> QGroupBox:
        box = QGroupBox("동기화")
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(box)

        self._last_sync_label = QLabel("마지막 동기화: 없음")
        self._last_sync_label.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        layout.addWidget(self._last_sync_label)

        btn_row = QHBoxLayout()
        self._full_sync_btn = QPushButton("전체 동기화 (BMS 스캔 포함)")
        self._full_sync_btn.setObjectName("primary")
        self._full_sync_btn.clicked.connect(self._on_full_sync)
        btn_row.addWidget(self._full_sync_btn)

        self._quick_sync_btn = QPushButton("빠른 동기화 (플레이 기록 DB만)")
        self._quick_sync_btn.setObjectName("accent")
        self._quick_sync_btn.clicked.connect(self._on_quick_sync)
        btn_row.addWidget(self._quick_sync_btn)

        self._cancel_sync_btn = QPushButton("동기화 취소")
        self._cancel_sync_btn.setObjectName("danger")
        self._cancel_sync_btn.clicked.connect(self._on_cancel_sync)
        self._cancel_sync_btn.setVisible(False)
        btn_row.addWidget(self._cancel_sync_btn)

        layout.addLayout(btn_row)
        return box

    def _make_progress_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label_container = QWidget()
        self._progress_label_container.setVisible(False)
        label_row = QHBoxLayout(self._progress_label_container)
        label_row.setContentsMargins(0, 0, 0, 0)
        self._progress_label_name = QLabel("")
        self._progress_label_name.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        label_row.addWidget(self._progress_label_name)
        self._progress_label_count = QLabel("")
        self._progress_label_count.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        self._progress_label_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_row.addWidget(self._progress_label_count)
        layout.addWidget(self._progress_label_container)

        self._log_edit = QTextBrowser()
        self._log_edit.setOpenLinks(False)
        self._log_edit.anchorClicked.connect(lambda url: QDesktopServices.openUrl(url))
        self._log_edit.setMinimumHeight(80)
        self._log_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._log_edit)

        return w

    # ------------------------------------------------------------------
    # State loading
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        config = load_config()

        lr2 = config.get("lr2_db_path") or ""
        self._lr2_edit.setText(lr2)

        bea = config.get("beatoraja_db_dir") or ""
        self._bea_edit.setText(bea)

        self._folder_list.clear()
        for folder in config.get("bms_folders", []):
            self._folder_list.addItem(QListWidgetItem(folder))

        self._api_url_edit.setText(config.get("api_url", "http://localhost:8000"))

        last = config.get("last_synced_at")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                self._last_sync_label.setText(f"마지막 동기화: {dt.strftime('%Y-%m-%d %H:%M')}")
            except ValueError:
                pass

        self._refresh_login_ui()

    def _refresh_login_ui(self) -> None:
        logged_in = is_logged_in()
        if logged_in:
            self._login_status_label.setText("로그인 중")
            self._login_status_label.setStyleSheet(f"color: {_GREEN};")
            self._login_badge.setText("● 로그인됨")
            self._login_badge.setStyleSheet(f"color: {_GREEN}; font-size: 12px;")
            self._login_btn.setVisible(False)
            self._logout_btn.setVisible(True)
        else:
            self._login_status_label.setText("로그인되지 않았습니다.")
            self._login_status_label.setStyleSheet(f"color: {_MUTED};")
            self._login_badge.setText("● 로그아웃")
            self._login_badge.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
            self._login_btn.setVisible(True)
            self._logout_btn.setVisible(False)

    # ------------------------------------------------------------------
    # Auth slots
    # ------------------------------------------------------------------

    def _on_login(self) -> None:
        api_url = self._api_url_edit.text().strip() or "http://localhost:8000"
        self._login_btn.setEnabled(False)
        self._append_log("[INFO] 브라우저에서 Discord 로그인 페이지를 엽니다...")

        self._login_worker = LoginWorker(api_url)
        self._login_worker.url_ready.connect(self._on_login_url_ready)
        self._login_worker.finished.connect(self._on_login_finished)
        self._login_worker.start()

    def _on_login_url_ready(self, url: str) -> None:
        self._append_log(
            f'[INFO] 브라우저가 열리지 않았다면 아래 링크를 직접 클릭하세요:<br>'
            f'&nbsp;&nbsp;<a href="{url}" style="color:{_ACCENT};">{url}</a>'
        )

    def _on_login_finished(self, success: bool, message: str) -> None:
        self._login_btn.setEnabled(True)
        if success:
            self._append_log(f"[INFO] {message}")
        else:
            self._append_log(f"[ERROR] {message}")
        self._refresh_login_ui()

    def _on_logout(self) -> None:
        clear_tokens()
        self._append_log("[INFO] 로그아웃되었습니다.")
        self._refresh_login_ui()

    # ------------------------------------------------------------------
    # Settings slots
    # ------------------------------------------------------------------

    def _browse_lr2(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "LR2 score.db 선택", "", "SQLite DB (*.db);;모든 파일 (*)"
        )
        if path:
            self._lr2_edit.setText(path)
            set_lr2_db_path(path)

    def _browse_beatoraja(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Beatoraja data 폴더 선택")
        if path:
            self._bea_edit.setText(path)
            set_beatoraja_db_dir(path)

    def _add_bms_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "BMS 폴더 추가")
        if path:
            config = load_config()
            folders = config.get("bms_folders", [])
            if path not in folders:
                folders.append(path)
                config["bms_folders"] = folders
                save_config(config)
                self._folder_list.addItem(QListWidgetItem(path))

    def _remove_bms_folder(self) -> None:
        selected = self._folder_list.selectedItems()
        if not selected:
            return
        config = load_config()
        folders = config.get("bms_folders", [])
        for item in selected:
            folder = item.text()
            if folder in folders:
                folders.remove(folder)
            self._folder_list.takeItem(self._folder_list.row(item))
        config["bms_folders"] = folders
        save_config(config)

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        self._adv_widget.setVisible(self._advanced_visible)
        arrow = "▼" if self._advanced_visible else "▶"
        self._adv_toggle.setText(f"{arrow} 고급 설정")

    def _save_api_url(self) -> None:
        url = self._api_url_edit.text().strip()
        if url:
            set_api_url(url)

    # ------------------------------------------------------------------
    # Sync slots
    # ------------------------------------------------------------------

    def _collect_sync_args(self) -> dict[str, Any]:
        config = load_config()
        return {
            "lr2_db_path": config.get("lr2_db_path") or None,
            "beatoraja_db_dir": config.get("beatoraja_db_dir") or None,
            "bms_folders": config.get("bms_folders", []),
        }

    def _on_full_sync(self) -> None:
        self._start_sync(quick=False)

    def _on_quick_sync(self) -> None:
        self._start_sync(quick=True)

    def _start_sync(self, *, quick: bool) -> None:
        if self._worker and self._worker.isRunning():
            return

        if not is_logged_in():
            QMessageBox.warning(self, "로그인 필요", "동기화하려면 먼저 Discord 로그인이 필요합니다.")
            return

        args = self._collect_sync_args()
        self._set_syncing(True)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._progress_label_container.setVisible(True)
        kind = "빠른" if quick else "전체"
        self._append_log(f"[INFO] {kind} 동기화 시작...")

        self._worker = SyncWorker(
            lr2_db_path=args["lr2_db_path"],
            beatoraja_db_dir=args["beatoraja_db_dir"],
            bms_folders=args["bms_folders"],
            quick=quick,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_sync_finished)
        self._worker.error.connect(self._on_sync_error)
        self._worker.cancelled.connect(self._on_sync_cancelled)
        self._worker.start()

    def _on_progress(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            self._progress_bar.setMaximum(0)  # indeterminate animation
            if label:
                self._progress_label_name.setText(label)
            self._progress_label_count.setText(f"{current:,}개 발견" if current > 0 else "")
        else:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)
            self._progress_label_name.setText(label)
            self._progress_label_count.setText(f"{current:,} / {total:,}")

    def _on_sync_finished(self, result: dict[str, Any]) -> None:
        self._set_syncing(False)
        self._progress_bar.setMaximum(100)  # reset from possible indeterminate
        self._progress_bar.setVisible(False)
        self._progress_label_container.setVisible(False)

        config = load_config()
        last = config.get("last_synced_at")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                self._last_sync_label.setText(f"마지막 동기화: {dt.strftime('%Y-%m-%d %H:%M')}")
            except ValueError:
                pass

    def _on_sync_error(self, message: str) -> None:
        self._set_syncing(False)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setVisible(False)
        self._progress_label_container.setVisible(False)
        self._append_log(f"[ERROR] 동기화 오류: {message}")
        QMessageBox.critical(self, "동기화 오류", message)

    def _on_cancel_sync(self) -> None:
        if self._worker and self._worker.isRunning():
            self._cancel_sync_btn.setEnabled(False)
            self._cancel_sync_btn.setText("취소 중...")
            self._worker.cancel()

    def _on_sync_cancelled(self) -> None:
        self._set_syncing(False)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setVisible(False)
        self._progress_label_container.setVisible(False)

    def _set_syncing(self, syncing: bool) -> None:
        self._full_sync_btn.setEnabled(not syncing)
        self._quick_sync_btn.setEnabled(not syncing)
        self._cancel_sync_btn.setVisible(syncing)
        self._cancel_sync_btn.setEnabled(True)
        self._cancel_sync_btn.setText("동기화 취소")
        self._auth_box.setEnabled(not syncing)
        self._settings_box.setEnabled(not syncing)


    # ------------------------------------------------------------------
    # Log helper
    # ------------------------------------------------------------------

    def _append_log(self, message: str) -> None:
        # Colorize log prefixes
        color_map = {
            "[INFO]": _PRIMARY,
            "[WARN]": "#E6C880",
            "[ERROR]": _RED,
        }
        line = message
        for prefix, color in color_map.items():
            if message.startswith(prefix):
                rest = message[len(prefix):]
                line = f'<span style="color:{color};font-weight:bold;">{prefix}</span>{rest}'
                break

        self._log_edit.append(line)
        # Auto-scroll to bottom
        sb = self._log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())
