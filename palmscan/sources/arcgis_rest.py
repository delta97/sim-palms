"""``arcgis_rest`` inventory adapter: an ArcGIS MapServer / FeatureServer point layer.

Every HTTP response (layer info, each query page, each id list) is cached as its own JSON
entry in namespace ``arcgis_rest``, keyed on the URL plus the full parameter set, so a warm
cache replays a run with zero requests. ArcGIS reports most failures as HTTP 200 with an
``error`` object; that is detected before anything is cached.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from palmcore.cache import cache_key
from palmcore.log import get_logger
from palmscan.cache import Cache
from palmscan.config import InventorySourceCfg
from palmscan.geo import Bbox
from palmscan.http import HttpClient
from palmscan.model import TreeRecord
from palmscan.sources.base import FetchResult, SourceError, as_bbox, derive_vintage

__all__ = ["MAX_RECORDS", "ArcGisRestAdapter"]

_log = get_logger(__name__)
_CACHE_NAMESPACE = "arcgis_rest"
DEFAULT_MAX_RECORD_COUNT = 1000
PAGE_CAP = 2000
# Ids per ``objectIds=`` request in the no-pagination fallback. They travel in a GET query
# string, so this is capped below ``PAGE_CAP`` to keep URLs short.
ID_CHUNK_CAP = 500
MAX_RECORDS = 200_000  # per source per run; guards a wrong bbox


def _text(value: Any) -> str | None:
    """Raw attribute as stripped text; empty, NaN and missing become ``None``."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


