"""``geojson_file`` inventory adapter: local or downloaded GeoJSON / CSV tree files.

Memory behaviour
----------------
* CSV is streamed row by row (``csv.DictReader``); only rows inside the bbox are kept, so
  memory is proportional to the clipped result, not the file.
* GeoJSON is read with ``geopandas.read_file(..., bbox=..., engine="pyogrio")``. The bbox is
  an OGR spatial filter, so only matching features reach Python and the resulting
  GeoDataFrame is proportional to the clipped result. Whether the GDAL GeoJSON driver itself
  has to hold the whole document while parsing is a GDAL detail (GeoJSON has no spatial
  index). VERIFY: peak memory on the real 627 MB LA County file (SCAN-007). If it is too
  high, convert the file once to GeoPackage or FlatGeobuf (indexed) and point ``path`` at
  that; any OGR-readable file works with ``format: geojson``.
* This module never loads the whole file into Python objects.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pyproj

from palmcore.cache import cache_key
from palmcore.log import get_logger
from palmscan.cache import Cache
from palmscan.config import InventorySourceCfg
from palmscan.geo import WGS84, Bbox
from palmscan.http import HttpClient
from palmscan.model import TreeRecord
from palmscan.sources.base import FetchResult, SourceError, as_bbox, derive_vintage

__all__ = ["GeoJsonFileAdapter"]

_log = get_logger(__name__)
_CACHE_NAMESPACE = "geojson_file"
_VALID_SUFFIX = re.compile(r"^\.[a-z0-9.]{1,16}$")
_FORMAT_BY_SUFFIX = {".geojson": "geojson", ".json": "geojson", ".csv": "csv"}
_DEFAULT_SUFFIX = {"geojson": ".geojson", "csv": ".csv"}


def _text(value: Any) -> str | None:
    """Raw cell value as stripped text; empty, NaN and missing become ``None``."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    return text or None


