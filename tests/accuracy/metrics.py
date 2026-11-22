"""Accuracy metrics of a ``palms.geojson`` against hand-labelled ground truth (TEST-010).

The single implementation of matching, metrics and thresholds for the project. It gates Phase 4
(TEST-012) and palmscan's in-run QA (SCAN-029) imports it; never copy it into ``palmscan``.
Spec: ``plans/detailed/06-testing.md#matching-algorithm``, ``#metric-definitions``, ``#thresholds``.

Public API (kept stable, SCAN-029 depends on it)::

    match(pred_xy, gt_xy, radius_m) -> list[(pred_index, gt_index, distance_m)]
    evaluate(pred_fc, gt_fc, area, *, radius_m, profile) -> dict
    load_thresholds(site, path=None, overrides=None) -> dict
    check_thresholds(result, thresholds) -> list[str]        # failures only
    unchecked_thresholds(result, thresholds) -> list[str]    # "not checked" lines

Inputs are plain dicts and a shapely polygon, so nothing here touches the disk except the CLI and
``load_thresholds``. ``pred_fc`` is a ``palms.geojson`` FeatureCollection, ``gt_fc`` a
``ground_truth.geojson`` FeatureCollection (``tests.accuracy.gt``), ``area`` the labelled area
polygon in EPSG:4326 (``gt.load_labeled_area``) or its GeoJSON. ``profile`` is a mapping with the
optional keys ``pred_detected_by`` (list or null) and ``gt_context`` (list or null), plus an
optional ``name``; a profile entry of ``load_thresholds(...)["profiles"]`` is one.

Matching is optimal and deterministic: predictions and ground truth are sorted by id, projected to
an azimuthal equidistant CRS centred on the area, and paired one-to-one by
``scipy.optimize.linear_sum_assignment`` (the most in-radius pairs first, then the least total
distance). Height classes come from ``tests.accuracy.gt.height_class``.

Thresholds: ``tests/accuracy/thresholds.yaml``, overridden per site by ``meta.yaml`` ``thresholds:``
and by the CLI (``--radius``). A ``null`` threshold is never checked. A threshold that is set but
whose metric is undefined fails (precision, recall, position error: nothing to measure means the
gate cannot pass) except height error and species accuracy, which are "not checked" when no matched
palm has the reference; both are listed by :func:`unchecked_thresholds`.

CLI (exit 0 all checked thresholds pass, 1 a threshold failed, 2 input error)::

    python -m tests.accuracy.metrics evaluate --site T1 --pred build/scan/<region>/palms.geojson \
        [--profile lidar_only | --all-profiles] [--radius 3.0] [--label phase4] [--write]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from palmcore import geo
from palmcore.contract import validate_palms
from palmcore.errors import EXIT_CONFIG, EXIT_OK, EXIT_UNEXPECTED, ConfigError
from palmcore.log import get_logger
from tests.accuracy.gt import (
    ACCURACY_DIR,
    META_FILE,
    GroundTruthError,
    height_class,
    load_ground_truth,
    load_labeled_area,
    load_meta,
    site_dir,
)
from tests.helpers.fixtures import REPO_ROOT

logger = get_logger(__name__)

THRESHOLDS_FILE: Final = ACCURACY_DIR / "thresholds.yaml"
SPECIES_KEYS_FILE: Final = REPO_ROOT / "palmscan" / "data" / "species_keys.yaml"
UNKNOWN: Final = "unknown"
_BIG_COST: Final = 1e9  # cost of an out-of-radius pair; only the cardinality-first effect matters
_DECIMALS: Final = 4
DEFAULT_PROFILE: Final = "combined"  # CLI default only; the profile itself lives in the YAML
DEFAULT_LABEL: Final = "run"


# --- matching -------------------------------------------------------------------------------


def match(
    pred_xy: Sequence[Sequence[float]] | np.ndarray,
    gt_xy: Sequence[Sequence[float]] | np.ndarray,
    radius_m: float,
) -> list[tuple[int, int, float]]:
    """One-to-one optimal matching of two point sets in a metric CRS.

    Pairs farther apart than ``radius_m`` never match. Among the allowed pairs the solver takes the
    most pairs first and the smallest total distance second (out-of-radius entries cost 1e9).
    Returns ``(pred_index, gt_index, distance_m)`` sorted by prediction index. Deterministic for a
    given input order; :func:`evaluate` sorts its inputs by id first.
    """
    pred = np.asarray(pred_xy, dtype=float).reshape(-1, 2)
    gt = np.asarray(gt_xy, dtype=float).reshape(-1, 2)
    if len(pred) == 0 or len(gt) == 0:
        return []
    dist = np.hypot(pred[:, None, 0] - gt[None, :, 0], pred[:, None, 1] - gt[None, :, 1])
    cost = np.where(dist > radius_m, _BIG_COST, dist)
    rows, cols = linear_sum_assignment(cost)
    return [
        (int(r), int(c), float(dist[r, c]))
        for r, c in zip(rows, cols, strict=True)
        if dist[r, c] <= radius_m
    ]


# --- helpers --------------------------------------------------------------------------------


def _rnd(value: float | None) -> float | None:
    return None if value is None else round(float(value), _DECIMALS)


def _stats(values: Sequence[float]) -> dict[str, Any]:
    """n, median, mean, p90 (linear percentile); None statistics when n is 0."""
    if not values:
        return {"n": 0, "median": None, "mean": None, "p90": None}
    arr = np.asarray(values, dtype=float)
    return {
        "n": len(values),
        "median": _rnd(np.median(arr)),
        "mean": _rnd(np.mean(arr)),
        "p90": _rnd(np.percentile(arr, 90, method="linear")),
    }


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else _rnd(num / den)


def _as_geometry(area: BaseGeometry | Mapping[str, Any]) -> BaseGeometry:
    if isinstance(area, BaseGeometry):
        return area
    data: Any = area
    if data.get("type") == "FeatureCollection":
        data = data["features"][0]
    if data.get("type") == "Feature":
        data = data["geometry"]
    return shape(data)


def _features(fc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    feats = fc.get("features")
    if not isinstance(feats, list):
        raise ConfigError("FeatureCollection has no 'features' list")
    return feats


def _lonlat(feature: Mapping[str, Any]) -> tuple[float, float]:
    lon, lat = feature["geometry"]["coordinates"][:2]
    return float(lon), float(lat)


def _pred_id(feature: Mapping[str, Any], index: int) -> str:
    pid = (feature.get("properties") or {}).get("palm_id", feature.get("id"))
    return str(pid) if pid is not None else f"pred[{index}]"


def _gt_id(feature: Mapping[str, Any], index: int) -> str:
    gid = (feature.get("properties") or {}).get("gt_id", feature.get("id"))
    return str(gid) if gid is not None else f"gt[{index}]"


def _registry_keys() -> set[str] | None:
    try:
        data = yaml.safe_load(SPECIES_KEYS_FILE.read_text(encoding="utf-8"))
        return {str(item["key"]) for item in data["keys"]}
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return None


# --- evaluate -------------------------------------------------------------------------------


def evaluate(
    pred_fc: Mapping[str, Any],
    gt_fc: Mapping[str, Any],
    area: BaseGeometry | Mapping[str, Any],
    *,
    radius_m: float,
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Match predictions to ground truth and compute every metric (see the module docstring).

    Returns a JSON-serialisable dict: ``profile``, ``radius_m``, ``counts`` (n_pred, n_gt, tp, fp,
    fn, ignored, and the ignored_* breakdown), ``precision``, ``recall``, ``f1``,
    ``position_error_m``, ``height_error_m`` (plus ``bias``), ``height_class_agreement``,
    ``species`` (accuracy, confusion, by_species_source), ``fp_ids``, ``fn_ids`` and
    ``unregistered_species``. Ratios are ``None`` when their denominator is 0.
    """
    if not radius_m > 0:
        raise ConfigError(f"match radius must be positive, got {radius_m}")
    profile = profile or {}
    detected_by = profile.get("pred_detected_by")
    contexts = profile.get("gt_context")
    polygon = _as_geometry(area)

    # 1. predictions inside the area; 2. profile filters. Sorted by id for a stable assignment.
    preds: list[tuple[str, Mapping[str, Any]]] = []
    outside = filtered_pred = 0
    for i, feat in enumerate(_features(pred_fc)):
        if not polygon.covers(Point(*_lonlat(feat))):
            outside += 1
        elif detected_by is not None and feat["properties"]["detected_by"] not in detected_by:
            filtered_pred += 1
        else:
            preds.append((_pred_id(feat, i), feat))
    gts: list[tuple[str, Mapping[str, Any]]] = []
    filtered_gt = 0
    for i, feat in enumerate(_features(gt_fc)):
        if contexts is not None and feat["properties"]["context"] not in contexts:
            filtered_gt += 1
        else:
            gts.append((_gt_id(feat, i), feat))
    preds.sort(key=lambda item: item[0])
    gts.sort(key=lambda item: item[0])

    # 3. local metric CRS centred on the area; 4-5. optimal one-to-one assignment.
    centroid = polygon.centroid
    crs = f"+proj=aeqd +lat_0={centroid.y:.9f} +lon_0={centroid.x:.9f} +datum=WGS84 +units=m"

    def project(items: list[tuple[str, Mapping[str, Any]]]) -> np.ndarray:
        if not items:
            return np.empty((0, 2))
        lons, lats = zip(*(_lonlat(f) for _, f in items), strict=True)
        xs, ys = geo.to_local(lons, lats, crs)
        return np.column_stack([xs, ys])

    matches = match(project(preds), project(gts), radius_m)
    matched_p = {p for p, _, _ in matches}
    matched_g = {g for _, g, _ in matches}

    # 6. classify.
    tp = len(matches)
    fp_ids = [pid for i, (pid, _) in enumerate(preds) if i not in matched_p]
    fn_ids: list[str] = []
    ignored = 0
    for j, (gid, feat) in enumerate(gts):
        if j in matched_g:
            continue
        if feat["properties"]["confidence"] == "high":
            fn_ids.append(gid)
        else:
            ignored += 1
    fp, fn = len(fp_ids), len(fn_ids)

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and precision + recall > 0:
        f1 = _rnd(2 * precision * recall / (precision + recall))
    elif precision is not None and recall is not None:
        f1 = 0.0

    # Metrics over matched pairs.
    pos_err: list[float] = []
    h_abs: list[float] = []
    h_signed: list[float] = []
    cls_n = cls_ok = 0
    sp_n = sp_ok = 0
    confusion: dict[str, Counter[str]] = {}
    by_source: dict[str, list[int]] = {}
    for p, g, dist in matches:
        pp = preds[p][1]["properties"]
        gp = gts[g][1]["properties"]
        pos_err.append(dist)
        ref = gp.get("height_ref_m")
        if ref is not None:
            diff = float(pp["height_m"]) - float(ref)
            h_abs.append(abs(diff))
            h_signed.append(diff)
        if gp["height_class"] != UNKNOWN:
            cls_n += 1
            cls_ok += height_class(float(pp["height_m"])) == gp["height_class"]
        if gp["species"] != UNKNOWN:
            sp_n += 1
            hit = pp["species"] == gp["species"]
            sp_ok += hit
            confusion.setdefault(gp["species"], Counter())[pp["species"]] += 1
            counts = by_source.setdefault(str(pp["species_source"]), [0, 0])
            counts[0] += 1
            counts[1] += hit

    height_stats = _stats(h_abs)
    height_stats["bias"] = _rnd(np.median(h_signed)) if h_signed else None

    registry = _registry_keys()
    unregistered: list[str] = []
    if registry is not None:
        used = {str(f["properties"]["species"]) for _, f in preds}
        used |= {str(f["properties"]["species"]) for _, f in gts}
        unregistered = sorted(used - registry - {UNKNOWN})

    return {
        "profile": profile.get("name"),
        "radius_m": radius_m,
        "counts": {
            "n_pred": len(preds),
            "n_gt": len(gts),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "ignored": ignored,
            "ignored_pred_outside_area": outside,
            "ignored_pred_profile": filtered_pred,
            "ignored_gt_profile": filtered_gt,
        },
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "position_error_m": _stats(pos_err),
        "height_error_m": height_stats,
        "height_class_agreement": {
            "n": cls_n,
            "correct": cls_ok,
            "agreement": _ratio(cls_ok, cls_n),
        },
        "species": {
            "n": sp_n,
            "correct": sp_ok,
            "accuracy": _ratio(sp_ok, sp_n),
            "confusion": {
                gt_sp: dict(sorted(row.items())) for gt_sp, row in sorted(confusion.items())
            },
            "by_species_source": {
                src: {"n": n, "correct": ok, "accuracy": _ratio(ok, n)}
                for src, (n, ok) in sorted(by_source.items())
            },
        },
        "fp_ids": fp_ids,
        "fn_ids": fn_ids,
        "unregistered_species": unregistered,
    }


