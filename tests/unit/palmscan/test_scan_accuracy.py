"""palmscan.qa.accuracy: the QA accuracy section runs TEST-010 on a run's palms (SCAN-029).

Fixtures are SYNTHETIC (Null Island, site T9, tests/fixtures/palmscan/accuracy/).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pytest

from palmscan.qa import accuracy
from palmscan.qa.accuracy import (
    SKIP_WARNING,
    accuracy_doc,
    accuracy_section_md,
    evaluate_site,
    fallback_height_error,
    load_evaluator,
    write_accuracy,
)
from tests.helpers.fixtures import FIXTURES_ROOT, REPO_ROOT

FIX = FIXTURES_ROOT / "palmscan" / "accuracy"
SITE = "T9"


def _pred(name: str = "pred.geojson") -> dict[str, Any]:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _direct(profile: str, radius_m: float | None = None) -> tuple[dict[str, Any], list[str]]:
    """TEST-010 called directly, with no palmscan code in between."""
    from tests.accuracy import gt, metrics

    overrides = {"match_radius_m": radius_m} if radius_m is not None else None
    thresholds = metrics.load_thresholds(SITE, overrides=overrides, root=FIX)
    result = metrics.evaluate(
        _pred(),
        gt.load_ground_truth(SITE, FIX),
        gt.load_labeled_area(SITE, FIX),
        radius_m=thresholds["match_radius_m"],
        profile=metrics.profile_for(thresholds, profile),
    )
    return result, metrics.check_thresholds(result, thresholds)


def test_evaluator_imports_from_checkout() -> None:
    evaluator = load_evaluator(REPO_ROOT)
    assert evaluator is not None
    assert evaluator.metrics.__name__ == "tests.accuracy.metrics"


def test_evaluate_site_equals_direct_test010_call() -> None:
    out = evaluate_site(_pred(), SITE, repo_root=REPO_ROOT, sites_root=FIX)
    assert sorted(out) == ["combined", "lidar_only", "phase1_inventory"]
    for name, entry in out.items():
        expected, failures = _direct(name)
        assert entry["result"] == expected
        assert entry["failures"] == failures
    # The fixture is built so that the combined profile fails and the lidar one has a recall miss.
    assert out["combined"]["failures"]
    assert out["lidar_only"]["result"]["counts"]["fn"] == 3


def test_profiles_pass_through_and_radius_override() -> None:
    out = evaluate_site(_pred(), SITE, repo_root=REPO_ROOT, sites_root=FIX, profiles=["combined"])
    assert list(out) == ["combined"]

    tight = evaluate_site(
        _pred(), SITE, repo_root=REPO_ROOT, sites_root=FIX, profiles=["combined"], radius_m=1.0
    )
    expected, _ = _direct("combined", radius_m=1.0)
    assert tight["combined"]["result"] == expected
    assert tight["combined"]["result"]["radius_m"] == 1.0
    assert tight["combined"]["result"]["counts"]["tp"] == 2  # the 1.5 m shifted palms miss


def test_unknown_profile_is_a_config_error() -> None:
    from palmcore.errors import ConfigError

    with pytest.raises(ConfigError, match="unknown profile"):
        evaluate_site(_pred(), SITE, repo_root=REPO_ROOT, sites_root=FIX, profiles=["nope"])


def test_missing_evaluator_is_a_warning_not_a_crash(tmp_path: Path) -> None:
    # tests.accuracy resolves to the real checkout, not to tmp_path, so it counts as not importable.
    assert load_evaluator(tmp_path) is None
    warnings: list[str] = []
    out = evaluate_site(_pred(), SITE, repo_root=tmp_path, sites_root=FIX, warnings=warnings)
    assert out == {}
    assert warnings == [SKIP_WARNING]


def test_empty_predictions_do_not_raise() -> None:
    out = evaluate_site(
        _pred("pred_empty.geojson"),
        SITE,
        repo_root=REPO_ROOT,
        sites_root=FIX,
        profiles=["combined"],
    )
    result = out["combined"]["result"]
    assert result["counts"]["n_pred"] == 0
    assert result["counts"]["tp"] == 0
    assert result["precision"] is None
    assert result["recall"] == 0.0
    assert any("precision" in msg and "undefined" in msg for msg in out["combined"]["failures"])


def test_fallback_height_error_hand_built() -> None:
    rows: list[dict[str, Any]] = []
    # Five LiDAR palms of one species: region median 14, abs errors 4, 2, 0, 2, 4 -> median 2.
    for height in (10.0, 12.0, 14.0, 16.0, 18.0):
        rows.append(
            {"species": "washingtonia_robusta", "height_m": height, "height_source": "lidar"}
        )
    # Two LiDAR palms of another species: below region_median_min_n (5), so they do not count.
    for height in (5.0, 30.0):
        rows.append(
            {"species": "washingtonia_filifera", "height_m": height, "height_source": "lidar"}
        )
    # Inventory heights never count.
    rows.append({"species": "washingtonia_robusta", "height_m": 1.0, "height_source": "inventory"})
    palms = gpd.GeoDataFrame(rows)
    assert fallback_height_error(palms) == 2.0


def test_fallback_height_error_none_when_no_lidar() -> None:
    assert fallback_height_error(gpd.GeoDataFrame()) is None
    rows = [{"species": "washingtonia_robusta", "height_m": 9.0, "height_source": "inventory"}]
    assert fallback_height_error(gpd.GeoDataFrame(rows)) is None


def test_write_accuracy_and_section(tmp_path: Path) -> None:
    out = evaluate_site(_pred(), SITE, repo_root=REPO_ROOT, sites_root=FIX)
    doc = accuracy_doc(SITE, out, fallback_height_error_m=None)
    path = write_accuracy(doc, tmp_path)
    assert path == tmp_path / "accuracy.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["profiles"]["combined"]["result"] == out["combined"]["result"]
    assert loaded["fallback_height_error_m"] is None

    section = accuracy_section_md(doc)
    assert "| combined | 4 | 1 | 1 |" in section
    assert "FAIL" in section
    assert not section.startswith("## ")  # the QA renderer adds the heading


def test_module_holds_no_metric_or_target() -> None:
    source = Path(accuracy.__file__).read_text(encoding="utf-8")
    assert "linear_sum_assignment" not in source
    assert "0.9" not in source
