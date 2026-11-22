"""Recorded live source responses (SCAN-007) parse offline and normalise as expected.

The fixtures under ``tests/fixtures/palmscan/recorded/`` are real responses recorded on
2026-11-22 (see the README there). Each test replays them through the real adapter, then
re-runs the adapter against the warmed cache with a client that fails on any request.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from palmcore.contract import validate_buildings
from palmscan.attributes import parse_height
from palmscan.cache import Cache
from palmscan.config import InventorySourceCfg, load_scan_config, scan_config_from_mapping
from palmscan.filters import non_tree_reason, palm_filter
from palmscan.model import TreeRecord
from palmscan.sources.arcgis_rest import ArcGisRestAdapter
from palmscan.sources.base import FetchResult
from palmscan.sources.buildings import fetch_buildings
from palmscan.sources.geojson_file import GeoJsonFileAdapter
from palmscan.sources.osm_overpass import OsmTreesAdapter
from palmscan.sources.overpass import OSM_ATTRIBUTION, OverpassClient
from palmscan.species_names import normalize_species

ROOT = Path(__file__).resolve().parents[3]
RECORDED = ROOT / "tests" / "fixtures" / "palmscan" / "recorded"

# Recording bboxes (lon_min, lat_min, lon_max, lat_max): 400 m x 400 m, see the README.
SD_BBOX = (-117.25523713722649, 32.78750337765001, -117.25096286277352, 32.79109662234998)
OSM_BBOX = (-117.21153694263549, 32.77940337765001, -117.20726305736451, 32.782996622349984)
SM_BBOX = (-118.49966745499573, 34.01140337765001, -118.49533254500427, 34.01499662234998)

SD_LAYER = "https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20"


def load_json(*parts: str) -> Any:
    return json.loads(RECORDED.joinpath(*parts).read_text(encoding="utf-8"))


class ReplayHttp:
    """Replays recorded bodies in place of ``HttpClient``; counts the calls it serves."""

    def __init__(self, json_by_url: dict[str, Any] | None = None, text: str | None = None) -> None:
        self.json_by_url = json_by_url or {}
        self.text = text
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((url, dict(params or {})))
        return self.json_by_url[url]

    def post_text(self, url: str, data: dict[str, Any]) -> str:
        assert self.text is not None
        self.calls.append((url, dict(data)))
        return self.text


class NoNetwork:
    """Any request is a test failure: the warmed cache must answer."""

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        raise AssertionError(f"unexpected network request: {url}")

    def post_text(self, url: str, data: dict[str, Any]) -> str:
        raise AssertionError(f"unexpected network request: {url}")

    def download(self, url: str, dest: Path) -> None:
        raise AssertionError(f"unexpected network request: {url}")


def sd_cfg() -> InventorySourceCfg:
    cfg = load_scan_config(ROOT / "regions" / "san-diego-coastal.yaml")
    return cfg.region.sources.inventory[0]


def sd_fetch(tmp_path: Path) -> tuple[FetchResult, ReplayHttp]:
    http = ReplayHttp(
        {
            SD_LAYER: load_json("sd_street_trees", "layer_info.json"),
            f"{SD_LAYER}/query": load_json("sd_street_trees", "query_page_0.json"),
        }
    )
    result = ArcGisRestAdapter(sd_cfg()).fetch(SD_BBOX, Cache(tmp_path / "cache"), http)  # type: ignore[arg-type]
    return result, http


def normalized(record: TreeRecord) -> tuple[str | None, bool]:
    ns = normalize_species(record.species_raw, record.common_name_raw)
    return ns.key, ns.is_palm


def palms_of(records: list[TreeRecord]) -> list[TreeRecord]:
    """Standing palms of any modelled genus set (socal, florida, other)."""
    sets = ("socal", "florida", "other")
    return [
        r
        for r in records
        if non_tree_reason(r.species_raw, r.status_raw) is None
        and palm_filter(normalize_species(r.species_raw, r.common_name_raw), sets, ()) is None
    ]


# --------------------------------------------------------------------- fixtures themselves


def test_each_recorded_fixture_is_under_2_mb_and_has_a_readme_entry() -> None:
    readme = (RECORDED / "README.md").read_text(encoding="utf-8")
    for source in ("sd_street_trees", "la_trees", "osm_trees", "osm_buildings"):
        folder = RECORDED / source
        assert folder.is_dir(), source
        assert source in readme
        assert sum(p.stat().st_size for p in folder.iterdir()) < 2 * 1024 * 1024


# --------------------------------------------------------------------- San Diego layer 20


def test_sd_layer_facts_match_the_config(tmp_path: Path) -> None:
    info = load_json("sd_street_trees", "layer_info.json")
    fields = {f["name"]: f for f in info["fields"]}
    cfg = sd_cfg()
    assert info["maxRecordCount"] == 2000
    assert info["advancedQueryCapabilities"]["supportsPagination"] is True
    assert "editingInfo" not in info  # no layer-level lastEditDate
    for name in (cfg.species_field, cfg.common_name_field, cfg.height_field, cfg.date_field):
        assert name in fields
    assert cfg.status_field == "MAPNG_STAT_CD"
    codes = {c["code"]: c["name"] for c in fields["MAPNG_STAT_CD"]["domain"]["codedValues"]}
    assert codes["RM"] == "REMOVED"
    assert codes["AB"] == "AS BUILT"


def test_sd_adapter_parses_the_recording_and_pages_with_resultoffset(tmp_path: Path) -> None:
    result, http = sd_fetch(tmp_path)
    assert len(result.records) == 49
    assert result.vintage.basis == "record_dates"
    assert result.vintage.vintage == "2022"
    assert result.warnings == []
    query = [params for url, params in http.calls if url.endswith("/query")]
    assert query[0]["resultOffset"] == 0
    assert query[0]["resultRecordCount"] == 2000
    first = result.records[0]
    assert first.source == "sd_street_trees"
    assert first.status_raw in {"AB", "RM"}


def test_sd_replays_from_the_warm_cache_with_no_network(tmp_path: Path) -> None:
    first, _ = sd_fetch(tmp_path)
    again = ArcGisRestAdapter(sd_cfg()).fetch(
        SD_BBOX,
        Cache(tmp_path / "cache", offline=True),
        NoNetwork(),  # type: ignore[arg-type]
    )
    assert [r.source_id for r in again.records] == [r.source_id for r in first.records]


def test_sd_removed_rows_are_rejected_and_standing_palms_normalize(tmp_path: Path) -> None:
    result, _ = sd_fetch(tmp_path)
    removed = [r for r in result.records if r.status_raw == "RM"]
    standing = [r for r in result.records if r.status_raw == "AB"]
    assert removed
    assert all(non_tree_reason(r.species_raw, r.status_raw) == "removed" for r in removed)
    assert all(non_tree_reason(r.species_raw, r.status_raw) is None for r in standing)
    # Removed rows carry no SPECIES_NAME, only a common name that would pass as a palm.
    removed_palm = next(r for r in removed if r.common_name_raw == "Mexican Fan Palm")
    assert removed_palm.species_raw is None
    assert normalized(removed_palm) == ("washingtonia_robusta", True)
    keys = {normalized(r)[0] for r in palms_of(result.records)}
    assert {"washingtonia_robusta", "syagrus_romanzoffiana", "howea_forsteriana"} <= keys
    assert len(palms_of(result.records)) < len(
        [r for r in result.records if normalized(r)[1]]
    )  # the removed palms are the difference


def test_sd_height_dbh_and_date_fields_are_read(tmp_path: Path) -> None:
    result, _ = sd_fetch(tmp_path)
    washingtonia = next(r for r in result.records if r.species_raw == "Washingtonia robusta")
    assert washingtonia.height_raw is not None
    assert parse_height(washingtonia.height_raw, "ft") == pytest.approx(
        float(washingtonia.height_raw) * 0.3048
    )
    assert washingtonia.dbh_raw is not None
    assert washingtonia.date_raw is not None


# --------------------------------------------------------------------- OSM trees


def osm_trees(tmp_path: Path, fixture: str, bbox: tuple[float, ...]) -> FetchResult:
    text = (RECORDED / "osm_trees" / fixture).read_text(encoding="utf-8")
    http = ReplayHttp(text=text)
    client = OverpassClient(http, Cache(tmp_path / "cache"))  # type: ignore[arg-type]
    return OsmTreesAdapter(client).fetch(bbox)


def test_osm_trees_recording_yields_tagged_palms(tmp_path: Path) -> None:
    result = osm_trees(tmp_path, "trees_response.json", OSM_BBOX)
    assert len(result.records) == 30
    assert any("dropped 6 tree node(s)" in w for w in result.warnings)
    assert all(r.source_id.startswith("node/") for r in result.records)
    assert all(r.extra["attribution"] == OSM_ATTRIBUTION for r in result.records)
    assert result.vintage.basis == "fetched"
    palms = palms_of(result.records)
    assert len(palms) == 29
    assert {normalized(r)[0] for r in palms} == {"jubaea_chilensis"}


def test_osm_trees_empty_recording_is_not_an_error(tmp_path: Path) -> None:
    result = osm_trees(tmp_path, "empty_response.json", SD_BBOX)
    assert result.records == []
    assert result.warnings == []


# --------------------------------------------------------------------- OSM buildings


def test_osm_buildings_recording_is_contract_valid(tmp_path: Path) -> None:
    text = (RECORDED / "osm_buildings" / "buildings_response.json").read_text(encoding="utf-8")
    cfg = scan_config_from_mapping(
        {"region": "recorded-sd", "bbox": list(SD_BBOX), "sources": {"buildings": "osm"}}
    )
    frame, warnings = fetch_buildings(cfg, Cache(tmp_path / "cache"), ReplayHttp(text=text))  # type: ignore[arg-type]
    assert len(frame) == 32
    assert warnings == []
    assert all(i.startswith("way/") for i in frame.building_id)
    assert frame.geometry.is_valid.all()
    assert frame.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all()
    doc = {
        "type": "FeatureCollection",
        "schema_version": "1.0",
        "region": "recorded-sd",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(json.dumps(row.geometry.__geo_interface__)),
                "properties": {"building_id": row.building_id, "source": row.source},
            }
            for row in frame.itertuples()
        ],
    }
    report = validate_buildings(doc)
    assert not [i for i in report.issues if i.severity == "error"], report.issues


# --------------------------------------------------------------------- la-trees


def la_cfg(path: Path, **overrides: Any) -> InventorySourceCfg:
    base = load_scan_config(ROOT / "regions" / "la-westside.yaml").region.sources.inventory[0]
    return dataclasses.replace(base, path=path, **overrides)


def test_la_county_slice_matches_the_region_config(tmp_path: Path) -> None:
    path = RECORDED / "la_trees" / "la_county_sample.geojson"
    cfg = la_cfg(path)
    result = GeoJsonFileAdapter(cfg).fetch(SM_BBOX, Cache(tmp_path), NoNetwork())  # type: ignore[arg-type]
    assert len(result.records) == 14
    # The compilation's "id" is a row index and "species" holds common names only.
    assert all(r.source_id.isdigit() for r in result.records)
    assert all(r.common_name_raw is None for r in result.records)
    names = {r.species_raw for r in result.records}
    assert {"Canary Island Date Palm", "Mexican Fan Palm", "Vacant"} <= names
    assert {normalized(r)[0] for r in palms_of(result.records)} == {
        "phoenix_canariensis",
        "washingtonia_robusta",
    }
    vacant = next(r for r in result.records if r.species_raw == "Vacant")
    assert non_tree_reason(vacant.species_raw, vacant.status_raw) == "vacant"


def test_la_santa_monica_clip_reads_state_plane_coordinates(tmp_path: Path) -> None:
    path = RECORDED / "la_trees" / "santa_monica_clip.geojson"
    cfg = la_cfg(
        path,
        name="la_trees_santa_monica",
        species_field="BotanicalN",
        common_name_field="species",
        id_field="OBJECTID",
        height_field="height",
        dbh_field="DBH",
    )
    result = GeoJsonFileAdapter(cfg).fetch(SM_BBOX, Cache(tmp_path), NoNetwork())  # type: ignore[arg-type]
    assert len(result.records) == 42
    assert any("EPSG:2229" in w for w in result.warnings)  # per-city file is not WGS84
    assert all(SM_BBOX[0] <= r.lon <= SM_BBOX[2] for r in result.records)
    assert all(SM_BBOX[1] <= r.lat <= SM_BBOX[3] for r in result.records)
    keys = {normalized(r)[0] for r in palms_of(result.records)}
    assert {"phoenix_canariensis", "washingtonia_robusta", "syagrus_romanzoffiana"} <= keys
    heights = {r.height_raw for r in result.records}
    assert {"15-30", "60+"} <= heights  # height classes, not measurements
    assert parse_height("15-30", "ft") == pytest.approx(22.5 * 0.3048)
    assert parse_height("60+", "ft") is None


# --------------------------------------------------------------------- tables


@pytest.mark.parametrize(
    ("species", "common", "status", "key", "is_palm", "reason"),
    [
        ("Washingtonia robusta", "Mexican Fan Palm", "AB", "washingtonia_robusta", True, None),
        (None, "Mexican Fan Palm", "RM", "washingtonia_robusta", True, "removed"),
        (None, "Palm Species", "RM", "palm_unknown", True, "removed"),
        ("Hyophorbe lagenicaulis", "Bottle Palm", "AB", "palm_unknown", True, None),
        (None, "Bottle Palm", None, "palm_unknown", True, None),
        (None, "Pigmy Date Palm", None, "phoenix_roebelenii", True, None),
        (None, "Filibusta Palm", None, "washingtonia_filibusta", True, None),
        (None, "Clustered Fishtail Palm", None, "caryota_mitis", True, None),
        (None, "Fishtail Wine Palm", None, "caryota_sp", True, None),
        (None, "Ribbon Fan Palm; Weeping Cabba", None, "livistona_sp", True, None),
        (None, "Puerto Rican Hat Palm; Puerto", None, "sabal_sp", True, None),
        (None, "Palmetto Species", None, "sabal_sp", True, None),
        (None, "Hesper Palm", None, "brahea_sp", True, None),
        (None, "Paradise Palm", None, "palm_unknown", True, None),
        (None, "Med Fan Palm", None, "chamaerops_humilis", True, None),
        (None, "PHOENIX MESQUITE", None, None, False, None),
        (None, "Madagascar Palm", None, None, False, None),
        (None, "Pony-tail Palm", None, None, False, None),
        (None, "Travelers Palm", None, None, False, None),
        (None, "Sago Palm", None, None, False, None),
        ("Stump - Not Accessible", None, None, None, False, "stump"),
        ("Vacant Planting Site - Large", None, None, None, False, "vacant"),
        ("Vacant/Inadequate Spacing", None, None, None, False, "vacant"),
    ],
)
def test_recorded_strings_normalize(
    species: str | None,
    common: str | None,
    status: str | None,
    key: str | None,
    is_palm: bool,
    reason: str | None,
) -> None:
    ns = normalize_species(species, common)
    assert (ns.key, ns.is_palm) == (key, is_palm)
    assert non_tree_reason(species, status) == reason


def test_status_code_marker_is_a_whole_string_match() -> None:
    assert non_tree_reason("Washingtonia robusta", "RM") == "removed"
    assert non_tree_reason("Washingtonia robusta", "rm") == "removed"
    # "rm" inside an ordinary word must not trigger it.
    assert non_tree_reason("Washingtonia robusta", "Dormant") is None
    assert non_tree_reason("Washingtonia robusta", "AB") is None
    assert non_tree_reason("Washingtonia robusta", "OP") is None
