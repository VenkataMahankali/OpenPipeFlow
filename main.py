"""
OpenPipeFlow — Entry point.
Run with:  python main.py
Build EXE: python build/build_exe.py
"""

import sys
import os

# Make sure the package root is on sys.path when running as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from app.main_window import MainWindow


def main():
    # Enable HiDPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("OpenPipeFlow")
    app.setApplicationDisplayName("OpenPipeFlow")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("OpenPipeFlow Project")

    window = MainWindow()
    window.show()

    # If a .opf file was passed as a command-line argument, open it
    if len(sys.argv) > 1 and sys.argv[1].endswith(".opf"):
        window._load_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
