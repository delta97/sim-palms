"""palmscan source base helpers and the geojson_file adapter. Offline; synthetic fixtures."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from palmscan.cache import Cache, CacheMiss
from palmscan.config import InventorySourceCfg
from palmscan.geo import Bbox
from palmscan.model import TreeRecord
from palmscan.sources.base import FetchResult, SourceError, derive_vintage, parse_date
from palmscan.sources.geojson_file import GeoJsonFileAdapter

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "palmscan" / "geojson_file"
GEOJSON = FIXTURES / "trees_sample.geojson"
CSV = FIXTURES / "trees_sample.csv"
BBOX = (-118.52, 33.96, -118.37, 34.09)
FETCHED = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
URL = "https://example.invalid/data/trees.geojson"


def make_cfg(**overrides: Any) -> InventorySourceCfg:
    base: dict[str, Any] = {
        "name": "sample",
        "type": "geojson_file",
        "url": None,
        "path": GEOJSON,
        "format": "geojson",
        "species_field": "species",
        "common_name_field": "common_name",
        "id_field": "id",
        "status_field": "status",
        "height_field": "height_ft",
        "height_units": "ft",
        "dbh_field": "dbh_in",
        "date_field": "survey_date",
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


def csv_cfg(**overrides: Any) -> InventorySourceCfg:
    base: dict[str, Any] = {"path": CSV, "format": "csv", "lon_field": "lon", "lat_field": "lat"}
    return make_cfg(**{**base, **overrides})


class NoHttp:
    def download(self, url: str, dest: Path) -> None:
        raise AssertionError("no network expected")


class FakeHttp:
    """Serves a local file for any URL and records the calls."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self.urls: list[str] = []

    def download(self, url: str, dest: Path) -> None:
        self.urls.append(url)
        shutil.copyfile(self.source, dest)


def fetch(
    cfg: InventorySourceCfg, tmp_path: Path, bbox: Bbox | tuple[float, ...] = BBOX
) -> FetchResult:
    adapter = GeoJsonFileAdapter(cfg)
    return adapter.fetch(bbox, Cache(tmp_path / "cache"), NoHttp())  # type: ignore[arg-type]


def by_id(records: list[TreeRecord]) -> dict[str, TreeRecord]:
    return {r.source_id: r for r in records}


# ---------------------------------------------------------------- bbox, mapping, polygons


def test_bbox_clipping_excludes_outside_points(tmp_path: Path) -> None:
    result = fetch(make_cfg(), tmp_path)
    ids = {r.source_id for r in result.records}
    assert ids == {str(i) for i in range(101, 117)} | {"119", "120"}
    for r in result.records:
        assert BBOX[0] <= r.lon <= BBOX[2]
        assert BBOX[1] <= r.lat <= BBOX[3]


def test_accepts_bbox_object(tmp_path: Path) -> None:
    result = fetch(make_cfg(), tmp_path, bbox=Bbox.from_list(BBOX))
    assert len(result.records) == 18


def test_field_mapping(tmp_path: Path) -> None:
    rec = by_id(fetch(make_cfg(), tmp_path).records)["101"]
    assert rec.source == "sample"
    assert rec.species_raw == "Washingtonia robusta"
    assert rec.common_name_raw == "Mexican Fan Palm"
    assert rec.status_raw == "Alive"
    assert rec.height_raw == "45"
    assert rec.dbh_raw == "14"
    assert rec.date_raw == "2019-05-14"
    assert (rec.lon, rec.lat) == pytest.approx((-118.45, 34.02))


def test_missing_values_are_none(tmp_path: Path) -> None:
    records = by_id(fetch(make_cfg(), tmp_path).records)
    assert records["120"].species_raw is None
    assert records["120"].common_name_raw is None
    assert records["116"].date_raw is None
    assert records["116"].height_raw is None


def test_polygon_becomes_point_with_warning(tmp_path: Path) -> None:
    result = fetch(make_cfg(), tmp_path)
    rec = by_id(result.records)["119"]
    assert (rec.lon, rec.lat) == pytest.approx((-118.4795, 34.0005), abs=1e-4)
    assert any("1 non-point" in w and "Polygon" in w for w in result.warnings)


def test_non_palms_are_not_filtered_by_adapter(tmp_path: Path) -> None:
    species = {r.species_raw for r in fetch(make_cfg(), tmp_path).records}
    assert "Quercus agrifolia" in species
    assert None in species