class ArcGisRestAdapter:
    """Pulls every tree point inside the bbox from an ArcGIS layer (``cfg.url`` is the layer)."""

    def __init__(self, cfg: InventorySourceCfg) -> None:
        self.cfg = cfg
        self.name = cfg.name

    # ------------------------------------------------------------------ transport

    def _check_error(self, body: Any, url: str) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise SourceError(f"{self.name}: unexpected non-object JSON from {url}")
        err = body.get("error")
        if err:
            if isinstance(err, dict):
                code = err.get("code", "?")
                message = err.get("message", "")
                details = err.get("details")
                extra = f" ({'; '.join(str(d) for d in details)})" if details else ""
                raise SourceError(f"{self.name}: ArcGIS error {code}: {message}{extra} [{url}]")
            raise SourceError(f"{self.name}: ArcGIS error: {err} [{url}]")
        return body

    def _get(
        self, url: str, params: Mapping[str, Any], cache: Cache, http: HttpClient
    ) -> dict[str, Any]:
        """GET JSON through the cache; error bodies are raised and never cached."""

        def fetch(dest: Path) -> None:
            body = self._check_error(http.get_json(url, dict(params)), url)
            dest.write_text(json.dumps(body), encoding="utf-8")

        path = cache.get_or_fetch(
            _CACHE_NAMESPACE,
            cache_key({"url": url, "params": dict(params)}),
            fetch,
            suffix=".json",
            meta={"url": url, "params": dict(params)},
        )
        return self._check_error(json.loads(path.read_text(encoding="utf-8")), url)

    # ------------------------------------------------------------------ layer info

    def _layer_info(
        self, layer_url: str, cache: Cache, http: HttpClient, warnings: list[str]
    ) -> tuple[int, str, bool, Any]:
        """``(maxRecordCount, objectIdField, supportsPagination, lastEditDate)``."""
        cfg = self.cfg
        info = self._get(layer_url, {"f": "json"}, cache, http)
        raw_fields = info.get("fields")
        fields = raw_fields if isinstance(raw_fields, list) else []
        names = {str(f.get("name")) for f in fields if isinstance(f, dict)}
        if cfg.species_field not in names:
            raise SourceError(
                f"{self.name}: species_field {cfg.species_field!r} not in layer fields "
                f"({', '.join(sorted(names)) or 'none listed'}) [{layer_url}]"
            )
        wanted = [cfg.common_name_field, cfg.id_field, cfg.status_field, cfg.height_field]
        wanted += [cfg.dbh_field, cfg.date_field]
        for name in wanted:
            if name and name not in names:
                warnings.append(f"configured field {name!r} not in layer fields; values empty")

        max_count = info.get("maxRecordCount")
        if not isinstance(max_count, int) or isinstance(max_count, bool) or max_count < 1:
            max_count = DEFAULT_MAX_RECORD_COUNT
        oid = info.get("objectIdField")
        if not isinstance(oid, str) or not oid:
            oid = next(
                (
                    str(f.get("name"))
                    for f in fields
                    if isinstance(f, dict) and f.get("type") == "esriFieldTypeOID"
                ),
                "OBJECTID",
            )
        caps = info.get("advancedQueryCapabilities")
        # Only an explicit true enables resultOffset paging: a server that ignores the
        # parameter would otherwise return the same first page forever.
        paging = isinstance(caps, dict) and caps.get("supportsPagination") is True
        editing = info.get("editingInfo")
        edit_ms = editing.get("lastEditDate") if isinstance(editing, dict) else None
        return max_count, oid, paging, edit_ms

    # ------------------------------------------------------------------ features

    def _base_params(self, box: Bbox) -> dict[str, Any]:
        return {
            "where": self.cfg.where or "1=1",
            "geometry": f"{box.lon_min},{box.lat_min},{box.lon_max},{box.lat_max}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }

    @staticmethod
    def _features(body: dict[str, Any]) -> list[dict[str, Any]]:
        raw = body.get("features")
        return [f for f in raw if isinstance(f, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _oid_of(feature: dict[str, Any], oid: str) -> str | None:
        attrs = feature.get("attributes")
        return _text(attrs.get(oid)) if isinstance(attrs, dict) else None

    def _paged(
        self, query_url: str, box: Bbox, oid: str, page: int, cache: Cache, http: HttpClient
    ) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []
        seen: set[str] = set()
        offset = 0
        while True:
            params = {
                **self._base_params(box),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "orderByFields": f"{oid} ASC",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": page,
            }
            body = self._get(query_url, params, cache, http)
            batch = self._features(body)
            if not batch:
                break
            ids = {i for i in (self._oid_of(f, oid) for f in batch) if i is not None}
            if ids and ids <= seen:
                raise SourceError(
                    f"{self.name}: server ignored resultOffset (repeated records) [{query_url}]"
                )
            seen |= ids
            features.extend(batch)
            self._guard_total(len(features), query_url)
            if not (body.get("exceededTransferLimit") is True or len(batch) >= page):
                break
            offset += len(batch)
        return features

    def _by_ids(
        self, query_url: str, box: Bbox, page: int, cache: Cache, http: HttpClient
    ) -> list[dict[str, Any]]:
        ids_params = {**self._base_params(box), "returnIdsOnly": "true", "f": "json"}
        body = self._get(query_url, ids_params, cache, http)
        raw = body.get("objectIds")
        ids = sorted(
            {int(i) for i in raw if isinstance(i, int) and not isinstance(i, bool)}
            if isinstance(raw, list)
            else set()
        )
        self._guard_total(len(ids), query_url)
        chunk = min(page, ID_CHUNK_CAP)
        features: list[dict[str, Any]] = []
        for start in range(0, len(ids), chunk):
            params = {
                "objectIds": ",".join(str(i) for i in ids[start : start + chunk]),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "json",
            }
            features.extend(self._features(self._get(query_url, params, cache, http)))
        return features

    def _guard_total(self, count: int, url: str) -> None:
        if count > MAX_RECORDS:
            raise SourceError(
                f"{self.name}: more than {MAX_RECORDS} records from {url}; "
                "check the bbox and where clause"
            )

    # ------------------------------------------------------------------ fetch

    def fetch(self, bbox: Bbox | Sequence[float], cache: Cache, http: HttpClient) -> FetchResult:
        cfg = self.cfg
        box = as_bbox(bbox)
        if not cfg.url:
            raise SourceError(f"{self.name}: arcgis_rest source needs url")
        layer_url = cfg.url.rstrip("/")
        query_url = f"{layer_url}/query"
        warnings: list[str] = []

        max_count, layer_oid, paging, edit_ms = self._layer_info(layer_url, cache, http, warnings)
        page = min(max_count, PAGE_CAP)
        if paging:
            features = self._paged(query_url, box, layer_oid, page, cache, http)
        else:
            warnings.append("layer does not report pagination support: fetched by object id")
            features = self._by_ids(query_url, box, page, cache, http)

        id_field = cfg.id_field or layer_oid
        records: list[TreeRecord] = []
        dates: list[Any] = []
        seen: set[str] = set()
        n_null = n_other = n_outside = n_dup = n_noid = 0
        for feature in features:
            attrs = feature.get("attributes")
            attrs = attrs if isinstance(attrs, dict) else {}
            geom = feature.get("geometry")
            if not isinstance(geom, dict):
                n_null += 1
                continue
            if "x" not in geom and "y" not in geom:
                n_other += 1
                continue
            lon, lat = _number(geom.get("x")), _number(geom.get("y"))
            if lon is None or lat is None:
                n_null += 1  # empty points come back as NaN or missing coordinates
                continue
            if not (box.lon_min <= lon <= box.lon_max and box.lat_min <= lat <= box.lat_max):
                n_outside += 1
                continue
            source_id = _text(attrs.get(id_field)) or _text(attrs.get(layer_oid))
            if source_id is None:
                n_noid += 1
                continue
            if source_id in seen:
                n_dup += 1
                continue
            seen.add(source_id)
            records.append(self._record(attrs, source_id, lon, lat))
            if cfg.date_field:
                dates.append(attrs.get(cfg.date_field))
        for count, text in (
            (n_null, "skipped: null or empty geometry"),
            (n_other, "skipped: geometry is not a point"),
            (n_outside, "skipped: point outside bbox"),
            (n_noid, "skipped: no object id"),
            (n_dup, "dropped: duplicate object id"),
        ):
            if count:
                warnings.append(f"{count} features {text}")

        vintage = derive_vintage(cfg.vintage, dates, edit_ms, datetime.now(UTC), source=self.name)
        for message in warnings:
            _log.warning("%s: %s", self.name, message)
        return FetchResult(records=records, vintage=vintage, warnings=warnings)

    def _record(
        self, attrs: Mapping[str, Any], source_id: str, lon: float, lat: float
    ) -> TreeRecord:
        c = self.cfg

        def get(name: str | None) -> str | None:
            return _text(attrs.get(name)) if name else None

        return TreeRecord(
            source=c.name,
            source_id=source_id,
            lon=lon,
            lat=lat,
            species_raw=get(c.species_field),
            common_name_raw=get(c.common_name_field),
            status_raw=get(c.status_field),
            height_raw=get(c.height_field),
            dbh_raw=get(c.dbh_field),
            date_raw=get(c.date_field),
        )