# --- thresholds -----------------------------------------------------------------------------


def _merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    """Deep merge of mappings; any non-mapping value (including null) in ``over`` replaces."""
    out = copy.deepcopy(dict(base))
    for key, value in over.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def load_thresholds(
    site: str | None,
    path: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Thresholds for a site: ``thresholds.yaml`` < site ``meta.yaml`` ``thresholds:`` < overrides.

    ``path`` replaces ``tests/accuracy/thresholds.yaml``; ``overrides`` has the same shape as the
    file (for example ``{"match_radius_m": 1.5}`` or ``{"profiles": {"combined": {"recall_min":
    None}}}``) and wins over everything; ``root`` replaces ``tests/accuracy`` for the site folder.
    ``site=None`` skips the meta step. A site folder without ``meta.yaml`` adds no overrides.
    Mappings merge key by key. Returns ``{"match_radius_m", "profiles", ...}``.
    """
    merged = _read_yaml_mapping(path or THRESHOLDS_FILE)
    if site is not None:
        meta_path = site_dir(site, root) / META_FILE
        if meta_path.is_file():
            site_over = load_meta(site, root).get("thresholds")
            if site_over is not None:
                if not isinstance(site_over, Mapping):
                    raise ConfigError(f"{meta_path}: thresholds must be a mapping")
                merged = _merge(merged, site_over)
    if overrides:
        merged = _merge(merged, overrides)
    if not isinstance(merged.get("profiles"), Mapping) or not merged["profiles"]:
        raise ConfigError("thresholds need a non-empty 'profiles' mapping")
    radius = merged.get("match_radius_m")
    if not isinstance(radius, int | float) or isinstance(radius, bool) or not radius > 0:
        raise ConfigError(f"match_radius_m must be a positive number, got {radius!r}")
    return merged


def profile_for(thresholds: Mapping[str, Any], name: str) -> dict[str, Any]:
    """The named profile entry, with ``name`` set. Raises ConfigError for an unknown name."""
    profiles = thresholds["profiles"]
    if name not in profiles:
        raise ConfigError(f"unknown profile {name!r}; known: {', '.join(sorted(profiles))}")
    return {**profiles[name], "name": name}


# (threshold key, direction, label, result lookup, undefined policy)
_CHECKS: Final = (
    ("precision_min", "min", "precision", lambda r: r["precision"], "fail"),
    ("recall_min", "min", "recall", lambda r: r["recall"], "fail"),
    (
        "position_error_median_max_m",
        "max",
        "position error median (m)",
        lambda r: r["position_error_m"]["median"],
        "fail",
    ),
    (
        "height_error_median_max_m",
        "max",
        "height error median (m)",
        lambda r: r["height_error_m"]["median"],
        "skip",
    ),
    ("species_accuracy_min", "min", "species accuracy", lambda r: r["species"]["accuracy"], "skip"),
)


def _threshold_report(
    result: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    name = result.get("profile")
    profiles = thresholds.get("profiles", {})
    if name not in profiles:
        raise ConfigError(f"result profile {name!r} is not in the thresholds profiles")
    profile = profiles[name]
    failures: list[str] = []
    unchecked: list[str] = []
    for key, direction, label, getter, undefined in _CHECKS:
        limit = profile[key] if key in profile else thresholds.get(key)
        if limit is None:
            unchecked.append(f"{key}: not checked (null)")
            continue
        value = getter(result)
        if value is None:
            if undefined == "fail":
                failures.append(f"{label} is undefined (no data) but {key} = {limit} is set")
            else:
                unchecked.append(f"{key}: not checked (no data)")
        elif direction == "min" and value < limit:
            failures.append(f"{label} {value:.3f} is below {key} = {limit}")
        elif direction == "max" and value > limit:
            failures.append(f"{label} {value:.3f} is above {key} = {limit}")
    return failures, unchecked


def check_thresholds(result: Mapping[str, Any], thresholds: Mapping[str, Any]) -> list[str]:
    """Failure messages for ``result`` against ``thresholds`` (empty list: all checked pass).

    ``thresholds`` is the output of :func:`load_thresholds`; the profile named in
    ``result["profile"]`` supplies ``precision_min`` and ``recall_min`` (and wins over a global
    value of the same key). ``null`` thresholds are skipped; see :func:`unchecked_thresholds`.
    """
    return _threshold_report(result, thresholds)[0]


def unchecked_thresholds(result: Mapping[str, Any], thresholds: Mapping[str, Any]) -> list[str]:
    """Thresholds that were not checked (``null``, or no data for height and species)."""
    return _threshold_report(result, thresholds)[1]


# --- reports --------------------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def format_markdown(
    result: Mapping[str, Any],
    *,
    site: str,
    failures: Sequence[str] = (),
    unchecked: Sequence[str] = (),
    label: str = DEFAULT_LABEL,
) -> str:
    """Compact Markdown summary of one result."""
    c = result["counts"]
    pos, hgt = result["position_error_m"], result["height_error_m"]
    hca, sp = result["height_class_agreement"], result["species"]
    lines = [
        f"## Accuracy {site} / {result['profile']} / {label}",
        "",
        f"Match radius {result['radius_m']:g} m. "
        f"TP {c['tp']}, FP {c['fp']}, FN {c['fn']}, ignored {c['ignored']} "
        f"(predictions outside area {c['ignored_pred_outside_area']}, "
        f"filtered by profile {c['ignored_pred_profile']}; "
        f"ground truth filtered {c['ignored_gt_profile']}).",
        "",
        "| Metric | Value | n |",
        "|---|---|---|",
        f"| Precision | {_fmt(result['precision'])} | {c['tp'] + c['fp']} |",
        f"| Recall | {_fmt(result['recall'])} | {c['tp'] + c['fn']} |",
        f"| F1 | {_fmt(result['f1'])} | |",
        f"| Position error median / mean / p90 (m) | {_fmt(pos['median'], 2)} / "
        f"{_fmt(pos['mean'], 2)} / {_fmt(pos['p90'], 2)} | {pos['n']} |",
        f"| Height error median / mean / p90 / bias (m) | {_fmt(hgt['median'], 2)} / "
        f"{_fmt(hgt['mean'], 2)} / {_fmt(hgt['p90'], 2)} / {_fmt(hgt['bias'], 2)} | {hgt['n']} |",
        f"| Height-class agreement | {_fmt(hca['agreement'])} | {hca['n']} |",
        f"| Species accuracy | {_fmt(sp['accuracy'])} | {sp['n']} |",
    ]
    for src, row in sp["by_species_source"].items():
        lines.append(f"| Species accuracy, source {src} | {_fmt(row['accuracy'])} | {row['n']} |")
    if result["fp_ids"]:
        lines += ["", f"FP: {', '.join(result['fp_ids'])}"]
    if result["fn_ids"]:
        lines += ["", f"FN: {', '.join(result['fn_ids'])}"]
    if result["unregistered_species"]:
        lines += [
            "",
            "Species not in palmscan/data/species_keys.yaml: "
            + ", ".join(result["unregistered_species"]),
        ]
    lines += ["", "Thresholds: " + ("FAIL" if failures else "pass")]
    lines += [f"- FAIL: {msg}" for msg in failures]
    lines += [f"- {msg}" for msg in unchecked]
    return "\n".join(lines) + "\n"


def errors_geojson(
    result: Mapping[str, Any], pred_fc: Mapping[str, Any], gt_fc: Mapping[str, Any]
) -> dict[str, Any]:
    """FP and FN points for QGIS review: ``error`` (fp|fn) plus ``palm_id`` or ``gt_id``."""
    fp = set(result["fp_ids"])
    fn = set(result["fn_ids"])
    out: list[dict[str, Any]] = []
    for i, feat in enumerate(_features(pred_fc)):
        pid = _pred_id(feat, i)
        if pid in fp:
            out.append(_point(feat, {"error": "fp", "palm_id": pid}))
    for i, feat in enumerate(_features(gt_fc)):
        gid = _gt_id(feat, i)
        if gid in fn:
            out.append(_point(feat, {"error": "fn", "gt_id": gid}))
    out.sort(
        key=lambda f: (
            f["properties"]["error"],
            str(f["properties"].get("palm_id", "")),
            str(f["properties"].get("gt_id", "")),
        )
    )
    return {"type": "FeatureCollection", "features": out}


def _point(feature: Mapping[str, Any], props: dict[str, Any]) -> dict[str, Any]:
    lon, lat = _lonlat(feature)
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# --- CLI ------------------------------------------------------------------------------------


def _load_predictions(path: Path) -> dict[str, Any]:
    """Read and contract-check a palms.geojson. Any problem is an input error (exit 2)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"prediction file not found: {path}") from None
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError(f"{path}: top-level JSON value must be an object")
    report = validate_palms(doc, mode="read")
    if not report.ok:
        shown = "\n  ".join(report.error_strings(10))
        raise ConfigError(f"{path} is not a valid palms.geojson:\n  {shown}")
    return doc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.accuracy.metrics",
        description="Accuracy metrics of a palms.geojson against a site's ground truth.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser(
        "evaluate",
        help="evaluate predictions (exit 0 pass, 1 threshold failed, 2 input error)",
    )
    ev.add_argument("--site", required=True, help="site id, for example T1")
    ev.add_argument("--pred", type=Path, required=True, help="palms.geojson to evaluate")
    which = ev.add_mutually_exclusive_group()
    which.add_argument(
        "--profile",
        default=None,
        help=f"profile name in thresholds.yaml (default {DEFAULT_PROFILE})",
    )
    which.add_argument("--all-profiles", action="store_true", help="evaluate every profile")
    ev.add_argument("--radius", type=float, default=None, help="match radius in metres")
    ev.add_argument("--label", default=DEFAULT_LABEL, help="run label used in result file names")
    ev.add_argument("--write", action="store_true", help="save .json, .md and _errors.geojson")
    ev.add_argument("--thresholds", type=Path, default=None, help="alternate thresholds.yaml")
    ev.add_argument("--root", type=Path, default=None, help="alternate tests/accuracy folder")
    ev.add_argument("--date", default=None, help="date for result file names (YYYY-MM-DD)")
    return parser


