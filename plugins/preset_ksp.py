"""
KSP-oriented presets and helpers with scalable presets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

from plugins.registry import Plugin
from geometry.primitives import create_capsule, export_mesh_glb
from metadata.manifest import create_for_mesh, write_sidecars
from scale import ALL_PROFILES


def create_tank_glb(
    output_path: Path,
    diameter_m: float = 1.25,
    body_length_factor: float = 1.0,
    segments: int = 64,
    scale_profile_id: str = 'normal_m',
) -> Path:
    """
    Create a KSP-style cylindrical tank with rounded ends as a single mesh.
    diameter_m: overall diameter in meters (caps radius = diameter/2)
    body_length_factor: multiple of diameter for the cylinder body (hemispheres added automatically)
    """
    radius = float(diameter_m) / 2.0
    body_height = float(body_length_factor) * float(diameter_m)
    mesh = create_capsule(radius=radius, height=body_height, count=segments)
    out_path = export_mesh_glb(mesh, Path(output_path))
    # write enhanced sidecar manifest
    bbox_min = tuple(map(float, mesh.bounds[0]))
    bbox_max = tuple(map(float, mesh.bounds[1]))
    unit = 'm'
    manifest = create_for_mesh(
        out_path,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        scale_profile_id=scale_profile_id,
        unit=unit,
        conversion_action='create_tank',
        conversion_params={'diameter_m': diameter_m, 'body_length_factor': body_length_factor, 'segments': segments},
        source_type='generated',
    )
    write_sidecars(manifest, out_path)
    return out_path


def create_tank_variants_glb(
    output_dir: Path,
    diameters_m: Iterable[float],
    body_length_factors: Iterable[float],
    segments: int = 64,
    scale_profile_id: str = 'normal_m',
) -> List[Path]:
    """
    Generate a whole family of tanks in one operation.
    Returns list of created file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    created: List[Path] = []
    for d in diameters_m:
        for k in body_length_factors:
            name = f"tank_{d:.3f}m_L{k:.2f}x.glb".replace("..", ".")
            path = output_dir / name
            created.append(create_tank_glb(path, diameter_m=float(d), body_length_factor=float(k), segments=segments, scale_profile_id=scale_profile_id))
    return created


def get_plugin() -> Plugin:
    return Plugin(
        plugin_id="preset.ksp",
        name="KSP Presets",
        description="Kerbal-style part presets (e.g., cylindrical tanks with rounded ends).",
        functions={
            "create_tank_glb": create_tank_glb,
            "create_tank_variants_glb": create_tank_variants_glb,
        },
    )
