"""Overpass API client shared by the OSM tree and building adapters.

Responses are cached by the SHA-1 of the query text (namespace ``overpass``). Transport
problems (HTTP 406/429/502/504, retries with backoff, a generic User-Agent) are handled by
:class:`~palmscan.http.HttpClient`. Overpass also reports runtime errors and timeouts with
HTTP 200 and a ``remark`` field; those raise :class:`SourceError` and are never cached.

OSM data is ODbL 1.0, copyright OpenStreetMap contributors; see ``docs/licenses/data-sources.md``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Final

from palmcore.log import get_logger
from palmscan.cache import Cache
from palmscan.geo import Bbox
from palmscan.http import HttpClient
from palmscan.sources.base import SourceError, as_bbox

__all__ = [
    "DEFAULT_OVERPASS_URL",
    "OSM_ATTRIBUTION",
    "OSM_LICENSE",
    "OverpassClient",
    "bbox_tiles",
]

DEFAULT_OVERPASS_URL: Final = "https://overpass-api.de/api/interpreter"
OSM_ATTRIBUTION: Final = "Contains information from OpenStreetMap contributors"
OSM_LICENSE: Final = "ODbL-1.0"
CACHE_NAMESPACE: Final = "overpass"

_log = get_logger(__name__)
_EPS = 1e-9


def bbox_tiles(bbox: Bbox, max_deg: float = 0.05) -> list[Bbox]:
    """Split ``bbox`` into equal tiles no larger than ``max_deg`` per side.

    A side is divided into ``ceil(span / max_deg)`` equal parts, so a 0.12 deg box with the
    default gives 3 x 3 = 9 tiles. Tiles are ordered south to north, then west to east.
    """
    if max_deg <= 0:
        raise ValueError(f"max_deg must be positive, got {max_deg!r}")
    nx = max(1, math.ceil((bbox.lon_max - bbox.lon_min) / max_deg - _EPS))
    ny = max(1, math.ceil((bbox.lat_max - bbox.lat_min) / max_deg - _EPS))
    lons = [bbox.lon_min + (bbox.lon_max - bbox.lon_min) * i / nx for i in range(nx)]
    lons.append(bbox.lon_max)
    lats = [bbox.lat_min + (bbox.lat_max - bbox.lat_min) * j / ny for j in range(ny)]
    lats.append(bbox.lat_max)
    return [Bbox(lons[i], lats[j], lons[i + 1], lats[j + 1]) for j in range(ny) for i in range(nx)]


def _check_body(text: str, url: str) -> dict[str, Any]:
    try:
        body = json.loads(text)
    except ValueError as exc:
        snippet = " ".join(text.split())[:120]
        raise SourceError(f"{url}: Overpass did not return JSON ({snippet!r})") from exc
    if not isinstance(body, dict):
        raise SourceError(f"{url}: Overpass returned JSON that is not an object")
    remark = body.get("remark")
    if isinstance(remark, str) and "runtime error" in remark.lower():
        raise SourceError(f"{url}: Overpass runtime error: {remark}")
    if remark:
        _log.warning("Overpass remark from %s: %s", url, remark)
    return body


def _elements(body: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for element in body.get("elements") or []:
        if isinstance(element, dict):
            yield element


def _num(value: float) -> str:
    return f"{value:.7f}".rstrip("0").rstrip(".")


class OverpassClient:
    """Cached Overpass client. ``query(ql)`` returns the parsed JSON response."""

    def __init__(self, http: HttpClient, cache: Cache, url: str = DEFAULT_OVERPASS_URL) -> None:
        self.http = http
        self.cache = cache
        self.url = url

    def query(self, ql: str) -> dict[str, Any]:
        """POST ``ql`` (``data=ql``), cached by sha1(ql); raise on a runtime-error remark."""
        key = hashlib.sha1(ql.encode("utf-8"), usedforsecurity=False).hexdigest()

        def fetch(dest: Path) -> None:
            text = self.http.post_text(self.url, {"data": ql})
            _check_body(text, self.url)  # never cache an error response
            dest.write_text(text, encoding="utf-8")

        path = self.cache.get_or_fetch(
            CACHE_NAMESPACE,
            key,
            fetch,
            suffix=".json",
            meta={"url": self.url, "params": {"ql": ql}},
        )
        return _check_body(path.read_text(encoding="utf-8"), self.url)

    def query_bbox(self, template: str, bbox: Bbox | Sequence[float]) -> dict[str, Any]:
        """Run ``template`` once per tile of ``bbox`` and merge elements by ``(type, id)``.

        The template may use ``{south}``, ``{west}``, ``{north}``, ``{east}`` or ``{bbox}``
        (``south,west,north,east``, Overpass order). Returns the first response with its
        ``elements`` replaced by the merged list (first occurrence wins).
        """
        box = as_bbox(bbox)
        merged: dict[tuple[Any, Any], dict[str, Any]] = {}
        first: dict[str, Any] | None = None
        for tile in bbox_tiles(box):
            south, west = _num(tile.lat_min), _num(tile.lon_min)
            north, east = _num(tile.lat_max), _num(tile.lon_max)
            ql = template.format(
                south=south,
                west=west,
                north=north,
                east=east,
                bbox=f"{south},{west},{north},{east}",
            )
            body = self.query(ql)
            if first is None:
                first = body
            for element in _elements(body):
                merged.setdefault((element.get("type"), element.get("id")), element)
        assert first is not None  # bbox_tiles always yields at least one tile
        result = dict(first)
        result["elements"] = list(merged.values())
        return result
