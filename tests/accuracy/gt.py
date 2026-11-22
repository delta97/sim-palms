"""Hand-labelled ground truth for the palm accuracy tests: format, checks and CLI (TEST-009).

Per test site, under ``tests/accuracy/<site>/``:

- ``ground_truth.geojson``: one Point per palm, EPSG:4326. Checked by ``ground_truth.schema.json``.
- ``labeled_area.geojson``: one Polygon, the area that was swept. Every point lies inside it.
- ``meta.yaml``: imagery, labellers, dates, notes, optional ``thresholds:`` overrides.

Full format and the labelling procedure: ``plans/detailed/06-testing.md#ground-truth-format`` and
``tests/accuracy/LABELING.md``.

How TEST-010 (``tests.accuracy.metrics``) reads a prediction against a label:

- position: the point geometry; match radius R (default 3.0 m) in a local azimuthal projection.
- species: ``species`` (compare only where it is not ``unknown``); ``species_basis`` for the split.
- height: ``height_class`` (class agreement, edges from :func:`height_class`) and ``height_ref_m``
  (CHM maximum, a derived value that checks palmscan's height extraction, not LiDAR itself).
- confidence: ``confidence == "low"`` points are ignored when unmatched, never counted as misses.
- context: filters the ground truth per profile (``context`` values in ``thresholds.yaml``).

Predictions are ``palms.geojson`` features (``schemas/palms.geojson.schema.json``): position from
the geometry, ``height_m`` for the class, ``species``, ``detected_by`` for the profile filter.

CLI (run from the repository root with the project venv)::

    python -m tests.accuracy.gt init-site T1
    python -m tests.accuracy.gt validate T1
    python -m tests.accuracy.gt fill-heights T1 --chm <chm.tif> [--radius-m 1.5]
    python -m tests.accuracy.gt next-id T1

Exit codes: 0 ok; 1 ``validate`` found a problem in the data; 2 bad input or config (missing file,
unreadable file, placeholder site, refused overwrite).
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, cast

import numpy as np
import yaml
from pyproj import Transformer
from shapely.geometry import Point, Polygon, shape
from shapely.validation import explain_validity

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmcore.schemas import make_validator
from tests.helpers.fixtures import REPO_ROOT
from tests.helpers.sites import SITES_FILE, get_site

logger = get_logger(__name__)

ACCURACY_DIR: Final = REPO_ROOT / "tests" / "accuracy"
SCHEMA_FILE: Final = ACCURACY_DIR / "ground_truth.schema.json"
GT_FILE: Final = "ground_truth.geojson"
AREA_FILE: Final = "labeled_area.geojson"
META_FILE: Final = "meta.yaml"

SITE_RE: Final = re.compile(r"^T[0-9]+$")
GT_ID_RE: Final = re.compile(r"^(T[0-9]+)-gt-([0-9]{4})$")
COORD_DECIMALS: Final = 7
CHM_RADIUS_DEFAULT_M: Final = 1.5
MAX_PROBLEMS_PRINTED: Final = 50
WGS84_CRS_NAMES: Final = (
    "EPSG:4326",
    "urn:ogc:def:crs:EPSG::4326",
    "urn:ogc:def:crs:OGC:1.3:CRS84",
)
META_REQUIRED: Final = ("site", "imagery", "labelers", "labeled_on", "notes")
IMAGERY_REQUIRED: Final = ("source", "date", "resolution_m")
GT_COUNT_FIELDS: Final = ("context", "confidence", "height_class", "species")


class GroundTruthError(ConfigError):
    """Missing or unreadable input, a placeholder site, or a refused overwrite (exit code 2)."""


@dataclass
class SiteReport:
    """Result of :func:`validate_site`. ``problems`` empty means the site passes."""

    site: str
    n_points: int = 0
    problems: list[str] = field(default_factory=list)
    counts: dict[str, Counter[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


def height_class(height_m: float) -> str:
    """Height class of a height in metres: S < 8, M 8 to < 15, T 15 to < 25, X >= 25.

    The single definition of the classes; TEST-010 imports it for predictions.
    """
    if height_m < 8.0:
        return "S"
    if height_m < 15.0:
        return "M"
    if height_m < 25.0:
        return "T"
    return "X"


# --- reading and writing --------------------------------------------------------------------


def site_dir(site: str, root: Path | None = None) -> Path:
    """The folder of one site. ``root`` replaces ``tests/accuracy`` (tests use it)."""
    if not SITE_RE.fullmatch(site):
        raise GroundTruthError(f"site id must look like T1, got {site!r}")
    return (ACCURACY_DIR if root is None else Path(root)) / site


@functools.cache
def _schema() -> dict[str, Any]:
    try:
        text = SCHEMA_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise GroundTruthError(f"cannot read schema {SCHEMA_FILE}: {exc}") from exc
    return cast("dict[str, Any]", json.loads(text))


def _read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GroundTruthError(f"missing file: {path}") from None
    except OSError as exc:
        raise GroundTruthError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GroundTruthError(f"{path} is not valid JSON: {exc}") from exc


def _read_meta(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GroundTruthError(f"missing file: {path}") from None
    except OSError as exc:
        raise GroundTruthError(f"cannot read {path}: {exc}") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise GroundTruthError(f"{path} is not valid YAML: {exc}") from exc


def _write_json(path: Path, data: object) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# --- checks ---------------------------------------------------------------------------------


def _fmt_path(parts: Iterable[object]) -> str:
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def _schema_problems(data: object, label: str) -> list[str]:
    validator = make_validator(_schema())
    errors = sorted(validator.iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path])
    return [f"{label}: {_fmt_path(e.absolute_path)}: {e.message}" for e in errors]


def _crs_problems(data: dict[str, Any], label: str) -> list[str]:
    crs = data.get("crs")
    if crs is None:
        return []
    name = crs.get("properties", {}).get("name") if isinstance(crs, dict) else None
    if name in WGS84_CRS_NAMES:
        return []
    return [f"{label}: crs is {name!r}; labels must be WGS84 (EPSG:4326)"]


def _area_problems(raw: object, label: str) -> tuple[Polygon | None, list[str]]:
    """Check labeled_area.geojson: one valid Polygon. Returns the polygon when it is usable."""
    if not isinstance(raw, dict):
        return None, [f"{label}: top level must be a GeoJSON object"]
    problems = _crs_problems(raw, label)
    kind = raw.get("type")
    geom: object
    if kind == "FeatureCollection":
        features = raw.get("features")
        if not isinstance(features, list) or len(features) != 1:
            count = len(features) if isinstance(features, list) else 0
            return None, [*problems, f"{label}: must hold exactly one feature, found {count}"]
        first = features[0]
        geom = first.get("geometry") if isinstance(first, dict) else None
    elif kind == "Feature":
        geom = raw.get("geometry")
    else:
        return None, [
            *problems,
            f"{label}: type must be FeatureCollection or Feature, not {kind!r}",
        ]
    if not isinstance(geom, dict) or geom.get("type") != "Polygon":
        return None, [*problems, f"{label}: geometry must be a single Polygon"]
    try:
        poly = cast("Polygon", shape(geom))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return None, [*problems, f"{label}: bad polygon coordinates: {exc}"]
    if poly.is_empty or not poly.is_valid:
        reason = explain_validity(poly) if not poly.is_empty else "empty"
        return None, [*problems, f"{label}: polygon is not valid: {reason}"]
    return poly, problems


def _gt_problems(raw: object, site: str, area: Polygon | None, label: str) -> list[str]:
    """Schema, ids, species/basis agreement, coordinate precision, and containment in the area."""
    problems = _schema_problems(raw, label)
    if isinstance(raw, dict):
        problems = [*_crs_problems(raw, label), *problems]
    if not isinstance(raw, dict) or not isinstance(raw.get("features"), list):
        return problems

    seen_ids: dict[str, int] = {}
    seen_positions: dict[tuple[float, float], str] = {}
    for i, feat in enumerate(raw["features"]):
        if not isinstance(feat, dict) or not isinstance(feat.get("properties"), dict):
            continue  # already reported by the schema check
        props = feat["properties"]
        gt_id = props.get("gt_id")
        where = f"features[{i}]" + (f" {gt_id}" if isinstance(gt_id, str) else "")

        id_match = GT_ID_RE.fullmatch(gt_id) if isinstance(gt_id, str) else None
        if isinstance(gt_id, str) and id_match is not None:
            prefix = id_match.group(1)
            if prefix != site:
                problems.append(
                    f"{label}: {where}: gt_id prefix {prefix} does not match site {site}"
                )
            if gt_id in seen_ids:
                problems.append(
                    f"{label}: {where}: duplicate gt_id (first at features[{seen_ids[gt_id]}])"
                )
            else:
                seen_ids[gt_id] = i

        species = props.get("species")
        basis = props.get("species_basis")
        if (
            isinstance(species, str)
            and isinstance(basis, str)
            and (species == "unknown") != (basis == "unknown")
        ):
            problems.append(
                f"{label}: {where}: species {species!r} and species_basis {basis!r} disagree "
                "(unknown species needs basis unknown, and the reverse)"
            )

        geom = feat.get("geometry")
        coords = geom.get("coordinates") if isinstance(geom, dict) else None
        if not (
            isinstance(coords, list)
            and len(coords) == 2
            and all(isinstance(c, int | float) and not isinstance(c, bool) for c in coords)
        ):
            continue  # already reported by the schema check
        lon, lat = float(coords[0]), float(coords[1])
        for c in (lon, lat):
            if round(c, COORD_DECIMALS) != c:
                problems.append(
                    f"{label}: {where}: coordinate {c!r} has more than {COORD_DECIMALS} decimals; "
                    "save with coordinate precision 7 (see LABELING.md)"
                )
        if area is not None and not area.covers(Point(lon, lat)):
            problems.append(f"{label}: {where}: point is outside labeled_area.geojson")
        key = (lon, lat)
        if key in seen_positions:
            problems.append(f"{label}: {where}: same position as {seen_positions[key]}")
        else:
            seen_positions[key] = where
    return problems


def _tbd_paths(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, str):
        return [prefix or "<root>"] if value.strip() == "TBD" else []
    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            out += _tbd_paths(item, f"{prefix}.{key}" if prefix else str(key))
        return out
    if isinstance(value, list):
        out = []
        for i, item in enumerate(value):
            out += _tbd_paths(item, f"{prefix}[{i}]")
        return out
    return []


def _meta_problems(meta: object, site: str, n_points: int) -> list[str]:
    if not isinstance(meta, dict):
        return [f"{META_FILE}: top level must be a mapping"]
    problems = [f"{META_FILE}: missing key {k!r}" for k in META_REQUIRED if k not in meta]
    if meta.get("site") not in (None, site):
        problems.append(f"{META_FILE}: site is {meta.get('site')!r} but the folder is {site}")
    imagery = meta.get("imagery")
    if isinstance(imagery, dict):
        problems += [
            f"{META_FILE}: imagery is missing {k!r}" for k in IMAGERY_REQUIRED if k not in imagery
        ]
    elif "imagery" in meta:
        problems.append(f"{META_FILE}: imagery must be a mapping with source, date, resolution_m")
    labelers = meta.get("labelers")
    if labelers is not None and not (
        isinstance(labelers, list) and all(isinstance(x, str) and x.strip() for x in labelers)
    ):
        problems.append(f"{META_FILE}: labelers must be a list of names")
    if n_points > 0:
        if not labelers:
            problems.append(f"{META_FILE}: labelers is empty but {GT_FILE} has points")
        if meta.get("labeled_on") in (None, ""):
            problems.append(f"{META_FILE}: labeled_on is not set but {GT_FILE} has points")
    problems += [f"{META_FILE}: {path} is still TBD" for path in _tbd_paths(meta)]
    return problems


def _features(raw: object) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("features"), list):
        return cast("list[Any]", raw["features"])
    return []


def _counts(features: Sequence[object]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {name: Counter() for name in GT_COUNT_FIELDS}
    for feat in features:
        props = feat.get("properties") if isinstance(feat, dict) else None
        if not isinstance(props, dict):
            continue
        for name in GT_COUNT_FIELDS:
            counts[name][str(props.get(name, "missing"))] += 1
    return counts


def validate_site(site: str, root: Path | None = None) -> SiteReport:
    """Run every check on one site folder and collect the problems (does not raise on them)."""
    folder = site_dir(site, root)
    if not folder.is_dir():
        raise GroundTruthError(f"no site folder {folder}; run init-site {site} first")
    gt_raw = _read_json(folder / GT_FILE)
    area_raw = _read_json(folder / AREA_FILE)
    meta_raw = _read_meta(folder / META_FILE)

    area, area_problems = _area_problems(area_raw, AREA_FILE)
    features = _features(gt_raw)
    gt_problems = _gt_problems(gt_raw, site, area, GT_FILE)
    meta_problems = _meta_problems(meta_raw, site, len(features))
    return SiteReport(
        site=site,
        n_points=len(features),
        problems=[*area_problems, *gt_problems, *meta_problems],
        counts=_counts(features),
    )


def _raise_if(problems: list[str]) -> None:
    if not problems:
        return
    shown = problems[:20]
    more = len(problems) - len(shown)
    text = f"{len(problems)} problem(s):\n  " + "\n  ".join(shown)
    if more > 0:
        text += f"\n  ... and {more} more"
    raise GroundTruthError(text)


def load_labeled_area(site: str, root: Path | None = None) -> Polygon:
    """The swept area as a shapely Polygon (EPSG:4326). Raises GroundTruthError if unusable."""
    raw = _read_json(site_dir(site, root) / AREA_FILE)
    poly, problems = _area_problems(raw, AREA_FILE)
    _raise_if(problems)
    if poly is None:  # pragma: no cover - _area_problems reports every None case
        raise GroundTruthError(f"{AREA_FILE}: no usable polygon")
    return poly


def load_ground_truth(site: str, root: Path | None = None) -> dict[str, Any]:
    """The checked ground truth of one site, as the GeoJSON dict.

    Runs the schema, id, species/basis, precision and inside-area checks. Metadata is not checked
    here; :func:`validate_site` does that. Raises GroundTruthError listing every problem found.
    """
    raw = _read_json(site_dir(site, root) / GT_FILE)
    area = load_labeled_area(site, root)
    _raise_if(_gt_problems(raw, site, area, GT_FILE))
    return cast("dict[str, Any]", raw)


def load_meta(site: str, root: Path | None = None) -> dict[str, Any]:
    """The meta.yaml mapping of one site. Only the YAML shape is checked; see validate_site."""
    raw = _read_meta(site_dir(site, root) / META_FILE)
    if not isinstance(raw, dict):
        raise GroundTruthError(f"{META_FILE}: top level must be a mapping")
    return cast("dict[str, Any]", raw)


# --- commands -------------------------------------------------------------------------------


def _bbox_polygon(bbox: Sequence[float], site: str) -> dict[str, Any]:
    lon_min, lat_min, lon_max, lat_max = (round(float(v), COORD_DECIMALS) for v in bbox)
    ring = [
        [lon_min, lat_min],
        [lon_max, lat_min],
        [lon_max, lat_max],
        [lon_min, lat_max],
        [lon_min, lat_min],
    ]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"site": site},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }


META_TEMPLATE: Final = """\
# Ground-truth metadata for {site}. Procedure: tests/accuracy/LABELING.md.
# Replace every TBD before running validate.
site: {site}
imagery:
  source: TBD          # for example USDA NAIP, service and layer name (LABELING.md)
  date: TBD            # capture date of the imagery you labelled on, YYYY-MM-DD
  resolution_m: TBD    # ground sample distance in metres
