"""
Background workers for long-running tasks to keep the UI responsive.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from typing import Optional, List
from pathlib import Path

from validators import CfgValidator, ValidationResult
from recipes.runner import run_recipe_file, StepResult


class ValidationWorker(QObject):
    finished = pyqtSignal(object)  # emits ValidationResult
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, text: str, max_line_length: int = 200) -> None:
        super().__init__()
        self._text = text
        self._max_len = max_line_length

    def run(self) -> None:
        try:
            validator = CfgValidator(max_line_length=self._max_len)
            result: ValidationResult = validator.validate(self._text)
            self.finished.emit(result)
        except Exception as e:  # pragma: no cover - defensive
            self.error.emit(str(e))


def run_validation_in_thread(text: str, max_line_length: int = 200):
    """Utility to create a thread+worker pair configured for validation.

    Returns (thread, worker) with connections left to the caller.
    """
    thread = QThread()
    worker = ValidationWorker(text=text, max_line_length=max_line_length)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    return thread, worker


class RecipeWorker(QObject):
    finished = pyqtSignal(object)  # emits List[StepResult]
    error = pyqtSignal(str)

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self._file_path = file_path

    def run(self) -> None:
        try:
            results: List[StepResult] = run_recipe_file(Path(self._file_path))  # type: ignore[name-defined]
            self.finished.emit(results)
        except Exception as e:  # pragma: no cover - defensive
            self.error.emit(str(e))


def run_recipe_in_thread(file_path: str):
    thread = QThread()
    worker = RecipeWorker(file_path=file_path)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    return thread, worker
