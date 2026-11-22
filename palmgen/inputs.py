"""Load palmgen's inputs: palms, building footprints and the region config.

Parsing and validation belong to palmcore (``read_palms``, ``validate_buildings``,
``load_region_dict``); this module maps the results onto palmgen's own types and turns every
failure into :class:`InputError`. No defaults are defined here: they all come from
``RegionConfig`` (ARCH-003).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from shapely import make_valid
from shapely.geometry import Polygon, shape
from shapely.geometry.base import BaseGeometry

from palmcore.config import (
    AirportMasks,
    ExclusionConfig,
    MaskArea,
    RegionConfig,
    _parse_yaml,
    load_region_dict,
)
from palmcore.contract import ValidationReport, validate_buildings
from palmcore.errors import ConfigError, ContractError
from palmcore.geo import Bbox
from palmcore.log import get_logger
from palmcore.palms import read_palms
from palmgen.errors import InputError
from palmgen.model import Palm

log = get_logger(__name__)

MAX_REPORTED_ERRORS: Final = 20
_NOT_MEMBERS: Final = frozenset({"type", "features"})


@dataclass(frozen=True)
class GenConfig:
    """The region settings palmgen reads. Satisfies ``palmgen.geometry.RadiusConfig``."""

    region: str
    id_prefix: str
    bbox: Bbox
    species_priors: Mapping[str, float]
    exclusion: ExclusionConfig
    # Optional per-region override of the manifest scale limits (ASSET-005); None when unset.
    scale_clamp: float | None
    mask_out: tuple[MaskArea, ...]
    airports: AirportMasks
    config_sha256: str
    source_path: Path | None

    # Flat views of exclusion.* for palmgen.geometry.RadiusConfig.
    @property
    def margin_m(self) -> float:
        return self.exclusion.margin_m

    @property
    def default_radius_m(self) -> float:
        return self.exclusion.default_radius_m

    @property
    def radius_min_m(self) -> float:
        return self.exclusion.radius_min_m

    @property
    def radius_max_m(self) -> float:
        return self.exclusion.radius_max_m

    @classmethod
    def from_region(cls, cfg: RegionConfig) -> GenConfig:
        """Map a loaded ``RegionConfig``; nothing is defaulted here."""
        placement = cfg.raw.get("placement")
        override = placement.get("scale_clamp") if isinstance(placement, Mapping) else None
        return cls(
            region=cfg.region,
            id_prefix=cfg.id_prefix,
            bbox=cfg.bbox,
            species_priors=cfg.species_priors,
            exclusion=cfg.exclusion,
            scale_clamp=None if override is None else float(override),
            mask_out=cfg.mask_out,
            airports=cfg.airport_masks,
            config_sha256=cfg.sha256,
            source_path=cfg.source_path,
        )


def _issue_lines(report: ValidationReport) -> str:
    lines = [f"  {line}" for line in report.error_strings(MAX_REPORTED_ERRORS)]
    if len(report.errors) > len(lines) or report.truncated:
        lines.append("  ...")
    return "\n".join(lines)


def load_gen_config(
    region_name: str, config_path: Path, *, base_dir: Path | None = None
) -> GenConfig:
    """Load the region YAML at ``config_path`` into a :class:`GenConfig`.

    ``base_dir`` resolves relative paths in the file (default: the parent of the directory that
    holds it, which is the repo root for ``regions/<name>.yaml``). The ``region`` key must equal
    ``region_name``; the file name is not checked. Unknown ``exclusion.*`` keys are dropped with a
    warning instead of failing the load.
    """
    path = Path(config_path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read region config {path}: {exc}") from exc
    try:
        data = _parse_yaml(raw, str(path))
        exclusion = data.get("exclusion")
        if isinstance(exclusion, dict):
            known = ExclusionConfig.__dataclass_fields__
            unknown = sorted(str(k) for k in exclusion if k not in known)
            if unknown:
                log.warning("%s: ignoring unknown exclusion keys: %s", path, ", ".join(unknown))
                data["exclusion"] = {k: v for k, v in exclusion.items() if k in known}
        region_cfg = load_region_dict(
            data,
            base_dir=base_dir if base_dir is not None else path.resolve().parent.parent,
            source_path=path,
        )
    except ConfigError as exc:
        raise InputError(str(exc)) from exc
    if region_cfg.region != region_name:
        raise InputError(
            f"{path}: region is {region_cfg.region!r} but the requested region is {region_name!r}"
        )
    region_cfg = dataclasses.replace(region_cfg, sha256=hashlib.sha256(raw).hexdigest())
    return GenConfig.from_region(region_cfg)


def load_palms(path: Path, region: str) -> tuple[list[Palm], dict[str, Any]]:
    """Read and validate ``palms.geojson`` for ``region``.

    Returns the palms sorted by ``palm_id`` and the collection-level members (every top-level key
    except ``type`` and ``features``). Schema failures (first 20 listed), a duplicate ``palm_id``,
    a file or feature ``region`` other than ``region``, and an unreadable file raise
    :class:`InputError`.
    """
    path = Path(path)
    if not path.is_file():
        raise InputError(f"palms file not found: {path} (run palmscan for region {region!r} first)")
    try:
        collection = read_palms(path, region=region)
    except ContractError as exc:
        lines = "\n".join(f"  {issue}" for issue in exc.issues[:MAX_REPORTED_ERRORS])
        detail = f"\n{lines}" if lines else ""
        raise InputError(f"{path}: invalid palms.geojson: {exc}{detail}") from exc
    palms = [
        Palm(
            palm_id=p.palm_id,
            lon=p.lon,
            lat=p.lat,
            species=p.species,
            height_m=p.height_m,
            crown_diam_m=p.crown_diam_m,
            exclusion_radius_m=p.exclusion_radius_m,
            building_conflict=p.building_conflict,
        )
        for p in collection.palms
    ]
    doc = json.loads(path.read_text(encoding="utf-8"))  # read_palms already proved it parses
    meta = {k: v for k, v in doc.items() if k not in _NOT_MEMBERS}
    return palms, meta


def _polygons(geom: BaseGeometry) -> list[Polygon]:
    """Non-empty polygons in ``geom``, exploding multi-part and collection geometries."""
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for part in geom.geoms for p in _polygons(part)]
    return []  # points and lines left over from make_valid


def load_buildings(path: Path) -> list[Polygon]:
    """Building footprints (lon/lat) from ``buildings.geojson``, validated and repaired.

    MultiPolygons are exploded, invalid geometries go through ``shapely.make_valid`` and empty
    results are dropped. Output order follows ``building_id``.
    """
    path = Path(path)
    if not path.is_file():
        raise InputError(
            f"buildings file not found: {path}. Pass --buildings <file> or set "
            "exclusion.clip_buildings: false in the region config"
        )
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise InputError(f"{path}: top-level JSON value must be an object")
    report = validate_buildings(doc)
    if not report.ok:
        raise InputError(
            f"{path}: invalid buildings.geojson: {report.summary()}\n{_issue_lines(report)}"
        )
    out: list[Polygon] = []
    for feature in sorted(doc["features"], key=lambda f: f["properties"]["building_id"]):
        try:
            geom = shape(feature["geometry"])
        except (ValueError, TypeError, KeyError) as exc:
            building_id = feature["properties"]["building_id"]
            raise InputError(f"{path}: building {building_id!r} has bad geometry: {exc}") from exc
        out.extend(_polygons(geom if geom.is_valid else make_valid(geom)))
    return out
