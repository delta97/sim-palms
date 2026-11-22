"""palmscan.sources.lidar_ept: selection, tiles, pipeline JSON, cache. No PDAL, no network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from palmcore import cache as pc
from palmcore.errors import CacheMiss, SourceError
from palmscan.cache import Cache
from palmscan.config import LidarParams, scan_config_from_mapping
from palmscan.detect.chm import build_chm
from palmscan.sources import lidar_ept as le
from palmscan.sources.lidar_ept import (
    EptDataset,
    EptPointSource,
    LidarTile,
    build_pipeline,
    fetch_tile,
    load_boundaries,
    parse_boundaries,
    parse_ept_srs,
    parse_year,
    plan_tiles,
    read_points,
    select_datasets,
)

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "palmscan" / "lidar_ept"
CRS = "EPSG:32611"
BBOX = [-117.16, 32.72, -117.1472, 32.7308]  # about 1.2 km square, inside SYN_SanDiego_2018
STRADDLE = [-117.146, 32.72, -117.134, 32.7308]  # crosses the east edge of SYN_SanDiego_2018


def _load(name: str) -> Any:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.fixture
def datasets() -> list[EptDataset]:
    return parse_boundaries(_load("boundaries_sample.geojson"))


class FakeRunner:
    """Records pipelines; ``write`` creates the output file like PDAL would."""

    version = "fake-1"

    def __init__(self, count: int | None = 42, points: np.ndarray | None = None) -> None:
        self.count = count
        self.points = points
        self.written: list[dict[str, Any]] = []
        self.reads: list[dict[str, Any]] = []

    def write(self, pipeline: Any) -> int | None:
        self.written.append(dict(pipeline))
        Path(pipeline["pipeline"][-1]["filename"]).write_bytes(b"LAZ")
        return self.count

    def read(self, pipeline: Any) -> np.ndarray:
        self.reads.append(dict(pipeline))
        assert self.points is not None
        return self.points


class FakeHttp:
    def __init__(self, payloads: dict[str, Path]) -> None:
        self.payloads = payloads
        self.downloads: list[str] = []

    def download(self, url: str, dest: Path) -> None:
        self.downloads.append(url)
        dest.write_bytes(self.payloads[url].read_bytes())


def _ds(datasets: list[EptDataset], name: str) -> EptDataset:
    return next(d for d in datasets if d.name == name)


# --- dataset selection ---------------------------------------------------------------------


def test_parse_boundaries_reads_name_url_year(datasets: list[EptDataset]) -> None:
    assert [d.name for d in datasets] == [
        "SYN_Elsewhere_2020",
        "SYN_SanDiego_2014",
        "SYN_SanDiego_2018",
    ]
    assert [d.year for d in datasets] == [2020, 2014, 2018]
    assert datasets[1].url == "https://example.test/usgs-lidar-public/SYN_SanDiego_2014/ept.json"


@pytest.mark.parametrize(
    ("name", "year"),
    [
        ("CA_SanDiego_2015_C17_1", 2015),
        ("USGS_LPC_CA_SanDiegoQL1_2014_LAS_2016", 2014),  # first year wins: collection year
        ("CA_LosAngeles_1_B23", None),
        ("X_20150", None),
    ],
)
def test_parse_year(name: str, year: int | None) -> None:
    assert parse_year(name) == year


def test_parse_boundaries_skips_incomplete_features() -> None:
    fc = {
        "features": [
            {"properties": {"name": "A_2010"}, "geometry": None},
            {"properties": {"url": "u"}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
        ]
    }
    assert parse_boundaries(fc) == []


def test_newest_dataset_wins_on_overlap(datasets: list[EptDataset]) -> None:
    chosen = select_datasets(datasets, BBOX, [])
    assert [d.name for d in chosen] == ["SYN_SanDiego_2018"]


def test_older_dataset_kept_for_area_the_newer_one_misses(datasets: list[EptDataset]) -> None:
    chosen = select_datasets(datasets, STRADDLE, [])
    assert [d.name for d in chosen] == ["SYN_SanDiego_2018", "SYN_SanDiego_2014"]


def test_bbox_may_be_a_bbox_object(datasets: list[EptDataset]) -> None:
    from palmcore.geo import Bbox

    assert select_datasets(datasets, Bbox.from_list(BBOX))[0].year == 2018


def test_forced_datasets_override_selection(datasets: list[EptDataset]) -> None:
    chosen = select_datasets(datasets, BBOX, ["SYN_SanDiego_2014"])
    assert [d.name for d in chosen] == ["SYN_SanDiego_2014"]


def test_forced_unknown_dataset_raises(datasets: list[EptDataset]) -> None:
    with pytest.raises(SourceError, match="NOPE"):
        select_datasets(datasets, BBOX, ["NOPE"])


def test_no_coverage_raises(datasets: list[EptDataset]) -> None:
    with pytest.raises(SourceError, match="no 3DEP EPT coverage for bbox"):
        select_datasets(datasets, [-100.0, 40.0, -99.99, 40.01], [])


# --- tiles ---------------------------------------------------------------------------------


def test_plan_tiles_count_ids_and_buffer() -> None:
    tiles = plan_tiles(BBOX, CRS)
    assert len(tiles) == 9
    assert tiles[0].tile_id == "e485000_n3620000"
    assert [t.tile_id for t in tiles] == sorted(
        (t.tile_id for t in tiles), key=lambda s: tuple(int(p[1:]) for p in s.split("_"))
    )
    for t in tiles:
        x0, y0, x1, y1 = t.bounds
        assert (x1 - x0, y1 - y0) == (500.0, 500.0)
        assert x0 % 500 == 0 and y0 % 500 == 0
        assert t.buffered == (x0 - 20, y0 - 20, x1 + 20, y1 + 20)
        assert t.tile_id == f"e{round(x0)}_n{round(y0)}"
    # Union of the tiles covers the bbox in local coordinates.
    from palmscan.geo import to_local

    lon, lat = (BBOX[0], BBOX[2]), (BBOX[1], BBOX[3])
    xs, ys = to_local(np.array(lon), np.array(lat), CRS)
    assert (
        min(t.bounds[0] for t in tiles) <= xs.min() and max(t.bounds[2] for t in tiles) >= xs.max()
    )
    assert (
        min(t.bounds[1] for t in tiles) <= ys.min() and max(t.bounds[3] for t in tiles) >= ys.max()
    )


def test_plan_tiles_custom_size_and_validation() -> None:
    assert (
        len(plan_tiles(BBOX, CRS, tile_size_m=2000, buffer_m=0)) == 2
    )  # both 2 km tiles straddle the 486000 m line
    with pytest.raises(ValueError):
        plan_tiles(BBOX, CRS, tile_size_m=0)


# --- pipeline ------------------------------------------------------------------------------


def test_pipeline_matches_golden(datasets: list[EptDataset]) -> None:
    tile = plan_tiles(BBOX, CRS)[0]
    srs = parse_ept_srs(_load("ept_sample.json"))
    got = build_pipeline(
        _ds(datasets, "SYN_SanDiego_2018"),
        tile,
        CRS,
        (7, 18),
        Path("out") / "tile.laz",
        ept_srs=srs,
    )
    assert got == _load("expected_pipeline.json")


def test_pipeline_without_noise_classes_has_no_range_filter(datasets: list[EptDataset]) -> None:
    tile = plan_tiles(BBOX, CRS)[0]
    got = build_pipeline(datasets[0], tile, CRS, (), Path("t.laz"), ept_srs="EPSG:3857")
    assert [s["type"] for s in got["pipeline"]] == [
        "readers.ept",
        "filters.reprojection",
        "writers.las",
    ]


def test_ept_srs_parsing() -> None:
    assert parse_ept_srs(_load("ept_sample.json")).to_epsg() == 3857
    wkt_only = {
        "srs": {
            "wkt": parse_ept_srs({"srs": {"authority": "EPSG", "horizontal": "32611"}}).to_wkt()
        }
    }
    assert parse_ept_srs(wkt_only).to_epsg() == 32611
    with pytest.raises(SourceError):
        parse_ept_srs({})
    with pytest.raises(SourceError):
        parse_ept_srs({"srs": {}})
    with pytest.raises(SourceError):
        parse_ept_srs({"srs": {"authority": "EPSG", "horizontal": "notacode"}})


# --- cache / fetch_tile --------------------------------------------------------------------


def _fetch(
    cache: Cache,
    runner: FakeRunner,
    ds: EptDataset,
    tile: LidarTile,
    params: LidarParams | None = None,
    srs_calls: list[int] | None = None,
) -> Path:
    def srs() -> str:
        if srs_calls is not None:
            srs_calls.append(1)
        return "EPSG:3857"

    return fetch_tile(ds, tile, CRS, params or LidarParams(), cache, ept_srs=srs, runner=runner)


def test_fetch_tile_writes_laz_and_meta(tmp_path: Path, datasets: list[EptDataset]) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]
    runner = FakeRunner(count=7)
    path = _fetch(Cache(tmp_path), runner, ds, tile)
    assert path == tmp_path / "lidar" / "SYN_SanDiego_2018" / "e485000_n3620000.laz"
    assert path.read_bytes() == b"LAZ"
    meta = pc.read_meta(path)
    assert meta["url"] == ds.url
    assert meta["params"]["point_count"] == 7
    assert meta["params"]["pdal_version"] == "fake-1"
    assert meta["params"]["bounds"] == list(tile.bounds)
    assert meta["params"]["dataset"] == "SYN_SanDiego_2018"
    # PDAL was pointed at a part file beside the target, not at the target itself.
    target = runner.written[0]["pipeline"][-1]["filename"]
    assert target != path.as_posix() and target.endswith(".laz")
    assert not list(path.parent.glob("*.part-*"))


def test_cached_tile_is_not_refetched(tmp_path: Path, datasets: list[EptDataset]) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]
    runner, srs_calls = FakeRunner(), []
    cache = Cache(tmp_path)
    first = _fetch(cache, runner, ds, tile, srs_calls=srs_calls)
    again = _fetch(cache, runner, ds, tile, srs_calls=srs_calls)
    assert first == again
    assert len(runner.written) == 1 and len(srs_calls) == 1  # ept.json not needed on a hit
    offline = _fetch(Cache(tmp_path, offline=True), runner, ds, tile)
    assert offline == first and len(runner.written) == 1


def test_refresh_refetches(tmp_path: Path, datasets: list[EptDataset]) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]
    runner = FakeRunner()
    _fetch(Cache(tmp_path), runner, ds, tile)
    _fetch(Cache(tmp_path, refresh=True), runner, ds, tile)
    assert len(runner.written) == 2


def test_offline_miss_raises_cachemiss(tmp_path: Path, datasets: list[EptDataset]) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]
    runner = FakeRunner()
    with pytest.raises(CacheMiss):
        _fetch(Cache(tmp_path, offline=True), runner, ds, tile)
    assert runner.written == []


def test_changed_noise_classes_invalidate_the_cache(
    tmp_path: Path, datasets: list[EptDataset]
) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]
    runner = FakeRunner()
    _fetch(Cache(tmp_path), runner, ds, tile)
    other = LidarParams(noise_classes=(7,))
    _fetch(Cache(tmp_path), runner, ds, tile, other)
    assert len(runner.written) == 2
    with pytest.raises(CacheMiss, match="other settings"):
        _fetch(Cache(tmp_path, offline=True), runner, ds, tile)


def test_failed_run_leaves_no_cache_entry(tmp_path: Path, datasets: list[EptDataset]) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]

    class Broken(FakeRunner):
        def write(self, pipeline: Any) -> int | None:
            Path(pipeline["pipeline"][-1]["filename"]).write_bytes(b"half")
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _fetch(Cache(tmp_path), Broken(), ds, tile)
    folder = tmp_path / "lidar" / "SYN_SanDiego_2018"
    assert list(folder.iterdir()) == []


def test_runner_that_writes_nothing_is_an_error(tmp_path: Path, datasets: list[EptDataset]) -> None:
    ds, tile = _ds(datasets, "SYN_SanDiego_2018"), plan_tiles(BBOX, CRS)[0]

    class Silent(FakeRunner):
        def write(self, pipeline: Any) -> int | None:
            return 0

    with pytest.raises(SourceError, match="did not write"):
        _fetch(Cache(tmp_path), Silent(), ds, tile)


# --- boundaries cache ----------------------------------------------------------------------


def test_load_boundaries_caches_and_goes_offline(tmp_path: Path) -> None:
    http = FakeHttp({le.BOUNDARIES_URL: FIX / "boundaries_sample.geojson"})
    cache = Cache(tmp_path)
    assert len(load_boundaries(cache, http)) == 3  # type: ignore[arg-type]
    assert len(load_boundaries(cache, http)) == 3  # type: ignore[arg-type]
    assert http.downloads == [le.BOUNDARIES_URL]
    assert len(load_boundaries(Cache(tmp_path, offline=True), http)) == 3  # type: ignore[arg-type]
    with pytest.raises(CacheMiss):
        load_boundaries(Cache(tmp_path / "empty", offline=True), http)  # type: ignore[arg-type]


def test_stale_boundaries_are_refetched_online_but_used_offline(tmp_path: Path) -> None:
    http = FakeHttp({le.BOUNDARIES_URL: FIX / "boundaries_sample.geojson"})
    cache = Cache(tmp_path)
    load_boundaries(cache, http)  # type: ignore[arg-type]
    path = cache.path_for(le.BOUNDARIES_NAMESPACE, le.cache_key(le.BOUNDARIES_URL), ".geojson")
    meta = pc.meta_path(path)
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["fetched_at"] = "2020-01-01T00:00:00Z"
    meta.write_text(json.dumps(data), encoding="utf-8")
    load_boundaries(Cache(tmp_path, offline=True), http)  # type: ignore[arg-type]
    assert len(http.downloads) == 1
    load_boundaries(cache, http)  # type: ignore[arg-type]
    assert len(http.downloads) == 2


# --- point source and chm contract ---------------------------------------------------------


def _cfg(**lidar: Any) -> Any:
    raw: dict[str, Any] = {"region": "san-diego-coastal", "bbox": BBOX}
    if lidar:
        raw["palmscan"] = {"lidar": lidar}
    return scan_config_from_mapping(raw)


def test_point_source_pairs_tiles_with_newest_dataset(
    tmp_path: Path, datasets: list[EptDataset]
) -> None:
    src = EptPointSource(_cfg(), Cache(tmp_path), None, FakeRunner(), datasets=datasets)  # type: ignore[arg-type]
    pairs = src.tiles()
    assert len(pairs) == 9
    assert {d.name for d, _ in pairs} == {"SYN_SanDiego_2018"}
    assert src.tiles() is pairs  # planned once


def test_point_source_respects_forced_datasets(tmp_path: Path, datasets: list[EptDataset]) -> None:
    cfg = _cfg(datasets=["SYN_SanDiego_2014"])
    src = EptPointSource(cfg, Cache(tmp_path), None, FakeRunner(), datasets=datasets)  # type: ignore[arg-type]
    assert {d.name for d, _ in src.tiles()} == {"SYN_SanDiego_2014"}


def test_point_source_without_coverage_raises(tmp_path: Path, datasets: list[EptDataset]) -> None:
    far = scan_config_from_mapping(
        {"region": "x", "id_prefix": "xx", "bbox": [-100.0, 40.0, -99.99, 40.01]}
    )
    src = EptPointSource(far, Cache(tmp_path), None, FakeRunner(), datasets=datasets)  # type: ignore[arg-type]
    with pytest.raises(SourceError, match="no 3DEP EPT coverage"):
        src.tiles()


def _raw_points(n: int = 50) -> np.ndarray:
    """What PDAL hands back: many dimensions, various dtypes, extra fields."""
    dt = np.dtype(
        [
            ("X", "f8"),
            ("Y", "f8"),
            ("Z", "f8"),
            ("Intensity", "u2"),
            ("ReturnNumber", "u1"),
            ("NumberOfReturns", "u1"),
            ("Classification", "u1"),
            ("GpsTime", "f8"),
        ]
    )
    arr = np.zeros(n, dtype=dt)
    arr["X"] = np.linspace(485000, 485010, n)
    arr["Y"] = np.linspace(3620000, 3620010, n)
    arr["Z"] = 10.0
    arr["Classification"] = 2
    arr["ReturnNumber"] = 1
    arr["NumberOfReturns"] = 1
    return arr


def test_read_points_returns_the_chm_fields(tmp_path: Path) -> None:
    runner = FakeRunner(points=_raw_points())
    out = read_points(tmp_path / "t.laz", runner)
    assert out.dtype == le.POINT_DTYPE
    assert out.dtype.names == (
        "X",
        "Y",
        "Z",
        "Classification",
        "ReturnNumber",
        "NumberOfReturns",
    )
    assert runner.reads[0]["pipeline"][0]["type"] == "readers.las"
    assert len(out) == 50


def test_read_points_missing_dimension(tmp_path: Path) -> None:
    raw = _raw_points()
    bad = raw[[n for n in raw.dtype.names if n != "NumberOfReturns"]]  # type: ignore[union-attr]
    with pytest.raises(SourceError, match="NumberOfReturns"):
        read_points(tmp_path / "t.laz", FakeRunner(points=bad))


def test_points_feed_build_chm(tmp_path: Path, datasets: list[EptDataset]) -> None:
    runner = FakeRunner(points=_raw_points(200))
    src = EptPointSource(_cfg(), Cache(tmp_path), None, runner, datasets=datasets)  # type: ignore[arg-type]
    ds, tile = src.tiles()[0]
    src.ept_srs = lambda _ds: le.parse_ept_srs(_load("ept_sample.json"))  # type: ignore[method-assign]
    pts = src.points(ds, tile)
    chm = build_chm(pts, (485000.0, 3620000.0, 485020.0, 3620020.0), CRS)
    assert chm.chm.shape == (40, 40)
    assert len(runner.written) == 1


# --- PDAL (skipped when absent) and network ------------------------------------------------


def test_pdal_python_runner_roundtrip(tmp_path: Path) -> None:
    """Write a LAZ with PDAL from an in-memory array and read it back with read_points."""
    pdal = pytest.importorskip("pdal", reason="PDAL Python binding not installed")
    arr = _raw_points(20)
    out = tmp_path / "rt.laz"
    spec = [{"type": "writers.las", "filename": out.as_posix(), "compression": "laszip"}]
    pdal.Pipeline(json.dumps(spec), arrays=[arr]).execute()
    got = read_points(out)
    assert got.dtype == le.POINT_DTYPE and len(got) == 20
    assert np.allclose(got["Z"], 10.0, atol=0.01)


def test_runner_without_pdal_gives_a_clear_error(tmp_path: Path) -> None:
    try:
        import pdal  # noqa: F401
    except ImportError:
        with pytest.raises(SourceError, match="pdal Python binding"):
            le.PdalPythonRunner().write({"pipeline": []})
    else:
        pytest.skip("PDAL is installed; the absent-PDAL error path cannot be exercised")


@pytest.mark.network
def test_live_ept_json_srs_is_read() -> None:
    from palmscan.http import HttpClient

    ds = EptDataset(
        "USGS_LPC_CA_SanDiegoQL1_2014_LAS_2016",
        "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/"
        "USGS_LPC_CA_SanDiegoQL1_2014_LAS_2016/ept.json",
        2014,
        parse_boundaries(_load("boundaries_sample.geojson"))[0].footprint,
    )
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        srs = le.load_ept_srs(ds, Cache(Path(tmp)), HttpClient())
    assert srs.to_epsg() == 3857
