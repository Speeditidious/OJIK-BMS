"""OJIK BMS Client — PyQt6 main window."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEvent, QObject, QSize, Qt
from PyQt6.QtGui import (
    QDesktopServices,
    QFont,
    QIcon,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ojikbms_client.auth import clear_tokens, is_logged_in
from ojikbms_client.config import (
    get_api_url,
    is_local_url,
    load_config,
    set_api_url,
    set_beatoraja_db_dir,
    set_beatoraja_songdata_db_path,
    set_beatoraja_songinfo_db_path,
    set_lr2_db_path,
    set_lr2_song_db_path,
)
from ojikbms_client.gui.workers import ClientFilter, LoginWorker, SyncMode, SyncWorker

_ASSETS = Path(__file__).parent / "assets"

# ---------------------------------------------------------------------------
# Colour palette (dark, matches web app)
# ---------------------------------------------------------------------------
_BG = "#12151C"
_SURFACE = "#1E2330"
_SURFACE2 = "#252A38"   # slightly lighter surface for inner section areas
_PRIMARY = "#C8E6A0"
_ACCENT = "#C8A0E6"
_TEXT = "#E8EAF0"
_MUTED = "#8B8FA8"
_RED = "#E68080"
_GREEN = "#80E6A0"
_BORDER = "#2E3348"

_STYLESHEET = f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: "Segoe UI", "Malgun Gothic", "Noto Sans KR", "NanumGothic", sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
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
QFrame#section {{
    background-color: {_SURFACE2};
    border: 1px solid {_BORDER};
    border-radius: 4px;
}}
QLineEdit {{
    background-color: {_BG};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {_TEXT};
}}
QLineEdit:focus {{
    border-color: {_PRIMARY};
}}
QPushButton {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
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
QPushButton#client-quick {{
    background-color: #202E1A;
    border-color: {_PRIMARY};
    color: {_PRIMARY};
    padding: 5px 14px;
    font-size: 12px;
}}
QPushButton#client-quick:hover {{
    background-color: #2A3C22;
}}
QPushButton#client-quick:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QPushButton#client-full {{
    background-color: #22192E;
    border-color: {_ACCENT};
    color: {_ACCENT};
    padding: 5px 14px;
    font-size: 12px;
}}
QPushButton#client-full:hover {{
    background-color: #2E2040;
}}
QPushButton#client-full:disabled {{
    color: #3E4258;
    border-color: #1E2230;
    background-color: #14161E;
}}
QTextEdit {{
    background-color: {_BG};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    font-family: "Consolas", "D2Coding", monospace;
    font-size: 12px;
    color: {_TEXT};
}}
QProgressBar {{
    background-color: {_BG};
    border: 1px solid {_BORDER};
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
    border: 1px solid {_BORDER};
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
    background-color: {_BORDER};
    height: 2px;
}}
QSplitter::handle:hover {{
    background-color: {_PRIMARY};
}}
"""

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _make_label(text: str, bold: bool = False, color: str = _MUTED, size: int = 12) -> QLabel:
    lbl = QLabel(text)
    style = f"color: {color}; font-size: {size}px; background: transparent;"
    if bold:
        style += " font-weight: bold;"
    lbl.setStyleSheet(style)
    return lbl


