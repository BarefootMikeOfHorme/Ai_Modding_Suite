from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QModelIndex, QPoint
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeView,
    QFileSystemModel,
    QMenu,
    QToolTip,
    QLineEdit,
    QPushButton,
    QComboBox,
)
from PyQt6.QtCore import QUrl, QSortFilterProxyModel


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tiff", ".gif"}
MODEL_EXTS = {".obj", ".fbx", ".dae", ".stl", ".ply", ".gltf", ".glb"}
TEXT_EXTS = {".cfg", ".ini", ".txt", ".json", ".yaml", ".yml", ".xml"}


class ExplorerWidget(QWidget):
    """
    Folder explorer with collapsible tree, hover thumbnails for images,
    and a context menu to route items to different windows/editors or actions.
    Includes a navigation bar with Back/Forward/Up, drive chooser, path, and search.
    """

    def __init__(self, root: Optional[Path] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._history: list[Path] = []
        self._future: list[Path] = []

        self._model = QFileSystemModel(self)
        self._model.setOption(QFileSystemModel.Option.DontWatchForChanges, False)
        self._model.setRootPath(str(root or Path.home()))

        # Filter proxy for name filtering
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(0)
        self._proxy.setSourceModel(self._model)

        self._view = QTreeView(self)
        self._view.setModel(self._proxy)
        src_index = self._model.index(str(root or Path.home()))
        self._view.setRootIndex(self._proxy.mapFromSource(src_index))
        self._view.setSortingEnabled(True)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        self._view.setAlternatingRowColors(True)
        self._view.setAnimated(True)
        self._view.viewport().installEventFilter(self)
        # columns: 0=Name, 1=Size, 2=Type, 3=Date Modified
        self._view.setColumnWidth(0, 280)
        self._view.setColumnWidth(1, 100)

        # Navigation bar
        nav = QHBoxLayout()
        self._back_btn = QPushButton("◀")
        self._back_btn.setToolTip("Back")
        self._back_btn.clicked.connect(self._go_back)
        self._fwd_btn = QPushButton("▶")
        self._fwd_btn.setToolTip("Forward")
        self._fwd_btn.clicked.connect(self._go_forward)
        self._up_btn = QPushButton("↑")
        self._up_btn.setToolTip("Up one level")
        self._up_btn.clicked.connect(self._go_up)
        self._drive_combo = QComboBox()
        for d in self._detect_drives():
            self._drive_combo.addItem(d)
        self._drive_combo.currentTextChanged.connect(self._on_drive_changed)
        self._path_edit = QLineEdit(str(root or Path.home()))
        self._path_edit.returnPressed.connect(self._on_path_entered)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search…")
        self._search_edit.textChanged.connect(self._on_search_changed)
        nav.addWidget(self._back_btn)
        nav.addWidget(self._fwd_btn)
        nav.addWidget(self._up_btn)
        nav.addWidget(self._drive_combo)
        nav.addWidget(self._path_edit, 1)
        nav.addWidget(self._search_edit)

        layout = QVBoxLayout()
        layout.addLayout(nav)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _detect_drives(self) -> list[str]:
        drives = []
        for ch in map(chr, range(ord('A'), ord('Z') + 1)):
            p = Path(f"{ch}:/")
            if p.exists():
                drives.append(f"{ch}:/")
        return drives

    def _navigate_to(self, path: Path, push_history: bool = True) -> None:
        path = path.resolve()
        try:
            src_index = self._model.index(str(path))
            if not src_index.isValid():
                return
            proxy_index = self._proxy.mapFromSource(src_index)
            self._view.setRootIndex(proxy_index)
            self._path_edit.setText(str(path))
            if push_history:
                if self._history and self._history[-1] == path:
                    return
                self._history.append(path)
                self._future.clear()
        except Exception:
            pass

    def _go_back(self) -> None:
        if len(self._history) >= 2:
            current = self._history.pop()
            self._future.append(current)
            self._navigate_to(self._history[-1], push_history=False)

    def _go_forward(self) -> None:
        if self._future:
            nxt = self._future.pop()
            self._history.append(nxt)
            self._navigate_to(nxt, push_history=False)

    def _go_up(self) -> None:
        path = Path(self._path_edit.text())
        parent = path.parent if path.parent != path else path
        self._navigate_to(parent)

    def _on_drive_changed(self, drive: str) -> None:
        self._navigate_to(Path(drive))

    def _on_path_entered(self) -> None:
        self._navigate_to(Path(self._path_edit.text()))

    def _on_search_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    def set_root(self, path: Path) -> None:
        self._navigate_to(path)

    def current_path(self) -> Optional[Path]:
        idx = self._view.currentIndex()
        if not idx.isValid():
            return None
        src_idx = self._proxy.mapToSource(idx)
        return Path(self._model.filePath(src_idx))

    def _on_context_menu(self, point: QPoint) -> None:
        idx = self._view.indexAt(point)
        if not idx.isValid():
            return
        src_idx = self._proxy.mapToSource(idx)
        path = Path(self._model.filePath(src_idx))
        menu = QMenu(self)

        if path.is_file():
            # Open in editors
            open_text = menu.addAction("Open in Text Editor")
            open_text.triggered.connect(lambda: self.parent().open_file_in_editor(path))

            open_map = menu.addAction("Open in Map/Area Editor")
            open_map.triggered.connect(lambda: self.parent().open_in_map_editor(path))

            # Actions by type
            ext = path.suffix.lower()
            if ext in MODEL_EXTS:
                act_glb = menu.addAction("Convert to GLB…")
                act_glb.triggered.connect(lambda: self.parent().convert_model_to_glb_action(path))
            if ext in IMAGE_EXTS:
                act_img = menu.addAction("Convert Image…")
                act_img.triggered.connect(lambda: self.parent().convert_image_action(path))
            if ext in TEXT_EXTS or ext in {'.json', '.yaml', '.yml'}:
                act_val = menu.addAction("Validate…")
                act_val.triggered.connect(lambda: self.parent().validate_file_action(path))

            # Scan/Analyze
            act_scan = menu.addAction("Scan / Analyze…")
            act_scan.triggered.connect(lambda: self.parent().scan_analyze_action(path))

            # Recipes
            if ext in {'.json', '.yaml', '.yml'}:
                act_recipe = menu.addAction("Run Recipe…")
                act_recipe.triggered.connect(lambda: self.parent().run_recipe_action(path))

            # Validate Schema
            act_vs = menu.addAction("Validate Schema…")
            act_vs.triggered.connect(lambda: self.parent().validate_schema_action(path))

            # View Manifest
            sidecar_json = Path(str(path) + ".ams.json")
            sidecar_yaml = Path(str(path) + ".ams.yaml")
            is_manifest_file = path.name.endswith('.ams.json') or path.name.endswith('.ams.yaml')
            if is_manifest_file or sidecar_json.exists() or sidecar_yaml.exists():
                act_view = menu.addAction("View Manifest…")
                act_view.triggered.connect(lambda: self.parent().view_manifest_action(path))

            menu.addSeparator()
            sys_open = menu.addAction("Open with System Default")
            sys_open.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))

            reveal = menu.addAction("Reveal in Explorer")
            reveal.triggered.connect(lambda: self.parent().reveal_in_explorer(path))

            # Stage in Intake for supported archives
            if path.suffix.lower() in {'.zip', '.7z'}:
                menu.addSeparator()
                stage = menu.addAction("Stage in Intake…")
                stage.triggered.connect(lambda: self.parent().stage_in_intake_action(path))
        else:
            set_root_here = menu.addAction("Set as Root Folder")
            set_root_here.triggered.connect(lambda: self.set_root(path))
            stage = menu.addAction("Stage in Intake…")
            stage.triggered.connect(lambda: self.parent().stage_in_intake_action(path))

        menu.exec(self._view.viewport().mapToGlobal(point))

    def eventFilter(self, obj, event):  # noqa: N802
        # Show thumbnails for images on hover
        if obj is self._view.viewport() and event.type() == event.Type.MouseMove:
            pos = event.position().toPoint()  # type: ignore[attr-defined]
            idx = self._view.indexAt(pos)
            if idx.isValid():
                src_idx = self._proxy.mapToSource(idx)
                path = Path(self._model.filePath(src_idx))
                if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                    url = QUrl.fromLocalFile(str(path))
                    html = f"<b>{path.name}</b><br><img src='{url.toString()}' width='256'>"
                    QToolTip.showText(self._view.mapToGlobal(pos), html, self._view)
                else:
                    QToolTip.hideText()
        return super().eventFilter(obj, event)
