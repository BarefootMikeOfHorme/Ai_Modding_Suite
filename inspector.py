from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel

import json
try:
    import yaml  # type: ignore
except Exception:
    yaml = None


class InspectorWidget(QWidget):
    """
    Read-only inspector for selected files.
    Shows basic file info and, when present, AMS Enhanced Metadata from sidecars.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._label = QLabel("Inspector")
        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        lay = QVBoxLayout()
        lay.addWidget(self._label)
        lay.addWidget(self._text)
        lay.setContentsMargins(4, 4, 4, 4)
        self.setLayout(lay)

    def update_path(self, path: Optional[Path]) -> None:
        if path is None:
            self._label.setText("Inspector")
            self._text.clear()
            return
        p = Path(path)
        self._label.setText(f"Inspector: {p.name}")
        if p.is_dir():
            self._text.setPlainText(f"Directory:\n{p}\n\nContains: {len(list(p.glob('*')))} entries")
            return
        # file
        try:
            size = p.stat().st_size
        except Exception:
            size = 0
        info = [
            f"Path: {p}",
            f"Size: {size} bytes",
            f"Extension: {p.suffix.lower()}",
        ]
        # Find manifest sidecars
        targets = []
        if p.name.endswith('.ams.json') or p.name.endswith('.ams.yaml'):
            targets.append(p)
        else:
            j = Path(str(p) + ".ams.json")
            y = Path(str(p) + ".ams.yaml")
            if j.exists():
                targets.append(j)
            if y.exists():
                targets.append(y)
        if targets:
            target = next((t for t in targets if t.suffix.lower() == '.json'), targets[0])
            try:
                text = target.read_text(encoding='utf-8')
                if target.suffix.lower() == '.json':
                    obj = json.loads(text)
                    # Summarize key fields if present
                    ams_id = obj.get('ams_id')
                    created_on = obj.get('created_on')
                    tool_version = obj.get('tool_version')
                    scale = obj.get('scale') or {}
                    geometry = obj.get('geometry') or {}
                    summary = [
                        "AMS Manifest:",
                        f"  ams_id: {ams_id}",
                        f"  created_on: {created_on}",
                        f"  tool_version: {tool_version}",
                        f"  scale: {scale}",
                        f"  geometry: {geometry}",
                    ]
                    info.append("\n".join(summary))
                else:
                    if yaml:
                        obj = yaml.safe_load(text)  # type: ignore
                        info.append("AMS Manifest (YAML) present")
                    else:
                        info.append("AMS Manifest (YAML) present — PyYAML not available")
            except Exception as e:
                info.append(f"Manifest read error: {e}")
        self._text.setPlainText("\n".join(info))