def _float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class GeoJsonFileAdapter:
    """Reads a GeoJSON or CSV tree file clipped to the region bbox.

    ``cfg.url`` is downloaded once through the cache (the file extension is kept);
    ``cfg.path`` is read in place. CSV needs ``lon_field`` and ``lat_field`` (WGS84 degrees).
    """

    def __init__(self, cfg: InventorySourceCfg) -> None:
        self.cfg = cfg
        self.name = cfg.name

    # ------------------------------------------------------------------ helpers

    def _optional_fields(self) -> list[str]:
        c = self.cfg
        names = [c.common_name_field, c.id_field, c.status_field, c.height_field]
        names += [c.dbh_field, c.date_field]
        return [n for n in names if n]

    def _record(self, row: Any, source_id: str, lon: float, lat: float) -> TreeRecord:
        c = self.cfg

        def get(field: str | None) -> str | None:
            return _text(row.get(field)) if field else None

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

    def _format(self) -> str:
        if self.cfg.format:
            return self.cfg.format
        location = self.cfg.path.name if self.cfg.path else urlparse(self.cfg.url or "").path
        fmt = _FORMAT_BY_SUFFIX.get(Path(location).suffix.lower())
        if fmt is None:
            raise SourceError(
                f"{self.name}: cannot infer format from {location!r}; set format: geojson or csv"
            )
        return fmt

    def _locate(self, fmt: str, cache: Cache, http: HttpClient) -> Path:
        cfg = self.cfg
        if cfg.path is not None:
            if not cfg.path.is_file():
                raise SourceError(f"{self.name}: file not found: {cfg.path}")
            return cfg.path
        if not cfg.url:
            raise SourceError(f"{self.name}: geojson_file source needs url or path")
        url = cfg.url
        suffix = Path(urlparse(url).path).suffix.lower()
        if not _VALID_SUFFIX.match(suffix):
            suffix = _DEFAULT_SUFFIX[fmt]
        return cache.get_or_fetch(
            _CACHE_NAMESPACE,
            cache_key(url),
            lambda dest: http.download(url, dest),
            suffix=suffix,
            meta={"url": url},
        )

    # ------------------------------------------------------------------ fetch

    def fetch(self, bbox: Bbox | Sequence[float], cache: Cache, http: HttpClient) -> FetchResult:
        box = as_bbox(bbox)
        fmt = self._format()
        path = self._locate(fmt, cache, http)
        warnings: list[str] = []
        if fmt == "csv":
            records, dates = self._read_csv(path, box, warnings)
        else:
            records, dates = self._read_geo(path, box, warnings)
        vintage = derive_vintage(self.cfg.vintage, dates, None, datetime.now(UTC), source=self.name)
        for message in warnings:
            _log.warning("%s: %s", self.name, message)
        return FetchResult(records=records, vintage=vintage, warnings=warnings)

    # ------------------------------------------------------------------ GeoJSON / OGR

    def _read_geo(
        self, path: Path, box: Bbox, warnings: list[str]
    ) -> tuple[list[TreeRecord], list[Any]]:
        import geopandas as gpd
        import pyogrio

        cfg = self.cfg
        try:
            info = pyogrio.read_info(path)
        except Exception as exc:
            raise SourceError(f"{self.name}: cannot read {path.name}: {exc}") from exc
        wgs84 = pyproj.CRS.from_user_input(WGS84)
        file_crs = pyproj.CRS.from_user_input(info["crs"]) if info.get("crs") else None
        reproject = file_crs is not None and file_crs != wgs84

        # The OGR spatial filter is applied in the file's own CRS.
        read_box: tuple[float, float, float, float] = (
            box.lon_min,
            box.lat_min,
            box.lon_max,
            box.lat_max,
        )
        if reproject and file_crs is not None:
            to_file = pyproj.Transformer.from_crs(wgs84, file_crs, always_xy=True)
            xmin, ymin, xmax, ymax = to_file.transform_bounds(*read_box, densify_pts=21)
            read_box = (xmin, ymin, xmax, ymax)
            warnings.append(
                f"file CRS is {file_crs.to_string()}, not EPSG:4326: reprojected to WGS84"
            )

        columns = {str(f) for f in info.get("fields", [])}
        if cfg.species_field not in columns:
            raise SourceError(
                f"{self.name}: species_field {cfg.species_field!r} not in {path.name} "
                f"(fields: {', '.join(sorted(columns)) or 'none'})"
            )
        for field in self._optional_fields():
            if field not in columns:
                warnings.append(f"configured field {field!r} not in file; values will be empty")

        try:
            frame = gpd.read_file(
                path, bbox=read_box, engine="pyogrio", fid_as_index=True, datetime_as_string=True
            )
        except Exception as exc:
            raise SourceError(f"{self.name}: cannot read {path.name}: {exc}") from exc
        if reproject:
            frame = frame.to_crs(WGS84)

        frame = frame[~(frame.geometry.isna() | frame.geometry.is_empty)]
        geom_types = frame.geometry.geom_type
        non_point = geom_types != "Point"
        n_non_point = int(non_point.sum())
        points = frame.geometry.copy()
        if n_non_point:
            points[non_point] = frame.geometry[non_point].representative_point()
            kinds = ", ".join(
                f"{k} x{v}" for k, v in sorted(Counter(geom_types[non_point]).items())
            )
            warnings.append(f"{n_non_point} non-point geometries replaced by a point ({kinds})")

        records: list[TreeRecord] = []
        dates: list[Any] = []
        n_fallback_id = 0
        n_outside = 0
        rows = frame[[c for c in frame.columns if c != "geometry"]].to_dict("records")
        for fid, geom, row in zip(frame.index, points, rows, strict=True):
            lon, lat = float(geom.x), float(geom.y)
            if not (box.lon_min <= lon <= box.lon_max and box.lat_min <= lat <= box.lat_max):
                n_outside += 1  # the geometry touched the bbox but its point is outside
                continue
            source_id = _text(row.get(cfg.id_field)) if cfg.id_field else None
            if source_id is None:
                source_id = str(fid)
                n_fallback_id += 1
            records.append(self._record(row, source_id, lon, lat))
            if cfg.date_field:
                dates.append(row.get(cfg.date_field))
        if n_fallback_id:
            warnings.append(
                f"{n_fallback_id} records had no {cfg.id_field or 'id_field'} value: used the "
                "feature id or row index (unstable across file updates)"
            )
        if n_outside:
            warnings.append(f"{n_outside} features dropped: representative point outside bbox")
        return records, dates

    # ------------------------------------------------------------------ CSV

    @staticmethod
    def _csv_rows(path: Path) -> Iterator[dict[str, str]]:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            yield from csv.DictReader(handle)

    def _read_csv(
        self, path: Path, box: Bbox, warnings: list[str]
    ) -> tuple[list[TreeRecord], list[Any]]:
        cfg = self.cfg
        if not cfg.lon_field or not cfg.lat_field:
            raise SourceError(f"{self.name}: CSV sources need lon_field and lat_field")
        records: list[TreeRecord] = []
        dates: list[Any] = []
        n_bad = 0
        n_fallback_id = 0
        header_checked = False
        for index, row in enumerate(self._csv_rows(path)):
            if not header_checked:
                header_checked = True
                missing = [
                    f for f in (cfg.lon_field, cfg.lat_field, cfg.species_field) if f not in row
                ]
                if missing:
                    raise SourceError(
                        f"{self.name}: columns {missing} not in {path.name} "
                        f"(columns: {', '.join(row)})"
                    )
                for field in self._optional_fields():
                    if field not in row:
                        warnings.append(
                            f"configured field {field!r} not in file; values will be empty"
                        )
            lon = _float(row.get(cfg.lon_field))
            lat = _float(row.get(cfg.lat_field))
            if lon is None or lat is None or abs(lon) > 180 or abs(lat) > 90:
                n_bad += 1
                continue
            if not (box.lon_min <= lon <= box.lon_max and box.lat_min <= lat <= box.lat_max):
                continue
            source_id = _text(row.get(cfg.id_field)) if cfg.id_field else None
            if source_id is None:
                source_id = str(index)
                n_fallback_id += 1
            records.append(self._record(row, source_id, lon, lat))
            if cfg.date_field:
                dates.append(row.get(cfg.date_field))
        if n_bad:
            warnings.append(f"{n_bad} rows skipped: missing or invalid coordinates")
        if n_fallback_id:
            warnings.append(
                f"{n_fallback_id} records had no {cfg.id_field or 'id_field'} value: used the "
                "0-based row index (unstable across file updates)"
            )
        return records, dates
