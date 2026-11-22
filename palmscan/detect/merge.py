"""Inventory-to-LiDAR matching and merge (plan W17).

Inventory palms are matched one-to-one to LiDAR crown candidates within a radius. A matched
palm keeps its inventory position (the trunk base, plan Q8) and takes height, crown and ground
elevation from LiDAR. Accepted candidates left over become LiDAR-only palms.

Nothing depends on input order: pairs are resolved globally, closest first, with ties broken by
(inventory ``stable_key``, ``candidate_id``). Distances use ``x``/``y``, which must come from one
local metric CRS (``palmscan.geo.to_local``). Inputs are not modified.
"""

from __future__ import annotations

import dataclasses
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

from palmscan.config import MergeParams, PeakParams
from palmscan.model import LidarCandidate, PalmRecord, Reject
from palmscan.species_names import GENERIC_KEY

__all__ = ["MergeResult", "match_inventory_to_lidar", "merge"]

BUILDING_REASON = "building"
HEIGHT_SOURCE_LIDAR = "lidar"
REJECT_NEAR_INVENTORY = "near_inventory"


@dataclass(slots=True)
class MergeResult:
    palms: list[PalmRecord]  # inventory palms (some matched) + LiDAR-only palms, by stable_key
    training: list[tuple[PalmRecord, LidarCandidate]]  # species-level matches = labels
    region_medians: dict[str, float] = field(default_factory=dict)
    rejects: list[Reject] = field(default_factory=list)


def _is_species_level(key: str | None) -> bool:
    return key is not None and key != GENERIC_KEY and not key.endswith("_sp")


def _matchable(cand: LidarCandidate, min_height_m: float) -> bool:
    return cand.height_m >= min_height_m and BUILDING_REASON not in cand.reasons


def _copy(palm: PalmRecord) -> PalmRecord:
    return dataclasses.replace(
        palm, source_ids=list(palm.source_ids), data_vintage=dict(palm.data_vintage)
    )


def _pairs_within(
    inv: Sequence[PalmRecord], cands: Sequence[LidarCandidate], radius_m: float
) -> list[tuple[float, str, str, int, int]]:
    if not inv or not cands:
        return []
    tree = cKDTree(np.array([[c.x, c.y] for c in cands], dtype=float))
    pairs: list[tuple[float, str, str, int, int]] = []
    for i, palm in enumerate(inv):
        for j in tree.query_ball_point([palm.x, palm.y], r=radius_m):
            dist = float(np.hypot(palm.x - cands[j].x, palm.y - cands[j].y))
            if dist <= radius_m:
                pairs.append((dist, palm.stable_key, cands[j].candidate_id, i, j))
    return pairs


def match_inventory_to_lidar(
    inv: Sequence[PalmRecord],
    cands: Sequence[LidarCandidate],
    match_radius_m: float = 3.0,
) -> list[tuple[int, int, float]]:
    """One-to-one global greedy matching of inventory palms to candidates.

    Every pair within ``match_radius_m`` (inclusive) is a candidate pair; pairs are taken in
    order of (distance, inventory ``stable_key``, ``candidate_id``) when neither side is already
    taken. Returns ``(inventory index, candidate index, distance_m)`` sorted by inventory index.
    Which palm gets which candidate does not depend on the order of ``inv`` or ``cands``. The
    caller decides which candidates are in the pool (see :func:`merge`).
    """
    pairs = _pairs_within(inv, cands, match_radius_m)
    pairs.sort(key=lambda t: t[:3])
    used_inv: set[int] = set()
    used_cand: set[int] = set()
    out: list[tuple[int, int, float]] = []
    for dist, _inv_key, _cand_id, i, j in pairs:
        if i in used_inv or j in used_cand:
            continue
        used_inv.add(i)
        used_cand.add(j)
        out.append((i, j, dist))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def _apply_match(palm: PalmRecord, cand: LidarCandidate) -> PalmRecord:
    out = _copy(palm)
    out.height_m = cand.height_m
    out.height_source = HEIGHT_SOURCE_LIDAR
    out.crown_diam_m = cand.crown_diam_m
    out.ground_elev_m = cand.ground_elev_m
    if not out.detected_by.endswith("+lidar"):
        out.detected_by = f"{out.detected_by}+lidar"
    out.source_ids = sorted({*out.source_ids, f"lidar:{cand.candidate_id}"})
    if cand.vintage is not None:
        out.data_vintage["lidar"] = cand.vintage
    out.lidar = cand
    return out


def _lidar_only_key(cand: LidarCandidate, taken: set[str]) -> str:
    base = f"lidar:{cand.dataset}:{round(cand.x)}:{round(cand.y)}"
    key, n = base, 1
    while key in taken:  # two peaks in one metre cell: rare, resolved in candidate_id order
        n += 1
        key = f"{base}:{n}"
    taken.add(key)
    return key