# ---------------------------------------------------------------- CSV parity


def test_csv_matches_geojson(tmp_path: Path) -> None:
    geo = by_id(fetch(make_cfg(), tmp_path).records)
    csv_rows = by_id(fetch(csv_cfg(), tmp_path).records)
    assert set(csv_rows) == set(geo)
    assert len(csv_rows) == 18
    for key, g in geo.items():
        c = csv_rows[key]
        assert (c.lon, c.lat) == pytest.approx((g.lon, g.lat), abs=1e-9)
        assert c.species_raw == g.species_raw
        assert c.common_name_raw == g.common_name_raw
        assert c.status_raw == g.status_raw
        assert c.height_raw == g.height_raw
        assert c.date_raw == g.date_raw


def test_csv_bad_coordinates_counted(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "id,species,lon,lat\n"
        "1,Washingtonia robusta,-118.45,34.02\n"
        "2,Washingtonia robusta,,34.02\n"
        "3,Washingtonia robusta,abc,def\n"
        "4,Washingtonia robusta,-118.40,nan\n"
        "5,Washingtonia robusta,-118.30,34.02\n",
        encoding="utf-8",
    )
    cfg = csv_cfg(
        path=path,
        common_name_field=None,
        status_field=None,
        height_field=None,
        dbh_field=None,
        date_field=None,
    )
    result = fetch(cfg, tmp_path)
    assert [r.source_id for r in result.records] == ["1"]
    assert any("3 rows skipped" in w for w in result.warnings)


def test_csv_requires_coordinate_fields(tmp_path: Path) -> None:
    cfg = make_cfg(path=CSV, format="csv")
    with pytest.raises(SourceError, match="lon_field"):
        fetch(cfg, tmp_path)


def test_csv_missing_column_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="no_such"):
        fetch(csv_cfg(species_field="no_such"), tmp_path)


# ---------------------------------------------------------------- ids


def test_id_fallback_to_feature_id_with_warning(tmp_path: Path) -> None:
    data = json.loads(GEOJSON.read_text(encoding="utf-8"))
    for feat in data["features"]:
        feat["properties"].pop("id")
    path = tmp_path / "noids.geojson"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = fetch(make_cfg(path=path), tmp_path)
    assert len(result.records) == 18
    assert all(r.source_id.isdigit() for r in result.records)
    assert len({r.source_id for r in result.records}) == 18
    assert any("unstable" in w for w in result.warnings)


def test_id_fallback_to_row_index_for_csv(tmp_path: Path) -> None:
    result = fetch(csv_cfg(id_field=None), tmp_path)
    assert by_id(result.records)["0"].species_raw == "Washingtonia robusta"
    assert any("row index" in w for w in result.warnings)


def test_id_field_used_without_warning(tmp_path: Path) -> None:
    assert not any("unstable" in w for w in fetch(make_cfg(), tmp_path).warnings)


# ---------------------------------------------------------------- CRS


def test_non_4326_crs_is_reprojected(tmp_path: Path) -> None:
    import geopandas as gpd

    frame = gpd.read_file(GEOJSON, engine="pyogrio")
    projected = tmp_path / "utm.geojson"
    frame.to_crs(32611).to_file(projected, driver="GeoJSON", engine="pyogrio")
    result = fetch(make_cfg(path=projected), tmp_path)
    expected = by_id(fetch(make_cfg(), tmp_path).records)
    got = by_id(result.records)
    assert set(got) == set(expected)
    for key, e in expected.items():
        assert (got[key].lon, got[key].lat) == pytest.approx((e.lon, e.lat), abs=1e-6)
    assert any("EPSG:32611" in w and "reprojected" in w for w in result.warnings)


# ---------------------------------------------------------------- URL download and cache


