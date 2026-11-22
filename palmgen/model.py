"""Shared dataclasses. Coordinates are lon/lat WGS84 unless a name says ``local``."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shapely.geometry import Polygon


@dataclass(frozen=True)
class Palm:
    palm_id: str
    lon: float
    lat: float
    species: str
    height_m: float | None
    crown_diam_m: float | None
    exclusion_radius_m: float | None
    building_conflict: bool


@dataclass(frozen=True)
class Cluster:
    member_ids: tuple[str, ...]  # sorted
    polygon_local: Polygon


@dataclass(frozen=True)
class ExclusionPolygon:
    name: str
    member_ids: tuple[str, ...]
    part: int
    ring: tuple[tuple[float, float], ...]
    tile_id: str
    guid: uuid.UUID


@dataclass(frozen=True)
class Placement:
    palm_id: str
    lon: float
    lat: float
    tile_id: str
    species: str
    variant: str
    model_guid: str
    simobject_title: str | None
    scale: float
    heading_deg: float
    guid: uuid.UUID


@dataclass(frozen=True)
class TileContent:
    tile_id: str
    polygons: list[ExclusionPolygon]
    placements: list[Placement]


@dataclass(frozen=True)
class BuildWarning:
    code: str
    message: str
    palm_id: str | None


@dataclass
class GenerateResult:
    """Mutable: stages fill the counters, warnings and file lists as they run."""

    region: str
    package_name: str
    version: Any  # PackageVersion (palmgen.version, GEN-007)
    tiles: list[TileContent] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[BuildWarning] = field(default_factory=list)
    files_written: list[Path] = field(default_factory=list)
    files_unchanged: list[Path] = field(default_factory=list)
    files_removed: list[Path] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CompileResult:
    exit_code: int
    duration_s: float
    command: list[str]
    log_path: Path


@dataclass(frozen=True)
class Check:
    name: str
    expected: str
    actual: str
    passed: bool