def _lidar_only_palm(cand: LidarCandidate, key: str) -> PalmRecord:
    return PalmRecord(
        stable_key=key,
        lon=cand.lon,
        lat=cand.lat,
        x=cand.x,
        y=cand.y,
        species=None,
        species_confidence=None,
        species_source=None,
        height_m=cand.height_m,
        height_source=HEIGHT_SOURCE_LIDAR,
        crown_diam_m=cand.crown_diam_m,
        ground_elev_m=cand.ground_elev_m,
        detected_by="lidar",
        source_ids=[f"lidar:{cand.candidate_id}"],
        data_vintage={"lidar": cand.vintage} if cand.vintage is not None else {},
        lidar=cand,
    )


def merge(
    inv: Sequence[PalmRecord],
    cands: Sequence[LidarCandidate],
    params: MergeParams | None = None,
    dedupe_radius_m: float = 2.0,
    min_height_m: float | None = None,
) -> MergeResult:
    """Merge inventory palms with LiDAR candidates (plan W17).

    ``cands`` are the candidates after the palm rules (``accepted`` and ``reasons`` set).
    Match pool: height >= ``min_height_m`` (default ``PeakParams().min_height_m``) and no
    ``building`` reason; other rule-rejected candidates may still match, because the inventory
    says it is a palm. Matched palms get LiDAR height, crown and ground elevation
    (``height_source="lidar"``), ``detected_by`` ``<origin>+lidar``, ``lidar:<candidate_id>`` in
    ``source_ids`` and ``data_vintage["lidar"]``; their position and stable key do not change.

    Accepted candidates that did not match become LiDAR-only palms (species ``None``, key
    ``lidar:<dataset>:<round(x)>:<round(y)>``), unless within ``dedupe_radius_m`` of any
    inventory palm, which gives a ``Reject(stage="merge", reason="near_inventory")``.
    ``region_medians`` holds the median LiDAR height per species-level species with at least
    ``params.region_median_min_n`` matches. ``training`` lists the species-level matches.
    """
    params = params or MergeParams()
    floor = PeakParams().min_height_m if min_height_m is None else min_height_m
    inv_sorted = sorted(inv, key=lambda p: p.stable_key)
    cands_sorted = sorted(cands, key=lambda c: c.candidate_id)
    pool = [c for c in cands_sorted if _matchable(c, floor)]

    matches = match_inventory_to_lidar(inv_sorted, pool, params.match_radius_m)
    match_of = {i: pool[j] for i, j, _ in matches}
    matched_ids = {pool[j].candidate_id for _, j, _ in matches}

    palms: list[PalmRecord] = []
    training: list[tuple[PalmRecord, LidarCandidate]] = []
    heights: dict[str, list[float]] = defaultdict(list)
    for i, palm in enumerate(inv_sorted):
        cand = match_of.get(i)
        if cand is None:
            palms.append(_copy(palm))
            continue
        merged = _apply_match(palm, cand)
        palms.append(merged)
        if merged.species is not None and _is_species_level(merged.species):
            training.append((merged, cand))
            heights[merged.species].append(cand.height_m)

    region_medians = {
        sp: float(statistics.median(hs))
        for sp, hs in sorted(heights.items())
        if len(hs) >= params.region_median_min_n
    }

    inv_tree = (
        cKDTree(np.array([[p.x, p.y] for p in inv_sorted], dtype=float)) if inv_sorted else None
    )
    rejects: list[Reject] = []
    taken: set[str] = set()
    for cand in cands_sorted:
        if not cand.accepted or cand.candidate_id in matched_ids:
            continue
        if inv_tree is not None:
            dist = float(inv_tree.query([cand.x, cand.y])[0])
            if dist <= dedupe_radius_m:
                rejects.append(
                    Reject(
                        stage="merge",
                        source=cand.dataset,
                        source_id=cand.candidate_id,
                        lon=cand.lon,
                        lat=cand.lat,
                        reason=REJECT_NEAR_INVENTORY,
                        all_reasons=[REJECT_NEAR_INVENTORY],
                        metrics={
                            "height_m": cand.height_m,
                            "crown_diam_m": cand.crown_diam_m,
                            "distance_m": dist,
                        },
                    )
                )
                continue
        palms.append(_lidar_only_palm(cand, _lidar_only_key(cand, taken)))

    palms.sort(key=lambda p: p.stable_key)
    training.sort(key=lambda t: t[0].stable_key)
    rejects.sort(key=lambda r: (r.source, r.source_id))
    return MergeResult(palms, training, region_medians, rejects)
