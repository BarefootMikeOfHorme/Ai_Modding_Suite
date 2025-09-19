"""
Geometry primitives and exporters for part creation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import trimesh


def create_box(size=(1.0, 1.0, 1.0)) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=size)


def create_cylinder(radius=0.5, height=1.25, segments: int = 64) -> trimesh.Trimesh:
    return trimesh.creation.cylinder(radius=radius, height=height, sections=segments)


def create_sphere(radius=0.5, subdivisions: int = 3) -> trimesh.Trimesh:
    return trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius)


def create_capsule(radius=0.5, height=1.0, count: int = 32) -> trimesh.Trimesh:
    return trimesh.creation.capsule(radius=radius, height=height, count=count)


def create_torus(radius=1.0, tube_radius=0.25, sections: int = 64, tube_sections: int = 32) -> trimesh.Trimesh:
    return trimesh.creation.torus(radius=radius, tube_radius=tube_radius, sections=sections, tube_sections=tube_sections)


def export_mesh_glb(mesh: trimesh.Trimesh, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Export to GLB (binary glTF)
    scene = trimesh.Scene(mesh)
    data = scene.export(file_type='glb')
    out_path.write_bytes(data)
    return out_path
