from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSettings, Qt, QThread
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QLabel,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QHBoxLayout,
    QStatusBar,
    QInputDialog,
    QDockWidget,
    QMenu,
    QDialog,
)

from validators import ValidationResult
from workers import run_validation_in_thread, run_recipe_in_thread
from paths_utils import default_workspace_root, CFG_FILTER, ORG_NAME, APP_NAME
from plugins.preset_ksp import create_tank_glb, create_tank_variants_glb
from scale import get_current_profile, list_profiles, set_current_profile
from explorer import ExplorerWidget
from converters.converters import convert_model_to_glb, convert_image
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
import json
from inspector import InspectorWidget
from ams_io.intake import stage_source, compute_intake_summary
from scanning.scanner import scan_path, write_sidecar_from_scan
from schemas.loader import validate_document
import yaml


class ModdingSuite(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Modding Suite")
        self.resize(900, 650)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.current_file: Optional[Path] = None
        self._modified: bool = False
        self._validation_thread: Optional[QThread] = None

        self._init_ui()

    # UI setup
    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        self.label = QLabel("Select a mod file or create a new one:")
        layout.addWidget(self.label)

        self.text_edit = QTextEdit()
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        self.load_button = QPushButton("Load Mod File")
        self.load_button.clicked.connect(self.load_mod_file)
        btn_row.addWidget(self.load_button)

        self.save_button = QPushButton("Save Mod File")
        self.save_button.clicked.connect(self.save_mod_file)
        btn_row.addWidget(self.save_button)

        self.run_button = QPushButton("Run AI Validation & Fixes")
        self.run_button.clicked.connect(self.run_ai_validation)
        btn_row.addWidget(self.run_button)

        self.clear_button = QPushButton("Clear Editor")
        self.clear_button.clicked.connect(self.clear_editor)
        btn_row.addWidget(self.clear_button)

        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.close)
        btn_row.addWidget(self.exit_button)

        layout.addLayout(btn_row)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Left dock: Explorer
        self._explorer = ExplorerWidget(root=self._last_dir(), parent=self)
        dock = QDockWidget("Explorer", self)
        dock.setWidget(self._explorer)
        dock.setObjectName("ExplorerDock")
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        status = QStatusBar()
        self.setStatusBar(status)
        self._set_status("Ready")

        # Right dock: Inspector
        self._inspector = InspectorWidget(parent=self)
        dock_ins = QDockWidget("Inspector", self)
        dock_ins.setWidget(self._inspector)
        dock_ins.setObjectName("InspectorDock")
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_ins)

        # Build menus
        self._build_menus()

        # Connect explorer selection to inspector
        try:
            sel = self._explorer._view.selectionModel()
            sel.selectionChanged.connect(lambda *_: self._on_explorer_selection_changed())
        except Exception:
            pass

        # Load current scale profile for UI
        self._scale_profile = get_current_profile(self.settings)

    # Helpers
    def _set_status(self, text: str) -> None:
        if self.statusBar():
            self.statusBar().showMessage(text, 5000)

    def _build_menus(self) -> None:
        tools = self.menuBar().addMenu("Tools")
        act1 = tools.addAction("Generate KSP Tank...")
        act1.triggered.connect(self.generate_ksp_tank)
        act2 = tools.addAction("Generate KSP Tank Family...")
        act2.triggered.connect(self.generate_ksp_tank_family)

        prefs = self.menuBar().addMenu("Preferences")
        actp = prefs.addAction("Scale Profile…")
        actp.triggered.connect(self.choose_scale_profile)

        window_menu = self.menuBar().addMenu("Window")
        act_map = window_menu.addAction("Open Map/Area Editor")
        act_map.triggered.connect(self.open_map_editor)
        act_root = window_menu.addAction("Set Explorer Root…")
        act_root.triggered.connect(self.set_explorer_root)

    def _last_dir(self) -> Path:
        p = self.settings.value("last_dir", type=str)
        if p:
            return Path(p)
        return default_workspace_root()

    def _set_last_dir(self, p: Path) -> None:
        self.settings.setValue("last_dir", str(p))

    def _on_text_changed(self) -> None:
        self._modified = True

    # Slots
    def load_mod_file(self) -> None:
        start_dir = str(self._last_dir())
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Mod File", start_dir, CFG_FILTER
        )
        if not file_name:
            return
        fpath = Path(file_name)
        if not fpath.exists():
            QMessageBox.warning(self, "Error", "File not found!")
            return
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
            return
        self.text_edit.setPlainText(text)
        self.current_file = fpath
        self._modified = False
        self._set_last_dir(fpath.parent)
        self._set_status(f"Loaded: {fpath}")

    def save_mod_file(self) -> None:
        text = self.text_edit.toPlainText()
        # If already have a current file, ask whether to overwrite or Save As
        target_path: Optional[Path] = self.current_file
        if target_path is None:
            start_dir = str(self._last_dir())
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save Mod File", start_dir, CFG_FILTER
            )
            if not file_name:
                return
            target_path = Path(file_name)
        else:
            if target_path.exists():
                resp = QMessageBox.question(
                    self,
                    "Confirm Overwrite",
                    f"Overwrite existing file?\n\n{target_path}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    # Save As
                    start_dir = str(self._last_dir())
                    file_name, _ = QFileDialog.getSaveFileName(
                        self, "Save Mod File As", start_dir, CFG_FILTER
                    )
                    if not file_name:
                        return
                    target_path = Path(file_name)
        try:
            target_path.write_text(text, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
            return
        self.current_file = target_path
        self._modified = False
        self._set_last_dir(target_path.parent)
        QMessageBox.information(self, "Success", f"Saved: {target_path}")
        self._set_status(f"Saved: {target_path}")

    def clear_editor(self) -> None:
        if self._modified and self.text_edit.toPlainText().strip():
            resp = QMessageBox.question(
                self,
                "Clear Editor?",
                "You have unsaved changes. Clear anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self.text_edit.clear()
        self.current_file = None
        self._modified = False
        self._set_status("Editor cleared")

    def run_ai_validation(self) -> None:
        text = self.text_edit.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Validation", "Nothing to validate.")
            return

        self._set_status("Validating...")
        thread, worker = run_validation_in_thread(text=text, max_line_length=200)
        self._validation_thread = thread  # keep reference to avoid GC

        def on_finished(result: ValidationResult) -> None:
            try:
                if result.is_ok:
                    QMessageBox.information(self, "Validation", "No issues found.")
                else:
                    # Show a concise summary; for large outputs, truncate
                    summary = result.as_text()
                    if len(summary) > 4000:
                        summary = summary[:4000] + "\n... (truncated)"
                    QMessageBox.information(self, "Validation Report", summary)
            finally:
                self._set_status("Validation complete")

        def on_error(msg: str) -> None:
            QMessageBox.critical(self, "Validation Error", msg)
            self._set_status("Validation error")

        # Wire signals
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.finished.connect(lambda: setattr(self, "_validation_thread", None))

        # Auto-cleanup
        worker.finished.connect(thread.quit)
        thread.start()

    # Prompt on close if unsaved
    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._modified and self.text_edit.toPlainText().strip():
            resp = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Exit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()

    # Tools menu actions
    def generate_ksp_tank(self) -> None:
        # Ask for diameter and length factor, using the selected scale profile
        sp = get_current_profile(self.settings)
        unit_label = "mm" if sp.unit == "mm" else "m"
        default_diam = sp.from_meters(1.25)
        diameter, ok = QInputDialog.getDouble(
            self,
            "Tank Diameter",
            f"Diameter ({unit_label}):",
            value=float(default_diam),
            min=float(sp.min_value),
            max=float(sp.max_value),
            decimals=3 if sp.unit == "mm" else 3,
        )
        if not ok:
            return
        length_factor, ok = QInputDialog.getDouble(
            self,
            "Body Length Factor",
            "Length as multiples of diameter:",
            value=1.0,
            min=0.1,
            max=20.0,
            decimals=2,
        )
        if not ok:
            return
        start_dir = str(self._last_dir())
        out_path, _ = QFileDialog.getSaveFileName(self, "Save Tank GLB", start_dir, "glTF Binary (*.glb)")
        if not out_path:
            return
        try:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            diameter_m = sp.to_meters(float(diameter))
            create_tank_glb(p, diameter_m=diameter_m, body_length_factor=length_factor, segments=128, scale_profile_id=sp.id)
            self._set_last_dir(p.parent)
            QMessageBox.information(self, "Success", f"Created tank: {p}")
            self._set_status(f"Created tank: {p}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create tank: {e}")

    def generate_ksp_tank_family(self) -> None:
        # Read comma-separated lists for diameters and length factors
        sp = get_current_profile(self.settings)
        unit_label = "mm" if sp.unit == "mm" else "m"
        default_list = ",".join([str(sp.from_meters(x)) for x in (0.625, 1.25, 2.5)])
        diam_text, ok = QInputDialog.getText(self, "Diameters", f"Diameters ({unit_label}, comma-separated):", text=default_list)
        if not ok:
            return
        len_text, ok = QInputDialog.getText(self, "Length Factors", "Length factors (multiples of diameter, comma-separated):", text="1.0,2.0,4.0")
        if not ok:
            return
        def parse_floats(s: str):
            vals = []
            for tok in s.split(','):
                tok = tok.strip()
                if not tok:
                    continue
                vals.append(float(tok))
            return vals
        diameters = [sp.to_meters(v) for v in parse_floats(diam_text)]
        length_factors = parse_floats(len_text)
        if not diameters or not length_factors:
            QMessageBox.warning(self, "Input Required", "Please provide at least one diameter and one length factor.")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Output Directory", str(self._last_dir()))
        if not out_dir:
            return
        try:
            created = create_tank_variants_glb(Path(out_dir), diameters, length_factors, segments=128, scale_profile_id=sp.id)
            self._set_last_dir(Path(out_dir))
            QMessageBox.information(self, "Success", f"Created {len(created)} tank variants in {out_dir}")
            self._set_status(f"Created {len(created)} tank variants")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create tank family: {e}")

    def choose_scale_profile(self) -> None:
        # Simple chooser dialog using profile names
        profiles = list_profiles()
        names = [p.name for p in profiles]
        current = get_current_profile(self.settings)
        try:
            idx = names.index(current.name)
        except ValueError:
            idx = 0
        name, ok = QInputDialog.getItem(self, "Scale Profile", "Select profile:", names, current=idx, editable=False)
        if not ok or not name:
            return
        chosen = next((p for p in profiles if p.name == name), None)
        if chosen:
            set_current_profile(chosen.id, self.settings)
            self._scale_profile = chosen
            self._set_status(f"Scale profile set: {chosen.name}")

    def _on_explorer_selection_changed(self) -> None:
        path = self._explorer.current_path()
        try:
            self._inspector.update_path(path)
        except Exception:
            pass

    def open_map_editor(self) -> None:
        try:
            from map_editor import MapAreaEditor
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load Map/Area Editor: {e}")
            return
        editor = MapAreaEditor()
        editor.show()
        # keep a reference to prevent GC
        if not hasattr(self, "_child_windows"):
            self._child_windows = []
        self._child_windows.append(editor)

    # Explorer support methods
    def set_explorer_root(self) -> None:
        dir_ = QFileDialog.getExistingDirectory(self, "Explorer Root", str(self._last_dir()))
        if not dir_:
            return
        self._explorer.set_root(Path(dir_))
        self._set_last_dir(Path(dir_))

    def open_file_in_editor(self, path: Path) -> None:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")
            return
        self.text_edit.setPlainText(text)
        self.current_file = Path(path)
        self._modified = False
        self._set_status(f"Opened in editor: {path}")

    def validate_file_action(self, path: Path) -> None:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read file: {e}")
            return
        self.text_edit.setPlainText(text)
        self.current_file = Path(path)
        self.run_ai_validation()

    def open_in_map_editor(self, path: Path) -> None:
        try:
            from map_editor import MapAreaEditor
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load Map/Area Editor: {e}")
            return
        editor = MapAreaEditor()
        # try to call open_asset if available
        if hasattr(editor, "open_asset"):
            try:
                editor.open_asset(Path(path))  # type: ignore[attr-defined]
            except Exception:
                pass
        editor.show()
        if not hasattr(self, "_child_windows"):
            self._child_windows = []
        self._child_windows.append(editor)

    def convert_model_to_glb_action(self, path: Path) -> None:
        out, _ = QFileDialog.getSaveFileName(self, "Save GLB", str(Path(path).with_suffix('.glb')), "glTF Binary (*.glb)")
        if not out:
            return
        try:
            convert_model_to_glb(Path(path), Path(out))
            QMessageBox.information(self, "Converted", f"Saved GLB: {out}")
            self._set_status(f"Converted to GLB: {out}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Conversion failed: {e}")

    def convert_image_action(self, path: Path) -> None:
        fmt, ok = QInputDialog.getItem(self, "Image Format", "Choose format:", ["PNG", "JPEG"], current=0, editable=False)
        if not ok:
            return
        suffix = ".png" if fmt.upper() == "PNG" else ".jpg"
        out, _ = QFileDialog.getSaveFileName(self, "Save Image", str(Path(path).with_suffix(suffix)), f"{fmt} (*.{suffix[1:]})")
        if not out:
            return
        try:
            convert_image(Path(path), Path(out), format=fmt.upper())
            QMessageBox.information(self, "Converted", f"Saved image: {out}")
            self._set_status(f"Converted image: {out}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Image conversion failed: {e}")

    def reveal_in_explorer(self, path: Path) -> None:
        # Use Windows Explorer to select the file
        try:
            import subprocess
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def stage_in_intake_action(self, path: Path) -> None:
        # Choose source name and stage into the workspace Intake
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        src = Path(path)
        default_name = src.stem if src.is_file() else src.name
        name, ok = QInputDialog.getText(self, "Source Name", "Name for intake staging:", text=default_name)
        if not ok or not name:
            return
        workspace = default_workspace_root() / "Intake"
        try:
            staged = stage_source(src, workspace, source_name=name)
            summary = compute_intake_summary(staged)
            msg = (
                f"Staged to: {staged}\n\n"
                f"Models: {summary.counts.get('models',0)}\n"
                f"Textures: {summary.counts.get('textures',0)}\n"
                f"Scripts: {summary.counts.get('scripts',0)}\n"
                f"Other: {summary.counts.get('other',0)}\n"
            )
            # Offer immediate scan
            scan_now = QMessageBox.question(
                self,
                "Intake Staging Complete",
                msg + "\n\nRun scan/analyze now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if scan_now == QMessageBox.StandardButton.Yes:
                data = scan_path(staged)
                self._show_scan_summary(data)
            # Open staged folder
            self._explorer.set_root(staged)
            self._set_last_dir(staged)
            self._on_explorer_selection_changed()
        except Exception as e:
            QMessageBox.critical(self, "Intake Error", f"Failed to stage: {e}")

    def _show_scan_summary(self, data) -> None:
        from PyQt6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Scan / Analyze Summary")
        te = QTextEdit(dlg)
        te.setReadOnly(True)
        import json as _json
        te.setPlainText(_json.dumps(data, indent=2, ensure_ascii=False))
        lay = QVBoxLayout()
        lay.addWidget(te)
        dlg.setLayout(lay)
        dlg.resize(800, 600)
        dlg.exec()

    def scan_analyze_action(self, path: Path) -> None:
        from PyQt6.QtWidgets import QMessageBox
        p = Path(path)
        data = scan_path(p)
        self._show_scan_summary(data)
        if data.get("kind") == "file":
            resp = QMessageBox.question(
                self,
                "Write Manifest",
                "Write or update AMS sidecar for this file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if resp == QMessageBox.StandardButton.Yes:
                out = write_sidecar_from_scan(p)
                if out:
                    QMessageBox.information(self, "Manifest", f"Sidecar written: {out}")
                else:
                    QMessageBox.warning(self, "Manifest", "Failed to write sidecar.")

    def validate_schema_action(self, path: Path) -> None:
        # Choose schema and validate a JSON/YAML document (or its AMS sidecar)
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        doc_path = Path(path)
        target_doc: Path | None = None
        if doc_path.suffix.lower() in {'.json', '.yaml', '.yml'}:
            target_doc = doc_path
        else:
            j = Path(str(doc_path) + '.ams.json')
            y = Path(str(doc_path) + '.ams.yaml')
            if j.exists():
                target_doc = j
            elif y.exists():
                target_doc = y
        if not target_doc:
            QMessageBox.information(self, "Validate Schema", "Select a JSON/YAML file or an asset with .ams sidecars.")
            return
        schema_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Schema JSON",
            str(Path('standards/schemas').resolve()),
            "JSON Schema (*.json)"
        )
        if not schema_file:
            return
        try:
            text = target_doc.read_text(encoding='utf-8')
            if target_doc.suffix.lower() == '.json':
                doc = json.loads(text)
            else:
                doc = yaml.safe_load(text)
            errors = validate_document(doc, schema_file)
            if errors:
                msg = "\n".join(errors)
                if len(msg) > 6000:
                    msg = msg[:6000] + "\n... (truncated)"
                QMessageBox.warning(self, "Schema Validation", f"Validation FAILED with {len(errors)} error(s):\n\n{msg}")
            else:
                QMessageBox.information(self, "Schema Validation", "Validation OK.")
        except Exception as e:
            QMessageBox.critical(self, "Schema Validation", f"Error: {e}")

    # Manifest and recipe actions
    def view_manifest_action(self, path: Path) -> None:
        p = Path(path)
        targets = []
        # If user right-clicked the product (e.g., .glb), look for sidecars
        if not p.name.endswith('.ams.json') and not p.name.endswith('.ams.yaml'):
            j = Path(str(p) + ".ams.json")
            y = Path(str(p) + ".ams.yaml")
            if j.exists():
                targets.append(j)
            if y.exists():
                targets.append(y)
        else:
            targets.append(p)
        if not targets:
            QMessageBox.information(self, "Manifest", "No manifest sidecar found.")
            return
        # Prefer JSON
        target = next((t for t in targets if t.suffix.lower() == '.json'), targets[0])
        try:
            text = target.read_text(encoding='utf-8')
            # Pretty-print JSON where applicable
            if target.suffix.lower() == '.json':
                obj = json.loads(text)
                text = json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read manifest: {e}")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Manifest: {target.name}")
        te = QTextEdit(dlg)
        te.setReadOnly(True)
        te.setPlainText(text)
        lay = QVBoxLayout()
        lay.addWidget(te)
        dlg.setLayout(lay)
        dlg.resize(800, 600)
        dlg.exec()

    def run_recipe_action(self, path: Path) -> None:
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "Recipe", "File does not exist.")
            return
        self._set_status("Running recipe…")
        thread, worker = run_recipe_in_thread(str(p))
        self._recipe_thread = thread

        def on_finished(results):
            # Format a concise summary
            lines = []
            ok_count = 0
            fail_count = 0
            for r in results:
                status = "OK" if r.ok else "FAIL"
                if r.ok:
                    ok_count += 1
                else:
                    fail_count += 1
                out = f" -> {len(r.outputs)} outputs" if getattr(r, 'outputs', None) else ""
                lines.append(f"[{status}] {r.index}: {r.action}{out} — {r.message}")
            summary = "\n".join(lines)
            if len(summary) > 6000:
                summary = summary[:6000] + "\n... (truncated)"
            QMessageBox.information(self, "Recipe Results", f"Completed. OK={ok_count}, FAIL={fail_count}\n\n{summary}")
            self._set_status("Recipe complete")

        def on_error(msg: str):
            QMessageBox.critical(self, "Recipe Error", msg)
            self._set_status("Recipe error")

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda: setattr(self, "_recipe_thread", None))
        thread.start()