def _make_field_header(title: str, hint: str = "", accent: str = _PRIMARY) -> QWidget:
    """Field label with a left accent bar and an optional muted hint badge."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 4, 0, 2)
    row.setSpacing(8)

    bar = QFrame()
    bar.setFixedWidth(3)
    bar.setMinimumHeight(16)
    bar.setStyleSheet(f"background-color: {accent}; border-radius: 1px; border: none;")
    row.addWidget(bar)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f"color: {_TEXT}; font-size: 13px; font-weight: bold; background: transparent;"
    )
    row.addWidget(title_lbl)

    if hint:
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(
            f"color: {_MUTED}; font-size: 11px; background: transparent;"
        )
        row.addWidget(hint_lbl)

    row.addStretch()
    return w


def _make_path_row(
    edit: QLineEdit,
    browse_btn: QPushButton,
) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    row.addWidget(edit)
    row.addWidget(browse_btn)
    return row


class _CollapsibleSection(QWidget):
    """A widget with a toggle header that shows/hides its content area."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header toggle button
        self._toggle = QToolButton()
        self._toggle.setCheckable(False)
        self._toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toggle.setStyleSheet(
            f"QToolButton {{ color: {_PRIMARY}; background: {_SURFACE}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 6px 10px; font-weight: bold; text-align: left; }}"
            f"QToolButton:hover {{ background: #2A3040; border-color: {_PRIMARY}; }}"
        )
        self._set_title(title)
        self._toggle.clicked.connect(self._on_toggle)
        outer.addWidget(self._toggle)

        # Content frame
        self._content = QFrame()
        self._content.setObjectName("section")
        self._content.setVisible(False)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 8, 10, 8)
        self._content_layout.setSpacing(8)
        outer.addWidget(self._content)

    def _set_title(self, title: str) -> None:
        arrow = "▼" if self._expanded else "▶"
        self._toggle.setText(f"{arrow}  {title}")

    def _on_toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        arrow = "▼" if self._expanded else "▶"
        text = self._toggle.text()
        # Replace leading arrow
        self._toggle.setText(f"{arrow}  {text[3:]}")
        self.updateGeometry()

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def add_widget(self, w: QWidget) -> None:
        self._content_layout.addWidget(w)

    def add_layout(self, lay: Any) -> None:
        self._content_layout.addLayout(lay)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    """OJIK BMS Client main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OJIK BMS Client")
        self.setWindowIcon(QIcon(str(_ASSETS / "ojikbms_logo.png")))
        self.setMinimumSize(620, 420)
        self.resize(660, 720)
        self.setStyleSheet(_STYLESHEET)

        self._worker: SyncWorker | None = None
        self._login_worker: LoginWorker | None = None

        self._build_ui()
        self._load_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(16, 16, 16, 16)

        # Single scrollable area containing all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._make_header())
        content_layout.addWidget(self._make_auth_section())
        content_layout.addWidget(self._make_settings_section())
        content_layout.addWidget(self._make_sync_section())

        log_widget = self._make_progress_section()
        log_widget.setMinimumHeight(280)
        log_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_layout.addWidget(log_widget)  # no stretch — height fixed by minimum

        scroll.setWidget(content_widget)
        root.addWidget(scroll, 1)

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
        layout.setSpacing(6)

        # --- LR2 collapsible section ---
        self._lr2_section = _CollapsibleSection("LR2 설정")
        lr2_layout = self._lr2_section.content_layout()

        lr2_layout.addWidget(_make_field_header("기록 DB", "(<username>.db)", _PRIMARY))
        self._lr2_edit = self._make_path_edit("<username>.db 경로...")
        self._lr2_edit.installEventFilter(self)
        lr2_browse = self._make_browse_btn()
        lr2_browse.clicked.connect(self._browse_lr2)
        lr2_layout.addLayout(_make_path_row(self._lr2_edit, lr2_browse))

        lr2_layout.addWidget(_make_field_header("차분 DB", "(song.db)", _ACCENT))
        self._lr2_song_edit = self._make_path_edit("song.db 경로...")
        self._lr2_song_edit.installEventFilter(self)
        lr2_song_browse = self._make_browse_btn()
        lr2_song_browse.clicked.connect(self._browse_lr2_song)
        lr2_layout.addLayout(_make_path_row(self._lr2_song_edit, lr2_song_browse))

        # LR2-only sync buttons
        lr2_btn_row = QHBoxLayout()
        self._lr2_quick_btn = QPushButton("LR2만 빠른 동기화")
        self._lr2_quick_btn.setObjectName("client-quick")
        self._lr2_quick_btn.clicked.connect(self._on_lr2_quick_sync)
        self._lr2_full_btn = QPushButton("LR2만 전체 동기화")
        self._lr2_full_btn.setObjectName("client-full")
        self._lr2_full_btn.clicked.connect(self._on_lr2_full_sync)
        lr2_btn_row.addWidget(self._lr2_quick_btn)
        lr2_btn_row.addWidget(self._lr2_full_btn)
        lr2_btn_row.addStretch()
        lr2_layout.addLayout(lr2_btn_row)

        layout.addWidget(self._lr2_section)

        # --- Beatoraja collapsible section ---
        self._bea_section = _CollapsibleSection("Beatoraja 설정")
        bea_layout = self._bea_section.content_layout()

        bea_layout.addWidget(_make_field_header("기록 DB 폴더", "(score.db, scorelog.db 있는 폴더)", _PRIMARY))
        self._bea_edit = self._make_path_edit("player/player1/ 폴더...")
        self._bea_edit.installEventFilter(self)
        bea_browse = self._make_browse_btn()
        bea_browse.clicked.connect(self._browse_beatoraja)
        bea_layout.addLayout(_make_path_row(self._bea_edit, bea_browse))

        bea_layout.addWidget(_make_field_header("차분 DB", "(songdata.db)", _ACCENT))
        self._bea_songdata_edit = self._make_path_edit("songdata.db 경로...")
        self._bea_songdata_edit.installEventFilter(self)
        bea_songdata_browse = self._make_browse_btn()
        bea_songdata_browse.clicked.connect(self._browse_bea_songdata)
        bea_layout.addLayout(_make_path_row(self._bea_songdata_edit, bea_songdata_browse))

        bea_layout.addWidget(_make_field_header("차분 정보 DB", "(songinfo.db)", _ACCENT))
        self._bea_songinfo_edit = self._make_path_edit("songinfo.db 경로...")
        self._bea_songinfo_edit.installEventFilter(self)
        bea_songinfo_browse = self._make_browse_btn()
        bea_songinfo_browse.clicked.connect(self._browse_bea_songinfo)
        bea_layout.addLayout(_make_path_row(self._bea_songinfo_edit, bea_songinfo_browse))

        # Beatoraja-only sync buttons
        bea_btn_row = QHBoxLayout()
        self._bea_quick_btn = QPushButton("Beatoraja만 빠른 동기화")
        self._bea_quick_btn.setObjectName("client-quick")
        self._bea_quick_btn.clicked.connect(self._on_bea_quick_sync)
        self._bea_full_btn = QPushButton("Beatoraja만 전체 동기화")
        self._bea_full_btn.setObjectName("client-full")
        self._bea_full_btn.clicked.connect(self._on_bea_full_sync)
        bea_btn_row.addWidget(self._bea_quick_btn)
        bea_btn_row.addWidget(self._bea_full_btn)
        bea_btn_row.addStretch()
        bea_layout.addLayout(bea_btn_row)

        layout.addWidget(self._bea_section)

        # --- Advanced (collapsible) ---
        self._adv_section = _CollapsibleSection("고급 설정")
        adv_layout = self._adv_section.content_layout()
        adv_row = QHBoxLayout()
        adv_row.addWidget(_make_label("API URL", bold=True, color=_TEXT, size=13))
        self._api_url_edit = QLineEdit()
        self._api_url_edit.setPlaceholderText("https://api.ojikbms.kr")
        self._api_url_edit.editingFinished.connect(self._save_api_url)
        adv_row.addWidget(self._api_url_edit)
        adv_layout.addLayout(adv_row)
        layout.addWidget(self._adv_section)

        return box

    def _make_sync_section(self) -> QGroupBox:
        box = QGroupBox("동기화")
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        self._last_sync_label = _make_label("마지막 동기화: 없음", size=12)
        layout.addWidget(self._last_sync_label)

        btn_row = QHBoxLayout()
        self._sync_quick_btn = QPushButton("빠른 동기화  (플레이 기록 DB)")
        self._sync_quick_btn.setObjectName("primary")
        self._sync_quick_btn.clicked.connect(self._on_quick_sync)
        btn_row.addWidget(self._sync_quick_btn)

        self._sync_full_btn = QPushButton("전체 동기화  (플레이 + 곡 DB)")
        self._sync_full_btn.setObjectName("accent")
        self._sync_full_btn.clicked.connect(self._on_full_sync)
        btn_row.addWidget(self._sync_full_btn)

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
        self._progress_label_name = _make_label("", size=12)
        label_row.addWidget(self._progress_label_name)
        self._progress_label_count = _make_label("", size=12)
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
    # Widget factories
    # ------------------------------------------------------------------

    @staticmethod
    def _make_path_edit(placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setReadOnly(True)
        edit.setAcceptDrops(True)
        return edit

    @staticmethod
    def _make_browse_btn() -> QPushButton:
        btn = QPushButton("찾아보기")
        btn.setFixedWidth(80)
        return btn

    # ------------------------------------------------------------------
    # State loading
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        config = load_config()

        self._lr2_edit.setText(config.get("lr2_db_path") or "")
        self._lr2_song_edit.setText(config.get("lr2_song_db_path") or "")
        self._bea_edit.setText(config.get("beatoraja_db_dir") or "")
        self._bea_songdata_edit.setText(config.get("beatoraja_songdata_db_path") or "")
        self._bea_songinfo_edit.setText(config.get("beatoraja_songinfo_db_path") or "")
        self._api_url_edit.setText(config.get("api_url", "https://api.ojikbms.kr"))

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
        api_url = self._api_url_edit.text().strip() or "https://api.ojikbms.kr"
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
    # Settings browse slots
    # ------------------------------------------------------------------

    def _browse_lr2(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "LR2 기록 DB 선택", "", "SQLite DB (*.db);;모든 파일 (*)"
        )
        if path:
            self._lr2_edit.setText(path)
            set_lr2_db_path(path)

    def _browse_lr2_song(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "LR2 song.db 선택", "", "SQLite DB (*.db);;모든 파일 (*)"
        )
        if path:
            self._lr2_song_edit.setText(path)
            set_lr2_song_db_path(path)

    def _browse_beatoraja(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Beatoraja player 폴더 선택")
        if path:
            self._bea_edit.setText(path)
            set_beatoraja_db_dir(path)

    def _browse_bea_songdata(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Beatoraja songdata.db 선택", "", "SQLite DB (*.db);;모든 파일 (*)"
        )
        if path:
            self._bea_songdata_edit.setText(path)
            set_beatoraja_songdata_db_path(path)

    def _browse_bea_songinfo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Beatoraja songinfo.db 선택", "", "SQLite DB (*.db);;모든 파일 (*)"
        )
        if path:
            self._bea_songinfo_edit.setText(path)
            set_beatoraja_songinfo_db_path(path)

    def _save_api_url(self) -> None:
        url = self._api_url_edit.text().strip()
        if not url:
            return
        # Auto-rewrite https://localhost → http://localhost
        if url.startswith("https://") and is_local_url(url):
            url = "http://" + url[len("https://"):]
            self._api_url_edit.setText(url)
        set_api_url(url)

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.DragEnter:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.Drop:
            urls = event.mimeData().urls()
            if not urls:
                return False
            path = urls[0].toLocalFile()
            if obj is self._lr2_edit and os.path.isfile(path):
                self._lr2_edit.setText(path)
                set_lr2_db_path(path)
                return True
            elif obj is self._lr2_song_edit and os.path.isfile(path):
                self._lr2_song_edit.setText(path)
                set_lr2_song_db_path(path)
                return True
            elif obj is self._bea_edit and os.path.isdir(path):
                self._bea_edit.setText(path)
                set_beatoraja_db_dir(path)
                return True
            elif obj is self._bea_songdata_edit and os.path.isfile(path):
                self._bea_songdata_edit.setText(path)
                set_beatoraja_songdata_db_path(path)
                return True
            elif obj is self._bea_songinfo_edit and os.path.isfile(path):
                self._bea_songinfo_edit.setText(path)
                set_beatoraja_songinfo_db_path(path)
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Sync slots
    # ------------------------------------------------------------------

    def _on_quick_sync(self) -> None:
        self._start_sync(SyncMode.QUICK, ClientFilter.ALL)

    def _on_full_sync(self) -> None:
        self._start_sync(SyncMode.FULL, ClientFilter.ALL)

    def _on_lr2_quick_sync(self) -> None:
        self._start_sync(SyncMode.QUICK, ClientFilter.LR2_ONLY)

    def _on_lr2_full_sync(self) -> None:
        self._start_sync(SyncMode.FULL, ClientFilter.LR2_ONLY)

    def _on_bea_quick_sync(self) -> None:
        self._start_sync(SyncMode.QUICK, ClientFilter.BEA_ONLY)

    def _on_bea_full_sync(self) -> None:
        self._start_sync(SyncMode.FULL, ClientFilter.BEA_ONLY)

    def _start_sync(self, mode: SyncMode, client_filter: ClientFilter) -> None:
        if self._worker and self._worker.isRunning():
            return

        if not is_logged_in():
            QMessageBox.warning(self, "로그인 필요", "동기화하려면 먼저 Discord 로그인이 필요합니다.")
            return

        config = load_config()
        self._set_syncing(True)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._progress_label_container.setVisible(True)
        self._append_log("[INFO] 동기화 시작...")

        self._worker = SyncWorker(
            lr2_db_path=config.get("lr2_db_path") or None,
            beatoraja_db_dir=config.get("beatoraja_db_dir") or None,
            beatoraja_songdata_db_path=config.get("beatoraja_songdata_db_path") or None,
            beatoraja_songinfo_db_path=config.get("beatoraja_songinfo_db_path") or None,
            lr2_song_db_path=config.get("lr2_song_db_path") or None,
            mode=mode,
            client_filter=client_filter,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_sync_finished)
        self._worker.error.connect(self._on_sync_error)
        self._worker.cancelled.connect(self._on_sync_cancelled)
        self._worker.start()

    def _on_progress(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            self._progress_bar.setMaximum(0)
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
        self._progress_bar.setMaximum(100)
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
        self._sync_quick_btn.setEnabled(not syncing)
        self._sync_full_btn.setEnabled(not syncing)
        self._lr2_quick_btn.setEnabled(not syncing)
        self._lr2_full_btn.setEnabled(not syncing)
        self._bea_quick_btn.setEnabled(not syncing)
        self._bea_full_btn.setEnabled(not syncing)
        self._cancel_sync_btn.setVisible(syncing)
        self._cancel_sync_btn.setEnabled(True)
        self._cancel_sync_btn.setText("동기화 취소")
        self._auth_box.setEnabled(not syncing)
        self._settings_box.setEnabled(not syncing)

    # ------------------------------------------------------------------
    # Log helper
    # ------------------------------------------------------------------

    def _append_log(self, message: str) -> None:
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

        # Use QTextCursor directly to prevent character format (bold, font-size)
        # from leaking across paragraph boundaries via QTextEdit.append().
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self._log_edit.document().characterCount() > 1:
            cursor.insertBlock()
        cursor.setCharFormat(QTextCharFormat())  # reset to default before inserting
        cursor.insertHtml(line)
        self._log_edit.setTextCursor(cursor)

        sb = self._log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())
