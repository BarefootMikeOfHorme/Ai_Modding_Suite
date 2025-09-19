"""
Intake utilities for staging and classifying incoming sources.
"""
from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import py7zr


@dataclass
class IntakeSummary:
    staged_path: Path
    counts: Dict[str, int]
    files_by_type: Dict[str, List[Path]]


ARCHIVE_EXTS = {".zip", ".7z"}
MODEL_EXTS = {".obj", ".fbx", ".dae", ".stl", ".ply", ".gltf", ".glb"}
TEXTURE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tiff", ".dds"}
SCRIPT_EXTS = {".cfg", ".ini", ".txt", ".json", ".lua", ".xml"}


def is_supported_archive(path: Path) -> bool:
    return path.suffix.lower() in ARCHIVE_EXTS


def extract_archive(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest)
    elif archive.suffix.lower() == ".7z":
        with py7zr.SevenZipFile(archive, "r") as z:
            z.extractall(path=dest)
    else:
        raise ValueError(f"Unsupported archive type: {archive.suffix}")
    return dest


def stage_source(src: Path, workspace_root: Path, source_name: str | None = None) -> Path:
    workspace_root.mkdir(parents=True, exist_ok=True)
    if source_name is None:
        source_name = src.stem
    target = workspace_root / source_name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        # Copy directory tree
        for item in src.rglob("*"):
            rel = item.relative_to(src)
            dst = target / rel
            if item.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst)
    elif src.is_file() and is_supported_archive(src):
        extract_archive(src, target)
    else:
        # Single file scenario: copy into target root
        shutil.copy2(src, target / src.name)

    return target


def sniff_content(root: Path) -> Tuple[Dict[str, List[Path]], Dict[str, int]]:
    files_by_type: Dict[str, List[Path]] = {"models": [], "textures": [], "scripts": [], "other": []}
    counts = {"models": 0, "textures": 0, "scripts": 0, "other": 0}

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in MODEL_EXTS:
            files_by_type["models"].append(p)
            counts["models"] += 1
        elif ext in TEXTURE_EXTS:
            files_by_type["textures"].append(p)
            counts["textures"] += 1
        elif ext in SCRIPT_EXTS:
            files_by_type["scripts"].append(p)
            counts["scripts"] += 1
        else:
            files_by_type["other"].append(p)
            counts["other"] += 1
    return files_by_type, counts


def compute_intake_summary(staged_path: Path) -> IntakeSummary:
    files_by_type, counts = sniff_content(staged_path)
    return IntakeSummary(staged_path=staged_path, counts=counts, files_by_type=files_by_type)
