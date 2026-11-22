"""Contract conformance for palms.geojson: valid passes, each invalid fails by rule."""

from __future__ import annotations

import copy
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.contract import (
    assert_palms_ok,
    check_palms_invariants,
    main,
    validate_palms,
)
from tests.helpers.fixtures import REPO_ROOT, fixture_path, load_geojson, load_json

PKG = "contract"
REGION = fixture_path(PKG, "region-minimal.yaml")


def _doc(name: str) -> dict[str, Any]:
    doc: dict[str, Any] = load_json(PKG, name)
    return doc


# (fixture, rule-specific message the failure must contain)
INVALID: list[tuple[str, str]] = [
    ("dup_palm_id.geojson", "duplicate palm_id"),
    ("outside_bbox.geojson", "lies outside region bbox"),
    ("radius_too_small.geojson", "exclusion_radius_m 1.0"),
    ("region_mismatch.geojson", "does not match"),
    ("lidar_height_without_lidar.geojson", "does not include 'lidar'"),
    ("height_nonpositive.geojson", "height_m"),
    ("confidence_out_of_range.geojson", "outside [0, 1]"),
    ("schema_missing_field.geojson", "'crown_diam_m' is a required property"),
]


def test_valid_fixture_passes_schema_and_invariants() -> None:
    doc = load_geojson(PKG, "valid_minimal.geojson")
    assert len(doc["features"]) == 3
    assert validate_palms(doc) == []
    assert check_palms_invariants(doc, region=REGION) == []
    assert check_palms_invariants(doc) == []
    assert_palms_ok(fixture_path(PKG, "valid_minimal.geojson"), region=REGION)


@pytest.mark.parametrize(("name", "expected"), INVALID)
def test_invalid_fixture_fails_with_rule_message(name: str, expected: str) -> None:
    doc = _doc(name)
    problems = validate_palms(doc) + check_palms_invariants(doc, region=REGION)
    assert problems, f"{name} passed but must fail"
    assert any(expected in p for p in problems), (
        f"{name}: no problem contains {expected!r}: {problems}"
    )
    with pytest.raises(AssertionError, match=re.escape(expected)):
        assert_palms_ok(fixture_path(PKG, name), region=REGION)


def test_outside_bbox_is_caught_only_by_invariant() -> None:
    # JSON Schema and palmcore have no bbox rule without a region; the invariant must catch it.
    doc = _doc("outside_bbox.geojson")
    assert validate_palms(doc) == []
    assert any("outside region bbox" in p for p in check_palms_invariants(doc, region=REGION))


def test_radius_rule_without_region_is_half_crown() -> None:
    doc = _doc("radius_too_small.geojson")
    problems = check_palms_invariants(doc)
    assert any("is below crown_diam_m / 2" in p for p in problems)


def test_failure_message_names_feature_and_palm_id() -> None:
    # dup_palm_id.geojson sets features[2] to the palm_id of features[0]
    problems = validate_palms(_doc("dup_palm_id.geojson"))
    assert any(
        "features[2] sdc-0000000000000001" in p and "duplicate palm_id" in p for p in problems
    )


def _with_palm(doc: dict[str, Any], index: int, **props: Any) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    out["features"][index]["properties"].update(props)
    return out


@pytest.mark.parametrize(
    ("crown", "radius", "ok"),
    [
        (4.0, 3.5, True),  # 4/2 + 1.5
        (0.6, 1.8, True),  # 0.3 + 1.5 stays inside the clamp range
        (20.0, 8.0, True),  # 10 + 1.5 clamped to radius_max_m
        (20.0, 11.5, False),  # unclamped value is not allowed
        (4.0, 4.0, False),  # off by more than 0.01 m
    ],
)
def test_exclusion_radius_clamp_formula(crown: float, radius: float, ok: bool) -> None:
    doc = _with_palm(
        _doc("valid_minimal.geojson"), 0, crown_diam_m=crown, exclusion_radius_m=radius
    )
    problems = check_palms_invariants(doc, region=REGION)
    assert (problems == []) is ok, problems


def test_radius_within_tolerance_passes() -> None:
    doc = _with_palm(_doc("valid_minimal.geojson"), 0, exclusion_radius_m=3.505)
    assert check_palms_invariants(doc, region=REGION) == []


def test_lidar_rule_passes_when_detected_by_includes_lidar() -> None:
    doc = _doc("valid_minimal.geojson")
    assert doc["features"][1]["properties"]["height_source"] == "lidar"
    assert "lidar" in doc["features"][1]["properties"]["detected_by"]
    assert check_palms_invariants(doc, region=REGION) == []


def test_feature_region_mismatch_is_reported_when_region_given() -> None:
    doc = _with_palm(_doc("valid_minimal.geojson"), 0, region="other-region")
    problems = check_palms_invariants(doc, region=REGION)
    assert any("does not match region config" in p for p in problems)


def test_assert_palms_ok_caps_listing_at_50() -> None:
    doc = _doc("valid_minimal.geojson")
    template = doc["features"][0]
    features = []
    for index in range(60):
        item = copy.deepcopy(template)
        item["properties"]["palm_id"] = item["id"] = f"sdc-{index + 1:016x}"
        item["properties"]["exclusion_radius_m"] = 0.5  # fails the radius rule for every palm
        features.append(item)
    doc["features"] = features
    with pytest.raises(AssertionError) as info:
        assert_palms_ok(doc, region=REGION)
    lines = str(info.value).splitlines()
    # 60 palmcore errors + 60 invariant errors = 120 problems: header, 50 shown, "and 70 more"
    assert lines[0] == "palms.geojson failed the contract: 120 problem(s)"
    assert len(lines) == 52
    assert lines[-1] == "... and 70 more"


# --- local palmscan output (build/scan/<region>/palms.geojson) -------------------------------

LOCAL_OUTPUTS = sorted((REPO_ROOT / "build" / "scan").glob("*/palms.geojson"))
LOCAL_PARAMS = (
    [pytest.param(p, id=p.parent.name) for p in LOCAL_OUTPUTS]
    if LOCAL_OUTPUTS
    else [
        pytest.param(
            None,
            marks=pytest.mark.skip(reason="no local palmscan output: build/scan/*/palms.geojson"),
            id="no-local-output",
        )
    ]
)


@pytest.mark.parametrize("path", LOCAL_PARAMS)
def test_local_palmscan_output_conforms(path: Path | None) -> None:
    assert path is not None
    region_yaml = REPO_ROOT / "regions" / f"{path.parent.name}.yaml"
    assert_palms_ok(path, region=region_yaml if region_yaml.is_file() else None)


# --- CLI ---------------------------------------------------------------------------------------


def test_cli_exit_0_on_valid_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(fixture_path(PKG, "valid_minimal.geojson")), "--region", str(REGION)])
    assert code == 0
    assert "OK:" in capsys.readouterr().out


def test_cli_exit_1_on_invalid_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(fixture_path(PKG, "dup_palm_id.geojson"))])
    assert code == 1
    assert "duplicate palm_id" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("name", "expected_exit"), [("valid_minimal.geojson", 0), ("dup_palm_id.geojson", 1)]
)
def test_cli_module_entry_point_exit_codes(name: str, expected_exit: int) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.helpers.contract",
            str(fixture_path(PKG, name)),
            "--region",
            str(REGION),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
