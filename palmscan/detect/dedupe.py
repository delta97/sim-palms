"""Cross-source dedupe: the same palm seen by two sources within a small radius becomes one.

Only points from *different* sources merge; two points of one source stay separate because
palms are planted in tight clusters. The result does not depend on input order: inputs are
sorted by stable key, sources are processed in priority order, and candidate pairs are
resolved by (distance, stable key of the incoming point, stable key of the kept point).
Distances use ``PalmRecord.x`` and ``y``, which must come from one local metric CRS
(``palmscan.geo.to_local``).
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from scipy.spatial import cKDTree

from palmscan.model import PalmRecord, Reject
from palmscan.species_names import GENERIC_KEY

__all__ = ["dedupe_cross_source", "source_of"]


def source_of(stable_key: str) -> str:
    """Source name of a ``<source>:<source_id>`` stable key."""
    return stable_key.split(":", 1)[0]


def _source_id_of(stable_key: str) -> str:
    return stable_key.split(":", 1)[1] if ":" in stable_key else stable_key


def _is_species_level(key: str | None) -> bool:
    return key is not None and key != GENERIC_KEY and not key.endswith("_sp")


def _copy(palm: PalmRecord) -> PalmRecord:
    return dataclasses.replace(
        palm, source_ids=list(palm.source_ids), data_vintage=dict(palm.data_vintage)
    )


def _absorb(kept: PalmRecord, other: PalmRecord) -> None:
    """Fold ``other`` into ``kept``: keep position, add ids, upgrade species, fill gaps."""
    for source_id in other.source_ids or [other.stable_key]:
        if source_id not in kept.source_ids:
            kept.source_ids.append(source_id)
    if _is_species_level(other.species) and not _is_species_level(kept.species):
        kept.species = other.species
        kept.species_confidence = other.species_confidence
        kept.species_source = other.species_source
        if other.species_raw is not None:
            kept.species_raw = other.species_raw
    if kept.height_raw is None and other.height_raw is not None:
        kept.height_raw = other.height_raw
    for key, value in other.data_vintage.items():
        kept.data_vintage.setdefault(key, value)


def dedupe_cross_source(
    palms: Sequence[PalmRecord],
    radius_m: float = 2.0,
    source_priority: Sequence[str] | None = None,
) -> tuple[list[PalmRecord], list[Reject]]:
    """Merge palms of different sources that lie within ``radius_m`` of each other.

    ``source_priority`` lists source names, highest priority first (normally the config order,
    then ``osm``); sources not listed rank after the listed ones, alphabetically. A point of a
    lower-priority source merges into the nearest kept point of a higher-priority source within
    ``radius_m``, provided that kept point has not already absorbed a point from the same
    source. The kept point keeps its position and gains the other's ``source_ids`` (the
    output ``source_ids`` are sorted), its species when it had none or only a genus and the
    other has a species, and its ``height_raw`` when it had none. Inputs are not modified.

    Returns ``(palms sorted by stable_key, one Reject per merged-away point)`` where the reject
    has ``stage="dedupe"`` and ``reason="duplicate_of:<stable_key of the kept palm>"``.
    """
    ordered = sorted(palms, key=lambda p: p.stable_key)
    by_source: dict[str, list[PalmRecord]] = defaultdict(list)
    for palm in ordered:
        by_source[source_of(palm.stable_key)].append(palm)

    listed = list(dict.fromkeys(source_priority or ()))
    rank_order = [s for s in listed if s in by_source]
    rank_order += sorted(s for s in by_source if s not in set(listed))

    kept: list[PalmRecord] = []  # kept points of all sources processed so far
    rejects: list[Reject] = []
    for source in rank_order:
        incoming = by_source[source]
        merged_away: set[int] = set()
        if kept:
            tree = cKDTree(np.array([[p.x, p.y] for p in kept], dtype=float))
            pairs: list[tuple[float, str, str, int, int]] = []
            for i, palm in enumerate(incoming):
                for j in tree.query_ball_point([palm.x, palm.y], r=radius_m):
                    other = kept[j]
                    dist = float(np.hypot(palm.x - other.x, palm.y - other.y))
                    if dist <= radius_m:
                        pairs.append((dist, palm.stable_key, other.stable_key, i, j))
            pairs.sort(key=lambda t: t[:3])
            used_incoming: set[int] = set()
            absorbed_by_source: set[int] = set()
            for _dist, _in_key, _kept_key, i, j in pairs:
                if i in used_incoming or j in absorbed_by_source:
                    continue
                used_incoming.add(i)
                absorbed_by_source.add(j)
                palm = incoming[i]
                _absorb(kept[j], palm)
                merged_away.add(i)
                reason = f"duplicate_of:{kept[j].stable_key}"
                rejects.append(
                    Reject(
                        stage="dedupe",
                        source=source,
                        source_id=_source_id_of(palm.stable_key),
                        lon=palm.lon,
                        lat=palm.lat,
                        reason=reason,
                        all_reasons=[reason],
                        species_raw=palm.species_raw,
                    )
                )
        # Add this source's survivors after matching, so same-source points never match.
        kept.extend(_copy(p) for i, p in enumerate(incoming) if i not in merged_away)

    for palm in kept:
        palm.source_ids = sorted(set(palm.source_ids or [palm.stable_key]))
    kept.sort(key=lambda p: p.stable_key)
    rejects.sort(key=lambda r: (r.source, r.source_id))
    return kept, rejects
