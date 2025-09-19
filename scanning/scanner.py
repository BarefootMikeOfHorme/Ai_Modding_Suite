# Scanning and analysis of files and folders to populate AMS metadata.
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import hashlib

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

import trimesh
from PIL import Image

from scale import get_current_profile
from metadata.manifest import create_for_mesh, create_for_file, write_sidecars


@dataclass
class ScanResult:
    path: Path
    detected_type: str  # 'model' | 'image' | 'text' | 'binary' | 'folder'
    details: Dict[str, Any]
    missing: List[str]


MODEL_EXTS = {".obj", ".fbx", ".dae", ".stl", ".ply", ".gltf", ".glb"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tiff", ".gif", ".dds"}
TEXT_EXTS = {".cfg", ".ini", ".txt", ".json", ".yaml", ".yml", ".xml"}


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_file(path: Path) -> ScanResult:
    path = Path(path)
    ext = path.suffix.lower()
    details: Dict[str, Any] = {}
    missing: List[str] = []

    try:
        size = path.stat().st_size
    except Exception:
        size = 0
    details["size_bytes"] = size
    details["sha256"] = _sha256_file(path) if path.is_file() else None

    if ext in MODEL_EXTS:
        try:
            mesh = trimesh.load(path, force="mesh")
            if mesh is None:
                raise ValueError("No mesh")
            bbox_min = tuple(map(float, mesh.bounds[0]))
            bbox_max = tuple(map(float, mesh.bounds[1]))
            details.update({
                "bbox_min": bbox_min,
                "bbox_max": bbox_max,
                "vertices": int(mesh.vertices.shape[0]) if hasattr(mesh, 'vertices') else None,
                "faces": int(mesh.faces.shape[0]) if hasattr(mesh, 'faces') else None,
            })
            # Potential missing items to track later
            if details.get("faces") is None:
                missing.append("faces")
            detected = "model"
        except Exception:
            detected = "binary"
    elif ext in IMAGE_EXTS:
        try:
            with Image.open(path) as im:
                details.update({
                    "width": int(im.width),
                    "height": int(im.height),
                    "mode": im.mode,
                    "format": im.format,
                })
            detected = "image"
        except Exception:
            detected = "binary"
    elif ext in TEXT_EXTS:
        detected = "text"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            # Try JSON, YAML detection
            kind = "plain"
            try:
                json.loads(text)
                kind = "json"
            except Exception:
                if yaml:
                    try:
                        yaml.safe_load(text)
                        kind = "yaml"
                    except Exception:
                        pass
            details["text_kind"] = kind
        except Exception:
            details["text_kind"] = "unknown"
    else:
        detected = "binary"

    return ScanResult(path=path, detected_type=detected, details=details, missing=missing)


def scan_path(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if path.is_dir():
        results: List[ScanResult] = []
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    results.append(scan_file(p))
                except Exception:
                    pass
        summary = {
            "files": len(results),
            "models": sum(1 for r in results if r.detected_type == "model"),
            "images": sum(1 for r in results if r.detected_type == "image"),
            "text": sum(1 for r in results if r.detected_type == "text"),
            "binary": sum(1 for r in results if r.detected_type == "binary"),
        }
        return {"kind": "folder", "path": str(path), "summary": summary}
    else:
        r = scan_file(path)
        return {
            "kind": "file",
            "path": str(path),
            "detected_type": r.detected_type,
            "details": r.details,
            "missing": r.missing,
        }


def write_sidecar_from_scan(path: Path) -> Optional[Path]:
    """Create or update an AMS sidecar using scan results. Returns JSON sidecar path."""
    path = Path(path)
    data = scan_path(path)
    sp = get_current_profile()

    if data["kind"] == "file":
        if data["detected_type"] == "model":
            bbox_min = tuple(data["details"].get("bbox_min", (0.0, 0.0, 0.0)))
            bbox_max = tuple(data["details"].get("bbox_max", (0.0, 0.0, 0.0)))
            manifest = create_for_mesh(
                path,
                bbox_min=bbox_min, bbox_max=bbox_max,
                scale_profile_id=sp.id, unit=sp.unit if sp.unit in ("mm", "m") else "m",
                conversion_action="scan",
                conversion_params={"detected_type": "model"},
            )
        else:
            manifest = create_for_file(
                path,
                scale_profile_id=sp.id, unit=sp.unit if sp.unit in ("mm", "m") else "m",
                conversion_action="scan",
                conversion_params={"detected_type": data.get("detected_type")},
            )
        # Attach audit info
        try:
            # monkey-patch audit if present in manifest dataclass
            setattr(manifest, "audit", data)  # type: ignore
        except Exception:
            pass
        write_sidecars(manifest, path)
        json_sidecar = Path(str(path) + ".ams.json")
        return json_sidecar if json_sidecar.exists() else None
    return None
