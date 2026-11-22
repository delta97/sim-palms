"""palmscan run with the LiDAR stages, end to end on a synthetic point cloud (SCAN-028).

No PDAL and no network: ``EptPointSource`` runs with a fake PDAL runner that serves points cut
from one synthetic scene (see tests/fixtures/palmscan/pipeline_lidar/README.md). Coordinates in
this file are metres in EPSG:32611, the UTM zone of the fixture region.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pyogrio
import pyproj
import pytest
import yaml
from shapely import box as shapely_box

from palmscan import pipeline
from palmscan.cli import main
from palmscan.config import ScanConfig
from palmscan.qa.accuracy import evaluate_site
from palmscan.sources.lidar_ept import POINT_DTYPE, EptDataset, EptPointSource
from tests.helpers.contract import assert_palms_ok
from tests.helpers.fixtures import FIXTURES_ROOT, REPO_ROOT

FIX = FIXTURES_ROOT / "palmscan" / "pipeline_lidar"
REGION_YAML = FIX / "lidar-e2e.yaml"
SITE = "T8"
DATASET = "USGS_LPC_CA_Fake_2018_LAS"
EPT_URL = "https://example.invalid/fake/ept.json"
UTM = pyproj.CRS.from_epsg(32611)

# Ground rises 2 cm per metre of easting, so DTM sampling is checked against a real slope.
GROUND_Z0 = 10.0
GROUND_SLOPE = 0.02
E0 = 476000.0


def ground_z(easting: np.ndarray | float) -> np.ndarray | float:
    return GROUND_Z0 + GROUND_SLOPE * (easting - E0)


# --------------------------------------------------------------------- synthetic scene


@dataclass(frozen=True)
class Cone:
    """Palm-like crown: apex ``height`` m above ground, linear to the ground at ``radius``."""

    e: float
    n: float
    height: float
    radius: float


@dataclass(frozen=True)
class Dome:
    """Flat-topped broad canopy."""

    e: float
    n: float
    height: float
    radius: float


@dataclass(frozen=True)
class Roof:
    """Flat roof of class 6 points."""

    e0: float
    n0: float
    e1: float
    n1: float
    height: float


PALM_A = Cone(476300.0, 3627900.0, 14.0, 2.6)  # inventory palm 1 stands 1.2 m east of it
PALM_B = Cone(476399.0, 3627850.0, 11.0, 2.4)  # 1 m west of the 476400 tile edge
PALM_C = Cone(476230.0, 3627750.0, 18.0, 3.0)
THIN = Cone(476250.0, 3627950.0, 12.0, 1.3)  # a 3.2 m crown: fails crown_min_m = 3.5
CANOPY = Dome(476440.0, 3627900.0, 10.0, 8.0)
GROVE = tuple(  # 3 x 3 cones 3.5 m apart: crowns that share most of their boundary
    Cone(476150.0 + 3.5 * i, 3628100.0 + 3.5 * j, 12.0, 4.0) for i in range(3) for j in range(3)
)
BUILDING = Roof(476420.0, 3628050.0, 476440.0, 3628070.0, 1.5)  # below the 2 m crown mask
BUILDING_PALM = Cone(476430.0, 3628060.0, 14.0, 2.6)
SCENE_BOUNDS = (476000.0, 3627600.0, 476600.0, 3628200.0)  # the nine 200 m tiles
GROUND_STEP = 0.5  # one ground return per CHM cell, so no DTM holes to fill
SURFACE_STEP = 0.25


def _grid(e0: float, n0: float, e1: float, n1: float, step: float, offset: float) -> np.ndarray:
    es = np.arange(e0 + offset, e1, step)
    ns = np.arange(n0 + offset, n1, step)
    ee, nn = np.meshgrid(es, ns)
    return np.column_stack((ee.ravel(), nn.ravel()))


def _points(xy: np.ndarray, z: np.ndarray, cls: int) -> np.ndarray:
    out = np.zeros(len(xy), dtype=POINT_DTYPE)
    out["X"], out["Y"], out["Z"] = xy[:, 0], xy[:, 1], z
    out["Classification"], out["ReturnNumber"], out["NumberOfReturns"] = cls, 1, 1
    return out


def _above_ground(obj: Cone | Dome) -> np.ndarray:
    r = obj.radius
    xy = _grid(obj.e - r, obj.n - r, obj.e + r, obj.n + r, SURFACE_STEP, SURFACE_STEP / 2)
    d = np.hypot(xy[:, 0] - obj.e, xy[:, 1] - obj.n)
    h = obj.height * (1.0 - d / r) if isinstance(obj, Cone) else np.full(len(xy), obj.height)
    keep = d < r
    return np.column_stack((xy[keep], h[keep]))


def synthetic_cloud() -> np.ndarray:
    """Flat-sloped ground plus the objects above; first returns only, no noise."""
    e0, n0, e1, n1 = SCENE_BOUNDS
    gxy = _grid(e0, n0, e1, n1, GROUND_STEP, GROUND_STEP / 2)
    parts = [_points(gxy, np.asarray(ground_z(gxy[:, 0])), 2)]
    objects: list[Cone | Dome] = [PALM_A, PALM_B, PALM_C, THIN, CANOPY, *GROVE]
    objects.append(BUILDING_PALM)
    for obj in objects:
        top = _above_ground(obj)
        if isinstance(obj, Cone) and obj is BUILDING_PALM:
            top[:, 2] = np.maximum(top[:, 2], BUILDING.height)
        z = np.asarray(ground_z(top[:, 0])) + top[:, 2]
        parts.append(_points(top[:, :2], z, 5))
    roof_xy = _grid(
        BUILDING.e0, BUILDING.n0, BUILDING.e1, BUILDING.n1, SURFACE_STEP, SURFACE_STEP / 2
    )
    parts.append(_points(roof_xy, np.asarray(ground_z(roof_xy[:, 0])) + BUILDING.height, 6))
    return np.concatenate(parts)


_BOUNDS_RE = re.compile(r"\(\[([-\d.]+), ([-\d.]+)\], \[([-\d.]+), ([-\d.]+)\]\)")


class FakePdal:
    """PDAL runner serving one scene: ``write`` cuts the pipeline's reader bounds, ``read`` loads.

    The pipeline JSON is the one palmscan builds, so the test also covers the reader bounds and
    the cache layout of ``fetch_tile``. ``ept.json`` is taken to be in the local CRS.
    """

    version = "fake"

    def __init__(self, cloud: np.ndarray) -> None:
        self.cloud = cloud
        self.writes: list[str] = []
        self.reads = 0

    def write(self, pipeline: Mapping[str, Any]) -> int | None:
        stages = pipeline["pipeline"]
        match = _BOUNDS_RE.fullmatch(stages[0]["bounds"])
        assert match is not None, stages[0]["bounds"]
        xmin, xmax, ymin, ymax = (float(v) for v in match.groups())
        c = self.cloud
        cut = c[(c["X"] >= xmin) & (c["X"] <= xmax) & (c["Y"] >= ymin) & (c["Y"] <= ymax)]
        target = Path(stages[-1]["filename"])
        with target.open("wb") as handle:
            np.save(handle, cut)
        self.writes.append(target.name)
        return len(cut)

    def read(self, pipeline: Mapping[str, Any]) -> np.ndarray:
        self.reads += 1
        out: np.ndarray = np.load(Path(pipeline["pipeline"][0]["filename"]))
        return out


@pytest.fixture(scope="module")
def cloud() -> np.ndarray:
    return synthetic_cloud()


def make_source(cfg: ScanConfig, cache: Any, http: Any, cloud: np.ndarray) -> EptPointSource:
    footprint = shapely_box(*cfg.region.bbox.as_tuple())
    ds = EptDataset(DATASET, EPT_URL, 2018, footprint)
    source = EptPointSource(cfg, cache, http, runner=FakePdal(cloud), datasets=[ds])
    source._srs[EPT_URL] = UTM
    return source


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1795000000")


@pytest.fixture
def use_cloud(monkeypatch: pytest.MonkeyPatch, cloud: np.ndarray) -> list[EptPointSource]:
    """Make the pipeline build its EPT source on the fake runner; return the sources built."""
    built: list[EptPointSource] = []

    def factory(cfg: ScanConfig, cache: Any, http: Any) -> EptPointSource:
        source = make_source(cfg, cache, http, cloud)
        built.append(source)
        return source

    monkeypatch.setattr(pipeline, "EptPointSource", factory)
    return built


Region = Callable[[Callable[[dict[str, Any]], None]], Path]


@pytest.fixture
def make_region(tmp_path: Path) -> Region:
    """A tweaked copy of lidar-e2e.yaml in ``tmp_path/regions``; returns that directory."""

    def make(edit: Callable[[dict[str, Any]], None] = lambda data: None) -> Path:
        data = yaml.safe_load(REGION_YAML.read_text(encoding="utf-8"))
        for source in data["sources"]["inventory"]:
            source["path"] = str((FIX.parent / source["path"]).resolve())
        data["sources"]["buildings_path"] = str(
            (FIX.parent / data["sources"]["buildings_path"]).resolve()
        )
        edit(data)
        directory = tmp_path / "regions"
        directory.mkdir(exist_ok=True)
        (directory / "lidar-e2e.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
        return directory

    return make


def run_args(tmp_path: Path, regions_dir: Path, *extra: str, out: str = "out") -> list[str]:
    return [
        "run",
        "--region",
        "lidar-e2e",
        "--regions-dir",
        str(regions_dir),
        "--out",
        str(tmp_path / out),
        "--data-dir",
        str(tmp_path / "data"),
        "--no-log-file",
        *extra,
    ]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rejects_of(out: Path) -> list[dict[str, str]]:
    with (out / "qa_rejects.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def by_detected(palms: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for feature in palms["features"]:
        groups.setdefault(feature["properties"]["detected_by"], []).append(feature)
    return groups


_TO_UTM = pyproj.Transformer.from_crs("EPSG:4326", UTM, always_xy=True)


def utm_of(feature: Mapping[str, Any]) -> tuple[float, float]:
    lon, lat = feature["geometry"]["coordinates"]
    e, n = _TO_UTM.transform(lon, lat)
    return float(e), float(n)


def run_ok(tmp_path: Path, regions: Path, *extra: str, out: str = "out") -> Path:
    assert main(run_args(tmp_path, regions, *extra, out=out)) == 0
    return tmp_path / out


def with_site(*extra: str) -> tuple[str, ...]:
    return ("--eval-site", SITE, "--sites-root", str(FIX), *extra)


def runner_of(source: EptPointSource) -> FakePdal:
    assert isinstance(source.runner, FakePdal)
    return source.runner


# ------------------------------------------------------------------------------ end to end


def test_e2e_detected_by_mix_and_values(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    out = run_ok(tmp_path, make_region(), *with_site())
    palms = load(out / "palms.geojson")
    assert_palms_ok(palms, region=REGION_YAML)
    groups = by_detected(palms)
    assert {k: len(v) for k, v in groups.items()} == {
        "inventory+lidar": 1,
        "inventory": 1,
        "lidar": 2,
    }

    (matched,) = groups["inventory+lidar"]
    props = matched["properties"]
    assert "lidar_trees:1" in props["source_ids"]
    assert any(s.startswith(f"lidar:{DATASET}:") for s in props["source_ids"])
    assert props["height_source"] == "lidar"
    assert props["height_m"] == pytest.approx(PALM_A.height, abs=0.5)
    assert props["ground_elev_m"] == pytest.approx(ground_z(PALM_A.e), abs=0.3)
    assert props["species"] == "washingtonia_robusta"
    assert props["species_source"] == "inventory"
    assert props["data_vintage"] == {"inventory": "2021", "lidar": "2018"}
    # The inventory position (the trunk, 1.2 m east of the crown peak) is kept.
    assert utm_of(matched) == pytest.approx((PALM_A.e + 1.2, PALM_A.n), abs=0.05)

    (inventory_only,) = groups["inventory"]
    props = inventory_only["properties"]
    assert props["source_ids"] == ["lidar_trees:2"]
    assert props["height_source"] == "species_default"
    assert props["data_vintage"] == {"inventory": "2021"}
    # No LiDAR crown here, but the DTM of the tile gives its ground elevation.
    assert props["ground_elev_m"] == pytest.approx(ground_z(476350.0), abs=0.2)

    lidar_only = sorted(groups["lidar"], key=lambda f: utm_of(f)[0])
    assert len(lidar_only) == 2
    for feature, cone in zip(lidar_only, (PALM_C, PALM_B), strict=True):
        props = feature["properties"]
        assert props["height_source"] == "lidar"
        assert props["height_m"] == pytest.approx(cone.height, abs=1.5)
        assert props["data_vintage"] == {"lidar": "2018"}
        assert props["species"] is not None
        assert props["species_source"] in ("lidar_rules", "prior")
        assert props["source_ids"][0].startswith(f"lidar:{DATASET}:")
        assert utm_of(feature) == pytest.approx((cone.e, cone.n), abs=0.6)
    # PALM_B sits 1 m inside the tile edge and is seen by two tiles: it is reported once.
    assert sum(1 for f in lidar_only if abs(utm_of(f)[0] - PALM_B.e) < 1.0) == 1


def test_e2e_rejects_and_outputs(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    out = run_ok(tmp_path, make_region(), *with_site())
    for name in (
        "palms.geojson",
        "buildings.geojson",
        "species_priors.yaml",
        "qa_summary.md",
        "qa_map.gpkg",
        "qa_rejects.csv",
        "accuracy.json",
        "run.json",
    ):
        assert (out / name).is_file(), name
    assert not (out / "species_tree.json").exists()  # one training sample: no tree

    rows = [r for r in rejects_of(out) if r["stage"] == "lidar_rules"]
    assert len(rows) == 9
    codes = [r["all_reasons"].split(";") for r in rows]
    # THIN: a 3.2 m crown under crown_min_m = 3.5 (nothing else wrong with it).
    assert ["crown_small"] in codes
    # The cone over the building footprint passes every shape rule.
    (building,) = (r for r in rows if r["reason"] == "building")
    assert building["all_reasons"] == "building"
    assert float(building["height_m"]) == pytest.approx(BUILDING_PALM.height, abs=0.5)
    # The broad dome is too wide and too flat.
    assert ["crown_large", "ratio"] in codes
    # Every crown of the 3 x 3 grove shares most of its boundary with another crown.
    grove = [c for c in codes if "not_isolated" in c]
    assert len(grove) == 6
    assert all(r["species_raw"] == "" and r["source"] == "lidar" for r in rows)
    assert not [r for r in rejects_of(out) if r["stage"] == "merge"]
    # None of them became a palm.
    palms = load(out / "palms.geojson")
    assert len(palms["features"]) == 4

    layers = {str(row[0]) for row in pyogrio.list_layers(out / "qa_map.gpkg")}
    assert {"palms", "rejects", "vintage_grid", "lidar_candidates"} <= layers
    assert "crowns" not in layers
    candidates = gpd.read_file(out / "qa_map.gpkg", layer="lidar_candidates")
    assert len(candidates) == 12
    assert int(candidates["accepted"].sum()) == 3
    assert set(candidates["vintage"]) == {"2018"}
    grid = gpd.read_file(out / "qa_map.gpkg", layer="vintage_grid")
    assert grid["lidar_vintage"].eq(2018.0).all()

    summary = (out / "qa_summary.md").read_text(encoding="utf-8")
    assert "## Classifier" in summary
    assert "- Chosen model: shape_rules" in summary
    assert "- Reason: too_few_samples" in summary
    assert "## Accuracy" in summary
    assert f"| lidar:{DATASET} | 2018 | dataset_name |" in summary
    assert "| inventory+lidar | 1 |" in summary

    run = load(out / "run.json")
    assert run["exit_code"] == 0
    counts = run["counts"]
    assert counts["lidar_tiles"] == 9
    assert counts["lidar_candidates"] == 12
    assert counts["lidar_accepted"] == 3
    assert counts["lidar_matched"] == 1
    assert counts["lidar_only"] == 2
    assert counts["species_model"] == "shape_rules"
    stages = set(run["stage_seconds"])
    assert {"lidar_tiles", "lidar_rules", "merge", "classify", "accuracy"} <= stages
    assert "accuracy.json" in run["outputs"]
    assert run["warnings"] == []


def test_accuracy_json_has_expected_numbers(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    out = run_ok(tmp_path, make_region(), *with_site())
    doc = load(out / "accuracy.json")
    assert doc["site"] == SITE
    assert doc["fallback_height_error_m"] is None  # too few LiDAR palms per species
    counts = {
        name: (c["tp"], c["fp"], c["fn"])
        for name, c in ((n, p["result"]["counts"]) for n, p in doc["profiles"].items())
    }
    # Ground truth: the 4 palms plus one that no palm covers (gt 5, a park palm).
    assert counts["combined"] == (4, 0, 1)
    assert counts["lidar_only"] == (3, 0, 2)
    assert counts["phase1_inventory"] == (4, 0, 0)
    phase1 = doc["profiles"]["phase1_inventory"]
    assert phase1["result"]["recall"] == 1.0
    assert phase1["failures"] == []
    assert doc["profiles"]["combined"]["failures"]  # recall 0.8 < 0.9
    assert doc["profiles"]["combined"]["result"]["position_error_m"]["median"] < 0.5


def test_second_run_is_byte_identical_and_uses_cached_tiles(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    regions = make_region()
    first = run_ok(tmp_path, regions, *with_site(), out="first")
    assert len(runner_of(use_cloud[0]).writes) == 9
    second = run_ok(tmp_path, regions, *with_site("--offline"), out="second")
    assert runner_of(use_cloud[1]).writes == []  # every tile came from the cache
    for name in ("palms.geojson", "buildings.geojson", "accuracy.json", "qa_rejects.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    chm_first = (first / "eval" / SITE / "chm.tif").read_bytes()
    assert chm_first == (second / "eval" / SITE / "chm.tif").read_bytes()


def _without_source_ids(out: Path) -> list[dict[str, Any]]:
    features = load(out / "palms.geojson")["features"]
    for feature in features:
        del feature["properties"]["source_ids"]
    return list(features)


def test_tile_layout_does_not_change_the_palms(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    reference = run_ok(tmp_path, make_region(), out="ref")

    def retile(data: dict[str, Any]) -> None:
        data["palmscan"]["lidar"]["tile_size_m"] = 300.0
        data["palmscan"]["lidar"]["tile_buffer_m"] = 12.0

    other = run_ok(tmp_path, make_region(retile), out="other")
    # The files differ in meta (config hash) and in the tile named by each LiDAR source id; the
    # palms are the same.
    assert _without_source_ids(reference) == _without_source_ids(other)
    assert len(use_cloud[1].tiles()) != len(use_cloud[0].tiles())


def test_only_lidar_drops_inventory_palms(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    out = run_ok(tmp_path, make_region(), "--only", "lidar")
    palms = load(out / "palms.geojson")
    assert_palms_ok(palms, region=REGION_YAML)
    assert {k: len(v) for k, v in by_detected(palms).items()} == {"lidar": 3}
    ids = {s for f in palms["features"] for s in f["properties"]["source_ids"]}
    assert not any(s.startswith("lidar_trees:") for s in ids)
    run = load(out / "run.json")
    assert run["counts"]["sources"] == {}
    assert "ingest_inventory" not in run["stage_seconds"]
    # Palm A is now a plain LiDAR palm at its crown peak (the middle one by easting).
    peaks = sorted(utm_of(f) for f in palms["features"])
    assert peaks[1] == pytest.approx((PALM_A.e, PALM_A.n), abs=0.6)


def test_no_lidar_and_only_inventory_skip_the_stage(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    for i, flag in enumerate((["--no-lidar"], ["--only", "inventory"])):
        out = run_ok(tmp_path, make_region(), *flag, *with_site(), out=f"out{i}")
        palms = load(out / "palms.geojson")
        assert {k: len(v) for k, v in by_detected(palms).items()} == {"inventory": 2}
        assert all(f["properties"]["ground_elev_m"] is None for f in palms["features"])
        layers = {str(row[0]) for row in pyogrio.list_layers(out / "qa_map.gpkg")}
        assert "lidar_candidates" not in layers
        summary = (out / "qa_summary.md").read_text(encoding="utf-8")
        assert "## Classifier" not in summary
        assert "## Accuracy" in summary  # evaluation does not need LiDAR
        assert not (out / "eval").exists()  # but there is no CHM to write
        assert load(out / "run.json")["warnings"] == []
    assert use_cloud == []  # no point source was even built


# ---------------------------------------------------------------------- species classifier


def _stub_tree() -> Any:
    """One-leaf tree that answers washingtonia_robusta for every palm."""
    from palmscan.classify.species import FEATURES
    from palmscan.classify.tree_model import TreeModel

    return TreeModel(
        features=list(FEATURES),
        classes=["phoenix_canariensis", "washingtonia_robusta"],
        children_left=np.array([-1]),
        children_right=np.array([-1]),
        feature=np.array([-2]),
        threshold=np.array([-2.0]),
        value=np.array([[1.0, 9.0]]),
    )


def test_tree_is_written_used_and_can_be_loaded(
    tmp_path: Path,
    make_region: Region,
    use_cloud: list[EptPointSource],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from palmscan.classify import tree_model

    report = tree_model.TrainReport(
        n_samples=60,
        classes=["phoenix_canariensis", "washingtonia_robusta"],
        cv_acc_tree=0.9,
        cv_acc_rules=0.5,
        used=True,
        reason="ok",
        confusion={"washingtonia_robusta": {"washingtonia_robusta": 3}},
    )
    monkeypatch.setattr(tree_model, "train", lambda training, params: (_stub_tree(), report))
    out = run_ok(tmp_path, make_region(), out="trained")
    assert (out / "species_tree.json").is_file()
    palms = load(out / "palms.geojson")
    lidar_only = by_detected(palms)["lidar"]
    assert {f["properties"]["species"] for f in lidar_only} == {"washingtonia_robusta"}
    assert {f["properties"]["species_source"] for f in lidar_only} == {"lidar_tree"}
    assert {f["properties"]["species_confidence"] for f in lidar_only} == {
        0.81
    }  # 0.9 * the leaf share 9/10
    summary = (out / "qa_summary.md").read_text(encoding="utf-8")
    assert "- Chosen model: lidar_tree" in summary
    assert "- CV accuracy, tree: 0.900" in summary
    assert load(out / "run.json")["counts"]["species_model"] == "lidar_tree"

    # A second region reuses the saved model and never trains.
    def no_training(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("train must not be called with classify.tree_model_path")

    monkeypatch.setattr(tree_model, "train", no_training)
    model_path = str(out / "species_tree.json")

    def reuse(data: dict[str, Any]) -> None:
        data["palmscan"]["classify"] = {"tree_model_path": model_path}

    reused = run_ok(tmp_path, make_region(reuse), out="reused")
    assert load(reused / "palms.geojson")["features"] == load(out / "palms.geojson")["features"]
    assert (reused / "species_tree.json").read_bytes() == (out / "species_tree.json").read_bytes()
    assert "- Reason: loaded from" in (reused / "qa_summary.md").read_text(encoding="utf-8")


def test_missing_tree_model_path_exits_2(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    def edit(data: dict[str, Any]) -> None:
        data["palmscan"]["classify"] = {"tree_model_path": str(tmp_path / "nope.json")}

    assert main(run_args(tmp_path, make_region(edit))) == 2


# --------------------------------------------------------------------- optional outputs


def test_write_crowns_adds_the_crowns_layer(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    def edit(data: dict[str, Any]) -> None:
        data["palmscan"]["qa"] = {"write_crowns": True}

    out = run_ok(tmp_path, make_region(edit))
    crowns = gpd.read_file(out / "qa_map.gpkg", layer="crowns")
    candidates = gpd.read_file(out / "qa_map.gpkg", layer="lidar_candidates")
    assert len(crowns) == 12
    assert set(crowns["candidate_id"]) == set(candidates["candidate_id"])
    assert crowns.geometry.is_valid.all()
    assert not crowns.geometry.is_empty.any()
    # A crown polygon holds its own peak.
    peaks = candidates.set_index("candidate_id").geometry
    for cid, geom in zip(crowns["candidate_id"], crowns.geometry, strict=True):
        assert geom.buffer(1e-6).contains(peaks[cid])


def test_double_verbose_writes_debug_rasters(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    out = run_ok(tmp_path, make_region(), "-vv")
    tiles = sorted(p.name for p in (out / "debug").iterdir())
    assert len(tiles) == 9
    names = {p.name for p in (out / "debug" / tiles[0]).iterdir()}
    assert {"dtm.tif", "dsm.tif", "chm.tif", "chm_smooth.tif"} <= names
    plain = run_ok(tmp_path, make_region(), out="plain")
    assert not (plain / "debug").exists()


def test_eval_chm_feeds_fill_heights(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    import rasterio

    from tests.accuracy import gt

    out = run_ok(tmp_path, make_region(), *with_site())
    chm_path = out / "eval" / SITE / "chm.tif"
    with rasterio.open(chm_path) as src:
        assert src.crs.to_epsg() == 32611
        assert src.res == (0.5, 0.5)
        left, bottom, right, top = src.bounds
        # The labelled area is about 420 m x 300 m; the CHM adds 3 m on every side.
        assert 420.0 + 5.0 < right - left < 420.0 + 12.0
        assert 300.0 + 5.0 < top - bottom < 300.0 + 12.0
        assert src.nodata == -9999.0
        data = src.read(1)
        assert not (data == -9999.0).any()  # every tile of the site was read
        row, col = src.index(PALM_A.e, PALM_A.n)
        apex = data[row - 2 : row + 3, col - 2 : col + 3]  # the apex falls between cell centres
        assert float(apex.max()) == pytest.approx(PALM_A.height, abs=0.7)

    site = tmp_path / "sites"
    (site / SITE).mkdir(parents=True)
    for source in (FIX / SITE).iterdir():
        (site / SITE / source.name).write_bytes(source.read_bytes())
    filled, total = gt.fill_heights(SITE, chm_path, root=site)
    assert (filled, total) == (5, 5)
    heights = {
        f["properties"]["gt_id"]: f["properties"]["height_ref_m"]
        for f in gt.load_ground_truth(SITE, site)["features"]
    }
    assert heights["T8-gt-0001"] == pytest.approx(PALM_A.height, abs=1.5)
    assert heights["T8-gt-0002"] == pytest.approx(PALM_B.height, abs=1.5)
    assert heights["T8-gt-0003"] == pytest.approx(PALM_C.height, abs=1.5)
    assert heights["T8-gt-0004"] == 0.0  # the inventory-only palm has no crown in the scene


# ------------------------------------------------------------------------------- failures


def test_empty_tiles_warn_and_all_empty_is_a_source_error(
    tmp_path: Path, make_region: Region, monkeypatch: pytest.MonkeyPatch, cloud: np.ndarray
) -> None:
    east_cut = cloud[cloud["X"] < 476380.0]  # tiles from 476400 on (buffer 10 m) get nothing

    def factory_for(points: np.ndarray) -> Callable[[ScanConfig, Any, Any], EptPointSource]:
        return lambda cfg, cache, http: make_source(cfg, cache, http, points)

    monkeypatch.setattr(pipeline, "EptPointSource", factory_for(east_cut))
    out = run_ok(tmp_path, make_region(), out="partial")
    run = load(out / "run.json")
    assert run["counts"]["lidar_tiles_skipped"] == 3
    assert run["counts"]["lidar_tiles"] == 6
    assert any("skipped" in w for w in run["warnings"])

    monkeypatch.setattr(pipeline, "EptPointSource", factory_for(cloud[:0]))
    fresh_cache = ("--data-dir", str(tmp_path / "empty_cache"))
    assert main(run_args(tmp_path, make_region(), *fresh_cache, out="empty")) == 4
    assert load(tmp_path / "empty" / "run.json")["exit_code"] == 4


def test_offline_without_cached_tiles_exits_5(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    assert main(run_args(tmp_path, make_region(), "--offline")) == 5
    assert load(tmp_path / "out" / "run.json")["exit_code"] == 5


def test_option_errors_exit_2(
    tmp_path: Path, make_region: Region, use_cloud: list[EptPointSource]
) -> None:
    regions = make_region()
    assert main(run_args(tmp_path, regions, "--only", "lidar", "--no-lidar")) == 2
    assert main(run_args(tmp_path, regions, "--eval-site", "T7", "--sites-root", str(FIX))) == 2
    assert load(tmp_path / "out" / "run.json")["exit_code"] == 2

    def no_lidar(data: dict[str, Any]) -> None:
        data["sources"]["lidar"] = "none"

    assert main(run_args(tmp_path, make_region(no_lidar), "--only", "lidar")) == 2

    def unknown(data: dict[str, Any]) -> None:
        data["sources"]["lidar"] = "airborne_magic"

    assert main(run_args(tmp_path, make_region(unknown))) == 2


# --------------------------------------------------------------------------- eval command

ACCURACY_FIX = FIXTURES_ROOT / "palmscan" / "accuracy"


def _eval_args(*extra: str) -> list[str]:
    return [
        "eval",
        "--palms",
        str(ACCURACY_FIX / "pred.geojson"),
        "--site",
        "T9",
        "--sites-root",
        str(ACCURACY_FIX),
        "--no-log-file",
        *extra,
    ]


def test_eval_prints_the_profile_table_and_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "deep" / "acc.json"
    assert main(_eval_args("--out", str(target))) == 0
    stdout = capsys.readouterr().out
    assert "| Profile | TP | FP | FN |" in stdout
    for name in ("combined", "lidar_only", "phase1_inventory"):
        assert f"| {name} |" in stdout

    doc = load(target)
    expected = evaluate_site(
        load(ACCURACY_FIX / "pred.geojson"), "T9", repo_root=REPO_ROOT, sites_root=ACCURACY_FIX
    )
    assert doc["site"] == "T9"
    assert doc["profiles"] == json.loads(json.dumps(expected))
    assert doc["profiles"]["lidar_only"]["result"]["counts"]["fn"] == 3
    assert doc["profiles"]["combined"]["failures"]  # the fixture is built to miss a threshold


def test_eval_single_profile_radius_and_out_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    extra = ("--profile", "combined", "--match-radius-m", "1.0", "--out", str(tmp_path))
    assert main(_eval_args(*extra)) == 0
    doc = load(tmp_path / "accuracy.json")
    assert list(doc["profiles"]) == ["combined"]
    assert doc["profiles"]["combined"]["result"]["radius_m"] == 1.0
    assert "| lidar_only |" not in capsys.readouterr().out


def test_eval_errors_exit_2(tmp_path: Path) -> None:
    assert main(["eval", "--palms", str(tmp_path / "nope.geojson"), "--site", "T9"]) == 2
    broken = tmp_path / "broken.geojson"
    broken.write_text("{not json", encoding="utf-8")
    assert main(["eval", "--palms", str(broken), "--site", "T9"]) == 2
    argv = _eval_args()
    argv[argv.index("T9")] = "T7"  # no such site folder
    assert main(argv) == 2
