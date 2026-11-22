"""palmscan.detect.dedupe: cross-source merge, same-source kept, deterministic."""

from __future__ import annotations

import random
from typing import Any

from palmscan.detect.dedupe import dedupe_cross_source
from palmscan.model import PalmRecord, Reject


def palm(
    key: str,
    x: float,
    y: float = 0.0,
    species: str | None = None,
    conf: float | None = None,
    height_raw: str | None = None,
) -> PalmRecord:
    return PalmRecord(
        stable_key=key,
        lon=-117.0 + x * 1e-5,
        lat=32.0,
        x=x,
        y=y,
        species=species,
        species_confidence=conf,
        species_source="inventory" if species else None,
        source_ids=[key],
        height_raw=height_raw,
    )


def test_cross_source_pair_merges_with_species_upgrade() -> None:
    a = palm("a:1", 0.0, species="phoenix_sp", conf=0.8)
    b = palm("b:9", 1.5, species="phoenix_canariensis", conf=0.95, height_raw="30")
    b.data_vintage = {"osm": "2026-11"}
    out, rejects = dedupe_cross_source([b, a], source_priority=["a", "b"])
    assert len(out) == 1
    kept = out[0]
    assert kept.stable_key == "a:1" and kept.x == 0.0
    assert kept.source_ids == ["a:1", "b:9"]
    assert (kept.species, kept.species_confidence) == ("phoenix_canariensis", 0.95)
    assert kept.height_raw == "30" and kept.data_vintage == {"osm": "2026-11"}
    assert len(rejects) == 1
    r = rejects[0]
    assert (r.stage, r.source, r.source_id, r.reason) == ("dedupe", "b", "9", "duplicate_of:a:1")


def test_species_not_overwritten_when_kept_has_species() -> None:
    a = palm("a:1", 0.0, species="washingtonia_robusta", conf=0.95)
    b = palm("b:1", 0.5, species="washingtonia_filifera", conf=0.95)
    out, _ = dedupe_cross_source([a, b], source_priority=["a", "b"])
    assert out[0].species == "washingtonia_robusta"


def test_same_source_pair_kept() -> None:
    out, rejects = dedupe_cross_source([palm("a:1", 0.0), palm("a:2", 1.5)])
    assert [p.stable_key for p in out] == ["a:1", "a:2"] and rejects == []


def test_pair_beyond_radius_kept() -> None:
    out, rejects = dedupe_cross_source([palm("a:1", 0.0), palm("b:1", 2.1)])
    assert len(out) == 2 and rejects == []
    out, _ = dedupe_cross_source([palm("a:1", 0.0), palm("b:1", 2.0)])
    assert len(out) == 1  # radius is inclusive


def test_three_sources_collapse_to_one() -> None:
    palms = [palm("c:3", 1.0), palm("a:1", 0.0), palm("b:2", 0.8)]
    out, rejects = dedupe_cross_source(palms, source_priority=["a", "b", "c"])
    assert len(out) == 1 and out[0].stable_key == "a:1"
    assert out[0].source_ids == ["a:1", "b:2", "c:3"]
    assert sorted(r.source_id for r in rejects) == ["2", "3"]


def test_kept_point_absorbs_one_point_per_source() -> None:
    palms = [palm("a:1", 0.0), palm("b:1", 0.4), palm("b:2", 1.5)]
    out, _ = dedupe_cross_source(palms, source_priority=["a", "b"])
    assert [p.stable_key for p in out] == ["a:1", "b:2"]
    assert out[0].source_ids == ["a:1", "b:1"]  # the nearer one wins


def test_priority_decides_which_record_is_kept() -> None:
    palms = [palm("a:1", 0.0), palm("b:1", 1.0)]
    out, _ = dedupe_cross_source(palms, source_priority=["b", "a"])
    assert [p.stable_key for p in out] == ["b:1"]
    out, _ = dedupe_cross_source(palms)  # default: alphabetical
    assert [p.stable_key for p in out] == ["a:1"]


def test_input_not_modified() -> None:
    a, b = palm("a:1", 0.0), palm("b:1", 1.0)
    dedupe_cross_source([a, b], source_priority=["a", "b"])
    assert a.source_ids == ["a:1"] and b.source_ids == ["b:1"]


def _snap(out: list[PalmRecord], rej: list[Reject]) -> Any:
    return (
        [(p.stable_key, p.source_ids, p.x, p.y) for p in out],
        [(r.source, r.source_id, r.reason) for r in rej],
    )


def test_output_stable_under_shuffling() -> None:
    rng = random.Random(7)
    palms = [
        palm(f"{'abc'[i % 3]}:{i:03d}", rng.uniform(0, 30), rng.uniform(0, 30)) for i in range(60)
    ]
    prio = ["a", "b", "c"]
    base = dedupe_cross_source(palms, source_priority=prio)
    for seed in range(5):
        shuffled = palms[:]
        random.Random(seed).shuffle(shuffled)
        assert _snap(*dedupe_cross_source(shuffled, source_priority=prio)) == _snap(*base)
    assert len(base[0]) < len(palms)  # the random set does contain merges
