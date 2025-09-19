from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget


class MapAreaEditor(QMainWindow):
    """
    Placeholder window for the Map/Area Editor.
    Future features: heightmap terrain, asset placement, blueprint overlays, GLB export.
    """
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Map / Area Editor (Placeholder)")
        self.resize(1000, 700)

        self._label = QLabel("Map / Area Editor placeholder.\n\nPlanned features: terrain import, building placement, grids/snapping, blueprint overlays.")
        layout = QVBoxLayout()
        layout.addWidget(self._label)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def open_asset(self, path):
        # Light-weight placeholder: show the path for now
        self._label.setText(f"Map / Area Editor\n\nAsset: {path}")
