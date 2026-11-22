from __future__ import annotations

import argparse
import dataclasses
import json
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
import yaml
from shapely.geometry import Polygon, box

from palmcore.geo import Bbox
from palmgen import cli
from palmgen.errors import GenerationError, InputError
from palmgen.geometry import LocalProjection
from palmgen.inputs import GenConfig, load_gen_config, load_palms
from palmgen.masks import (
    LocalMask,
    Mask,
    OverpassHttpError,
    apply_point_masks,
    clip_polygons_by_masks,
    fetch_airports,
    load_masks,
    localize_masks,
    overpass_to_geojson,
    run_fetch_airports,
)
from palmgen.model import Palm
from tests.helpers.fixtures import FIXTURES_ROOT

FIX = FIXTURES_ROOT / "palmgen"
REGION = "fixture-small"
PROJ = LocalProjection(-117.25, 32.785)
AIRPORTS_SMALL = FIX / "airports_small.geojson"
OVERPASS = FIX / "overpass_airports.json"
ENDPOINT = "https://overpass.example/api/interpreter"


def _write_region(tmp_path: Path, name: str, data: dict[str, Any]) -> Path:
    path = tmp_path / "regions" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _cfg(tmp_path: Path, airports: Path | None = AIRPORTS_SMALL, **masks: Any) -> GenConfig:
    data = yaml.safe_load((FIX / "region_small.yaml").read_text(encoding="utf-8"))
    data["mask_out"].append(
        {"name": "fixture-file", "kind": "mod", "path": str(FIX / "masks_small.geojson")}
    )
    airport_cfg: dict[str, Any] = {"enabled": True, **masks}
    if airports is not None:
        airport_cfg["path"] = str(airports)
    data["masks"] = {"airports": airport_cfg}
    return load_gen_config(REGION, _write_region(tmp_path, "x.yaml", data))


@pytest.fixture
def palms() -> list[Palm]:
    return load_palms(FIX / "palms_small.geojson", REGION)[0]


def _overpass() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(OVERPASS.read_text(encoding="utf-8"))
    return loaded


def _fixture_bbox() -> Bbox:
    return load_gen_config(REGION, FIX / "region_small.yaml", base_dir=FIX).bbox


# --- loading ---------------------------------------------------------------------------------


def test_load_masks_order_and_kinds(tmp_path: Path) -> None:
    masks = load_masks(_cfg(tmp_path, buffer_m=100), PROJ)
    assert [(m.name, m.kind) for m in masks] == [
        ("fixture-mod", "mod"),
        ("fixture-file", "mod"),
        ("airport:KFXT", "airport"),
        ("airport:relation/2001", "airport"),
    ]


def test_airport_buffer_is_metric_and_deterministic(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, buffer_m=100)
    first = load_masks(cfg, PROJ)[2]
    again = load_masks(cfg, PROJ)[2]
    assert first.geometry_lonlat.equals_exact(again.geometry_lonlat, 0)
    raw = Polygon(
        json.loads(AIRPORTS_SMALL.read_text(encoding="utf-8"))["features"][0]["geometry"][
            "coordinates"
        ][0]
    )
    local_raw = PROJ.geom_to_local(raw)
    local_buf = PROJ.geom_to_local(first.geometry_lonlat)
    assert local_buf.area == pytest.approx(local_raw.buffer(100.0, quad_segs=8).area, rel=1e-3)
    # Every point of the raw polygon is at least 100 m from the buffered boundary.
    assert local_buf.exterior.distance(local_raw) == pytest.approx(100.0, abs=0.5)


