from __future__ import annotations

import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from modding_suite import ModdingSuite


def main() -> int:
    # High DPI and scaling hints for modern displays
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    win = ModdingSuite()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
