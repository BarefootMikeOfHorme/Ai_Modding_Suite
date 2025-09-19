"""
Path and dialog utilities using Qt's standard locations.
"""
from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QStandardPaths


APP_NAME = "AI_Modding_Suite"
ORG_NAME = "BarefootMikeOfHorme"  # used for QSettings in the app


def default_workspace_root() -> Path:
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    base = Path(docs) / APP_NAME
    return base


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


# Common file dialog filters
CFG_FILTER = "Config Files (*.cfg);;All Files (*)"
