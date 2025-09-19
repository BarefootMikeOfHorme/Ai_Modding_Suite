"""
Conversion helpers to pivot 3D assets and images into engine-friendly formats.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import trimesh
from PIL import Image
from metadata.manifest import create_for_mesh, create_for_file, write_sidecars
from scale import NORMAL_M


def convert_model_to_glb(input_path: Path, output_path: Path) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(input_path, force='mesh')
    if mesh is None:
        raise ValueError(f"Unsupported model or failed to load: {input_path}")
    scene = trimesh.Scene(mesh)
    data = scene.export(file_type='glb')
    output_path.write_bytes(data)
    # manifest with basic geometry and conversion info
    bbox_min = tuple(map(float, mesh.bounds[0]))
    bbox_max = tuple(map(float, mesh.bounds[1]))
    manifest = create_for_mesh(
        output_path,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        scale_profile_id=NORMAL_M.id,
        unit='m',
        conversion_action='convert_model_to_glb',
        conversion_params={'input': str(input_path)},
        source_type='converted',
        source_input_path=input_path,
    )
    write_sidecars(manifest, output_path)
    return output_path


def convert_image(input_path: Path, output_path: Path, format: Optional[str] = None) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as im:
        # Infer format from extension if not provided
        fmt = format or output_path.suffix.lstrip('.').upper()
        # Pillow expects special names for some formats
        if fmt == 'JPG':
            fmt = 'JPEG'
        im.save(output_path, format=fmt)
    # generic file manifest
    manifest = create_for_file(
        output_path,
        scale_profile_id=NORMAL_M.id,
        unit='m',
        conversion_action='convert_image',
        conversion_params={'input': str(input_path), 'format': fmt},
        source_type='converted',
        source_input_path=input_path,
    )
    write_sidecars(manifest, output_path)
    return output_path
