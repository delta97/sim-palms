"""palmscan Overpass client and OSM tree adapter. Offline; synthetic JSON, fake transport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from palmscan.cache import Cache, CacheMiss
from palmscan.geo import Bbox
from palmscan.http import HttpClient
from palmscan.sources.base import SourceError
from palmscan.sources.osm_overpass import OsmTreesAdapter
from palmscan.sources.overpass import DEFAULT_OVERPASS_URL, OverpassClient, bbox_tiles

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "palmscan" / "osm_overpass"
TREES = (FIXTURES / "trees_response.json").read_text(encoding="utf-8")
RUNTIME_ERROR = (FIXTURES / "runtime_error.json").read_text(encoding="utf-8")
BBOX = Bbox(-118.42, 34.0, -118.40, 34.02)  # one tile; holds every fixture node


class FakeHttp:
    """Stands in for HttpClient.post_text; replies via a callable and records queries."""

    def __init__(self, reply: Any = TREES) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def post_text(self, url: str, data: dict[str, Any]) -> str:
        self.calls.append((url, data["data"]))
        return self.reply(data["data"]) if callable(self.reply) else str(self.reply)


def client(tmp_path: Path, http: FakeHttp, **cache_kw: Any) -> OverpassClient:
    return OverpassClient(http, Cache(tmp_path / "cache", **cache_kw))  # type: ignore[arg-type]


def test_adapter_returns_only_tagged_nodes(tmp_path: Path) -> None:
    http = FakeHttp()
    result = OsmTreesAdapter(client(tmp_path, http)).fetch(BBOX, Cache(tmp_path), http)  # type: ignore[arg-type]
    assert [r.source_id for r in result.records] == [
        "node/1001",
        "node/1002",
        "node/1004",
        "node/1005",
        "node/1006",
    ]
    assert all(r.source == "osm" and r.date_raw is None for r in result.records)
    assert len(http.calls) == 1 and http.calls[0][0] == DEFAULT_OVERPASS_URL
    assert 'node["natural"="tree"](34,-118.42,34.02,-118.4)' in http.calls[0][1]


def test_species_tag_precedence_and_common_name(tmp_path: Path) -> None:
    result = OsmTreesAdapter(client(tmp_path, FakeHttp())).fetch(BBOX)
    by_id = {r.source_id: r for r in result.records}
    assert by_id["node/1001"].species_raw == "Washingtonia robusta"
    assert by_id["node/1001"].common_name_raw == "Mexican fan palm"
    assert by_id["node/1004"].species_raw == "Phoenix"  # genus only
    assert by_id["node/1005"].species_raw == "Syagrus"  # genus beats taxon
    assert by_id["node/1006"].species_raw == "Canary Island date palm"  # species:en last
    assert by_id["node/1006"].common_name_raw == "Canary Island date palm"
    assert by_id["node/1002"].common_name_raw is None


def test_untagged_counted_and_attribution_kept(tmp_path: Path) -> None:
    result = OsmTreesAdapter(client(tmp_path, FakeHttp()), name="osm_x").fetch(BBOX)
    assert any("dropped 3 tree node" in w for w in result.warnings)
    for r in result.records:
        assert r.source == "osm_x"
        assert r.extra["license"] == "ODbL-1.0"
        assert "OpenStreetMap" in r.extra["attribution"]


def test_vintage_is_fetch_month(tmp_path: Path) -> None:
    v = OsmTreesAdapter(client(tmp_path, FakeHttp())).fetch(BBOX).vintage
    assert v.basis == "fetched" and len(v.vintage) == 7 and v.vintage[4] == "-"


def test_records_outside_bbox_and_non_nodes_dropped(tmp_path: Path) -> None:
    body = {
        "elements": [
            {"type": "node", "id": 1, "lat": 10.0, "lon": 10.0, "tags": {"species": "x"}},
            {"type": "way", "id": 2, "tags": {"species": "x"}},
            {"type": "node", "id": 3, "tags": {"species": "x"}},
        ]
    }
    result = OsmTreesAdapter(client(tmp_path, FakeHttp(json.dumps(body)))).fetch(BBOX)
    assert result.records == []


def test_runtime_error_raises_and_is_not_cached(tmp_path: Path) -> None:
    http = FakeHttp(RUNTIME_ERROR)
    c = client(tmp_path, http)
    with pytest.raises(SourceError, match="runtime error"):
        c.query("q")
    with pytest.raises(SourceError):
        c.query("q")
    assert len(http.calls) == 2  # the error body was not cached


def test_non_json_response_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="did not return JSON"):
        client(tmp_path, FakeHttp("<html>busy</html>")).query("q")


def test_benign_remark_is_not_an_error(tmp_path: Path) -> None:
    body = {"elements": [], "remark": "something harmless"}
    assert client(tmp_path, FakeHttp(json.dumps(body))).query("q")["elements"] == []


def test_tile_splitting_9_tiles() -> None:
    tiles = bbox_tiles(Bbox(-118.0, 34.0, -117.88, 34.12))
    assert len(tiles) == 9
    assert all(t.lon_max - t.lon_min <= 0.05 + 1e-9 for t in tiles)
    assert all(t.lat_max - t.lat_min <= 0.05 + 1e-9 for t in tiles)
    assert tiles[0].lon_min == -118.0 and tiles[-1].lat_max == 34.12
    assert len(bbox_tiles(Bbox(-118.0, 34.0, -117.95, 34.05))) == 1


def test_query_bbox_runs_per_tile_and_merges_duplicates(tmp_path: Path) -> None:
    def reply(ql: str) -> str:
        # every tile returns the same shared node plus one node unique to the tile
        unique = 10 + len(http.calls)
        return json.dumps(
            {
                "elements": [
                    {"type": "node", "id": 1, "lat": 34.0, "lon": -118.0, "tags": {"species": "a"}},
                    {"type": "node", "id": unique, "lat": 34.0, "lon": -118.0},
                ]
            }
        )

    http = FakeHttp(reply)
    body = client(tmp_path, http).query_bbox(
        "node({south},{west},{north},{east});out;", Bbox(-118.0, 34.0, -117.88, 34.12)
    )
    assert len(http.calls) == 9
    assert len({q for _, q in http.calls}) == 9
    ids = [e["id"] for e in body["elements"]]
    assert ids.count(1) == 1
    assert len(ids) == len(set(ids)) == 10


def test_same_id_different_type_kept(tmp_path: Path) -> None:
    body = {"elements": [{"type": "node", "id": 5}, {"type": "way", "id": 5}]}
    big = Bbox(-118.0, 34.0, -117.88, 34.12)
    out = client(tmp_path, FakeHttp(json.dumps(body))).query_bbox("{bbox}", big)
    assert len(out["elements"]) == 2


def test_cache_reuse_and_offline(tmp_path: Path) -> None:
    http = FakeHttp()
    first = client(tmp_path, http).query("q")
    second = client(tmp_path, http).query("q")
    assert first == second and len(http.calls) == 1
    offline = client(tmp_path, FakeHttp(), offline=True)
    assert offline.query("q") == first
    with pytest.raises(CacheMiss):
        offline.query("other")


def test_custom_url_used(tmp_path: Path) -> None:
    http = FakeHttp()
    OverpassClient(http, Cache(tmp_path), "https://example.invalid/api").query("q")  # type: ignore[arg-type]
    assert http.calls[0][0] == "https://example.invalid/api"


def test_retries_502_through_http_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real HttpClient retries a 502 'at capacity' and then succeeds; UA is sent."""
    import requests

    class Resp:
        def __init__(self, status: int, text: str = "") -> None:
            self.status_code, self.text, self.headers = status, text, {}

        def close(self) -> None:
            pass

    steps = [Resp(502), Resp(429), Resp(200, TREES)]
    seen: list[dict[str, Any]] = []

    def fake_request(session: requests.Session, method: str, url: str, **kw: Any) -> Any:
        seen.append({"ua": session.headers["User-Agent"], **kw})
        return steps.pop(0)

    monkeypatch.setattr(requests.Session, "request", fake_request)
    sleeps: list[float] = []
    http = HttpClient(sleep=sleeps.append)
    body = OverpassClient(http, Cache(tmp_path)).query("q")
    assert len(body["elements"]) == 8
    assert len(seen) == 3 and sleeps == [2.0, 4.0]
    assert seen[0]["ua"].startswith("palmscan/") and seen[0]["data"] == {"data": "q"}