labelers: []           # one name per line: - "name"
labeled_on: null       # YYYY-MM-DD when labelling is finished
notes: ""              # QGIS version, area swept, anything a reviewer must know
"""


def init_site(site: str, root: Path | None = None, sites_file: Path = SITES_FILE) -> Path:
    """Create ``<root>/<site>/`` with an empty label set, the swept-area skeleton and meta.yaml.

    Refuses placeholder sites (status other than ``defined``) and an existing folder.
    """
    folder = site_dir(site, root)
    try:
        entry = get_site(site, sites_file)
    except KeyError as exc:
        raise GroundTruthError(str(exc.args[0])) from None
    if entry.status != "defined":
        raise GroundTruthError(
            f"site {site} is a {entry.status} in {sites_file}; TEST-100 must define its bbox "
            "before labels can be made"
        )
    if folder.exists():
        raise GroundTruthError(f"{folder} already exists; refusing to overwrite labels")
    folder.mkdir(parents=True)
    _write_json(folder / GT_FILE, {"type": "FeatureCollection", "features": []})
    area = _bbox_polygon(entry.bbox, site)
    _write_json(folder / AREA_FILE, area)
    _write_text(folder / META_FILE, META_TEMPLATE.format(site=site))
    logger.info("created ground-truth skeleton %s", folder)
    return folder


def _chm_peaks(
    chm: Path, lonlat: Sequence[tuple[float, float]], radius_m: float
) -> list[float | None]:
    """CHM maximum within radius_m of each point (cells whose centre is inside the circle).

    Points are reprojected from WGS84 to the CHM CRS. Nodata cells are ignored; a negative peak
    is written as 0.0. Returns None where no valid cell is inside the circle.
    """
    try:
        import rasterio
    except ImportError as exc:
        raise GroundTruthError(
            f"fill-heights needs rasterio (in palmscan's lidar extra: pip install rasterio): {exc}"
        ) from exc

    from rasterio.windows import Window

    out: list[float | None] = []
    with rasterio.open(chm) as src:
        crs = src.crs
        if crs is None or crs.is_geographic:
            raise GroundTruthError(f"CHM {chm} needs a projected CRS in metres")
        if str(crs.linear_units).lower() not in ("metre", "meter"):
            raise GroundTruthError(f"CHM {chm} needs metre units, got {crs.linear_units!r}")
        t = src.transform
        if t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0:
            raise GroundTruthError(f"CHM {chm} must be north-up with no rotation")
        transformer = Transformer.from_crs("EPSG:4326", crs.to_wkt(), always_xy=True)

        for lon, lat in lonlat:
            x, y = transformer.transform(lon, lat)
            col_c = (x - t.c) / t.a
            row_c = (y - t.f) / t.e
            rc = radius_m / t.a
            rr = radius_m / abs(t.e)
            col0 = max(0, math.floor(col_c - rc))
            col1 = min(src.width, math.ceil(col_c + rc) + 1)
            row0 = max(0, math.floor(row_c - rr))
            row1 = min(src.height, math.ceil(row_c + rr) + 1)
            if col0 >= col1 or row0 >= row1:
                out.append(None)
                continue
            window = Window(col0, row0, col1 - col0, row1 - row0)
            data = src.read(1, window=window, masked=True)
            xs = t.c + (np.arange(col0, col1) + 0.5) * t.a
            ys = t.f + (np.arange(row0, row1) + 0.5) * t.e
            dist2 = (xs[np.newaxis, :] - x) ** 2 + (ys[:, np.newaxis] - y) ** 2
            inside = (dist2 <= radius_m * radius_m) & ~np.ma.getmaskarray(data)
            if not inside.any():
                out.append(None)
                continue
            peak = float(np.asarray(data)[inside].max())
            out.append(round(max(peak, 0.0), 1))
    return out


def fill_heights(
    site: str, chm: Path, radius_m: float = CHM_RADIUS_DEFAULT_M, root: Path | None = None
) -> tuple[int, int]:
    """Write ``height_ref_m`` for every point from the CHM. Returns (filled, total)."""
    if not radius_m > 0:
        raise GroundTruthError(f"--radius-m must be positive, got {radius_m}")
    chm = Path(chm)
    if not chm.is_file():
        raise GroundTruthError(f"CHM not found: {chm}")
    gt = load_ground_truth(site, root)
    features = _features(gt)
    lonlat = [
        (float(f["geometry"]["coordinates"][0]), float(f["geometry"]["coordinates"][1]))
        for f in features
    ]
    peaks = _chm_peaks(chm, lonlat, radius_m)
    for feat, value in zip(features, peaks, strict=True):
        feat["properties"]["height_ref_m"] = value
    _write_json(site_dir(site, root) / GT_FILE, gt)
    filled = sum(1 for v in peaks if v is not None)
    return filled, len(features)


def next_id(site: str, root: Path | None = None) -> str:
    """The next free gt_id for a site: one above the highest existing number."""
    raw = _read_json(site_dir(site, root) / GT_FILE)
    numbers = []
    for feat in _features(raw):
        props = feat.get("properties") if isinstance(feat, dict) else None
        gt_id = props.get("gt_id") if isinstance(props, dict) else None
        match = GT_ID_RE.fullmatch(gt_id) if isinstance(gt_id, str) else None
        if match and match.group(1) == site:
            numbers.append(int(match.group(2)))
    number = max(numbers, default=0) + 1
    if number > 9999:
        raise GroundTruthError(f"{site} has no free gt_id left (0001 to 9999 used)")
    return f"{site}-gt-{number:04d}"


# --- CLI ------------------------------------------------------------------------------------


def _count_lines(report: SiteReport) -> list[str]:
    lines = []
    for name in GT_COUNT_FIELDS:
        parts = ", ".join(f"{key}={n}" for key, n in sorted(report.counts[name].items()))
        lines.append(f"by {name}: {parts or 'none'}")
    return lines


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.accuracy.gt",
        description="Ground-truth palm labels: create, check, fill heights, next id.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-site", help="create tests/accuracy/<site>/ skeleton files")
    init.add_argument("site", help="site id, for example T1")
    init.add_argument("--sites", type=Path, default=SITES_FILE, help="site registry file")

    val = sub.add_parser("validate", help="check one site's files (exit 0 ok, 1 problems)")
    val.add_argument("site")

    fill = sub.add_parser("fill-heights", help="write height_ref_m from a CHM GeoTIFF")
    fill.add_argument("site")
    fill.add_argument("--chm", type=Path, required=True, help="CHM GeoTIFF (projected, metres)")
    fill.add_argument(
        "--radius-m",
        type=float,
        default=CHM_RADIUS_DEFAULT_M,
        help=f"search radius around each point (default {CHM_RADIUS_DEFAULT_M})",
    )

    nxt = sub.add_parser("next-id", help="print the next free gt_id")
    nxt.add_argument("site")

    for cmd in (init, val, fill, nxt):
        cmd.add_argument(
            "--root",
            type=Path,
            default=None,
            help="alternate accuracy folder instead of tests/accuracy (tests use this)",
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "init-site":
            folder = init_site(args.site, args.root, args.sites)
            print(f"created {folder}")
            print(
                "next: fill in meta.yaml, label ground_truth.geojson (LABELING.md), then validate"
            )
            return 0

        if args.command == "validate":
            report = validate_site(args.site, args.root)
            for line in _count_lines(report):
                print(line)
            if report.ok:
                print(f"OK: {report.n_points} point(s) at {args.site}")
                return 0
            for problem in report.problems[:MAX_PROBLEMS_PRINTED]:
                print(f"  {problem}")
            hidden = len(report.problems) - MAX_PROBLEMS_PRINTED
            if hidden > 0:
                print(f"  ... and {hidden} more")
            print(f"FAILED: {len(report.problems)} problem(s) at {args.site}")
            return 1

        if args.command == "fill-heights":
            filled, total = fill_heights(args.site, args.chm, args.radius_m, args.root)
            print(
                f"height_ref_m filled for {filled} of {total} point(s); "
                f"{total - filled} left null (no CHM data within {args.radius_m:g} m)"
            )
            return 0

        if args.command == "next-id":
            print(next_id(args.site, args.root))
            return 0
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    raise AssertionError(f"unhandled command {args.command!r}")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
