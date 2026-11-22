"""palmscan ``arcgis_rest`` adapter. Offline: a fake transport serves synthetic Esri JSON."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from palmscan.cache import Cache, CacheMiss
from palmscan.config import InventorySourceCfg
from palmscan.sources import arcgis_rest
from palmscan.sources.arcgis_rest import ArcGisRestAdapter
from palmscan.sources.base import FetchResult, SourceError

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "palmscan" / "arcgis_rest"
URL = "https://example.invalid/arcgis/rest/services/Trees/MapServer/20"
BBOX = (-117.28, 32.70, -117.15, 32.82)


def load(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return loaded


def make_cfg(**overrides: Any) -> InventorySourceCfg:
    base: dict[str, Any] = {
        "name": "sd_street_trees",
        "type": "arcgis_rest",
        "url": URL,
        "path": None,
        "format": None,
        "species_field": "SPECIES_NAME",
        "common_name_field": "COMMON_NAME",
        "id_field": "OBJECTID",
        "status_field": None,
        "height_field": "HEIGHT_FT",
        "height_units": "ft",
        "dbh_field": "DBH_IN",
        "date_field": "INSPCTDATE",
        "lon_field": None,
        "lat_field": None,
        "where": None,
        "vintage": None,
        "license": None,
        "cache_max_age_days": None,
        "options": {},
    }
    base.update(overrides)
    return InventorySourceCfg(**base)


class FakeHttp:
    """Serves fixture JSON keyed on the request parameters; records every call."""

    def __init__(
        self, info: dict[str, Any] | None = None, pages: list[dict[str, Any]] | None = None
    ) -> None:
        self.info = info if info is not None else load("layer_info.json")
        self.pages = pages or [load("query_page_0.json"), load("query_page_1.json")]
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        p = dict(params or {})
        self.calls.append((url, p))
        if url == URL:
            return copy.deepcopy(self.info)
        assert url == f"{URL}/query"
        if p.get("returnIdsOnly") == "true":
            return load("ids_only.json")
        if "objectIds" in p:
            wanted = {int(i) for i in str(p["objectIds"]).split(",")}
            body = load("query_by_ids.json")
            body["features"] = [
                f for f in body["features"] if f["attributes"]["OBJECTID"] in wanted
            ]
            return body
        size = int(p["resultRecordCount"])
        index = int(p["resultOffset"]) // size
        return copy.deepcopy(self.pages[index]) if index < len(self.pages) else {"features": []}

    @property
    def queries(self) -> list[dict[str, Any]]:
        return [p for u, p in self.calls if u.endswith("/query")]


def run(
    http: FakeHttp, tmp_path: Path, cfg: InventorySourceCfg | None = None, **cache_kw: Any
) -> FetchResult:
    adapter = ArcGisRestAdapter(cfg or make_cfg())
    return adapter.fetch(BBOX, Cache(tmp_path / "cache", **cache_kw), http)  # type: ignore[arg-type]


def test_two_page_pull(tmp_path: Path) -> None:
    result = run(FakeHttp(), tmp_path)
    assert [r.source_id for r in result.records] == ["101", "102", "103", "104", "105"]
    first = result.records[0]
    assert (first.lon, first.lat) == (-117.2531, 32.7893)
    assert first.source == "sd_street_trees"
    assert first.species_raw == "Washingtonia robusta"
    assert first.common_name_raw == "Mexican Fan Palm"
    assert first.height_raw == "45"
    assert first.dbh_raw == "14"
    assert first.date_raw == "1546300800000"
    assert result.records[4].species_raw is None
    assert (result.vintage.basis, result.vintage.vintage) == ("record_dates", "2019")


def test_query_parameters_and_paging(tmp_path: Path) -> None:
    http = FakeHttp()
    run(http, tmp_path)
    assert http.calls[0] == (URL, {"f": "json"})
    assert len(http.queries) == 2  # page 1 is partial: no third request
    q0, q1 = http.queries
    assert q0["where"] == "1=1"
    assert q0["geometry"] == "-117.28,32.7,-117.15,32.82"
    assert q0["geometryType"] == "esriGeometryEnvelope"
    assert q0["inSR"] == 4326 and q0["outSR"] == 4326
    assert q0["spatialRel"] == "esriSpatialRelIntersects"
    assert q0["outFields"] == "*" and q0["returnGeometry"] == "true"
    assert q0["orderByFields"] == "OBJECTID ASC" and q0["f"] == "json"
    assert (q0["resultOffset"], q0["resultRecordCount"]) == (0, 3)  # maxRecordCount from layer
    assert q1["resultOffset"] == 3


def test_page_size_capped_at_2000(tmp_path: Path) -> None:
    info = load("layer_info.json")
    info["maxRecordCount"] = 10_000
    http = FakeHttp(info=info, pages=[load("query_page_1.json")])
    run(http, tmp_path)
    assert http.queries[0]["resultRecordCount"] == 2000


def test_default_max_record_count_when_absent(tmp_path: Path) -> None:
    info = load("layer_info.json")
    del info["maxRecordCount"]
    http = FakeHttp(info=info, pages=[load("query_page_1.json")])
    run(http, tmp_path)
    assert http.queries[0]["resultRecordCount"] == 1000


def test_full_page_without_transfer_flag_continues(tmp_path: Path) -> None:
    page0 = load("query_page_0.json")
    del page0["exceededTransferLimit"]
    http = FakeHttp(pages=[page0, load("query_page_1.json")])
    assert len(run(http, tmp_path).records) == 5
    assert len(http.queries) == 2


def test_where_clause_is_passed(tmp_path: Path) -> None:
    http = FakeHttp()
    run(http, tmp_path, make_cfg(where="GENUS='Washingtonia'"))
    assert http.queries[0]["where"] == "GENUS='Washingtonia'"


def test_no_pagination_fallback_matches(tmp_path: Path) -> None:
    paged = run(FakeHttp(), tmp_path / "a")
    http = FakeHttp(info=load("layer_info_nopaging.json"))
    fallback = run(http, tmp_path / "b")
    assert fallback.records == paged.records
    assert any("pagination" in w for w in fallback.warnings)
    assert not any("resultOffset" in p for p in http.queries)
    assert http.queries[0]["returnIdsOnly"] == "true"
    id_chunks = [p["objectIds"] for p in http.queries if "objectIds" in p]
    assert id_chunks == ["101,102,103", "104,105"]  # chunks of the page size


def test_error_body_with_http_200_raises(tmp_path: Path) -> None:
    http = FakeHttp(pages=[load("error.json")])
    with pytest.raises(SourceError, match=r"400.*Unable to complete operation"):
        run(http, tmp_path)


def test_error_in_layer_info_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="400"):
        run(FakeHttp(info=load("error.json")), tmp_path)


def test_error_bodies_are_not_cached(tmp_path: Path) -> None:
    with pytest.raises(SourceError):
        run(FakeHttp(pages=[load("error.json")]), tmp_path)
    http = FakeHttp()
    assert len(run(http, tmp_path).records) == 5
    assert len(http.queries) == 2  # the failed page was fetched again, not replayed


def test_missing_species_field_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="species_field 'GENUS_SPECIES'"):
        run(FakeHttp(), tmp_path, make_cfg(species_field="GENUS_SPECIES"))


def test_missing_optional_field_warns(tmp_path: Path) -> None:
    result = run(FakeHttp(), tmp_path, make_cfg(status_field="STATUS"))
    assert any("'STATUS'" in w for w in result.warnings)


def test_null_and_non_point_geometry_skipped_and_counted(tmp_path: Path) -> None:
    page0 = load("query_page_0.json")
    page0["features"][1]["geometry"] = {"paths": [[[0, 0], [1, 1]]]}
    page1 = load("query_page_1.json")
    page1["features"][0]["geometry"] = None
    page1["features"][1]["geometry"] = {"x": "NaN", "y": "NaN"}
    result = run(FakeHttp(pages=[page0, page1]), tmp_path)
    assert [r.source_id for r in result.records] == ["101", "103"]
    assert any("2 features skipped: null or empty geometry" in w for w in result.warnings)
    assert any("1 features skipped: geometry is not a point" in w for w in result.warnings)


def test_points_outside_bbox_dropped(tmp_path: Path) -> None:
    page1 = load("query_page_1.json")
    page1["features"][0]["geometry"] = {"x": 0.0, "y": 0.0}
    result = run(FakeHttp(pages=[load("query_page_0.json"), page1]), tmp_path)
    assert [r.source_id for r in result.records] == ["101", "102", "103", "105"]
    assert any("outside bbox" in w for w in result.warnings)


def test_server_ignoring_offset_is_detected(tmp_path: Path) -> None:
    page0 = load("query_page_0.json")
    with pytest.raises(SourceError, match="ignored resultOffset"):
        run(FakeHttp(pages=[page0, page0, page0]), tmp_path)


def test_record_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(arcgis_rest, "MAX_RECORDS", 4)
    with pytest.raises(SourceError, match="more than 4 records"):
        run(FakeHttp(), tmp_path / "a")
    with pytest.raises(SourceError, match="more than 4 records"):
        run(FakeHttp(info=load("layer_info_nopaging.json")), tmp_path / "b")


def test_vintage_precedence(tmp_path: Path) -> None:
    assert run(FakeHttp(), tmp_path / "a", make_cfg(vintage="2023")).vintage.basis == "config"
    no_dates = make_cfg(date_field=None)
    edit = run(FakeHttp(), tmp_path / "b", no_dates).vintage
    assert (edit.basis, edit.vintage) == ("layer_edit_date", "2021")
    info = load("layer_info.json")
    del info["editingInfo"]
    assert run(FakeHttp(info=info), tmp_path / "c", no_dates).vintage.basis == "fetched"


def test_missing_url_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="needs url"):
        run(FakeHttp(), tmp_path, make_cfg(url=None))


def test_warm_cache_makes_no_http_calls(tmp_path: Path) -> None:
    first = FakeHttp()
    cold = run(first, tmp_path)
    assert len(first.calls) == 3
    second = FakeHttp()
    warm = run(second, tmp_path)
    assert second.calls == []
    assert warm.records == cold.records


def test_refresh_refetches(tmp_path: Path) -> None:
    run(FakeHttp(), tmp_path)
    again = FakeHttp()
    run(again, tmp_path, refresh=True)
    assert len(again.calls) == 3


def test_offline_cache_miss_raises(tmp_path: Path) -> None:
    http = FakeHttp()
    with pytest.raises(CacheMiss):
        run(http, tmp_path, offline=True)
    assert http.calls == []


def test_offline_with_warm_cache_works(tmp_path: Path) -> None:
    run(FakeHttp(), tmp_path)
    http = FakeHttp()
    assert len(run(http, tmp_path, offline=True).records) == 5
    assert http.calls == []
