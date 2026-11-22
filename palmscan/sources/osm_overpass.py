"""``osm`` adapter: OpenStreetMap ``natural=tree`` nodes that carry a species-like tag.

OSM data is ODbL 1.0, copyright OpenStreetMap contributors (``docs/licenses/data-sources.md``).
Every record carries ``extra["license"]`` and ``extra["attribution"]`` so downstream outputs
and QA files can credit OSM. The adapter owns an :class:`OverpassClient`, which holds the
HTTP client and cache, so the ``cache`` and ``http`` arguments of :meth:`fetch` are unused.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

from palmcore.log import get_logger
from palmscan.cache import Cache
from palmscan.geo import Bbox
from palmscan.http import HttpClient
from palmscan.model import TreeRecord
from palmscan.sources.base import FetchResult, as_bbox, derive_vintage
from palmscan.sources.overpass import OSM_ATTRIBUTION, OSM_LICENSE, OverpassClient

__all__ = ["OSM_TREES_QUERY", "OsmTreesAdapter"]

_log = get_logger(__name__)

OSM_TREES_QUERY: Final = """[out:json][timeout:120];
node["natural"="tree"]({south},{west},{north},{east});
out body;"""

SPECIES_TAGS: Final = ("species", "genus", "taxon", "species:en")


def _tag(tags: dict[str, Any], key: str) -> str | None:
    value = tags.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class OsmTreesAdapter:
    """Reads tagged OSM tree nodes inside the bbox through an :class:`OverpassClient`."""

    def __init__(self, overpass: OverpassClient, name: str = "osm") -> None:
        self.overpass = overpass
        self.name = name

    def fetch(
        self,
        bbox: Bbox | Sequence[float],
        cache: Cache | None = None,
        http: HttpClient | None = None,
    ) -> FetchResult:
        box = as_bbox(bbox)
        body = self.overpass.query_bbox(OSM_TREES_QUERY, box)
        records: list[TreeRecord] = []
        untagged = 0
        for element in body.get("elements", []):
            if element.get("type") != "node":
                continue
            try:
                lon, lat = float(element["lon"]), float(element["lat"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (box.lon_min <= lon <= box.lon_max and box.lat_min <= lat <= box.lat_max):
                continue
            tags = element.get("tags") or {}
            species = next((t for k in SPECIES_TAGS if (t := _tag(tags, k))), None)
            if species is None:
                untagged += 1
                continue
            records.append(
                TreeRecord(
                    source=self.name,
                    source_id=f"node/{element['id']}",
                    lon=lon,
                    lat=lat,
                    species_raw=species,
                    common_name_raw=_tag(tags, "species:en"),
                    extra={"license": OSM_LICENSE, "attribution": OSM_ATTRIBUTION},
                )
            )
        warnings: list[str] = []
        if untagged:
            warnings.append(
                f"{self.name}: dropped {untagged} tree node(s) without species, genus or taxon tags"
            )
        _log.info(
            "%s: %d tagged tree nodes, %d untagged dropped", self.name, len(records), untagged
        )
        vintage = derive_vintage(None, [], None, datetime.now(UTC), source=self.name)
        return FetchResult(records=records, vintage=vintage, warnings=warnings)
