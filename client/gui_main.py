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


def main() -> None:
    # Suppress "Could not load wayland plugin" warning in environments
    # without a Wayland compositor (e.g. WSL2). Only set if not already
    # overridden by the user.
    if "QT_QPA_PLATFORM" not in os.environ:
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
