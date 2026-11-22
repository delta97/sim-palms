"""palmscan.detect.merge: one-to-one deterministic matching, LiDAR heights, LiDAR-only palms."""

from __future__ import annotations

import random

from palmscan.config import MergeParams
from palmscan.detect.merge import match_inventory_to_lidar, merge
from palmscan.model import LidarCandidate, PalmRecord


def inv_palm(
    key: str, x: float, y: float = 0.0, species: str | None = None, origin: str = "inventory"
) -> PalmRecord:
    return PalmRecord(
        stable_key=key,
        lon=-117.0 + x * 1e-5,
        lat=32.0 + y * 1e-5,
        x=x,
        y=y,
        species=species,
        species_confidence=0.95 if species else None,
        species_source=origin if species else None,
        height_m=5.0,
        height_source="inventory",
        crown_diam_m=2.0,
        detected_by=origin,
        source_ids=[key],
        data_vintage={origin: "2020"},
    )


def cand(
    cid: str,
    x: float,
    y: float = 0.0,
    height: float = 14.0,
    accepted: bool = True,
    reasons: list[str] | None = None,
) -> LidarCandidate:
    return LidarCandidate(
        candidate_id=cid,
        dataset="ds",
        x=x,
        y=y,
        lon=-117.0 + x * 1e-5,
        lat=32.0 + y * 1e-5,
        height_m=height,
        crown_area_m2=20.0,
        crown_diam_m=5.0,
        ratio=height / 5.0,
        shared_boundary_frac=0.1,
        ground_elev_m=12.5,
        accepted=accepted and not reasons,
        reasons=list(reasons or []),
        vintage="2022",
    )


def test_exact_match_copies_lidar_attributes() -> None:
    p = inv_palm("sd:1", 10.0, 5.0, species="phoenix_canariensis")
    c = cand("ds:t:1", 10.0, 5.0, height=17.0)
    res = merge([p], [c], MergeParams())
    assert len(res.palms) == 1
    out = res.palms[0]
    assert (out.stable_key, out.x, out.y) == ("sd:1", 10.0, 5.0)
    assert (out.height_m, out.height_source) == (17.0, "lidar")
    assert (out.crown_diam_m, out.ground_elev_m) == (5.0, 12.5)
    assert out.detected_by == "inventory+lidar"
    assert out.source_ids == ["lidar:ds:t:1", "sd:1"]
    assert out.data_vintage == {"inventory": "2020", "lidar": "2022"}
    assert out.lidar is c
    assert p.height_source == "inventory" and p.detected_by == "inventory"  # input untouched
    assert res.rejects == []


def test_osm_origin_becomes_osm_plus_lidar() -> None:
    res = merge([inv_palm("osm:9", 0.0, origin="osm")], [cand("ds:t:1", 1.0)], MergeParams())
    assert res.palms[0].detected_by == "osm+lidar"


def test_radius_boundary_2_9_matches_3_1_does_not() -> None:
    a = inv_palm("sd:1", 0.0)
    assert match_inventory_to_lidar([a], [cand("c", 2.9)], 3.0) == [(0, 0, 2.9)]
    assert match_inventory_to_lidar([a], [cand("c", 3.1)], 3.0) == []
    res = merge([a], [cand("c", 3.1, accepted=False, reasons=["not_isolated"])], MergeParams())
    assert res.palms[0].height_source == "inventory"


def test_two_inventory_palms_one_candidate_closest_wins() -> None:
    near = inv_palm("sd:2", 1.0)
    far = inv_palm("sd:1", -2.0)
    res = merge([far, near], [cand("c", 0.0)], MergeParams())
    by_key = {p.stable_key: p for p in res.palms}
    assert by_key["sd:2"].height_source == "lidar"
    assert by_key["sd:1"].height_source == "inventory"


def test_equal_distance_tie_breaks_on_stable_key_then_candidate_id() -> None:
    a, b = inv_palm("sd:a", -1.0), inv_palm("sd:b", 1.0)
    # equal distance to the one candidate: the smaller stable key (sd:a, index 1 here) wins
    assert match_inventory_to_lidar([b, a], [cand("c", 0.0)], 3.0) == [(1, 0, 1.0)]
    # one palm, two candidates at equal distance: the smaller candidate_id (c1, index 1) wins
    c1, c2 = cand("c1", -1.0), cand("c2", 1.0)
    assert match_inventory_to_lidar([inv_palm("sd:a", 0.0)], [c2, c1], 3.0) == [(0, 1, 1.0)]


def test_matching_is_one_to_one() -> None:
    inv = [inv_palm("sd:1", 0.0), inv_palm("sd:2", 2.0), inv_palm("sd:3", 2.5)]
    cands = [cand("c1", 1.0), cand("c2", 4.5)]
    pairs = match_inventory_to_lidar(inv, cands, 3.0)
    assert len({i for i, _, _ in pairs}) == len(pairs)
    assert len({j for _, j, _ in pairs}) == len(pairs)
    assert len(pairs) == 2


