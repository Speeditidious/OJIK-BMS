"""OJIK BMS Client GUI entry point.

Run directly:
    python gui_main.py

PyInstaller build:
    pyinstaller --onefile --windowed --name ojikbms-gui gui_main.py
"""
import os
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ojikbms_client.gui.main_window import MainWindow

_ASSETS = Path(__file__).parent / "ojikbms_client" / "gui" / "assets"


def _setup_qt_plugins() -> None:
    """Set Qt platform plugin path when running as a PyInstaller --onefile bundle.

    In --onefile mode, PyInstaller extracts all files to a temporary directory
    (sys._MEIPASS) at runtime. Qt's plugin loader uses the exe location as its
    base path, not the temp directory, so it cannot find qwindows.dll without
    this explicit override.
    """
    if not getattr(sys, "frozen", False):
        return
    meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # Try the most common PyInstaller + PyQt6 plugin layout.
    candidates = [
        meipass / "PyQt6" / "Qt6" / "plugins" / "platforms",
        meipass / "PyQt6" / "Qt6" / "plugins",
        meipass / "platforms",
    ]
    for path in candidates:
        if path.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(path)
            break


def main() -> None:
    _setup_qt_plugins()

    # Suppress "Could not load wayland plugin" warning on Linux environments
    # without a Wayland compositor (e.g. WSL2). xcb is Linux-only — never set
    # this on Windows or macOS or it will break the platform plugin lookup.
    if sys.platform == "linux" and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QApplication(sys.argv)
    app.setApplicationName("OJIK BMS Client")
    app.setOrganizationName("OJIK")
    app.setWindowIcon(QIcon(str(_ASSETS / "ojikbms_logo.png")))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
