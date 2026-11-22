"""palmscan building footprint adapter. Offline; synthetic Overpass JSON and a tiny file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, Polygon, mapping

from palmcore.contract import validate_buildings
from palmscan.cache import Cache
from palmscan.config import ScanConfig, scan_config_from_mapping
from palmscan.geo import local_crs
from palmscan.sources.base import SourceError
from palmscan.sources.buildings import (
    MICROSOFT_ATTRIBUTION,
    NO_BUILDINGS_WARNING,
    SOURCE_NOTICES,
    fetch_buildings,
)
from palmscan.sources.overpass import OSM_ATTRIBUTION

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "palmscan" / "buildings"
OVERPASS = (FIXTURES / "overpass_buildings.json").read_text(encoding="utf-8")
MS_FILE = FIXTURES / "ms_footprints_sample.geojsonl"
BBOX = [-117.2540, 32.7885, -117.2520, 32.7905]  # one Overpass tile around the fixtures

Result = tuple[gpd.GeoDataFrame, list[str]]


class FakeHttp:
    """Stands in for HttpClient.post_text and records the queries."""

    def __init__(self, reply: str = OVERPASS) -> None:
        self.reply = reply
        self.queries: list[str] = []

    def post_text(self, url: str, data: dict[str, Any]) -> str:
        self.queries.append(data["data"])
        return self.reply


def make_cfg(buildings: Any = "osm", path: Path | None = None) -> ScanConfig:
    sources: dict[str, Any] = {"buildings": buildings}
    if path is not None:
        sources["buildings_path"] = str(path)
    return scan_config_from_mapping({"region": "test-buildings", "bbox": BBOX, "sources": sources})


def run(cfg: ScanConfig, tmp_path: Path, http: FakeHttp | None = None) -> Result:
    client: Any = http if http is not None else FakeHttp()
    return fetch_buildings(cfg, Cache(tmp_path / "cache"), client)


def fetch_osm(tmp_path: Path, reply: str = OVERPASS) -> Result:
    return run(make_cfg("osm"), tmp_path, FakeHttp(reply))


def area_m2(geom: Any) -> float:
    crs = local_crs(BBOX)
    return float(gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(crs).area.iloc[0])


def assert_contract(frame: gpd.GeoDataFrame) -> None:
    doc = {
        "type": "FeatureCollection",
        "schema_version": "1.0",
        "region": "test-buildings",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(json.dumps(mapping(row.geometry))),
                "properties": {"building_id": row.building_id, "source": row.source},
            }
            for row in frame.itertuples()
        ],
    }
    report = validate_buildings(doc)
    assert not [i for i in report.issues if i.severity == "error"], report.issues


def test_osm_counts_and_ids(tmp_path: Path) -> None:
    frame, warnings = fetch_osm(tmp_path)
    assert list(frame.columns) == ["building_id", "source", "geometry"]
    assert str(frame.crs) == "EPSG:4326"
    assert list(frame.building_id) == ["relation/2001", "way/1001", "way/1006"]
    assert set(frame.source) == {"osm"}
    assert any("1 unclosed" in w for w in warnings)
    assert any("1 multipolygon relations skipped" in w for w in warnings)
    assert any("1 invalid geometries repaired" in w for w in warnings)


def test_simple_way_is_a_polygon_of_the_right_area(tmp_path: Path) -> None:
    frame, _ = fetch_osm(tmp_path)
    geom = frame.set_index("building_id").geometry["way/1001"]
    assert isinstance(geom, Polygon)
    assert area_m2(geom) == pytest.approx(400.0, rel=0.01)


def test_multipolygon_has_courtyard_hole(tmp_path: Path) -> None:
    frame, _ = fetch_osm(tmp_path)
    geom = frame.set_index("building_id").geometry["relation/2001"]
    assert isinstance(geom, Polygon)  # one polygon: outer ring split over two ways is joined
    assert len(geom.interiors) == 1
    assert area_m2(geom) == pytest.approx(40 * 40 - 10 * 10, rel=0.01)


def test_self_intersecting_way_is_repaired(tmp_path: Path) -> None:
    frame, _ = fetch_osm(tmp_path)
    geom = frame.set_index("building_id").geometry["way/1006"]
    assert isinstance(geom, MultiPolygon)
    assert area_m2(geom) == pytest.approx(50.0, rel=0.02)


def test_unclosed_way_and_broken_relation_are_skipped(tmp_path: Path) -> None:
    frame, _ = fetch_osm(tmp_path)
    ids = set(frame.building_id)
    assert "way/1002" not in ids
    assert "relation/2002" not in ids
    assert not any(i.startswith("node/") for i in ids)


def test_osm_output_is_valid_nonempty_and_contract_conformant(tmp_path: Path) -> None:
    frame, _ = fetch_osm(tmp_path)
    assert frame.geometry.is_valid.all()
    assert not frame.geometry.is_empty.any()
    assert set(frame.geom_type) <= {"Polygon", "MultiPolygon"}
    assert_contract(frame)


def test_osm_carries_attribution_and_uses_the_buildings_query(tmp_path: Path) -> None:
    http = FakeHttp()
    frame, _ = run(make_cfg("osm"), tmp_path, http)
    assert frame.attrs["attribution"] == OSM_ATTRIBUTION
    assert frame.attrs["license"] == "ODbL-1.0"
    assert len(http.queries) == 1
    assert 'way["building"]' in http.queries[0]
    assert "out geom" in http.queries[0]


def test_osm_runtime_error_raises(tmp_path: Path) -> None:
    reply = json.dumps({"elements": [], "remark": "runtime error: Query timed out"})
    with pytest.raises(SourceError):
        fetch_osm(tmp_path, reply)


def test_osm_response_is_cached(tmp_path: Path) -> None:
    http = FakeHttp()
    run(make_cfg("osm"), tmp_path, http)
    run(make_cfg("osm"), tmp_path, http)
    assert len(http.queries) == 1


def test_microsoft_read_is_clipped_to_bbox(tmp_path: Path) -> None:
    frame, warnings = run(make_cfg("microsoft_footprints", MS_FILE), tmp_path)
    # rows 3 and 4 are kilometres away; row 5 is a bowtie that gets repaired
    assert list(frame.building_id) == ["msbf:0", "msbf:1", "msbf:2", "msbf:5"]
    assert set(frame.source) == {"microsoft_footprints"}
    assert frame.attrs["attribution"] == MICROSOFT_ATTRIBUTION
    assert any("1 invalid geometries repaired" in w for w in warnings)
    assert frame.geometry.is_valid.all()
    assert not frame.geometry.is_empty.any()
    assert_contract(frame)


def test_microsoft_reads_plain_geojson_and_gpkg(tmp_path: Path) -> None:
    source = gpd.read_file(MS_FILE)
    geojson = tmp_path / "ms.geojson"
    gpkg = tmp_path / "ms.gpkg"
    source.to_file(geojson, driver="GeoJSON")
    source.to_file(gpkg, driver="GPKG")
    for path in (geojson, gpkg):
        frame, _ = run(make_cfg("microsoft_footprints", path), tmp_path)
        assert len(frame) == 4, path.name
        assert all(i.startswith("msbf:") for i in frame.building_id)


def test_microsoft_file_in_projected_crs_is_reprojected(tmp_path: Path) -> None:
    path = tmp_path / "ms_utm.gpkg"
    gpd.read_file(MS_FILE).to_crs("EPSG:32611").to_file(path, driver="GPKG")
    frame, warnings = run(make_cfg("microsoft_footprints", path), tmp_path)
    assert len(frame) == 4
    assert str(frame.crs) == "EPSG:4326"
    assert frame.total_bounds[0] == pytest.approx(-117.2535, abs=0.001)
    assert any("reprojected" in w for w in warnings)


def test_microsoft_missing_path_or_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="buildings_path"):
        run(make_cfg("microsoft_footprints"), tmp_path)
    with pytest.raises(SourceError, match="not found"):
        run(make_cfg("microsoft_footprints", tmp_path / "nope.geojsonl"), tmp_path)


def test_microsoft_unreadable_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.geojsonl"
    bad.write_text("not geojson at all\n", encoding="utf-8")
    with pytest.raises(SourceError):
        run(make_cfg("microsoft_footprints", bad), tmp_path)


@pytest.mark.parametrize("value", ["none", None])
def test_no_source_returns_empty_frame_and_warning(tmp_path: Path, value: Any) -> None:
    http = FakeHttp()
    frame, warnings = run(make_cfg(value), tmp_path, http)
    assert len(frame) == 0
    assert list(frame.columns) == ["building_id", "source", "geometry"]
    assert str(frame.crs) == "EPSG:4326"
    assert warnings == [NO_BUILDINGS_WARNING]
    assert http.queries == []
    assert_contract(frame)


def test_empty_osm_response_gives_empty_frame(tmp_path: Path) -> None:
    frame, warnings = fetch_osm(tmp_path, json.dumps({"elements": []}))
    assert len(frame) == 0
    assert list(frame.columns) == ["building_id", "source", "geometry"]
    assert warnings == []


def test_notices_cover_both_sources() -> None:
    assert set(SOURCE_NOTICES) == {"osm", "microsoft_footprints"}
