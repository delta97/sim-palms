"""Self-tests for tests/accuracy/metrics.py: matching, metrics, thresholds and the CLI (TEST-010).

Fixtures are SYNTHETIC (Null Island, site T9, tests/fixtures/accuracy/metrics/); none is real.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from palmcore.errors import ConfigError
from tests.accuracy import gt, metrics
from tests.helpers.fixtures import FIXTURES_ROOT, REPO_ROOT

FIX = FIXTURES_ROOT / "accuracy" / "metrics"
ROW = FIX / "row"
TRAP = FIX / "trap"
RADIUS = 3.0


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _run(
    pred: str | dict[str, Any],
    *,
    base: Path = ROW,
    gt_fc: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    radius: float = RADIUS,
) -> dict[str, Any]:
    pred_fc = _load(base / pred) if isinstance(pred, str) else pred
    return metrics.evaluate(
        pred_fc,
        gt_fc if gt_fc is not None else gt.load_ground_truth("T9", base),
        gt.load_labeled_area("T9", base),
        radius_m=radius,
        profile=profile,
    )


@pytest.fixture
def thresholds() -> dict[str, Any]:
    return metrics.load_thresholds(None)


# --- match -----------------------------------------------------------------------------------


def test_match_basic_and_radius() -> None:
    pairs = metrics.match([[0, 0], [10, 0]], [[1, 0], [30, 0]], 3.0)
    assert pairs == [(0, 0, 1.0)]
    assert metrics.match([], [[0, 0]], 3.0) == []
    assert metrics.match([[0, 0]], [], 3.0) == []


def test_match_is_one_to_one_and_prefers_more_pairs() -> None:
    # One prediction between two ground-truth points can only take one of them.
    pairs = metrics.match([[0, 0]], [[-1, 0], [1.5, 0]], 3.0)
    assert pairs == [(0, 0, 1.0)]


def test_match_deterministic() -> None:
    pred = np.array([[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]])
    gt_xy = np.array([[1.0, 0.0], [3.0, 0.0], [5.0, 0.0]])
    first = metrics.match(pred, gt_xy, 3.0)
    assert all(metrics.match(pred, gt_xy, 3.0) == first for _ in range(5))


# --- spec properties on the fixtures ---------------------------------------------------------


def test_exact_copy_is_perfect() -> None:
    res = _run("pred_exact.geojson")
    assert (res["counts"]["tp"], res["counts"]["fp"], res["counts"]["fn"]) == (6, 0, 0)
    assert res["precision"] == res["recall"] == res["f1"] == 1.0
    pos = res["position_error_m"]
    assert pos["n"] == 6
    assert pos["median"] == pos["mean"] == pos["p90"] == 0.0
    assert res["height_error_m"]["bias"] == 0.0
    assert res["fp_ids"] == [] and res["fn_ids"] == []


def test_shift_2p5_m_within_radius() -> None:
    res = _run("pred_shift_2p5.geojson")
    assert res["precision"] == res["recall"] == 1.0
    assert res["position_error_m"]["median"] == pytest.approx(2.5, abs=0.05)
    assert res["position_error_m"]["p90"] == pytest.approx(2.5, abs=0.05)


def test_shift_3p5_m_outside_radius() -> None:
    res = _run("pred_shift_3p5.geojson")
    assert res["counts"]["tp"] == 0
    assert res["precision"] == res["recall"] == 0.0
    assert res["f1"] == 0.0
    assert res["position_error_m"]["median"] is None
    assert len(res["fp_ids"]) == 6 and len(res["fn_ids"]) == 6


def test_missing_plus_extra() -> None:
    res = _run("pred_missing_extra.geojson")
    assert (res["counts"]["tp"], res["counts"]["fp"], res["counts"]["fn"]) == (5, 1, 1)
    assert res["precision"] == res["recall"] == pytest.approx(5 / 6, abs=1e-4)
    assert res["fp_ids"] == ["syn-0000000000000063"]
    assert res["fn_ids"] == ["T9-gt-0004"]


def _greedy_matches(pred_xy: np.ndarray, gt_xy: np.ndarray, radius: float) -> int:
    """Reference nearest-first greedy, only to prove the trap fixture really defeats it."""
    pairs = sorted(
        (float(np.hypot(*(p - g))), i, j)
        for i, p in enumerate(pred_xy)
        for j, g in enumerate(gt_xy)
        if np.hypot(*(p - g)) <= radius
    )
    used_p: set[int] = set()
    used_g: set[int] = set()
    for _, i, j in pairs:
        if i not in used_p and j not in used_g:
            used_p.add(i)
            used_g.add(j)
    return len(used_p)


def test_greedy_trap_all_matched() -> None:
    assert (
        _greedy_matches(
            np.array([[2.0, 0], [5, 0], [8, 0]]), np.array([[0.0, 0], [3, 0], [6, 0]]), RADIUS
        )
        == 2
    )
    res = _run("pred_trap.geojson", base=TRAP)
    assert res["counts"]["tp"] == 3
    assert res["precision"] == res["recall"] == 1.0
    assert res["position_error_m"]["median"] == pytest.approx(2.0, abs=0.05)


def test_input_order_does_not_change_result() -> None:
    pred = _load(ROW / "pred_shift_2p5.geojson")
    shuffled = copy.deepcopy(pred)
    shuffled["features"].reverse()
    assert _run(pred) == _run(shuffled)


# --- ignoring rules --------------------------------------------------------------------------


def test_unmatched_low_confidence_gt_is_ignored_not_fn() -> None:
    gt_fc = gt.load_ground_truth("T9", ROW)
    gt_fc["features"][3]["properties"]["confidence"] = "low"
    res = _run("pred_missing_extra.geojson", gt_fc=gt_fc)
    assert res["counts"]["fn"] == 0
    assert res["counts"]["ignored"] == 1
    assert res["recall"] == 1.0
    assert res["precision"] == pytest.approx(5 / 6, abs=1e-4)


def test_matched_low_confidence_gt_counts_as_tp() -> None:
    gt_fc = gt.load_ground_truth("T9", ROW)
    gt_fc["features"][3]["properties"]["confidence"] = "low"
    res = _run("pred_exact.geojson", gt_fc=gt_fc)
    assert res["counts"]["tp"] == 6 and res["counts"]["ignored"] == 0


def test_prediction_outside_area_is_ignored() -> None:
    pred = _load(ROW / "pred_exact.geojson")
    far = copy.deepcopy(pred["features"][0])
    far["id"] = far["properties"]["palm_id"] = "syn-00000000000000ff"
    far["geometry"]["coordinates"] = [0.01, 0.0]  # about 1.1 km east, outside the 140 m area
    pred["features"].append(far)
    res = _run(pred)
    assert res["counts"]["fp"] == 0
    assert res["counts"]["ignored_pred_outside_area"] == 1
    assert res["precision"] == 1.0


def test_profile_filters_by_detected_by_and_context() -> None:
    lidar = _run(
        "pred_exact.geojson",
        profile={"name": "x", "pred_detected_by": ["lidar", "inventory+lidar"]},
    )
    assert lidar["counts"]["n_pred"] == 3 and lidar["counts"]["ignored_pred_profile"] == 3
    assert lidar["counts"]["tp"] == 3 and lidar["counts"]["fn"] == 3  # recall = 3 of 6
    street = _run("pred_exact.geojson", profile={"gt_context": ["street"]})
    assert street["counts"]["n_gt"] == 4 and street["counts"]["ignored_gt_profile"] == 2
    assert street["counts"]["tp"] == 4 and street["counts"]["fp"] == 2  # beach and park preds
    assert street["recall"] == 1.0
    both = _run(
        "pred_exact.geojson", profile={"pred_detected_by": ["inventory"], "gt_context": ["street"]}
    )
    assert both["counts"]["tp"] == 3 and both["counts"]["fp"] == 0 and both["counts"]["fn"] == 1


# --- height and species ----------------------------------------------------------------------


def test_height_error_uses_only_non_null_ref() -> None:
    pred = _load(ROW / "pred_exact.geojson")
    pred["features"][0]["properties"]["height_m"] = 11.0  # ref 10.0 -> +1.0
    pred["features"][2]["properties"]["height_m"] = 16.0  # ref 18.0 -> -2.0
    pred["features"][3]["properties"]["height_m"] = 30.0  # ref null: must not count
    h = _run(pred)["height_error_m"]
    assert h["n"] == 4  # gt 1, 2, 3, 5 have a reference
    assert h["mean"] == pytest.approx((1 + 0 + 2 + 0) / 4)
    assert h["median"] == pytest.approx(0.5)
    assert h["bias"] == pytest.approx(0.0)  # median of +1, 0, -2, 0
    assert h["p90"] == pytest.approx(
        float(np.percentile([1, 0, 2, 0], 90, method="linear")), abs=1e-3
    )


def test_height_error_none_without_references() -> None:
    gt_fc = gt.load_ground_truth("T9", ROW)
    for feat in gt_fc["features"]:
        feat["properties"]["height_ref_m"] = None
    h = _run("pred_exact.geojson", gt_fc=gt_fc)["height_error_m"]
    assert h["n"] == 0 and h["median"] is None and h["bias"] is None


def test_height_class_agreement_edges() -> None:
    pred = _load(ROW / "pred_exact.geojson")
    # gt classes M M T S X M; make two disagree (7.9 is S, 25.0 is X by the shared edges).
    pred["features"][0]["properties"]["height_m"] = 7.9  # gt M -> S: wrong
    pred["features"][2]["properties"]["height_m"] = 25.0  # gt T -> X: wrong
    hca = _run(pred)["height_class_agreement"]
    assert (hca["n"], hca["correct"]) == (6, 4)
    assert hca["agreement"] == pytest.approx(4 / 6, abs=1e-4)


def test_species_accuracy_ignores_unknown_and_splits_by_source() -> None:
    sp = _run("pred_exact.geojson")["species"]
    assert (sp["n"], sp["correct"]) == (5, 4)  # the unknown-species label is skipped
    assert sp["accuracy"] == 0.8
    assert sp["by_species_source"]["inventory"] == {"n": 4, "correct": 4, "accuracy": 1.0}
    assert sp["by_species_source"]["lidar_rules"] == {"n": 1, "correct": 0, "accuracy": 0.0}
    assert "lidar_tree" not in sp["by_species_source"]
    assert sp["confusion"]["washingtonia_filifera"] == {"washingtonia_robusta": 1}
    assert "unknown" not in sp["confusion"]


def test_species_accuracy_none_when_all_unknown() -> None:
    gt_fc = gt.load_ground_truth("T9", ROW)
    for feat in gt_fc["features"]:
        feat["properties"].update(species="unknown", species_basis="unknown")
    assert _run("pred_exact.geojson", gt_fc=gt_fc)["species"]["accuracy"] is None


def test_empty_inputs_give_null_ratios() -> None:
    empty = _load(ROW / "pred_exact.geojson")
    empty["features"] = []
    res = _run(empty)
    assert res["precision"] is None and res["recall"] == 0.0 and res["f1"] is None
    no_gt = {"type": "FeatureCollection", "features": []}
    res = _run("pred_exact.geojson", gt_fc=no_gt)
    assert res["recall"] is None and res["precision"] == 0.0


def test_unregistered_species_reported() -> None:
    pred = _load(ROW / "pred_exact.geojson")
    pred["features"][0]["properties"]["species"] = "not_a_real_palm"
    assert _run(pred)["unregistered_species"] == ["not_a_real_palm"]
    assert _run("pred_exact.geojson")["unregistered_species"] == []


# --- thresholds ------------------------------------------------------------------------------


def test_thresholds_file_values(thresholds: dict[str, Any]) -> None:
    assert thresholds["match_radius_m"] == 3.0
    assert set(thresholds["profiles"]) == {"lidar_only", "combined", "phase1_inventory"}
    assert thresholds["profiles"]["combined"]["recall_min"] == 0.90
    assert thresholds["profiles"]["phase1_inventory"]["precision_min"] is None


def test_check_thresholds_pass_and_fail(thresholds: dict[str, Any]) -> None:
    prof = metrics.profile_for(thresholds, "combined")
    good = _run("pred_exact.geojson", profile=prof)
    assert metrics.check_thresholds(good, thresholds) == []
    bad = _run("pred_missing_extra.geojson", profile=prof)
    failures = metrics.check_thresholds(bad, thresholds)
    assert len(failures) == 2 and "precision" in failures[0] and "recall" in failures[1]
    shifted = _run("pred_shift_2p5.geojson", profile=prof)
    failures = metrics.check_thresholds(shifted, thresholds)
    assert len(failures) == 1 and "position error" in failures[0]  # 2.5 m median > 2.0 m


def test_null_thresholds_never_fail(thresholds: dict[str, Any]) -> None:
    prof = metrics.profile_for(thresholds, "phase1_inventory")
    res = _run("pred_exact.geojson", profile=prof)
    res["precision"] = 0.0  # precision_min is null for this profile
    assert metrics.check_thresholds(res, thresholds) == []
    unchecked = metrics.unchecked_thresholds(res, thresholds)
    assert any(line.startswith("precision_min") for line in unchecked)
    assert any(line.startswith("species_accuracy_min") for line in unchecked)
    nulls = {**thresholds, "position_error_median_max_m": None, "height_error_median_max_m": None}
    nulls["profiles"] = {"p": {"precision_min": None, "recall_min": None}}
    res["profile"] = "p"
    res["recall"] = res["position_error_m"]["median"] = None
    assert metrics.check_thresholds(res, nulls) == []


def test_undefined_metric_fails_when_threshold_set(thresholds: dict[str, Any]) -> None:
    prof = metrics.profile_for(thresholds, "combined")
    res = _run("pred_shift_3p5.geojson", profile=prof)
    messages = " | ".join(metrics.check_thresholds(res, thresholds))
    assert "position error median (m) is undefined" in messages
    # height error with no reference is not checked rather than failed.
    gt_fc = gt.load_ground_truth("T9", ROW)
    for feat in gt_fc["features"]:
        feat["properties"]["height_ref_m"] = None
    res = _run("pred_exact.geojson", gt_fc=gt_fc, profile=prof)
    assert metrics.check_thresholds(res, thresholds) == []
    assert any(
        "height_error_median_max_m" in m for m in metrics.unchecked_thresholds(res, thresholds)
    )


def test_unknown_profile_is_an_error(thresholds: dict[str, Any]) -> None:
    with pytest.raises(ConfigError, match="unknown profile"):
        metrics.profile_for(thresholds, "nope")
    with pytest.raises(ConfigError):
        metrics.check_thresholds({"profile": "nope"}, thresholds)


def _site_root(tmp_path: Path, meta_thresholds: dict[str, Any] | None) -> Path:
    root = tmp_path / "acc"
    shutil.copytree(ROW, root)
    if meta_thresholds is not None:
        meta_file = root / "T9" / "meta.yaml"
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
        meta["thresholds"] = meta_thresholds
        meta_file.write_text(yaml.safe_dump(meta), encoding="utf-8")
    return root


def test_meta_override_wins_over_file(tmp_path: Path) -> None:
    root = _site_root(
        tmp_path,
        {
            "match_radius_m": 2.0,
            "profiles": {"combined": {"recall_min": None, "precision_min": 0.5}},
        },
    )
    th = metrics.load_thresholds("T9", root=root)
    assert th["match_radius_m"] == 2.0
    assert th["profiles"]["combined"]["recall_min"] is None
    assert th["profiles"]["combined"]["precision_min"] == 0.5
    assert th["profiles"]["lidar_only"]["recall_min"] == 0.80  # untouched siblings survive
    res = _run("pred_missing_extra.geojson", profile=metrics.profile_for(th, "combined"))
    assert metrics.check_thresholds(res, th) == []  # recall 5/6 would fail the file's 0.90


def test_cli_override_beats_meta(tmp_path: Path) -> None:
    root = _site_root(tmp_path, {"match_radius_m": 2.0})
    th = metrics.load_thresholds("T9", overrides={"match_radius_m": 1.0}, root=root)
    assert th["match_radius_m"] == 1.0


def test_load_thresholds_without_meta_and_custom_path(tmp_path: Path) -> None:
    root = tmp_path / "acc"
    (root / "T9").mkdir(parents=True)
    assert metrics.load_thresholds("T9", root=root)["match_radius_m"] == 3.0
    custom = tmp_path / "th.yaml"
    custom.write_text(
        "match_radius_m: 1.5\nprofiles:\n  a: {precision_min: 0.1}\n", encoding="utf-8"
    )
    assert metrics.load_thresholds(None, custom)["match_radius_m"] == 1.5
    custom.write_text("match_radius_m: 1.5\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        metrics.load_thresholds(None, custom)
    with pytest.raises(ConfigError):
        metrics.load_thresholds(None, tmp_path / "missing.yaml")


def test_no_numeric_targets_in_metrics_source() -> None:
    text = (REPO_ROOT / "tests" / "accuracy" / "metrics.py").read_text(encoding="utf-8")
    import re

    assert not re.search(r"(?<![\w.])(0\.9|0\.8|2\.0)(?![\w.])", text)


# --- CLI -------------------------------------------------------------------------------------


def _cli(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tests.accuracy.metrics", *map(str, args)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _evaluate_args(root: Path, pred: Path, *extra: str) -> list[str | Path]:
    return ["evaluate", "--site", "T9", "--pred", pred, "--root", root, *extra]


def test_cli_help() -> None:
    proc = _cli("evaluate", "--help")
    assert proc.returncode == 0 and "--all-profiles" in proc.stdout and "--write" in proc.stdout


def test_cli_exit_0_pass_and_1_fail() -> None:
    ok = _cli(*_evaluate_args(ROW, ROW / "pred_exact.geojson", "--profile", "combined"))
    assert ok.returncode == 0, ok.stderr
    assert "Precision | 1.000" in ok.stdout and "Thresholds: pass" in ok.stdout
    bad = _cli(*_evaluate_args(ROW, ROW / "pred_missing_extra.geojson", "--profile", "combined"))
    assert bad.returncode == 1
    assert "FAIL: precision" in bad.stdout


def test_cli_radius_override() -> None:
    proc = _cli(
        *_evaluate_args(
            ROW, ROW / "pred_shift_2p5.geojson", "--profile", "phase1_inventory", "--radius", "2.0"
        )
    )
    assert proc.returncode == 1  # recall 0 at 2.0 m
    assert "Match radius 2 m" in proc.stdout


def test_cli_all_profiles() -> None:
    proc = _cli(*_evaluate_args(ROW, ROW / "pred_exact.geojson", "--all-profiles"))
    assert proc.returncode == 1  # lidar_only recall is 0.5 on this fixture
    for name in ("combined", "lidar_only", "phase1_inventory"):
        assert f"/ {name} /" in proc.stdout


def test_cli_exit_2_on_input_errors(tmp_path: Path) -> None:
    missing = _cli(*_evaluate_args(ROW, tmp_path / "nope.geojson"))
    assert missing.returncode == 2 and "not found" in missing.stderr
    bad_json = tmp_path / "bad.geojson"
    bad_json.write_text("{not json", encoding="utf-8")
    assert _cli(*_evaluate_args(ROW, bad_json)).returncode == 2
    invalid = tmp_path / "invalid.geojson"
    invalid.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    assert _cli(*_evaluate_args(ROW, invalid)).returncode == 2
    profile = _cli(*_evaluate_args(ROW, ROW / "pred_exact.geojson", "--profile", "nope"))
    assert profile.returncode == 2 and "unknown profile" in profile.stderr
    no_site = _cli("evaluate", "--site", "T8", "--pred", ROW / "pred_exact.geojson", "--root", ROW)
    assert no_site.returncode == 2


def test_cli_write_produces_three_files(tmp_path: Path) -> None:
    root = _site_root(tmp_path, None)
    proc = _cli(
        *_evaluate_args(
            root,
            ROW / "pred_exact.geojson",
            "--profile",
            "combined",
            "--label",
            "unit",
            "--write",
            "--date",
            "2026-11-22",
        )
    )
    assert proc.returncode == 0, proc.stderr
    out = root / "T9" / "results"
    stem = "2026-11-22_unit_combined"
    assert sorted(p.name for p in out.iterdir()) == [
        f"{stem}.json",
        f"{stem}.md",
        f"{stem}_errors.geojson",
    ]
    data = json.loads((out / f"{stem}.json").read_text(encoding="utf-8"))
    assert (
        data["site"] == "T9" and data["counts"]["tp"] == 6 and data["thresholds"]["failures"] == []
    )
    assert (out / f"{stem}.md").read_text(encoding="utf-8").startswith("## Accuracy T9 / combined")


def test_cli_write_errors_geojson_has_fp_and_fn(tmp_path: Path) -> None:
    root = _site_root(tmp_path, None)
    proc = _cli(
        *_evaluate_args(
            root,
            ROW / "pred_missing_extra.geojson",
            "--profile",
            "combined",
            "--write",
            "--date",
            "2026-11-22",
        )
    )
    assert proc.returncode == 1
    errors = json.loads(
        (root / "T9" / "results" / "2026-11-22_run_combined_errors.geojson").read_text(
            encoding="utf-8"
        )
    )
    got = {
        (f["properties"]["error"], f["properties"].get("palm_id") or f["properties"]["gt_id"])
        for f in errors["features"]
    }
    assert got == {("fp", "syn-0000000000000063"), ("fn", "T9-gt-0004")}
    assert all(f["geometry"]["type"] == "Point" for f in errors["features"])


def test_cli_rejects_odd_label(tmp_path: Path) -> None:
    root = _site_root(tmp_path, None)
    proc = _cli(*_evaluate_args(root, ROW / "pred_exact.geojson", "--write", "--label", "../x"))
    assert proc.returncode == 2
