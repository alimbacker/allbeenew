"""ALLBEE Instant Uploader.

    pip install -r requirements.txt
    python main.py

Watches a folder (a tethered-capture target or a camera card) and uploads new
photos to an ALLBEE event as they appear.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python main.py` from this directory without installing a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ALLBEE Instant Uploader")
    app.setOrganizationName("ALLBEE")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
