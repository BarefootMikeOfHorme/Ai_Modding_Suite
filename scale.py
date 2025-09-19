"""
Scale profiles and unit conversion utilities for metric workflows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from PyQt6.QtCore import QSettings

from paths_utils import ORG_NAME, APP_NAME


@dataclass(frozen=True)
class ScaleProfile:
    id: str
    name: str
    unit: str  # 'mm' or 'm'
    min_value: float
    max_value: float
    step: float

    def to_meters(self, value: float) -> float:
        if self.unit == 'mm':
            return value / 1000.0
        return value

    def from_meters(self, meters: float) -> float:
        if self.unit == 'mm':
            return meters * 1000.0
        return meters


SMALL_MM = ScaleProfile(
    id="small_mm",
    name="Small (1 mm – 1 m)",
    unit="mm",
    min_value=1.0,   # 1 mm
    max_value=1000.0,  # 1000 mm = 1 m
    step=0.1,
)

NORMAL_M = ScaleProfile(
    id="normal_m",
    name="Normal (1 – 10 m)",
    unit="m",
    min_value=1.0,
    max_value=10.0,
    step=0.01,
)

LARGE_SCENE = ScaleProfile(
    id="large_scene",
    name="Large/Scene (10 – 1000 m)",
    unit="m",
    min_value=10.0,
    max_value=1000.0,
    step=0.1,
)


ALL_PROFILES: Dict[str, ScaleProfile] = {
    SMALL_MM.id: SMALL_MM,
    NORMAL_M.id: NORMAL_M,
    LARGE_SCENE.id: LARGE_SCENE,
}

DEFAULT_PROFILE_ID = NORMAL_M.id


def get_settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def get_current_profile(settings: QSettings | None = None) -> ScaleProfile:
    s = settings or get_settings()
    pid = s.value("scale/profile_id", DEFAULT_PROFILE_ID, type=str)
    return ALL_PROFILES.get(pid, NORMAL_M)


def set_current_profile(profile_id: str, settings: QSettings | None = None) -> None:
    if profile_id not in ALL_PROFILES:
        raise ValueError(f"Unknown profile: {profile_id}")
    s = settings or get_settings()
    s.setValue("scale/profile_id", profile_id)


def list_profiles() -> List[ScaleProfile]:
    return list(ALL_PROFILES.values())
