"""
Enhanced sidecar manifest (AMS Enhanced Metadata) for parts, scenes, and assets.
Writes JSON and YAML sidecars next to outputs.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from metadata.utils import sha256_file, get_user_host


AMS_VERSION = "0.1"


@dataclass
class GeometryInfo:
    bbox_min: Tuple[float, float, float]
    bbox_max: Tuple[float, float, float]
    extents: Tuple[float, float, float]
    units: str = "m"


@dataclass
class SourceInfo:
    type: str  # e.g., "generated", "converted", "imported"
    input_path: Optional[str] = None
    input_sha256: Optional[str] = None
    recipe_file: Optional[str] = None
    recipe_step: Optional[int] = None
    run_id: Optional[str] = None


@dataclass
class OutputInfo:
    file_path: str
    file_size: int
    file_sha256: str


@dataclass
class ScaleInfo:
    profile_id: str
    unit: str


@dataclass
class ConversionInfo:
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AMSManifest:
    ams_version: str
    ams_id: str
    created_on: str
    created_by: str
    host: str
    tool_version: str
    seed_uuid: str
    iteration: int
    lineage: List[str]
    tags: List[str]
    classification: str
    scale: ScaleInfo
    source: SourceInfo
    output: OutputInfo
    geometry: Optional[GeometryInfo] = None
    conversion: Optional[ConversionInfo] = None
    audit: Optional[Dict[str, Any]] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_version() -> str:
    # Single source of truth can be wired later
    return "AI_Modding_Suite/0.1"


def _uuid7_str() -> str:
    # Python 3.12 includes uuid.uuid7
    try:
        return str(uuid.uuid7())  # type: ignore[attr-defined]
    except Exception:
        return str(uuid.uuid4())


def _sidecar_paths(output_path: Path) -> Tuple[Path, Path]:
    base = Path(str(output_path) + ".ams")
    return base.with_suffix(base.suffix + ".json"), base.with_suffix(base.suffix + ".yaml")


def create_for_mesh(
    output_path: Path,
    bbox_min: Tuple[float, float, float],
    bbox_max: Tuple[float, float, float],
    scale_profile_id: str,
    unit: str,
    conversion_action: str,
    conversion_params: Dict[str, Any],
    source_type: str = "generated",
    source_input_path: Optional[Path] = None,
    recipe_ctx: Optional[Dict[str, Any]] = None,
    iteration: int = 1,
    tags: Optional[List[str]] = None,
    classification: str = "unclassified",
    audit: Optional[Dict[str, Any]] = None,
) -> AMSManifest:
    user, host = get_user_host()
    out = Path(output_path)
    file_sha = sha256_file(out)
    file_size = out.stat().st_size
    ams_id = _uuid7_str()
    manifest = AMSManifest(
        ams_version=AMS_VERSION,
        ams_id=ams_id,
        created_on=_now_iso(),
        created_by=user,
        host=host,
        tool_version=_tool_version(),
        seed_uuid=_uuid7_str(),
        iteration=int(iteration),
        lineage=[],
        tags=tags or [],
        classification=classification,
        scale=ScaleInfo(profile_id=scale_profile_id, unit=unit),
        source=SourceInfo(
            type=source_type,
            input_path=str(source_input_path) if source_input_path else None,
            input_sha256=sha256_file(source_input_path) if source_input_path else None,
            recipe_file=(recipe_ctx or {}).get("file"),
            recipe_step=(recipe_ctx or {}).get("step"),
            run_id=(recipe_ctx or {}).get("run_id"),
        ),
        output=OutputInfo(
            file_path=str(out),
            file_size=int(file_size),
            file_sha256=file_sha,
        ),
        geometry=GeometryInfo(
            bbox_min=tuple(map(float, bbox_min)),
            bbox_max=tuple(map(float, bbox_max)),
            extents=tuple(map(float, (
                bbox_max[0] - bbox_min[0],
                bbox_max[1] - bbox_min[1],
                bbox_max[2] - bbox_min[2],
            ))),
            units="m",
        ),
        conversion=ConversionInfo(action=conversion_action, parameters=conversion_params),
        audit=audit,
    )
    return manifest


def create_for_file(
    output_path: Path,
    scale_profile_id: str,
    unit: str,
    conversion_action: str,
    conversion_params: Dict[str, Any],
    source_type: str = "converted",
    source_input_path: Optional[Path] = None,
    recipe_ctx: Optional[Dict[str, Any]] = None,
    iteration: int = 1,
    tags: Optional[List[str]] = None,
    classification: str = "unclassified",
    audit: Optional[Dict[str, Any]] = None,
) -> AMSManifest:
    user, host = get_user_host()
    out = Path(output_path)
    file_sha = sha256_file(out)
    file_size = out.stat().st_size
    ams_id = _uuid7_str()
    manifest = AMSManifest(
        ams_version=AMS_VERSION,
        ams_id=ams_id,
        created_on=_now_iso(),
        created_by=user,
        host=host,
        tool_version=_tool_version(),
        seed_uuid=_uuid7_str(),
        iteration=int(iteration),
        lineage=[],
        tags=tags or [],
        classification=classification,
        scale=ScaleInfo(profile_id=scale_profile_id, unit=unit),
        source=SourceInfo(
            type=source_type,
            input_path=str(source_input_path) if source_input_path else None,
            input_sha256=sha256_file(source_input_path) if source_input_path else None,
            recipe_file=(recipe_ctx or {}).get("file"),
            recipe_step=(recipe_ctx or {}).get("step"),
            run_id=(recipe_ctx or {}).get("run_id"),
        ),
        output=OutputInfo(
            file_path=str(out),
            file_size=int(file_size),
            file_sha256=file_sha,
        ),
        geometry=None,
        conversion=ConversionInfo(action=conversion_action, parameters=conversion_params),
        audit=audit,
    )
    return manifest


def write_sidecars(manifest: AMSManifest, output_path: Path, write_yaml: bool = True) -> None:
    json_path, yaml_path = _sidecar_paths(Path(output_path))
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(manifest), f, ensure_ascii=False, indent=2)
    if write_yaml:
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(json.loads(json.dumps(asdict(manifest))), f, sort_keys=False)
