"""palmscan.qa: qa_rejects.csv, qa_map.gpkg and qa_summary.md."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import geopandas as gpd
import pyogrio
import pyproj
import pytest
from shapely.geometry import Point, box

from palmscan.model import LidarCandidate, PalmRecord, Reject, SourceVintage
from palmscan.qa.gpkg import (
    CHECK_RADIUS_M,
    LAYER_NAMES,
    ConflictBuilding,
    vintage_cell_id,
    vintage_grid,
    write_qa_gpkg,
)
from palmscan.qa.rejects import REJECT_COLUMNS, write_rejects_csv
from palmscan.qa.summary import (
    ClassifierSummary,
    QaContext,
    SourceCounts,
    git_sha,
    render_summary,
    write_summary,
)
from tests.helpers.fixtures import REPO_ROOT

EXPECTED = REPO_ROOT / "tests" / "fixtures" / "palmscan" / "qa" / "expected_summary.md"
RUN_TIME_LINE = re.compile(r"^- Run time \(UTC\): .*$", re.MULTILINE)
UTM = pyproj.CRS.from_epsg(32611)


def palm(
    key: str,
    lon: float,
    lat: float,
    *,
    species: str | None = "washingtonia_robusta",
    source: str = "inventory",
    height: float | None = 12.0,
    height_source: str | None = "inventory",
    radius: float | None = 2.5,
    vintage: dict[str, str] | None = None,
    conflict: bool = False,
    detected_by: str = "inventory",
) -> PalmRecord:
    return PalmRecord(
        stable_key=key,
        lon=lon,
        lat=lat,
        x=0.0,
        y=0.0,
        species=species,
        species_confidence=0.9 if species else None,
        species_source=source if species else None,
        height_m=height,
        height_source=height_source,
        exclusion_radius_m=radius,
        detected_by=detected_by,
        source_ids=[key],
        data_vintage=vintage if vintage is not None else {"sd_street_trees": "2019"},
        building_conflict=conflict,
    )


def sample_palms() -> list[PalmRecord]:
    return [
        palm("a1", -117.2610, 32.7810, vintage={"sd_street_trees": "2015"}),
        palm("a2", -117.2620, 32.7820, vintage={"sd_street_trees": "2017"}, conflict=True),
        palm(
            "b1",
            -117.2410,
            32.7910,
            species="phoenix_canariensis",
            source="prior",
            height=None,
            height_source=None,
            vintage={"sd_street_trees": "2024"},
        ),
        palm("c1", -117.2300, 32.7700, species=None, radius=None, vintage={}),
    ]


def sample_rejects() -> list[Reject]:
    return [
        Reject("mask", "sd_street_trees", "9", -117.25, 32.78, "mask_out"),
        Reject(
            "inventory",
            "sd_street_trees",
            "2",
            -117.2,
            32.7,
            "not_palm",
            all_reasons=["not_palm", "status"],
            species_raw="Quercus",
        ),
        Reject(
            "lidar_rules",
            "ept",
            "7",
            -117.21,
            32.71,
            "ratio",
            all_reasons=["ratio", "crown_large"],
            metrics={
                "height_m": 9.5,
                "crown_diam_m": 8.25,
                "ratio": 1.15,
                "shared_boundary_frac": 0.4,
                "extra": 1.0,
            },
        ),
        Reject("inventory", "osm", "1", -117.2, 32.7, "non_tree"),
    ]


# ---------------------------------------------------------------------------------------------
# qa_rejects.csv


def test_rejects_csv_header_and_order(tmp_path: Path) -> None:
    path = tmp_path / "qa_rejects.csv"
    write_rejects_csv(sample_rejects(), path)
    raw = path.read_bytes()
    assert b"\r" not in raw
    rows = list(csv.reader(raw.decode("utf-8").splitlines()))
    assert rows[0] == [
        "stage", "source", "source_id", "lon", "lat", "reason", "all_reasons", "species_raw",
        "height_m", "crown_diam_m", "ratio", "shared_boundary_frac",
    ]  # fmt: skip
    assert tuple(rows[0]) == REJECT_COLUMNS
    keys = [(r[0], r[1], r[2]) for r in rows[1:]]
    assert keys == [
        ("inventory", "osm", "1"),
        ("inventory", "sd_street_trees", "2"),
        ("lidar_rules", "ept", "7"),
        ("mask", "sd_street_trees", "9"),
    ]
    by_id = {r[2]: r for r in rows[1:]}
    assert by_id["2"][6] == "not_palm;status"
    assert by_id["2"][7] == "Quercus"
    assert by_id["2"][8:] == ["", "", "", ""]
    assert by_id["7"][3:5] == ["-117.2100000", "32.7100000"]
    assert by_id["7"][8:] == ["9.5000", "8.2500", "1.1500", "0.4000"]


def test_rejects_csv_is_input_order_independent_and_empty_ok(tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_rejects_csv(sample_rejects(), a)
    write_rejects_csv(list(reversed(sample_rejects())), b)
    assert a.read_bytes() == b.read_bytes()
    empty = tmp_path / "sub" / "empty.csv"
    write_rejects_csv([], empty)
    assert empty.read_text(encoding="utf-8").splitlines() == [",".join(REJECT_COLUMNS)]


# ---------------------------------------------------------------------------------------------
# vintage grid


def test_vintage_cell_id() -> None:
    assert vintage_cell_id(-117.2555, 32.7849, 0.01) == "n32p78_w117p26"
    assert vintage_cell_id(-117.26, 32.78, 0.01) == "n32p78_w117p26"
    assert vintage_cell_id(10.5, -3.25, 0.5) == "s3p5_e10p5"
    assert vintage_cell_id(5.2, 7.9, 1.0) == "n7_e5"


def test_vintage_grid_stale_flag_and_medians() -> None:
    grid = vintage_grid(sample_palms(), 0.01, run_year=2026, stale_years=5)
    assert list(grid["cell_id"]) == sorted(grid["cell_id"])
    cells = grid.set_index("cell_id")
    old = cells.loc["n32p78_w117p27"]  # a1 (2015) and a2 (2017)
    assert old["palm_count"] == 2
    assert old["inventory_vintage"] == 2016.0
    assert math.isnan(old["lidar_vintage"])
    assert bool(old["stale"]) is True
    assert bool(cells.loc["n32p79_w117p25", "stale"]) is False  # 2024
    assert bool(cells.loc["n32p77_w117p23", "stale"]) is False  # no vintage at all
    assert str(grid.crs) == "EPSG:4326"
    assert grid.geometry.iloc[1].bounds == pytest.approx((-117.27, 32.78, -117.26, 32.79))


def test_vintage_grid_lidar_vintage_and_boundary() -> None:
    p = palm("l1", -117.2605, 32.7805, vintage={"inv": "2024", "lidar_ept": "2016-05"})
    grid = vintage_grid([p], 0.01, run_year=2026, stale_years=9)
    row = grid.iloc[0]
    assert row["inventory_vintage"] == 2024.0
    assert row["lidar_vintage"] == 2016.0
    assert bool(row["stale"]) is True  # 2026 - 2016 = 10 > 9
    assert bool(vintage_grid([p], 0.01, 2026, 10).iloc[0]["stale"]) is False
    assert len(vintage_grid([], 0.01, 2026, 5)) == 0


# ---------------------------------------------------------------------------------------------
# qa_map.gpkg


def _write(tmp_path: Path, **kwargs: object) -> Path:
    path = tmp_path / "qa_map.gpkg"
    palms = sample_palms()
    building = ConflictBuilding("b-1", "ms_footprints", box(-117.2621, 32.7821, -117.2619, 32.7822))
    write_qa_gpkg(
        path,
        palms,
        sample_rejects(),
        [building],
        vintage_grid(palms, 0.01, 2026, 5),
        id_prefix="tst",
        **kwargs,  # type: ignore[arg-type]
    )
    return path


def _layers(path: Path) -> dict[str, str]:
    return {str(name): str(kind) for name, kind in pyogrio.list_layers(path)}


def test_gpkg_layers_and_counts(tmp_path: Path) -> None:
    path = _write(tmp_path)
    layers = _layers(path)
    assert set(layers) == set(LAYER_NAMES)
    assert layers["palms"] == "Point"
    assert layers["check_radius_3m"] == "Polygon"
    counts = {name: len(gpd.read_file(path, layer=name)) for name in layers}
    assert counts == {
        "palms": 4,
        "exclusion_circles": 3,  # one palm has no radius
        "check_radius_3m": 4,
        "rejects": 4,
        "building_conflicts": 1,
        "vintage_grid": 3,
    }


def test_gpkg_attributes(tmp_path: Path) -> None:
    path = _write(tmp_path)
    palms = gpd.read_file(path, layer="palms")
    assert list(palms["palm_id"]) == sorted(palms["palm_id"])
    assert all(re.fullmatch(r"tst-[0-9a-f]{16}", i) for i in palms["palm_id"])
    assert {"stable_key", "species_raw", "species", "detected_by", "data_vintage"} <= set(
        palms.columns
    )
    a2 = palms[palms["stable_key"] == "src:a2"].iloc[0]
    assert bool(a2["building_conflict"]) is True
    assert a2["data_vintage"] == '{"sd_street_trees":"2017"}'
    assert str(palms.crs).endswith("4326")
    circles = gpd.read_file(path, layer="exclusion_circles")
    assert set(circles.columns) >= {"palm_id", "exclusion_radius_m", "building_conflict"}
    rejects = gpd.read_file(path, layer="rejects")
    assert list(rejects["stage"]) == ["inventory", "inventory", "lidar_rules", "mask"]
    assert set(rejects.columns) >= set(REJECT_COLUMNS)
    buildings = gpd.read_file(path, layer="building_conflicts")
    assert list(buildings["building_id"]) == ["b-1"]
    grid = gpd.read_file(path, layer="vintage_grid")
    assert set(grid.columns) >= {
        "cell_id",
        "palm_count",
        "inventory_vintage",
        "lidar_vintage",
        "stale",
    }


def test_gpkg_check_radius_area(tmp_path: Path) -> None:
    path = _write(tmp_path)
    check = gpd.read_file(path, layer="check_radius_3m").to_crs(UTM)
    expected = math.pi * CHECK_RADIUS_M**2
    for area in check.geometry.area:
        assert area == pytest.approx(28.3, abs=0.2)
        assert area == pytest.approx(expected, rel=0.01)
    circles = gpd.read_file(path, layer="exclusion_circles").to_crs(UTM)
    first = circles.iloc[0]
    assert first.geometry.area == pytest.approx(
        math.pi * first["exclusion_radius_m"] ** 2, rel=0.01
    )


def test_gpkg_empty_layers_keep_schema_and_phase4_layers(tmp_path: Path) -> None:
    path = tmp_path / "empty.gpkg"
    write_qa_gpkg(path, [], [], [], vintage_grid([], 0.01, 2026, 5))
    layers = _layers(path)
    assert set(layers) == set(LAYER_NAMES)
    palms = gpd.read_file(path, layer="palms")
    assert len(palms) == 0
    assert "stable_key" in palms.columns
    assert "reason" in gpd.read_file(path, layer="rejects").columns

    cand = LidarCandidate(
        "ds:t:1", "ds", 1.0, 2.0, -117.25, 32.78, 14.0, 20.0, 5.0, 2.8, 0.1, 10.0,
        accepted=True, reasons=["ok", "x"], vintage="2021",
    )  # fmt: skip
    full = _write(
        tmp_path, candidates=[cand], crowns=[("ds:t:1", box(-117.25, 32.78, -117.2499, 32.7801))]
    )
    layers = _layers(full)
    assert layers["lidar_candidates"] == "Point"
    assert layers["crowns"] == "Polygon"
    cands = gpd.read_file(full, layer="lidar_candidates")
    assert cands.iloc[0]["reasons"] == "ok;x"
    assert bool(cands.iloc[0]["accepted"]) is True
    assert set(_layers(_write(tmp_path))) == set(LAYER_NAMES)  # rewrite drops Phase 4 layers


def test_gpkg_rewrites_existing_file(tmp_path: Path) -> None:
    path = _write(tmp_path)
    _write(tmp_path)
    assert len(gpd.read_file(path, layer="palms")) == 4


def test_gpkg_point_geometry(tmp_path: Path) -> None:
    path = _write(tmp_path)
    palms = gpd.read_file(path, layer="palms")
    row = palms[palms["stable_key"] == "src:a1"].iloc[0]
    assert row.geometry.equals_exact(Point(-117.261, 32.781), 1e-9)


# ---------------------------------------------------------------------------------------------
# qa_summary.md


def make_ctx() -> QaContext:
    palms = sample_palms()
    return QaContext(
        region="test-region",
        run_time="2026-11-22T12:00:00Z",
        palmscan_version="0.1.0",
        git_sha="abc1234",
        config_hash="deadbeef",
        stages=["fetch_buildings", "ingest_inventory", "dedupe", "masks"],
        output_path="build/scan/test-region",
        palms=palms,
        source_counts=[
            SourceCounts("sd_street_trees", 100, 10, 60, 30, 2, 1, 27),
            SourceCounts("osm", 5, 0, 1, 4, 0, 0, 4),
        ],
        conflict_building_count=1,
        source_vintages=[
            SourceVintage("sd_street_trees", "2019", "record_dates", "2026-11-22T00:00:00Z"),
            SourceVintage("osm", None, "fetched", "2026-11-22T00:00:00Z"),
        ],
        vintage_grid=vintage_grid(palms, 0.01, 2026, 5),
        unmatched_palm_names={"Palm sp.": 3, "Palmetto|odd": 7, "Fan palm": 3},
        priors_computed={"washingtonia_robusta": 0.7, "phoenix_canariensis": 0.3},
        priors_configured={"washingtonia_robusta": 0.5},
        priors_used="merged",
        warnings=["LiDAR stage not implemented yet; inventory only"],
    )


def mask_time(text: str) -> str:
    return RUN_TIME_LINE.sub("- Run time (UTC): <masked>", text)


def test_summary_matches_golden() -> None:
    text = render_summary(make_ctx())
    assert mask_time(text) == mask_time(EXPECTED.read_text(encoding="utf-8").replace("\r\n", "\n"))


def test_summary_run_time_is_the_only_volatile_line() -> None:
    a = render_summary(make_ctx())
    ctx = make_ctx()
    ctx.run_time = "2030-01-01T00:00:00Z"
    b = render_summary(ctx)
    assert a != b
    assert mask_time(a) == mask_time(b)


def test_summary_optional_sections_absent_without_data() -> None:
    text = render_summary(make_ctx())
    assert "## Classifier" not in text
    assert "## Accuracy" not in text
    assert text.index("## Species priors") < text.index("## Warnings")


def test_summary_optional_sections_present() -> None:
    ctx = make_ctx()
    ctx.classifier = ClassifierSummary(
        chosen_model="shape_rules",
        cv_acc_rules=0.8,
        cv_acc_tree=0.82,
        n_samples=120,
        reason="no_gain",
        confusion={"a": {"a": 5, "b": 1}, "b": {"b": 4}},
    )
    ctx.accuracy_md = "| profile | recall |\n|---|---|\n| combined | 0.9 |\n"
    text = render_summary(ctx)
    assert text.index("## Classifier") < text.index("## Accuracy") < text.index("## Warnings")
    assert "| a | 5 | 1 |" in text
    assert "| combined | 0.9 |" in text


def test_summary_empty_context_renders() -> None:
    text = render_summary(QaContext("r", "t", "0", None, [], "out", [], git_sha=None))
    assert "git sha: unavailable" in text
    assert text.endswith("None.\n")


def test_write_summary_uses_lf(tmp_path: Path) -> None:
    path = tmp_path / "x" / "qa_summary.md"
    write_summary(make_ctx(), path)
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert raw.decode("utf-8") == render_summary(make_ctx())


def test_git_sha_tolerates_failure(tmp_path: Path) -> None:
    assert git_sha(tmp_path / "does-not-exist") is None
    sha = git_sha(REPO_ROOT)
    assert sha is None or re.fullmatch(r"[0-9a-f]{4,40}", sha)
