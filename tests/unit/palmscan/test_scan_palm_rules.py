"""Tests for palmscan.detect.palm_rules (SCAN-024)."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from palmscan.config import RuleParams
from palmscan.detect.palm_rules import RULE_ORDER, apply_palm_rules
from palmscan.model import LidarCandidate
from palmscan.qa.rejects import REJECT_COLUMNS, write_rejects_csv

P = RuleParams()


def cand(
    height: float = 15.0,
    diam: float = 5.0,
    shared: float = 0.0,
    x: float = 0.0,
    in_building: bool = False,
    ratio: float | None = None,
    cid: str = "ds:t:1",
) -> LidarCandidate:
    return LidarCandidate(
        candidate_id=cid,
        dataset="ds",
        x=x,
        y=0.0,
        lon=-117.0,
        lat=33.0,
        height_m=height,
        crown_area_m2=3.14159 * (diam / 2) ** 2,
        crown_diam_m=diam,
        ratio=height / diam if ratio is None else ratio,
        shared_boundary_frac=shared,
        ground_elev_m=10.0,
        in_building=in_building,
    )


def run(
    c: LidarCandidate, params: RuleParams = P, bld: gpd.GeoDataFrame | None = None
) -> list[str]:
    apply_palm_rules([c], params, bld)
    return c.reasons


def test_baseline_candidate_accepted() -> None:
    c = cand()
    cands, rejects = apply_palm_rules([c], P, None)
    assert c.accepted and c.reasons == [] and rejects == [] and cands == [c]


@pytest.mark.parametrize(
    ("kwargs", "reasons"),
    [
        ({"height": 8.0, "diam": 3.5}, []),  # inclusive lower bound
        ({"height": 7.99, "diam": 3.5}, ["height_low"]),
        ({"height": 35.0, "diam": 11.0}, []),
        ({"height": 35.01, "diam": 11.0}, ["height_high"]),
        ({"diam": 3.0, "height": 15.0}, []),
        ({"diam": 2.99, "height": 15.0}, ["crown_small"]),
        ({"diam": 12.0, "height": 30.0}, []),
        ({"diam": 12.01, "height": 30.0}, ["crown_large"]),
        ({"height": 12.0, "diam": 6.0, "ratio": 2.01}, []),
        ({"height": 12.0, "diam": 6.0, "ratio": 2.0}, ["ratio"]),  # ratio <= min fails
        ({"shared": 0.35}, []),
        ({"shared": 0.36}, ["not_isolated"]),
        ({"in_building": True}, ["building"]),
    ],
)
def test_threshold_boundaries(kwargs: dict[str, float | bool], reasons: list[str]) -> None:
    assert run(cand(**kwargs)) == reasons  # type: ignore[arg-type]


def test_large_crown_exemption_on_off() -> None:
    on = cand(height=15.0, diam=9.0)  # ratio 1.67, isolated
    assert run(on) == [] and on.accepted
    off = cand(height=15.0, diam=9.0)
    assert run(off, replace(P, ratio_exempt_large_crown=False)) == ["ratio"]
    assert not off.accepted


@pytest.mark.parametrize(
    ("kwargs", "reasons"),
    [
        ({"height": 12.0, "diam": 6.99, "ratio": 1.7}, ["ratio"]),  # crown below exemption
        ({"height": 12.0, "diam": 7.0, "ratio": 1.01}, []),
        ({"height": 12.0, "diam": 7.0, "ratio": 1.0}, ["ratio"]),  # exemption needs ratio > 1
        ({"height": 12.0, "diam": 9.0, "shared": 0.5}, ["ratio", "not_isolated"]),  # embedded
    ],
)
def test_exemption_edges(kwargs: dict[str, float], reasons: list[str]) -> None:
    assert run(cand(**kwargs)) == reasons


def test_multiple_failures_in_rule_order() -> None:
    c = cand(height=5.0, diam=2.0, shared=0.9, in_building=True, ratio=1.5)
    _, rejects = apply_palm_rules([c], P, None)
    assert c.reasons == ["height_low", "crown_small", "ratio", "not_isolated", "building"]
    assert c.reasons == [r for r in RULE_ORDER if r in c.reasons]
    assert rejects[0].reason == "height_low"
    assert rejects[0].all_reasons == c.reasons


@pytest.mark.parametrize(("x", "rejected"), [(1.9, True), (2.1, False)])
def test_building_buffer(x: float, rejected: bool) -> None:
    # Building edge at x = 1.0 and a 1.0 m buffer: 0.9 m away is rejected, 1.1 m is not.
    bld = gpd.GeoDataFrame(geometry=[box(-20, -20, 1.0, 20)])
    assert ("building" in run(cand(x=x), bld=bld)) is rejected


def test_building_inside_polygon_and_empty_frame() -> None:
    bld = gpd.GeoDataFrame(geometry=[box(-5, -5, 5, 5)])
    assert run(cand(x=0.0), bld=bld) == ["building"]
    assert run(cand(), bld=gpd.GeoDataFrame(geometry=[])) == []


def test_reject_rows_carry_metrics_and_reach_csv(tmp_path: Path) -> None:
    good = cand(cid="ds:t:1")
    bad = cand(height=5.0, diam=4.0, shared=0.5, cid="ds:t:2")
    cands, rejects = apply_palm_rules([good, bad], P, None)
    assert [c.accepted for c in cands] == [True, False]
    (r,) = rejects
    assert (r.stage, r.source, r.source_id) == ("lidar_rules", "lidar", "ds:t:2")
    assert r.metrics == {
        "height_m": 5.0,
        "crown_diam_m": 4.0,
        "ratio": 1.25,
        "shared_boundary_frac": 0.5,
    }
    out = tmp_path / "qa_rejects.csv"
    write_rejects_csv(rejects, out)
    with out.open(encoding="utf-8", newline="") as handle:
        (row,) = list(csv.DictReader(handle))
    assert list(row) == list(REJECT_COLUMNS)
    assert row["reason"] == "height_low"
    assert row["all_reasons"] == "height_low;ratio;not_isolated"
    assert row["height_m"] == "5.0000" and row["shared_boundary_frac"] == "0.5000"
