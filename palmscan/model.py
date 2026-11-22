"""Internal dataclasses shared by every palmscan stage (inventory, LiDAR, merge, QA)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TreeRecord:
    """Raw record from an inventory or OSM adapter, before normalisation."""

    source: str  # config source name, e.g. "sd_street_trees"
    source_id: str
    lon: float
    lat: float
    species_raw: str | None
    common_name_raw: str | None = None
    status_raw: str | None = None
    height_raw: str | None = None
    dbh_raw: str | None = None
    date_raw: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LidarCandidate:
    """One crown segment found in the canopy height model (Phase 4)."""

    candidate_id: str  # "<dataset>:<tile_id>:<n>"
    dataset: str
    x: float  # local metric CRS (peak cell centre)
    y: float
    lon: float
    lat: float
    height_m: float  # unsmoothed CHM max in the segment
    crown_area_m2: float
    crown_diam_m: float  # 2 * sqrt(area / pi)
    ratio: float  # height_m / crown_diam_m
    shared_boundary_frac: float
    ground_elev_m: float | None
    in_building: bool = False
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)
    vintage: str | None = None


@dataclass(slots=True)
class PalmRecord:
    """One palm moving through the pipeline."""

    stable_key: str
    lon: float
    lat: float
    x: float
    y: float
    species: str | None
    species_confidence: float | None
    species_source: str | None
    height_m: float | None = None
    height_source: str | None = None
    crown_diam_m: float | None = None
    ground_elev_m: float | None = None
    detected_by: str = "inventory"
    source_ids: list[str] = field(default_factory=list)
    data_vintage: dict[str, str] = field(default_factory=dict)
    exclusion_radius_m: float | None = None
    building_conflict: bool = False
    lidar: LidarCandidate | None = None
    species_raw: str | None = None
    height_raw: str | None = None  # inventory height text, parsed by attributes.assign_sizes


@dataclass(slots=True)
class Reject:
    """A record or candidate that was dropped, with the reason (feeds qa_rejects.csv)."""

    stage: str  # inventory | dedupe | mask | lidar_rules | merge
    source: str
    source_id: str
    lon: float
    lat: float
    reason: str  # first failing rule
    all_reasons: list[str] = field(default_factory=list)
    species_raw: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class SourceVintage:
    """How old a source's data is and how that was determined."""

    source: str
    vintage: str | None  # "YYYY" or "YYYY-MM"
    basis: str  # config | record_dates | layer_edit_date | fetched
    fetched_at: str  # ISO 8601 UTC