def test_no_airport_mask_and_disabled(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    assert [m.kind for m in load_masks(cfg, PROJ, no_airport_mask=True)] == ["mod", "mod"]
    assert len(load_masks(_cfg(tmp_path, enabled=False), PROJ)) == 2


def test_missing_airport_file_is_input_error_with_hint(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, airports=tmp_path / "nope.geojson")
    with pytest.raises(InputError, match=r"not found.*masks airports --region"):
        load_masks(cfg, PROJ)
    assert load_masks(cfg, PROJ, no_airport_mask=True)  # not needed when switched off


def test_missing_mod_file_is_input_error(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    broken = dataclasses.replace(cfg.mask_out[1], path=tmp_path / "gone.geojson")
    cfg = dataclasses.replace(cfg, mask_out=(cfg.mask_out[0], broken))
    with pytest.raises(InputError, match="file not found"):
        load_masks(cfg, PROJ, no_airport_mask=True)


def test_manual_airport_entry_is_not_buffered(tmp_path: Path) -> None:
    data = yaml.safe_load((FIX / "region_small.yaml").read_text(encoding="utf-8"))
    data["mask_out"] = [
        {"name": "tower", "kind": "airport", "bbox": [-117.26, 32.78, -117.25, 32.79]}
    ]
    cfg = load_gen_config(REGION, _write_region(tmp_path, "y.yaml", data))
    (mask,) = load_masks(cfg, PROJ, no_airport_mask=True)
    assert mask.kind == "airport"
    assert mask.geometry_lonlat.equals(box(-117.26, 32.78, -117.25, 32.79))


# --- point masks -----------------------------------------------------------------------------


def test_point_masks_report_per_mask(tmp_path: Path, palms: list[Palm]) -> None:
    masks = load_masks(_cfg(tmp_path, buffer_m=100), PROJ)
    kept, dropped = apply_point_masks(palms, masks)
    assert dropped == {
        "fixture-mod": ["fs-0000000000000010"],
        "fixture-file": ["fs-0000000000000006", "fs-0000000000000007"],
        "airport:KFXT": ["fs-0000000000000011"],  # ~70 m from the raw corner, inside 100 m
        "airport:relation/2001": [],
    }
    assert [p.palm_id[-2:] for p in kept] == ["01", "02", "03", "04", "05", "08", "09", "12"]


def test_airport_buffer_decides_palm_11(tmp_path: Path, palms: list[Palm]) -> None:
    masks = load_masks(_cfg(tmp_path, buffer_m=10), PROJ)
    _, dropped = apply_point_masks(palms, masks)
    assert dropped["airport:KFXT"] == []


def test_palm_in_two_masks_counts_under_first(palms: list[Palm]) -> None:
    p10 = next(p for p in palms if p.palm_id.endswith("10"))
    around = box(p10.lon - 1e-4, p10.lat - 1e-4, p10.lon + 1e-4, p10.lat + 1e-4)
    masks = [Mask("first", "mod", around), Mask("second", "airport", around)]
    kept, dropped = apply_point_masks(palms, masks)
    assert dropped == {"first": [p10.palm_id], "second": []}
    assert p10 not in kept and len(kept) == len(palms) - 1


def test_point_masks_without_masks_keep_everything(palms: list[Palm]) -> None:
    kept, dropped = apply_point_masks(palms, [])
    assert kept == palms and dropped == {}


# --- clipping --------------------------------------------------------------------------------


def _lm(name: str, kind: str, x0: float, x1: float) -> LocalMask:
    return LocalMask(name, kind, box(x0, -50, x1, 50))


def test_airport_clip_removes_overlap_and_mod_does_not() -> None:
    parts, counts = clip_polygons_by_masks(
        [box(0, 0, 10, 10), box(100, 0, 110, 10)],
        [_lm("ap", "airport", 5, 20), _lm("mod", "mod", 0, 3)],
    )
    assert counts == {"ap": 1}  # mod masks are not even listed
    assert [i for i, _ in parts] == [0, 1]
    assert parts[0][1].area == pytest.approx(50.0)
    assert parts[0][1].intersection(box(5, 0, 20, 10)).area == pytest.approx(0.0)
    assert parts[1][1].area == pytest.approx(100.0)


def test_clip_counts_touching_as_not_clipped() -> None:
    parts, counts = clip_polygons_by_masks([box(0, 0, 10, 10)], [_lm("ap", "airport", 10, 20)])
    assert counts == {"ap": 0} and parts[0][1].area == pytest.approx(100.0)


def test_clip_holes_small_parts_and_full_cover() -> None:
    mid = LocalMask("mid", "airport", box(4, 4, 6, 6))
    parts, counts = clip_polygons_by_masks([box(0, 0, 10, 10)], [mid])
    assert counts == {"mid": 1} and len(parts) == 2  # hole split into two hole-free parts
    assert sum(p.area for _, p in parts) == pytest.approx(96.0)
    assert all(not p.interiors for _, p in parts)
    held, _ = clip_polygons_by_masks([box(0, 0, 10, 10)], [mid], supports_holes=True)
    assert len(held) == 1 and len(held[0][1].interiors) == 1
    sliver, _ = clip_polygons_by_masks(
        [box(0, 0, 10, 10)], [_lm("s", "airport", 0.5, 20)], min_part_area_m2=6.0
    )
    assert sliver == []  # the 0.5 m x 10 m remainder (5 m2) is below the threshold
    gone, counts = clip_polygons_by_masks([box(0, 0, 10, 10)], [_lm("all", "airport", -1, 20)])
    assert gone == [] and counts == {"all": 1}


def test_clip_localized_airport_masks(tmp_path: Path) -> None:
    masks = localize_masks(load_masks(_cfg(tmp_path, buffer_m=100), PROJ), PROJ)
    x, y = PROJ.forward(-117.2443595, 32.7858115)  # palm 11
    circle = Polygon([(x - 3, y - 3), (x + 3, y - 3), (x + 3, y + 3), (x - 3, y + 3)])
    parts, counts = clip_polygons_by_masks([circle], masks)
    assert parts == [] and counts["airport:KFXT"] == 1
    assert set(counts) == {"airport:KFXT", "airport:relation/2001"}


# --- Overpass --------------------------------------------------------------------------------


def test_overpass_conversion_matches_fixture() -> None:
    expected = json.loads(AIRPORTS_SMALL.read_text(encoding="utf-8"))
    assert overpass_to_geojson(_overpass()) == expected
    assert "OpenStreetMap" in expected["attribution"] and "ODbL" in expected["attribution"]


def test_overpass_conversion_details() -> None:
    way, rel = overpass_to_geojson(_overpass())["features"]
    assert way["properties"] == {"name": "Fixture Field", "icao": "KFXT", "osm_id": "way/1001"}
    assert rel["properties"]["icao"] is None
    rings = rel["geometry"]["coordinates"]
    assert len(rings) == 2  # outer merged from two ways, plus one hole
    assert Polygon(rings[0], rings[1:]).area == pytest.approx(0.004 * 0.004 - 0.002 * 0.002)


def test_overpass_skips_open_ways_and_junk() -> None:
    resp = _overpass()
    resp["elements"].append(
        {"type": "way", "id": 9, "geometry": [{"lat": 0, "lon": 0}, {"lat": 1, "lon": 1}]}
    )
    resp["elements"].append({"type": "node", "id": 10, "lat": 0, "lon": 0})
    assert len(overpass_to_geojson(resp)["features"]) == 2
    with pytest.raises(GenerationError):
        overpass_to_geojson({})


class FakeHttp:
    def __init__(self, *responses: bytes | OverpassHttpError) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, bytes]] = []

    def __call__(self, url: str, body: bytes) -> bytes:
        self.calls.append((url, body))
        item = self.responses.pop(0)
        if isinstance(item, OverpassHttpError):
            raise item
        return item


