"""Accuracy section of palmscan's QA: runs the TEST-010 evaluator on a run's palms (SCAN-029).

This module does not match, measure or set targets. TEST-010 (``tests/accuracy/metrics.py``) is the
single implementation; TEST-009 (``tests/accuracy/gt.py``) loads the site's ground truth. Both live
under ``tests/``, which is not part of the wheel, so they are imported from a repository checkout
only. This module adds the SCAN-only fallback height error (W19) and the JSON and Markdown output.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import numpy as np

from palmcore.log import get_logger
from palmscan.config import MergeParams

if TYPE_CHECKING:
    from types import ModuleType

    import geopandas as gpd

logger = get_logger(__name__)

SKIP_WARNING = "accuracy skipped: tests.accuracy not importable"
ACCURACY_FILE = "accuracy.json"
_DECIMALS = 4


class Evaluator(NamedTuple):
    """The two TEST modules this file calls: metrics (TEST-010) and gt (TEST-009)."""

    metrics: ModuleType
    gt: ModuleType


def load_evaluator(repo_root: Path) -> Evaluator | None:
    """Import ``tests.accuracy`` from the checkout at ``repo_root``; None when it is not there.

    The package must resolve to ``repo_root``; an unrelated installed ``tests`` package is refused.
    """
    root = str(Path(repo_root).resolve())
    added = root not in sys.path
    if added:
        sys.path.insert(0, root)
    try:
        metrics = importlib.import_module("tests.accuracy.metrics")
        gt = importlib.import_module("tests.accuracy.gt")
    except ImportError as exc:
        logger.warning("tests.accuracy import failed under %s: %s", root, exc)
        return None
    finally:
        if added and root in sys.path:
            sys.path.remove(root)
    for module in (metrics, gt):
        origin = getattr(module, "__file__", None)
        if origin is None or not Path(origin).resolve().is_relative_to(root):
            logger.warning("tests.accuracy resolves outside %s (%s)", root, origin)
            return None
    return Evaluator(metrics=metrics, gt=gt)


def evaluate_site(
    palms_fc: Mapping[str, Any],
    site: str,
    *,
    repo_root: Path,
    sites_root: Path | None = None,
    profiles: list[str] | None = None,
    radius_m: float | None = None,
    warnings: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """TEST-010 results for each profile on one site, keyed by profile name.

    Each value is ``{"result": <TEST-010 evaluate output, unchanged>, "failures": [...],
    "not_checked": [...]}``. ``profiles`` defaults to every profile in the thresholds file.
    ``radius_m`` overrides the match radius. When TEST-010 cannot be imported the skip is
    appended to ``warnings`` (and logged) and an empty dict is returned. A site folder that is
    missing or invalid raises the TEST-009 error, since the user asked for this evaluation.
    """
    evaluator = load_evaluator(repo_root)
    if evaluator is None:
        if warnings is not None:
            warnings.append(SKIP_WARNING)
        logger.warning(SKIP_WARNING)
        return {}
    ev_metrics, ev_gt = evaluator.metrics, evaluator.gt

    root = sites_root if sites_root is not None else Path(repo_root) / "tests" / "accuracy"
    overrides = {"match_radius_m": radius_m} if radius_m is not None else None
    thresholds = ev_metrics.load_thresholds(site, overrides=overrides, root=root)
    names = profiles if profiles is not None else sorted(thresholds["profiles"])

    gt_fc = ev_gt.load_ground_truth(site, root)
    area = ev_gt.load_labeled_area(site, root)
    out: dict[str, dict[str, Any]] = {}
    for name in names:
        profile = ev_metrics.profile_for(thresholds, name)
        result = ev_metrics.evaluate(
            palms_fc, gt_fc, area, radius_m=thresholds["match_radius_m"], profile=profile
        )
        out[name] = {
            "result": result,
            "failures": ev_metrics.check_thresholds(result, thresholds),
            "not_checked": ev_metrics.unchecked_thresholds(result, thresholds),
        }
    return out


def fallback_height_error(palms: gpd.GeoDataFrame) -> float | None:
    """Median |species region median - LiDAR height| over palms with ``height_source == "lidar"``.

    Region medians are per species over the LiDAR palms, and only species with at least
    ``MergeParams.region_median_min_n`` such palms count (the same rule palmscan uses to assign
    heights to palms without LiDAR). This estimates the error of the fallback height for palms
    without LiDAR. Returns None when no palm qualifies.
    """
    if palms.empty or "height_source" not in palms.columns:
        return None
    lidar = palms[(palms["height_source"] == "lidar") & palms["species"].notna()]
    if lidar.empty:
        return None
    heights = lidar["height_m"].astype(float)
    species = lidar["species"]
    region_median = heights.groupby(species).transform("median")
    region_n = heights.groupby(species).transform("size")
    keep = region_n >= MergeParams().region_median_min_n
    if not keep.any():
        return None
    errors = (region_median[keep] - heights[keep]).abs()
    return round(float(np.median(errors.to_numpy())), _DECIMALS)


def accuracy_doc(
    site: str,
    profiles: Mapping[str, Mapping[str, Any]],
    *,
    fallback_height_error_m: float | None,
    warnings: Sequence[str] = (),
) -> dict[str, Any]:
    """The document written to ``accuracy.json``: TEST-010 results per profile plus the fallback."""
    return {
        "site": site,
        "profiles": {name: dict(entry) for name, entry in profiles.items()},
        "fallback_height_error_m": fallback_height_error_m,
        "warnings": list(warnings),
    }


def write_accuracy(results: Mapping[str, Any], out_dir: Path) -> Path:
    """Write ``accuracy.json`` (see :func:`accuracy_doc`) into ``out_dir``; return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ACCURACY_FILE
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(results, indent=2, sort_keys=True) + "\n")
    return path


def _fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def accuracy_section_md(results: Mapping[str, Any]) -> str:
    """Body of the Accuracy section of ``qa_summary.md`` (the caller adds the heading).

    One row per profile with precision, recall, position and height error (medians), and the
    pass/fail status with TEST-010's failure and not-checked messages.
    """
    profiles: Mapping[str, Mapping[str, Any]] = results.get("profiles", {})
    lines = [
        f"Site {results.get('site', 'n/a')}. Predictions and ground truth are evaluated by "
        "TEST-010 (tests/accuracy/metrics.py); thresholds are in tests/accuracy/thresholds.yaml."
    ]
    if not profiles:
        lines += ["", "No profile was evaluated."]
    else:
        lines += [
            "",
            "| Profile | TP | FP | FN | Precision | Recall | Position median (m) | "
            "Height median (m) | Status |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for name, entry in profiles.items():
            res = entry["result"]
            c, pos, hgt = res["counts"], res["position_error_m"], res["height_error_m"]
            status = "FAIL" if entry.get("failures") else "pass"
            lines.append(
                f"| {name} | {c['tp']} | {c['fp']} | {c['fn']} | {_fmt(res['precision'])} | "
                f"{_fmt(res['recall'])} | {_fmt(pos['median'], 2)} | {_fmt(hgt['median'], 2)} | "
                f"{status} |"
            )
        for name, entry in profiles.items():
            for msg in entry.get("failures", []):
                lines.append(f"- {name}: FAIL: {msg}")
            for msg in entry.get("not_checked", []):
                lines.append(f"- {name}: {msg}")
    lines += [
        "",
        f"Fallback height error (palms without LiDAR, median |region median - LiDAR|): "
        f"{_fmt(results.get('fallback_height_error_m'), 2)} m",
    ]
    for msg in results.get("warnings", []):
        lines.append(f"- Warning: {msg}")
    return "\n".join(lines) + "\n"
