"""Palm shape rules for LiDAR crown candidates (plan W16).

Every rule is evaluated for every candidate. ``reasons`` lists all failures in
:data:`RULE_ORDER`, ``reason`` on the reject row is the first, and ``accepted`` is true only when
nothing failed. Reason codes are written as-is to ``qa_rejects.csv`` (``reason`` and the
``;``-joined ``all_reasons`` columns).

All thresholds come from :class:`palmscan.config.RuleParams` (the region config ``palmscan.rules``
block); there are no numbers in the rule logic.

VERIFY: the default thresholds are the source plan's starting values and are not validated on real
LiDAR data; SCAN-030 tunes them. The large-crown ratio exemption is a deviation from the source
plan (plan Q1), on by default and switchable with ``rules.ratio_exempt_large_crown``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Final

import numpy as np
import shapely
from shapely import STRtree

from palmscan.config import RuleParams
from palmscan.model import LidarCandidate, Reject

if TYPE_CHECKING:
    import geopandas as gpd

__all__ = ["RULE_ORDER", "STAGE", "apply_palm_rules", "failed_rules"]

STAGE: Final = "lidar_rules"
SOURCE: Final = "lidar"

RULE_ORDER: Final = (
    "height_low",
    "height_high",
    "crown_small",
    "crown_large",
    "ratio",
    "not_isolated",
    "building",
)

Predicate = Callable[[LidarCandidate, RuleParams, bool], bool]


def _height_low(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    return c.height_m < p.height_min_m


def _height_high(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    return c.height_m > p.height_max_m


def _crown_small(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    return c.crown_diam_m < p.crown_min_m


def _crown_large(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    return c.crown_diam_m > p.crown_max_m


def _not_isolated(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    return c.shared_boundary_frac > p.shared_boundary_max


def _ratio(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    if c.ratio > p.ratio_min:
        return False
    exempt = (
        p.ratio_exempt_large_crown
        and c.crown_diam_m >= p.ratio_exempt_crown_min_m
        and c.ratio > p.ratio_exempt_ratio_min
        and not _not_isolated(c, p, near_building)
    )
    return not exempt


def _building(c: LidarCandidate, p: RuleParams, near_building: bool) -> bool:
    return c.in_building or near_building


_PREDICATES: Final[dict[str, Predicate]] = {
    "height_low": _height_low,
    "height_high": _height_high,
    "crown_small": _crown_small,
    "crown_large": _crown_large,
    "ratio": _ratio,
    "not_isolated": _not_isolated,
    "building": _building,
}


def failed_rules(c: LidarCandidate, params: RuleParams, near_building: bool = False) -> list[str]:
    """Reason codes of every rule the candidate fails, in :data:`RULE_ORDER`."""
    return [name for name in RULE_ORDER if _PREDICATES[name](c, params, near_building)]


def _near_buildings(
    cands: Sequence[LidarCandidate], buildings_local: gpd.GeoDataFrame | None, buffer_m: float
) -> list[bool]:
    """Per candidate: peak within ``buffer_m`` of a building polygon (boundary inclusive)."""
    if buildings_local is None or len(buildings_local) == 0 or not cands:
        return [False] * len(cands)
    geoms = np.asarray(buildings_local.geometry.values, dtype=object)
    geoms = geoms[~shapely.is_missing(geoms) & ~shapely.is_empty(geoms)]
    if len(geoms) == 0:
        return [False] * len(cands)
    tree = STRtree(geoms)
    points = shapely.points([c.x for c in cands], [c.y for c in cands])
    # Bounding-box prefilter by the buffer, then an exact distance check.
    pt_idx, geom_idx = tree.query(shapely.buffer(points, buffer_m, quad_segs=1))
    near = [False] * len(cands)
    if len(pt_idx):
        dist = shapely.distance(points[pt_idx], geoms[geom_idx])
        for i in np.unique(pt_idx[dist <= buffer_m]):
            near[int(i)] = True
    return near


def apply_palm_rules(
    cands: list[LidarCandidate],
    params: RuleParams,
    buildings_local: gpd.GeoDataFrame | None,
) -> tuple[list[LidarCandidate], list[Reject]]:
    """Set ``accepted`` and ``reasons`` on every candidate and build the reject rows.

    ``buildings_local`` must already be in the candidates' local metric CRS (or ``None``).
    Returns ``(cands, rejects)``: the same candidates (all of them, accepted or not, since the
    inventory merge may still use rejected ones) and one ``Reject`` per failed candidate.
    """
    near = _near_buildings(cands, buildings_local, params.building_buffer_m)
    rejects: list[Reject] = []
    for cand, near_building in zip(cands, near, strict=True):
        cand.reasons = failed_rules(cand, params, near_building)
        cand.accepted = not cand.reasons
        if cand.accepted:
            continue
        rejects.append(
            Reject(
                stage=STAGE,
                source=SOURCE,
                source_id=cand.candidate_id,
                lon=cand.lon,
                lat=cand.lat,
                reason=cand.reasons[0],
                all_reasons=list(cand.reasons),
                metrics={
                    "height_m": cand.height_m,
                    "crown_diam_m": cand.crown_diam_m,
                    "ratio": cand.ratio,
                    "shared_boundary_frac": cand.shared_boundary_frac,
                },
            )
        )
    return cands, rejects
