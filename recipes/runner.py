"""
Recipe loader and runner for JSON/YAML conversion/creation workflows.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from PyQt6.QtCore import QSettings

from scale import get_current_profile, ALL_PROFILES
from plugins.preset_ksp import create_tank_glb, create_tank_variants_glb
from converters.converters import convert_model_to_glb, convert_image


@dataclass
class StepResult:
    index: int
    action: str
    ok: bool
    message: str
    outputs: List[str]


def _load_recipe_file(path: Path) -> Dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)  # type: ignore[no-any-unimported]
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Recipe must be a JSON/YAML object at top level")
    return data


def _get_scale_profile(recipe: Dict[str, Any], settings: QSettings) -> str:
    pid = recipe.get("scale_profile")
    if isinstance(pid, str) and pid in ALL_PROFILES:
        return pid
    # fallback to current
    cur = get_current_profile(settings)
    return cur.id


def _val_float(x: Any, name: str) -> float:
    if not isinstance(x, (int, float)):
        raise ValueError(f"{name} must be a number")
    return float(x)


def _val_list_of_numbers(xs: Any, name: str) -> List[float]:
    if not isinstance(xs, list) or any(not isinstance(t, (int, float)) for t in xs):
        raise ValueError(f"{name} must be a list of numbers")
    return [float(t) for t in xs]


def run_recipe_file(path: Path, settings: Optional[QSettings] = None) -> List[StepResult]:
    settings = settings or QSettings()
    recipe = _load_recipe_file(Path(path))
    pid = _get_scale_profile(recipe, settings)
    profile = ALL_PROFILES[pid]

    steps = recipe.get("steps")
    if not isinstance(steps, list):
        raise ValueError("Recipe 'steps' must be a list")

    results: List[StepResult] = []

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            results.append(StepResult(idx, "<invalid>", False, "Step must be a dict", []))
            continue
        action = step.get("action")
        try:
            outputs: List[str] = []
            if action == "create_tank":
                out = Path(step["output"])  # raises if missing
                diameter = _val_float(step.get("diameter"), "diameter")
                unit = step.get("diameter_unit") or profile.unit
                if unit == "mm":
                    diameter_m = diameter / 1000.0
                else:
                    diameter_m = diameter
                length_factor = _val_float(step.get("length_factor", 1.0), "length_factor")
                segments = int(step.get("segments", 128))
                out.parent.mkdir(parents=True, exist_ok=True)
                create_tank_glb(out, diameter_m=diameter_m, body_length_factor=length_factor, segments=segments)
                outputs.append(str(out))
                results.append(StepResult(idx, action, True, "ok", outputs))
            elif action == "create_tank_family":
                out_dir = Path(step["output_dir"])  # raises if missing
                diameters = _val_list_of_numbers(step.get("diameters"), "diameters")
                unit = step.get("diameters_unit") or profile.unit
                if unit == "mm":
                    diameters = [d / 1000.0 for d in diameters]
                length_factors = _val_list_of_numbers(step.get("length_factors"), "length_factors")
                segments = int(step.get("segments", 128))
                created = create_tank_variants_glb(out_dir, diameters, length_factors, segments=segments)
                outputs.extend([str(p) for p in created])
                results.append(StepResult(idx, action, True, f"created {len(created)}", outputs))
            elif action == "convert_model_to_glb":
                inp = Path(step["input"])  # raises if missing
                out = Path(step["output"])  # raises if missing
                convert_model_to_glb(inp, out)
                outputs.append(str(out))
                results.append(StepResult(idx, action, True, "ok", outputs))
            elif action == "convert_image":
                inp = Path(step["input"])  # raises if missing
                out = Path(step["output"])  # raises if missing
                fmt = step.get("format")
                convert_image(inp, out, format=fmt)
                outputs.append(str(out))
                results.append(StepResult(idx, action, True, "ok", outputs))
            else:
                results.append(StepResult(idx, str(action), False, "Unknown action", []))
        except Exception as e:
            results.append(StepResult(idx, str(action), False, str(e), []))

    return results
