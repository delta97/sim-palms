"""Self-tests for tests/accuracy/gt.py: schema, checks, commands and the CLI (TEST-009).

Fixtures are synthetic (Null Island, site T9); none of them is a real label.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from shapely.geometry import Point, Polygon

from tests.accuracy import gt
from tests.accuracy.gt import GroundTruthError
from tests.helpers.fixtures import FIXTURES_ROOT, REPO_ROOT, fixture_path
from tests.helpers.sites import SITES_FILE

FIXTURE_ROOT = FIXTURES_ROOT / "accuracy" / "gt"
SITES_VALID = fixture_path("helpers", "sites/valid.yaml")  # one defined site, T1


def _copy(tmp_path: Path, variant: str = "valid") -> Path:
    """Copy one fixture variant into tmp_path and return the accuracy root for it."""
    root = tmp_path / "acc"
    shutil.copytree(FIXTURE_ROOT / variant, root)
    return root


def _edit_gt(root: Path, mutate: Any) -> None:
    path = root / "T9" / gt.GT_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _gt_data(root: Path) -> dict[str, Any]:
    return json.loads((root / "T9" / gt.GT_FILE).read_text(encoding="utf-8"))


# --- format -----------------------------------------------------------------------------------


def test_schema_is_a_valid_draft_2020_12_document() -> None:
    schema = json.loads(gt.SCHEMA_FILE.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    ("height_m", "expected"),
    [(0.5, "S"), (7.99, "S"), (8.0, "M"), (14.99, "M"), (15.0, "T"), (24.99, "T"), (25.0, "X")],
)
def test_height_class_edges(height_m: float, expected: str) -> None:
    assert gt.height_class(height_m) == expected


def test_site_id_must_look_like_t_number(tmp_path: Path) -> None:
    with pytest.raises(GroundTruthError, match="site id"):
        gt.site_dir("../etc", tmp_path)


# --- validate ---------------------------------------------------------------------------------


def test_valid_fixture_passes_and_counts_by_field() -> None:
    report = gt.validate_site("T9", FIXTURE_ROOT / "valid")
    assert report.ok, report.problems
    assert report.n_points == 10
    assert report.counts["context"] == {
        "street": 3,
        "park": 2,
        "beach": 2,
        "yard": 1,
        "parking": 1,
        "other": 1,
    }
    assert report.counts["confidence"]["low"] == 2
    assert report.counts["height_class"]["unknown"] == 1
    assert report.counts["species"]["unknown"] == 1


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("dup_id", "duplicate gt_id"),
        ("outside_area", "outside labeled_area.geojson"),
        ("bad_enum", "'lawn' is not one of"),
    ],
)
def test_validate_catches_each_invalid_fixture(variant: str, expected: str) -> None:
    report = gt.validate_site("T9", FIXTURE_ROOT / variant)
    assert not report.ok
    assert any(expected in problem for problem in report.problems), report.problems


def test_coordinates_with_more_than_seven_decimals_fail(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit_gt(root, lambda d: d["features"][0]["geometry"].update(coordinates=[0.00120001, 0.0013]))
    report = gt.validate_site("T9", root)
    assert any("more than 7 decimals" in p for p in report.problems)


def test_species_and_basis_must_agree(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit_gt(root, lambda d: d["features"][0]["properties"].update(species="unknown"))
    report = gt.validate_site("T9", root)
    assert any("disagree" in p for p in report.problems)


def test_area_must_be_one_valid_polygon(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    area_path = root / "T9" / gt.AREA_FILE
    area = json.loads(area_path.read_text(encoding="utf-8"))
    bowtie = [[0.0, 0.0], [0.01, 0.01], [0.01, 0.0], [0.0, 0.01], [0.0, 0.0]]
    area["features"][0]["geometry"] = {"type": "Polygon", "coordinates": [bowtie]}
    area_path.write_text(json.dumps(area), encoding="utf-8")
    report = gt.validate_site("T9", root)
    assert any("polygon is not valid" in p for p in report.problems)


def test_area_with_two_features_fails(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    area_path = root / "T9" / gt.AREA_FILE
    area = json.loads(area_path.read_text(encoding="utf-8"))
    area["features"].append(area["features"][0])
    area_path.write_text(json.dumps(area), encoding="utf-8")
    report = gt.validate_site("T9", root)
    assert any("exactly one feature, found 2" in p for p in report.problems)


def test_missing_site_folder_is_an_input_error(tmp_path: Path) -> None:
    with pytest.raises(GroundTruthError, match="run init-site"):
        gt.validate_site("T9", tmp_path)


# --- loaders used by the metrics script -------------------------------------------------------


def test_load_ground_truth_returns_checked_features() -> None:
    data = gt.load_ground_truth("T9", FIXTURE_ROOT / "valid")
    assert len(data["features"]) == 10


def test_load_ground_truth_refuses_a_bad_fixture() -> None:
    with pytest.raises(GroundTruthError, match="duplicate gt_id"):
        gt.load_ground_truth("T9", FIXTURE_ROOT / "dup_id")


def test_load_labeled_area_is_a_polygon_that_covers_the_points() -> None:
    area = gt.load_labeled_area("T9", FIXTURE_ROOT / "valid")
    assert isinstance(area, Polygon)
    assert area.bounds == (0.0, 0.0, 0.01, 0.01)
    assert area.covers(Point(0.0012, 0.0013))


def test_load_meta_returns_the_mapping() -> None:
    meta = gt.load_meta("T9", FIXTURE_ROOT / "valid")
    assert meta["site"] == "T9"
    assert meta["imagery"]["source"].startswith("SYNTHETIC")


# --- next-id ----------------------------------------------------------------------------------


def test_next_id_is_one_above_the_highest(tmp_path: Path) -> None:
    assert gt.next_id("T9", FIXTURE_ROOT / "valid") == "T9-gt-0011"


def test_next_id_does_not_fill_gaps(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit_gt(root, lambda d: d["features"].pop(2))
    assert gt.next_id("T9", root) == "T9-gt-0011"


def test_next_id_on_empty_site_is_0001(tmp_path: Path) -> None:
    gt.init_site("T1", tmp_path, sites_file=SITES_VALID)
    assert gt.next_id("T1", tmp_path) == "T1-gt-0001"


# --- init-site --------------------------------------------------------------------------------


def test_init_site_writes_the_skeleton(tmp_path: Path) -> None:
    folder = gt.init_site("T1", tmp_path, sites_file=SITES_VALID)
    assert folder == tmp_path / "T1"
    assert json.loads((folder / gt.GT_FILE).read_text(encoding="utf-8")) == {
        "type": "FeatureCollection",
        "features": [],
    }
    area = gt.load_labeled_area("T1", tmp_path)
    assert area.bounds == pytest.approx((-117.2560, 32.7870, -117.2500, 32.7920))
    meta = gt.load_meta("T1", tmp_path)
    assert meta["imagery"] == {"source": "TBD", "date": "TBD", "resolution_m": "TBD"}
    assert meta["labelers"] == []
    assert meta["labeled_on"] is None
    assert meta["notes"] == ""


def test_skeleton_fails_validation_until_meta_is_filled(tmp_path: Path) -> None:
    gt.init_site("T1", tmp_path, sites_file=SITES_VALID)
    report = gt.validate_site("T1", tmp_path)
    assert not report.ok
    assert report.n_points == 0
    assert any("still TBD" in p for p in report.problems)
    assert not any("labeled_area" in p for p in report.problems)


def test_init_site_refuses_an_existing_folder(tmp_path: Path) -> None:
    gt.init_site("T1", tmp_path, sites_file=SITES_VALID)
    with pytest.raises(GroundTruthError, match="already exists"):
        gt.init_site("T1", tmp_path, sites_file=SITES_VALID)


def test_init_site_refuses_a_placeholder_site(tmp_path: Path) -> None:
    # The committed registry has T1 as a placeholder until TEST-100.
    with pytest.raises(GroundTruthError, match="placeholder"):
        gt.init_site("T1", tmp_path, sites_file=SITES_FILE)
    assert not (tmp_path / "T1").exists()


def test_init_site_rejects_an_unknown_site(tmp_path: Path) -> None:
    with pytest.raises(GroundTruthError, match="unknown site"):
        gt.init_site("T7", tmp_path, sites_file=SITES_VALID)


# --- fill-heights -----------------------------------------------------------------------------


def test_fill_heights_needs_rasterio_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy(tmp_path)
    chm = tmp_path / "chm.tif"
    chm.write_bytes(b"not really a tif; rasterio import fails first")
    monkeypatch.setitem(sys.modules, "rasterio", None)
    with pytest.raises(GroundTruthError, match="needs rasterio"):
        gt.fill_heights("T9", chm, 1.5, root)


def _write_chm(path: Path, point_xy: tuple[float, float], crs: str) -> None:
    """A 20 x 20 px CHM, 0.5 m, with pixel (row 10, col 10) centred on point_xy (in crs)."""
    import numpy as np
    import rasterio
    from rasterio.transform import Affine

    px, py = point_xy
    transform = Affine(0.5, 0.0, px - 5.25, 0.0, -0.5, py + 5.25)
    data = np.zeros((20, 20), dtype="float32")
    data[12, 10] = 12.34  # 1.0 m south of the point: inside 1.5 m
    data[14, 10] = 30.0  # 2.0 m south: outside 1.5 m, must be ignored
    data[9, 10] = -9999.0  # nodata 0.5 m north: inside but masked
    data[11, 11] = 5.0  # about 0.71 m away: inside
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)


def _utm_point(lon: float, lat: float) -> tuple[float, float]:
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32631", always_xy=True)
    x, y = transformer.transform(lon, lat)
    return float(x), float(y)


def test_fill_heights_takes_the_peak_inside_the_radius(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    root = _copy(tmp_path)
    chm = tmp_path / "chm.tif"
    _write_chm(chm, _utm_point(0.0012, 0.0013), "EPSG:32631")

    filled, total = gt.fill_heights("T9", chm, 1.5, root)

    assert (filled, total) == (1, 10)  # only point 1 lies on the synthetic CHM
    features = _gt_data(root)["features"]
    assert features[0]["properties"]["height_ref_m"] == 12.3
    assert all(f["properties"]["height_ref_m"] is None for f in features[1:])
    # Labels other than height_ref_m are untouched.
    assert features[0]["properties"]["height_class"] == "S"
    assert gt.validate_site("T9", root).ok


def test_fill_heights_counts_only_cells_inside_a_small_radius(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    root = _copy(tmp_path)
    chm = tmp_path / "chm.tif"
    _write_chm(chm, _utm_point(0.0012, 0.0013), "EPSG:32631")

    gt.fill_heights("T9", chm, 0.4, root)

    # Only the centre cell (0.0 m) is inside 0.4 m.
    assert _gt_data(root)["features"][0]["properties"]["height_ref_m"] == 0.0


def test_fill_heights_rejects_a_geographic_chm(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    root = _copy(tmp_path)
    chm = tmp_path / "chm_geo.tif"
    _write_chm(chm, (0.0012, 0.0013), "EPSG:4326")
    with pytest.raises(GroundTruthError, match="projected CRS"):
        gt.fill_heights("T9", chm, 1.5, root)


def test_fill_heights_rejects_a_non_positive_radius(tmp_path: Path) -> None:
    with pytest.raises(GroundTruthError, match="positive"):
        gt.fill_heights("T9", tmp_path / "missing.tif", 0.0, FIXTURE_ROOT / "valid")


# --- CLI --------------------------------------------------------------------------------------


def test_cli_help_lists_the_four_commands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tests.accuracy.gt", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for name in ("init-site", "validate", "fill-heights", "next-id"):
        assert name in result.stdout


def test_cli_validate_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gt.main(["validate", "T9", "--root", str(FIXTURE_ROOT / "valid")]) == 0
    assert "OK: 10 point(s) at T9" in capsys.readouterr().out
    for variant in ("dup_id", "outside_area", "bad_enum"):
        assert gt.main(["validate", "T9", "--root", str(FIXTURE_ROOT / variant)]) == 1
    capsys.readouterr()
    assert gt.main(["validate", "T9", "--root", str(tmp_path / "nothing")]) == 2


def test_cli_init_site_then_next_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gt.main(["init-site", "T1", "--root", str(tmp_path), "--sites", str(SITES_VALID)]) == 0
    assert gt.main(["next-id", "T1", "--root", str(tmp_path)]) == 0
    assert "T1-gt-0001" in capsys.readouterr().out