def test_url_downloads_once_through_cache(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    http = FakeHttp(GEOJSON)
    adapter = GeoJsonFileAdapter(make_cfg(path=None, url=URL))
    first = adapter.fetch(BBOX, cache, http)  # type: ignore[arg-type]
    second = adapter.fetch(BBOX, cache, http)  # type: ignore[arg-type]
    assert http.urls == [URL]
    assert len(first.records) == len(second.records) == 18
    assert len(list((tmp_path / "cache" / "geojson_file").rglob("*.geojson"))) == 1


def test_url_csv_offline_cache_miss_then_hit(tmp_path: Path) -> None:
    adapter = GeoJsonFileAdapter(csv_cfg(path=None, url="https://example.invalid/trees.csv"))
    with pytest.raises(CacheMiss):
        adapter.fetch(BBOX, Cache(tmp_path / "cache", offline=True), NoHttp())  # type: ignore[arg-type]
    adapter.fetch(BBOX, Cache(tmp_path / "cache"), FakeHttp(CSV))  # type: ignore[arg-type]
    offline = Cache(tmp_path / "cache", offline=True)
    result = adapter.fetch(BBOX, offline, NoHttp())  # type: ignore[arg-type]
    assert len(result.records) == 18
    assert list((tmp_path / "cache" / "geojson_file").rglob("*.csv"))


def test_format_inferred_from_suffix(tmp_path: Path) -> None:
    assert len(fetch(make_cfg(format=None), tmp_path).records) == 18
    with pytest.raises(SourceError, match="cannot infer format"):
        fetch(make_cfg(format=None, path=tmp_path / "x.dat"), tmp_path)


def test_missing_file_and_bad_species_field(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not found"):
        fetch(make_cfg(path=tmp_path / "nope.geojson"), tmp_path)
    with pytest.raises(SourceError, match="species_field"):
        fetch(make_cfg(species_field="no_such"), tmp_path)


# ---------------------------------------------------------------- vintage


def test_vintage_from_record_dates(tmp_path: Path) -> None:
    v = fetch(make_cfg(), tmp_path).vintage
    assert v.source == "sample"
    assert v.basis == "record_dates"
    assert v.vintage == "2020"


def test_vintage_config_override(tmp_path: Path) -> None:
    v = fetch(make_cfg(vintage="2017"), tmp_path).vintage
    assert (v.vintage, v.basis) == ("2017", "config")


def test_vintage_fetched_when_no_dates(tmp_path: Path) -> None:
    v = fetch(make_cfg(date_field=None), tmp_path).vintage
    assert v.basis == "fetched"
    assert len(v.vintage or "") == 7


# ---------------------------------------------------------------- base helpers


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2021-03-04", date(2021, 3, 4)),
        ("2021-03-04T10:00:00Z", date(2021, 3, 4)),
        ("2021-03-04T10:00:00+00:00", date(2021, 3, 4)),
        ("03/04/2021", date(2021, 3, 4)),
        ("3/4/2021", date(2021, 3, 4)),
        (1614816000000, date(2021, 3, 4)),
        ("1614816000000", date(2021, 3, 4)),
        (1614816000000.0, date(2021, 3, 4)),
        ("2021-03", date(2021, 3, 1)),
        ("2021", date(2021, 1, 1)),
        (date(2021, 3, 4), date(2021, 3, 4)),
        ("13/45/2021", None),
        ("not a date", None),
        ("", None),
        (None, None),
        (float("nan"), None),
        (True, None),
    ],
)
def test_parse_date(value: Any, expected: date | None) -> None:
    assert parse_date(value) == expected


def test_derive_vintage_precedence() -> None:
    edit_ms = 1_577_836_800_000  # 2020-01-01
    dates = ["2018-05-01", "03/04/2019", "2019-12-31", "junk"]
    assert derive_vintage("2022", dates, edit_ms, FETCHED, source="s").basis == "config"
    rec = derive_vintage(None, dates, edit_ms, FETCHED, source="s")
    assert (rec.vintage, rec.basis) == ("2019", "record_dates")
    layer = derive_vintage(None, ["junk", None], edit_ms, FETCHED, source="s")
    assert (layer.vintage, layer.basis) == ("2020", "layer_edit_date")
    fetched = derive_vintage(None, [], None, FETCHED, source="s")
    assert (fetched.vintage, fetched.basis) == ("2026-11", "fetched")
    assert fetched.fetched_at == "2026-11-22T09:30:00Z"
    assert fetched.source == "s"


def test_derive_vintage_median_is_lower_for_even_counts() -> None:
    v = derive_vintage(None, ["2018-01-01", "2020-01-01"], None, FETCHED)
    assert v.vintage == "2018"


def test_derive_vintage_blank_config_ignored() -> None:
    assert derive_vintage("  ", ["2019-01-01"], None, FETCHED).basis == "record_dates"