def test_matching_is_deterministic_under_shuffling() -> None:
    rng = random.Random(7)
    inv = [inv_palm(f"sd:{i}", rng.uniform(0, 30), rng.uniform(0, 30)) for i in range(40)]
    cands = [cand(f"ds:t:{i}", rng.uniform(0, 30), rng.uniform(0, 30)) for i in range(40)]

    def run(i: list[PalmRecord], c: list[LidarCandidate]) -> set[tuple[str, str]]:
        return {
            (i[a].stable_key, c[b].candidate_id) for a, b, _ in match_inventory_to_lidar(i, c, 3.0)
        }

    base = run(inv, cands)
    assert base
    res_a = merge(inv, cands, MergeParams())
    for seed in range(5):
        r = random.Random(seed)
        i2, c2 = inv[:], cands[:]
        r.shuffle(i2)
        r.shuffle(c2)
        assert run(i2, c2) == base
        res_b = merge(i2, c2, MergeParams())
        assert [p.stable_key for p in res_a.palms] == [p.stable_key for p in res_b.palms]
        assert [p.height_m for p in res_a.palms] == [p.height_m for p in res_b.palms]
        assert [p.source_ids for p in res_a.palms] == [p.source_ids for p in res_b.palms]


def test_rule_rejected_matches_but_building_rejected_does_not() -> None:
    a = inv_palm("sd:1", 0.0)
    b = inv_palm("sd:2", 20.0)
    ficus = cand("c1", 0.5, reasons=["not_isolated"])
    roof = cand("c2", 20.5, reasons=["ratio", "building"])
    res = merge([a, b], [ficus, roof], MergeParams())
    by_key = {p.stable_key: p for p in res.palms}
    assert by_key["sd:1"].height_source == "lidar"
    assert by_key["sd:2"].height_source == "inventory"
    assert len(res.palms) == 2  # a rejected candidate never becomes a LiDAR-only palm


def test_below_min_height_candidate_is_not_in_pool() -> None:
    res = merge([inv_palm("sd:1", 0.0)], [cand("c", 0.5, height=5.0)], MergeParams())
    assert res.palms[0].height_source == "inventory"


def test_lidar_only_palm_and_key() -> None:
    res = merge([], [cand("ds:t:1", 100.4, -7.6, height=20.0)], MergeParams())
    (p,) = res.palms
    assert p.stable_key == "lidar:ds:100:-8"
    assert p.detected_by == "lidar" and p.species is None
    assert (p.height_m, p.height_source, p.ground_elev_m) == (20.0, "lidar", 12.5)
    assert p.source_ids == ["lidar:ds:t:1"] and p.data_vintage == {"lidar": "2022"}
    assert (p.x, p.y) == (100.4, -7.6) and p.lidar is not None


def test_lidar_only_within_dedupe_radius_dropped_with_reject() -> None:
    inv = [inv_palm("sd:1", 0.0)]
    # c2 is 3.5 m from the inventory palm: not within 2 m, so it becomes a LiDAR-only palm
    res = merge(inv, [cand("c1", 0.5), cand("c2", 3.5)], MergeParams())
    assert sorted(p.stable_key for p in res.palms) == ["lidar:ds:4:0", "sd:1"]
    # c1 takes the match; c2 is 1.8 m from the inventory palm and is dropped
    res2 = merge(inv, [cand("c1", 0.2), cand("c2", 1.8)], MergeParams())
    assert [p.stable_key for p in res2.palms] == ["sd:1"]
    (rej,) = res2.rejects
    assert (rej.stage, rej.reason, rej.source_id) == ("merge", "near_inventory", "c2")
    assert abs(rej.metrics["distance_m"] - 1.8) < 1e-9


def test_rejected_unmatched_candidates_are_not_added() -> None:
    res = merge([], [cand("c", 0.0, reasons=["height_low"])], MergeParams())
    assert res.palms == [] and res.rejects == []


def test_region_medians_need_min_n_and_species_level() -> None:
    inv: list[PalmRecord] = []
    cands: list[LidarCandidate] = []
    for i in range(5):  # exactly 5 matches -> median
        inv.append(inv_palm(f"sd:a{i}", i * 10.0, species="phoenix_canariensis"))
        cands.append(cand(f"a{i}", i * 10.0, height=10.0 + i))
    for i in range(4):  # 4 matches -> omitted
        inv.append(inv_palm(f"sd:b{i}", i * 10.0, 50.0, species="washingtonia_robusta"))
        cands.append(cand(f"b{i}", i * 10.0, 50.0))
    for i in range(6):  # genus-level: never counted
        inv.append(inv_palm(f"sd:g{i}", i * 10.0, 100.0, species="phoenix_sp"))
        cands.append(cand(f"g{i}", i * 10.0, 100.0))
    res = merge(inv, cands, MergeParams())
    assert res.region_medians == {"phoenix_canariensis": 12.0}
    assert len(res.training) == 9
    assert all(
        p.species in {"phoenix_canariensis", "washingtonia_robusta"} for p, _ in res.training
    )
    assert all(c is p.lidar for p, c in res.training)


def test_region_median_min_n_is_configurable() -> None:
    inv = [inv_palm("sd:1", 0.0, species="phoenix_canariensis")]
    res = merge(inv, [cand("c", 0.0, height=9.0)], MergeParams(region_median_min_n=1))
    assert res.region_medians == {"phoenix_canariensis": 9.0}


def test_empty_inputs() -> None:
    res = merge([], [], MergeParams())
    assert res.palms == [] and res.training == [] and res.region_medians == {}
    assert merge([inv_palm("sd:1", 0.0)], [], MergeParams()).palms[0].height_source == "inventory"
