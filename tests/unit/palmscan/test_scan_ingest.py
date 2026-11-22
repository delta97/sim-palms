"""palmscan.ingest and the adapter registry, with in-memory fake adapters (offline)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from palmcore.errors import ConfigError, SourceError
from palmscan.cache import Cache
from palmscan.config import ScanConfig, scan_config_from_mapping
from palmscan.ingest import IngestResult, ingest_inventory
from palmscan.model import SourceVintage, TreeRecord
from palmscan.sources.base import FetchResult
from palmscan.sources.registry import ADAPTERS, build_inventory_adapters

SD_BBOX = [-117.28, 32.70, -117.15, 32.82]


def make_cfg(
    names: tuple[str, ...] = ("inv_a", "inv_b"),
    osm: bool = True,
    palmscan: dict[str, Any] | None = None,
    **source_extra: Any,
) -> ScanConfig:
    inventory = [
        {
            "name": n,
            "type": "geojson_file",
            "path": f"{n}.geojson",
            "species_field": "species",
            "height_units": "ft" if n == "inv_a" else "m",
            **source_extra,
        }
        for n in names
    ]
    return scan_config_from_mapping(
        {
            "region": "san-diego-coastal",
            "bbox": SD_BBOX,
            "sources": {"inventory": inventory, "osm_trees": osm},
            "palmscan": palmscan or {},
        }
    )


def tree(source: str, sid: str, species: str | None, **kw: Any) -> TreeRecord:
    return TreeRecord(source, sid, -117.2531, 32.7893, species, **kw)


class FakeAdapter:
    def __init__(
        self,
        name: str,
        records: list[TreeRecord] | None = None,
        error: Exception | None = None,
        vintage: str = "2019",
        calls: list[str] | None = None,
    ) -> None:
        self.name = name
        self.records = records or []
        self.error = error
        self.vintage = vintage
        self.calls = calls

    def fetch(self, bbox: Any, cache: Cache, http: Any) -> FetchResult:
        if self.calls is not None:
            self.calls.append(self.name)
        if self.error:
            raise self.error
        v = SourceVintage(self.name, self.vintage, "config", "2026-11-22T00:00:00Z")
        return FetchResult(self.records, v, [f"note from {self.name}"])


def run(
    cfg: ScanConfig, adapters: list[Any], osm: Any, tmp: Path, offline: bool = False
) -> IngestResult:
    return ingest_inventory(
        cfg, Cache(tmp, offline=offline), None, adapters=adapters, osm_adapter=osm
    )  # type: ignore[arg-type]


def test_counts_confidence_and_fields(tmp_path: Path) -> None:
    recs = [
        tree("inv_a", "1", "Washingtonia robusta", height_raw="45", date_raw="2021-03-04"),
        tree("inv_a", "2", "Phoenix"),
        tree("inv_a", "3", "Palm"),
        tree("inv_a", "4", "Jacaranda"),
        tree("inv_a", "5", "Stump"),
        tree("inv_a", "6", "Washingtonia robusta", status_raw="Vacant site"),
    ]
    adapters = [FakeAdapter("inv_a", recs), FakeAdapter("inv_b")]
    res = run(make_cfg(osm=False), adapters, None, tmp_path)
    assert res.counts["inv_a"] == {
        "fetched": 6,
        "non_tree": 2,
        "not_palm": 1,
        "excluded": 0,
        "palm": 3,
    }
    assert [p.stable_key for p in res.palms] == ["inv_a:1", "inv_a:2", "inv_a:3"]
    first, genus, generic = res.palms
    assert (first.species, first.species_confidence, first.species_source) == (
        "washingtonia_robusta",
        0.95,
        "inventory",
    )
    assert first.height_raw == "45"  # raw text, units are applied later from the source config
    assert genus.height_raw is None
    assert first.source_ids == ["inv_a:1"]
    assert first.data_vintage == {"inventory": "2021"}
    assert first.detected_by == "inventory"
    assert 100_000 < first.x < 900_000 and first.y > 3_000_000  # UTM metres
    assert genus.species_confidence == 0.8 and genus.data_vintage == {"inventory": "2019"}
    assert generic.species is None and generic.species_confidence is None
    assert generic.species_source is None
    # Non-palms are counted only; stumps and vacant rows are rejects.
    assert sorted((r.stage, r.source_id, r.reason) for r in res.rejects) == [
        ("inventory", "5", "stump"),
        ("inventory", "6", "vacant"),
    ]
    assert [v.source for v in res.vintages] == ["inv_a", "inv_b"]
    assert res.source_order == ["inv_a", "inv_b"]
    assert "inv_a: note from inv_a" in res.warnings


def test_list_non_palms_and_excluded_species(tmp_path: Path) -> None:
    cfg = make_cfg(
        osm=False,
        palmscan={
            "qa": {"list_non_palms": True},
            "palm_filter": {"exclude_species": ["phoenix_roebelenii"]},
        },
    )
    recs = [tree("inv_a", "1", "Jacaranda"), tree("inv_a", "2", "Pygmy Date Palm")]
    res = run(cfg, [FakeAdapter("inv_a", recs), FakeAdapter("inv_b")], None, tmp_path)
    assert res.palms == []
    assert {(r.source_id, r.reason) for r in res.rejects} == {
        ("1", "not_palm"),
        ("2", "excluded_species"),
    }
    assert res.counts["inv_a"]["excluded"] == 1


def test_unmatched_palm_names(tmp_path: Path) -> None:
    recs = [
        tree("inv_a", "1", "Palmetto Oak"),
        tree("inv_a", "2", "palmetto  oak"),
        tree("inv_a", "3", "Oak"),
        tree("inv_a", "4", "Oak", common_name_raw="Weird Palm Thing"),
    ]
    adapters = [FakeAdapter("inv_a", recs), FakeAdapter("inv_b")]
    res = run(make_cfg(osm=False), adapters, None, tmp_path)
    assert dict(res.unmatched_palm_names) == {"palmetto oak": 2, "weird palm thing": 1}


def test_osm_runs_after_inventory_with_osm_labels(tmp_path: Path) -> None:
    calls: list[str] = []
    inv = [FakeAdapter("inv_a", [tree("inv_a", "1", "Phoenix")], calls=calls)]
    osm = FakeAdapter(
        "osm", [tree("osm", "node/9", "Washingtonia robusta")], vintage="2026-11", calls=calls
    )
    res = run(make_cfg(("inv_a",), osm=True), inv, osm, tmp_path)
    assert calls == ["inv_a", "osm"]
    palm = res.palms[-1]
    assert (palm.stable_key, palm.detected_by, palm.species_source) == (
        "osm:node/9",
        "osm",
        "osm",
    )
    assert palm.data_vintage == {"osm": "2026-11"}
    assert res.source_order == ["inv_a", "osm"]


def test_osm_failure_is_a_warning(tmp_path: Path) -> None:
    inv = [FakeAdapter("inv_a", [tree("inv_a", "1", "Phoenix")])]
    osm = FakeAdapter("osm", error=SourceError("overpass down"))
    res = run(make_cfg(("inv_a",), osm=True), inv, osm, tmp_path)
    assert len(res.palms) == 1
    assert any("overpass down" in w for w in res.warnings)
    assert res.source_order == ["inv_a"]


def test_inventory_failure_raises(tmp_path: Path) -> None:
    inv = [FakeAdapter("inv_a", error=SourceError("boom")), FakeAdapter("inv_b")]
    with pytest.raises(SourceError, match=r"inv_a.*boom"):
        run(make_cfg(osm=False), inv, None, tmp_path)


def test_osm_skipped_when_disabled(tmp_path: Path) -> None:
    osm = FakeAdapter("osm", error=AssertionError("must not run"))
    res = run(make_cfg(("inv_a",), osm=False), [FakeAdapter("inv_a")], osm, tmp_path)
    assert res.palms == [] and "osm" not in res.counts


def test_unknown_genus_set_is_config_error(tmp_path: Path) -> None:
    cfg = make_cfg(palmscan={"palm_filter": {"genus_sets": ["atlantis"]}})
    with pytest.raises(ConfigError, match="atlantis"):
        run(cfg, [FakeAdapter("inv_a")], None, tmp_path)


def test_registry_builds_in_config_order_and_rejects_unknown_type() -> None:
    cfg = make_cfg(("inv_b", "inv_a"))
    assert [a.name for a in build_inventory_adapters(cfg)] == ["inv_b", "inv_a"]
    assert set(ADAPTERS) == {"arcgis_rest", "geojson_file"}
    saved = dict(ADAPTERS)
    ADAPTERS.pop("geojson_file")
    try:
        with pytest.raises(ConfigError, match="unknown type"):
            build_inventory_adapters(cfg)
    finally:
        ADAPTERS.update(saved)


class CachingAdapter:
    """Fetches one cached file through ``cache.get_or_fetch`` and counts real fetches."""

    name = "inv_a"

    def __init__(self) -> None:
        self.fetches = 0

    def fetch(self, bbox: Any, cache: Cache, http: Any) -> FetchResult:
        def fetch(dest: Path) -> None:
            self.fetches += 1
            dest.write_text("{}", encoding="utf-8")

        cache.get_or_fetch("ns", "abcdef", fetch, ".json", meta={"url": "http://x"})
        v = SourceVintage(self.name, "2019", "config", "2026-11-22T00:00:00Z")
        return FetchResult([], v, [])


def _age(root: Path, days: float) -> None:
    path = Cache(root).path_for("ns", "abcdef", ".json")
    meta = path.with_name(path.name + ".meta.json")
    data = json.loads(meta.read_text(encoding="utf-8"))
    old = datetime.now(UTC) - timedelta(days=days)
    data["fetched_at"] = old.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta.write_text(json.dumps(data), encoding="utf-8")


def test_cache_max_age_days_enforced(tmp_path: Path) -> None:
    cfg = make_cfg(("inv_a",), osm=False, cache_max_age_days=7)
    adapter = CachingAdapter()
    run(cfg, [adapter], None, tmp_path)
    run(cfg, [adapter], None, tmp_path)
    assert adapter.fetches == 1  # fresh: reused
    _age(tmp_path, 30)
    run(cfg, [adapter], None, tmp_path)
    assert adapter.fetches == 2  # stale: refetched
    run(cfg, [adapter], None, tmp_path)
    assert adapter.fetches == 2  # the refreshed copy is fresh again


def test_stale_cache_used_with_warning_offline(tmp_path: Path) -> None:
    cfg = make_cfg(("inv_a",), osm=False, cache_max_age_days=7)
    adapter = CachingAdapter()
    run(cfg, [adapter], None, tmp_path)
    _age(tmp_path, 30)
    res = run(cfg, [adapter], None, tmp_path, offline=True)
    assert adapter.fetches == 1
    assert any("older than cache_max_age_days=7" in w for w in res.warnings)


def test_no_age_limit_never_refetches(tmp_path: Path) -> None:
    cfg = make_cfg(("inv_a",), osm=False)
    adapter = CachingAdapter()
    run(cfg, [adapter], None, tmp_path)
    _age(tmp_path, 3000)
    run(cfg, [adapter], None, tmp_path)
    assert adapter.fetches == 1
