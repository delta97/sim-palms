"""Test-site registry: load and check ``tests/sites/sites.yaml``.

The YAML is checked in two steps. First ``tests/sites/sites.schema.json`` checks structure and
types. Then sites with ``status: defined`` get range checks that a schema cannot express (bbox
size, viewpoint altitude bands, viewpoints inside the bbox). ``status: placeholder`` sites are
accepted unchecked; tools must refuse to run against them.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import yaml

from palmcore.errors import ConfigError
from palmcore.geo import Bbox
from palmcore.log import get_logger
from palmcore.schemas import make_validator
from tests.helpers.fixtures import REPO_ROOT

logger = get_logger(__name__)

SITES_DIR: Final = REPO_ROOT / "tests" / "sites"
SITES_FILE: Final = SITES_DIR / "sites.yaml"
SITES_SCHEMA_FILE: Final = SITES_DIR / "sites.schema.json"

# Plan: 06-testing.md#site-registry-format ("200 m to 1 km a side").
BBOX_SIDE_MIN_M: Final = 200.0
BBOX_SIDE_MAX_M: Final = 1000.0
# Viewpoints must lie within the site bbox expanded by this margin.
VIEWPOINT_MARGIN_M: Final = 1000.0
# Altitude bands (metres above ground) per standard viewpoint.
VIEWPOINT_ALT_M: Final = {"VP1": (1.0, 5.0), "VP2": (100.0, 200.0), "VP3": (400.0, 700.0)}


class SiteRegistryError(ConfigError, ValueError):
    """sites.yaml is unreadable, fails the schema, or has a range error.

    Subclasses ``ConfigError`` (exit code 2, like region config) and ``ValueError``.
    """


@dataclass(frozen=True)
class Viewpoint:
    id: str
    kind: str
    lat: float
    lon: float
    alt_m_agl: float
    heading_deg: float
    pitch_deg: float
    preset: str | None


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    status: str
    purpose: str
    region: str
    bbox: tuple[float, float, float, float]
    photogrammetry: bool
    inventory_coverage: bool
    flight: str | None
    viewpoints: tuple[Viewpoint, ...]
    description: str
    ground_truth: bool
    time_local: str
    weather: str


@functools.cache
def _schema() -> dict[str, Any]:
    try:
        text = SITES_SCHEMA_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise SiteRegistryError(f"{SITES_SCHEMA_FILE}: cannot read schema: {exc}") from exc
    return cast("dict[str, Any]", json.loads(text))


def _read_registry(path: Path) -> dict[str, Any]:
    label = str(path)
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except OSError as exc:
        raise SiteRegistryError(f"{label}: cannot read site registry: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise SiteRegistryError(f"{label}: not valid UTF-8: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SiteRegistryError(f"{label}: invalid YAML: {exc}") from exc
    if data is None:
        raise SiteRegistryError(f"{label}: file is empty")
    if not isinstance(data, dict):
        raise SiteRegistryError(f"{label}: top level must be a mapping, got {type(data).__name__}")
    return cast("dict[str, Any]", data)


def _schema_problems(data: dict[str, Any]) -> list[str]:
    validator = make_validator(_schema())
    problems = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = ".".join(str(p) for p in err.absolute_path) or "<root>"
        problems.append(f"{where}: {err.message}")
    return problems


def _viewpoint(raw: dict[str, Any]) -> Viewpoint:
    return Viewpoint(
        id=str(raw["id"]),
        kind=str(raw["kind"]),
        lat=float(raw["lat"]),
        lon=float(raw["lon"]),
        alt_m_agl=float(raw["alt_m_agl"]),
        heading_deg=float(raw["heading_deg"]),
        pitch_deg=float(raw["pitch_deg"]),
        preset=None if raw["preset"] is None else str(raw["preset"]),
    )


def _site(site_id: str, raw: dict[str, Any]) -> Site:
    bbox = cast("list[float]", raw["bbox"])
    return Site(
        id=site_id,
        name=str(raw["name"]),
        status=str(raw["status"]),
        purpose=str(raw["purpose"]),
        region=str(raw["region"]),
        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        photogrammetry=bool(raw["photogrammetry"]),
        inventory_coverage=bool(raw["inventory_coverage"]),
        flight=None if raw["flight"] is None else str(raw["flight"]),
        viewpoints=tuple(_viewpoint(vp) for vp in raw["viewpoints"]),
        description=str(raw["description"]),
        ground_truth=bool(raw["ground_truth"]),
        time_local=str(raw["time_local"]),
        weather=str(raw["weather"]),
    )


def _range_problems(site: Site) -> Iterable[str]:
    """Rules for a site with status: defined. Each message starts with the site id."""
    prefix = f"site {site.id}"
    try:
        bbox = Bbox.from_list(site.bbox)
    except ValueError as exc:
        yield f"{prefix}: bbox {list(site.bbox)} is invalid: {exc}"
        return

    width, height = bbox.width_m(), bbox.height_m()
    for side, metres in (("width", width), ("height", height)):
        if not BBOX_SIDE_MIN_M <= metres <= BBOX_SIDE_MAX_M:
            yield (
                f"{prefix}: bbox {side} {metres:.0f} m is outside "
                f"{BBOX_SIDE_MIN_M:.0f} m to {BBOX_SIDE_MAX_M:.0f} m"
            )

    margin_box = bbox.buffer_m(VIEWPOINT_MARGIN_M)
    for vp in site.viewpoints:
        low, high = VIEWPOINT_ALT_M[vp.id]
        if not low <= vp.alt_m_agl <= high:
            yield (f"{prefix}: {vp.id} alt_m_agl {vp.alt_m_agl:g} is outside {low:g} to {high:g} m")
        if not margin_box.contains(vp.lon, vp.lat):
            yield (
                f"{prefix}: {vp.id} ({vp.lat:g}, {vp.lon:g}) is outside the bbox "
                f"expanded by {VIEWPOINT_MARGIN_M:.0f} m"
            )


def load_sites(path: Path = SITES_FILE) -> dict[str, Site]:
    """Load and check the site registry. Returns ``{site_id: Site}`` in file order.

    Raises :class:`SiteRegistryError` (a ``ValueError``) listing every problem, each prefixed
    with the file path and, for range errors, the site id.
    """
    path = Path(path)
    label = str(path)
    data = _read_registry(path)

    problems = _schema_problems(data)
    if problems:
        raise SiteRegistryError("\n".join(f"{label}: {p}" for p in problems))

    sites: dict[str, Site] = {}
    range_problems: list[str] = []
    for site_id, raw in cast("dict[str, dict[str, Any]]", data["sites"]).items():
        site = _site(site_id, raw)
        sites[site_id] = site
        if site.status == "defined":
            range_problems.extend(_range_problems(site))

    if range_problems:
        raise SiteRegistryError("\n".join(f"{label}: {p}" for p in range_problems))
    logger.debug("loaded %d test sites from %s", len(sites), label)
    return sites


def get_site(site_id: str, path: Path = SITES_FILE) -> Site:
    """Return one site. Raises ``KeyError`` listing the known ids if it is not in the registry."""
    sites = load_sites(path)
    try:
        return sites[site_id]
    except KeyError:
        known = ", ".join(sorted(sites)) or "none"
        raise KeyError(f"unknown site {site_id!r}; known sites: {known}") from None