def test_fetch_airports_writes_file(tmp_path: Path) -> None:
    http = FakeHttp(OVERPASS.read_bytes())
    out = tmp_path / "data" / "r" / "masks" / "airports.geojson"
    assert fetch_airports(_fixture_bbox(), out, ENDPOINT, http) == 2
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == json.loads(AIRPORTS_SMALL.read_text(encoding="utf-8"))
    ((url, body),) = http.calls
    assert url == ENDPOINT
    query = urllib.parse.parse_qs(body.decode())["data"][0]
    assert '["aeroway"="aerodrome"](32.7750000,-117.2650000,32.7950000,-117.2350000)' in query
    assert "out geom;" in query


def test_fetch_retries_then_succeeds_and_gives_up(tmp_path: Path) -> None:
    sleeps: list[float] = []
    http = FakeHttp(OverpassHttpError(429), OverpassHttpError(504), OVERPASS.read_bytes())
    out = tmp_path / "a.geojson"
    assert fetch_airports(_fixture_bbox(), out, ENDPOINT, http, sleep=sleeps.append) == 2
    assert sleeps == [5.0, 10.0] and len(http.calls) == 3
    bad = FakeHttp(*[OverpassHttpError(502)] * 4)
    with pytest.raises(GenerationError, match="502"):
        fetch_airports(_fixture_bbox(), tmp_path / "b.geojson", ENDPOINT, bad, sleep=sleeps.append)
    assert len(bad.calls) == 4 and not (tmp_path / "b.geojson").exists()
    other = FakeHttp(OverpassHttpError(406))
    with pytest.raises(GenerationError, match="406"):
        fetch_airports(
            _fixture_bbox(), tmp_path / "c.geojson", ENDPOINT, other, sleep=sleeps.append
        )
    assert len(other.calls) == 1


def test_fetch_rejects_remark_and_non_json(tmp_path: Path) -> None:
    resp = _overpass() | {"remark": "runtime error: Query timed out"}
    out = tmp_path / "a.geojson"
    with pytest.raises(GenerationError, match="timed out"):
        fetch_airports(_fixture_bbox(), out, ENDPOINT, FakeHttp(json.dumps(resp).encode()))
    with pytest.raises(GenerationError, match="not JSON"):
        fetch_airports(_fixture_bbox(), out, ENDPOINT, FakeHttp(b"<html>"))
    assert not out.exists()


def test_cli_masks_airports_with_injected_http(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg_path = tmp_path / "regions" / f"{REGION}.yaml"
    cfg_path.parent.mkdir()
    cfg_path.write_text((FIX / "region_small.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "airports.geojson"
    opts = cli.build_parser().parse_args(
        ["masks", "airports", "--region", REGION, "--config", str(cfg_path), "--out", str(out)]
    )
    http = FakeHttp(OVERPASS.read_bytes())
    opts.http_post = http
    assert run_fetch_airports(opts) == 0
    assert out.is_file() and "wrote 2 airport polygons" in capsys.readouterr().out
    # the query box is the region bbox grown by the 100 m airport buffer
    query = urllib.parse.parse_qs(http.calls[0][1].decode())["data"][0]
    assert "(32.7740" in query


def test_run_fetch_airports_bad_config_is_input_error(tmp_path: Path) -> None:
    ns = argparse.Namespace(
        region=REGION, config=FIX / "missing.yaml", out=tmp_path / "o", endpoint=ENDPOINT
    )
    with pytest.raises(InputError):
        run_fetch_airports(ns)