def _evaluate_command(args: argparse.Namespace) -> int:
    overrides = {"match_radius_m": args.radius} if args.radius is not None else None
    thresholds = load_thresholds(args.site, args.thresholds, overrides, root=args.root)
    names = (
        sorted(thresholds["profiles"]) if args.all_profiles else [args.profile or DEFAULT_PROFILE]
    )
    profiles = [profile_for(thresholds, n) for n in names]
    pred_fc = _load_predictions(args.pred)
    gt_fc = load_ground_truth(args.site, args.root)
    area = load_labeled_area(args.site, args.root)
    stamp = args.date or date.today().isoformat()
    if args.write and not args.label.replace("-", "").replace("_", "").isalnum():
        raise ConfigError(f"--label may only hold letters, digits, - and _: {args.label!r}")

    exit_code = EXIT_OK
    for profile in profiles:
        result = evaluate(
            pred_fc, gt_fc, area, radius_m=thresholds["match_radius_m"], profile=profile
        )
        failures, unchecked = _threshold_report(result, thresholds)
        result["thresholds"] = {"failures": failures, "not_checked": unchecked}
        text = format_markdown(
            result, site=args.site, failures=failures, unchecked=unchecked, label=args.label
        )
        print(text)
        if failures:
            exit_code = EXIT_UNEXPECTED
        if args.write:
            results_dir = site_dir(args.site, args.root) / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            stem = f"{stamp}_{args.label}_{profile['name']}"
            payload = {"site": args.site, "label": args.label, "date": stamp, **result}
            _write(results_dir / f"{stem}.json", json.dumps(payload, indent=2) + "\n")
            _write(results_dir / f"{stem}.md", text)
            _write(
                results_dir / f"{stem}_errors.geojson",
                json.dumps(errors_geojson(result, pred_fc, gt_fc), indent=2) + "\n",
            )
            print(f"wrote {results_dir / stem}.json, .md, _errors.geojson")
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            return _evaluate_command(args)
    except (ConfigError, GroundTruthError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    raise AssertionError(f"unhandled command {args.command!r}")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
