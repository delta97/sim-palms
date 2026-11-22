"""USGS 3DEP Entwine Point Tile (EPT) LiDAR adapter.

Selects the EPT dataset(s) covering a bbox, plans buffered tiles in the local UTM CRS, builds
one PDAL pipeline per tile, caches each result as LAZ under ``data/lidar/<dataset>/`` and exposes
the points through :class:`PointSource`.

PDAL is reached only through the small injectable :class:`PdalRunner` protocol, so pipeline
JSON, tiling, dataset selection and cache logic run (and are unit tested) without PDAL. The
default runner needs the ``pdal`` Python binding, which needs the native PDAL library; it is
imported lazily.

Facts read from the public sources on 2026-11-22 (they are parsed from data here, not assumed):

- Boundaries index ``https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/
  resources.geojson``: HTTP 200, 8.8 MB, FeatureCollection of 2284 MultiPolygon features in
  EPSG:4326 (lon/lat) whose properties are ``name``, ``id``, ``count`` and ``url`` (the
  ``ept.json`` URL). Some names carry no year (``CA_LosAngeles_1_B23``) and some carry two
  (``USGS_LPC_CA_SanDiegoQL1_2014_LAS_2016``); the first ``_YYYY`` is taken as the year.
- ``ept.json`` of ``USGS_LPC_CA_SanDiegoQL1_2014_LAS_2016`` has ``srs`` =
  ``{"authority": "EPSG", "horizontal": "3857", "wkt": ...}``, ``dataType`` ``laszip`` and
  schema dimensions including ``ReturnNumber``, ``NumberOfReturns`` and ``Classification``.
  Other datasets may differ, so the SRS is always read from each ``ept.json``.
VERIFY: ``Classification`` values (classes 2 and 6 present) and the vertical datum/units of each
dataset; the ``srs`` block has no ``vertical`` entry in the sample read.
VERIFY: ``pdal.Pipeline.execute_streaming`` / ``streamable`` exist as used by
:class:`PdalPythonRunner` (python-pdal 3.x docs, not exercised here: PDAL is not installed).
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Protocol

import numpy as np
import pyproj
from numpy.typing import NDArray
from shapely import box as shapely_box
from shapely.geometry import Polygon, shape
from shapely.geometry.base import BaseGeometry

from palmcore import cache as _pc
from palmcore.errors import CacheMiss, SourceError
from palmcore.log import get_logger
from palmscan.cache import Cache, cache_key
from palmscan.config import LidarParams, ScanConfig
from palmscan.geo import WGS84, Bbox
from palmscan.http import HttpClient

__all__ = [
    "BOUNDARIES_URL",
    "POINT_DTYPE",
    "EptDataset",
    "EptPointSource",
    "LidarTile",
    "PdalPythonRunner",
    "PdalRunner",
    "PointSource",
    "build_pipeline",
    "fetch_tile",
    "load_boundaries",
    "load_ept_srs",
    "parse_boundaries",
    "parse_ept_srs",
    "parse_year",
    "plan_tiles",
    "read_points",
    "select_datasets",
]

_log = get_logger(__name__)

# VERIFY: location of the index is the hobuinc/usgs-lidar repository (HTTP 200 on 2026-11-22).
BOUNDARIES_URL: Final = (
    "https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson"
)
BOUNDARIES_NAMESPACE: Final = "lidar_boundaries"
BOUNDARIES_MAX_AGE_DAYS: Final = 30.0
EPT_JSON_NAMESPACE: Final = "lidar_ept_json"
LIDAR_DIR: Final = "lidar"

# Fields chm.build_chm reads (SCAN-022): X Y Z float64, the other three uint8.
POINT_DTYPE: Final = np.dtype(
    [
        ("X", "f8"),
        ("Y", "f8"),
        ("Z", "f8"),
        ("Classification", "u1"),
        ("ReturnNumber", "u1"),
        ("NumberOfReturns", "u1"),
    ]
)

_YEAR_RE: Final = re.compile(r"_(\d{4})(?!\d)")
_SAFE_NAME_RE: Final = re.compile(r"[^A-Za-z0-9._-]")
_MIN_COVER_FRAC: Final = 1e-6  # share of the bbox a dataset must add to be selected

PointArray = NDArray[Any]
CrsLike = str | pyproj.CRS


@dataclass(frozen=True, slots=True)
class EptDataset:
    """One 3DEP EPT dataset: name, ``ept.json`` URL, collection year, footprint (EPSG:4326)."""

    name: str
    url: str
    year: int | None
    footprint: BaseGeometry


@dataclass(frozen=True, slots=True)
class LidarTile:
    """A tile in the local metric CRS. ``tile_id`` is ``e{easting}_n{northing}`` of its corner."""

    tile_id: str
    bounds: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax, without buffer
    buffered: tuple[float, float, float, float]


class PointSource(Protocol):
    """What the pipeline consumes; tests swap in a fake."""

    def tiles(self) -> list[tuple[EptDataset, LidarTile]]: ...

    def points(self, ds: EptDataset, tile: LidarTile) -> PointArray: ...


class PdalRunner(Protocol):
    """Thin seam over PDAL. Implementations must not hold written points in memory."""

    @property
    def version(self) -> str: ...

    def write(self, pipeline: Mapping[str, Any]) -> int | None:
        """Execute a pipeline that ends in a writer; return the point count if known."""
        ...

    def read(self, pipeline: Mapping[str, Any]) -> PointArray:
        """Execute a reader pipeline and return all points as one structured array."""
        ...


class PdalPythonRunner:
    """Runs pipelines through the ``pdal`` Python binding (imported on first use)."""

    def __init__(self, chunk_size: int = 100_000) -> None:
        self.chunk_size = chunk_size

    @staticmethod
    def _pdal() -> Any:
        try:
            import pdal
        except ImportError as exc:
            raise SourceError(
                "the pdal Python binding is not installed; install PDAL (e.g. conda-forge "
                "'pdal' and 'python-pdal') and then `pip install -e .[pdal]`"
            ) from exc
        return pdal

    @property
    def version(self) -> str:
        return str(getattr(self._pdal(), "__version__", "unknown"))

    def write(self, pipeline: Mapping[str, Any]) -> int | None:
        pipe = self._pdal().Pipeline(json.dumps(pipeline))
        if getattr(pipe, "streamable", False):
            # Streaming keeps memory flat: points go reader -> writer in chunks.
            return int(pipe.execute_streaming(chunk_size=self.chunk_size))
        return int(pipe.execute())

    def read(self, pipeline: Mapping[str, Any]) -> PointArray:
        pipe = self._pdal().Pipeline(json.dumps(pipeline))
        pipe.execute()
        arrays = pipe.arrays
        if not arrays:
            return np.empty(0, dtype=POINT_DTYPE)
        result: PointArray = np.concatenate(arrays) if len(arrays) > 1 else arrays[0]
        return result


def parse_year(name: str) -> int | None:
    """Collection year: the first ``_YYYY`` in the dataset name, or ``None``. VERIFY naming."""
    match = _YEAR_RE.search(name)
    return int(match.group(1)) if match else None


def parse_boundaries(geojson: Mapping[str, Any]) -> list[EptDataset]:
    """Datasets from the boundaries FeatureCollection (properties ``name`` and ``url``).

    Features without a name, URL or geometry are skipped. Order is by name for determinism.
    """
    datasets: list[EptDataset] = []
    for feature in geojson.get("features", []):
        props = feature.get("properties") or {}
        name, url = props.get("name"), props.get("url")
        geometry = feature.get("geometry")
        if not name or not url or not geometry:
            continue
        datasets.append(EptDataset(str(name), str(url), parse_year(str(name)), shape(geometry)))
    datasets.sort(key=lambda d: d.name)
    return datasets


def load_boundaries(cache: Cache, http: HttpClient) -> list[EptDataset]:
    """Boundaries index, cached in ``lidar_boundaries`` and refreshed after 30 days.

    Offline use accepts a stale copy; a missing copy raises :class:`CacheMiss`.
    """
    key = cache_key(BOUNDARIES_URL)
    path = cache.path_for(BOUNDARIES_NAMESPACE, key, ".geojson")
    stale = _pc.is_cached(path) and not _pc.is_fresh(path, BOUNDARIES_MAX_AGE_DAYS)
    # A stale copy is refetched when online; offline it is used as is.
    fetcher = (
        Cache(cache.root, offline=False, refresh=True) if stale and not cache.offline else cache
    )
    got = fetcher.get_or_fetch(
        BOUNDARIES_NAMESPACE,
        key,
        lambda tmp: http.download(BOUNDARIES_URL, tmp),
        suffix=".geojson",
        meta={"url": BOUNDARIES_URL},
    )
    return parse_boundaries(json.loads(got.read_text(encoding="utf-8")))


def _as_bbox(bbox: Bbox | Sequence[float]) -> Bbox:
    return bbox if isinstance(bbox, Bbox) else Bbox.from_list(bbox)


def select_datasets(
    datasets: Sequence[EptDataset], bbox: Bbox | Sequence[float], forced: Sequence[str] = ()
) -> list[EptDataset]:
    """Datasets to read for ``bbox``, newest first.

    ``forced`` (config ``lidar.datasets``) overrides selection: those names, in the given order;
    an unknown name raises :class:`SourceError`. Otherwise datasets whose footprint intersects
    the bbox are considered newest year first (no year last, then by name) and one is kept only
    if it covers part of the bbox that newer ones do not, so on overlap the newest wins.
    """
    if forced:
        by_name = {d.name: d for d in datasets}
        missing = [n for n in forced if n not in by_name]
        if missing:
            raise SourceError(f"unknown 3DEP EPT dataset(s) in lidar.datasets: {missing}")
        return [by_name[n] for n in forced]
    box = _as_bbox(bbox)
    area = shapely_box(*box.as_tuple())
    candidates = [d for d in datasets if d.footprint.intersects(area)]
    candidates.sort(key=lambda d: (-(d.year if d.year is not None else -1), d.name))
    chosen: list[EptDataset] = []
    covered: BaseGeometry = Polygon()
    for ds in candidates:
        added = area.intersection(ds.footprint).difference(covered)
        if added.area > _MIN_COVER_FRAC * area.area:
            chosen.append(ds)
            covered = covered.union(ds.footprint)
    if not chosen:
        raise SourceError("no 3DEP EPT coverage for bbox")
    return chosen


def _crs(crs: CrsLike) -> pyproj.CRS:
    return crs if isinstance(crs, pyproj.CRS) else pyproj.CRS.from_user_input(crs)


def _crs_text(crs: CrsLike) -> str:
    c = _crs(crs)
    authority = c.to_authority()
    return f"{authority[0]}:{authority[1]}" if authority else c.to_wkt()


def _envelope(
    bounds: Sequence[float], src: CrsLike, dst: CrsLike, densify: int = 8
) -> tuple[float, float, float, float]:
    """Envelope of the (edge-densified) rectangle ``bounds`` transformed ``src`` -> ``dst``."""
    xmin, ymin, xmax, ymax = bounds
    ts = np.linspace(0.0, 1.0, densify + 1)
    xs = np.concatenate([xmin + (xmax - xmin) * ts, np.full_like(ts, xmax)])
    ys = np.concatenate([np.full_like(ts, ymin), ymin + (ymax - ymin) * ts])
    xs = np.concatenate([xs, xmax - (xmax - xmin) * ts, np.full_like(ts, xmin)])
    ys = np.concatenate([ys, np.full_like(ts, ymax), ymax - (ymax - ymin) * ts])
    transformer = pyproj.Transformer.from_crs(_crs(src), _crs(dst), always_xy=True)
    tx, ty = transformer.transform(xs, ys)
    return float(np.min(tx)), float(np.min(ty)), float(np.max(tx)), float(np.max(ty))


def plan_tiles(
    bbox: Bbox | Sequence[float],
    crs: CrsLike,
    tile_size_m: float = 500.0,
    buffer_m: float = 20.0,
) -> list[LidarTile]:
    """Tiles covering ``bbox`` in ``crs`` (normally the local UTM), snapped to ``tile_size_m``.

    ``tile_id`` is ``e{x}_n{y}`` (integer metres of the lower-left corner). Tiles are returned
    sorted by (easting, northing); ``buffered`` extends ``bounds`` by ``buffer_m`` on each side.
    """
    if tile_size_m <= 0 or buffer_m < 0:
        raise ValueError("tile_size_m must be > 0 and buffer_m >= 0")
    box = _as_bbox(bbox)
    xmin, ymin, xmax, ymax = _envelope(box.as_tuple(), WGS84, crs)
    first_i, last_i = math.floor(xmin / tile_size_m), math.ceil(xmax / tile_size_m)
    first_j, last_j = math.floor(ymin / tile_size_m), math.ceil(ymax / tile_size_m)
    tiles: list[LidarTile] = []
    for i in range(first_i, max(last_i, first_i + 1)):
        for j in range(first_j, max(last_j, first_j + 1)):
            x0, y0 = i * tile_size_m, j * tile_size_m
            bounds = (x0, y0, x0 + tile_size_m, y0 + tile_size_m)
            buffered = (x0 - buffer_m, y0 - buffer_m, bounds[2] + buffer_m, bounds[3] + buffer_m)
            tiles.append(LidarTile(f"e{round(x0)}_n{round(y0)}", bounds, buffered))
    return tiles


def parse_ept_srs(ept: Mapping[str, Any]) -> pyproj.CRS:
    """Horizontal CRS of an ``ept.json`` ``srs`` block: authority+horizontal, else its WKT."""
    srs = ept.get("srs")
    if not isinstance(srs, Mapping):
        raise SourceError("ept.json has no srs block")
    authority, horizontal = srs.get("authority"), srs.get("horizontal")
    try:
        if authority and horizontal:
            return pyproj.CRS.from_user_input(f"{authority}:{horizontal}")
        if srs.get("wkt"):
            return pyproj.CRS.from_user_input(str(srs["wkt"]))
    except pyproj.exceptions.CRSError as exc:
        raise SourceError(f"ept.json srs is not a valid CRS: {exc}") from exc
    raise SourceError("ept.json srs has neither authority/horizontal nor wkt")


def load_ept_srs(ds: EptDataset, cache: Cache, http: HttpClient) -> pyproj.CRS:
    """Read the dataset's ``ept.json`` (cached in ``lidar_ept_json``) and return its CRS."""
    key = cache_key(ds.url)
    path = cache.get_or_fetch(
        EPT_JSON_NAMESPACE,
        key,
        lambda tmp: http.download(ds.url, tmp),
        suffix=".json",
        meta={"url": ds.url},
    )
    return parse_ept_srs(json.loads(path.read_text(encoding="utf-8")))


def _bounds_text(b: Sequence[float]) -> str:
    return f"([{b[0]:.2f}, {b[2]:.2f}], [{b[1]:.2f}, {b[3]:.2f}])"


def _range_limits(noise_classes: Sequence[int]) -> str:
    return ",".join(f"Classification![{c}:{c}]" for c in noise_classes)


def build_pipeline(
    ds: EptDataset,
    tile: LidarTile,
    crs: CrsLike,
    noise_classes: Sequence[int],
    out_path: Path,
    *,
    ept_srs: CrsLike,
) -> dict[str, Any]:
    """PDAL pipeline for one tile: EPT read of the buffered bounds, drop noise, reproject, write.

    The buffered local-CRS bounds are transformed into ``ept_srs`` (read from ``ept.json``; the
    reader's ``bounds`` are in the dataset's own SRS) and widened to their envelope. The
    ``filters.range`` stage is omitted when ``noise_classes`` is empty.
    """
    ept_bounds = _envelope(tile.buffered, crs, ept_srs)
    stages: list[dict[str, Any]] = [
        {"type": "readers.ept", "filename": ds.url, "bounds": _bounds_text(ept_bounds)}
    ]
    if noise_classes:
        stages.append({"type": "filters.range", "limits": _range_limits(noise_classes)})
    stages.append({"type": "filters.reprojection", "out_srs": _crs_text(crs)})
    stages.append(
        {"type": "writers.las", "filename": Path(out_path).as_posix(), "compression": "laszip"}
    )
    return {"pipeline": stages}


def tile_path(cache: Cache, ds: EptDataset, tile: LidarTile) -> Path:
    """``<cache root>/lidar/<dataset>/<tile_id>.laz``, dataset name made filesystem-safe."""
    return cache.root / LIDAR_DIR / _SAFE_NAME_RE.sub("_", ds.name) / f"{tile.tile_id}.laz"


def _signature(ds: EptDataset, tile: LidarTile, crs: CrsLike, noise_classes: Sequence[int]) -> str:
    """Identity of the request; a cached tile is reused only when it matches."""
    return cache_key(
        {
            "url": ds.url,
            "buffered": [round(v, 3) for v in tile.buffered],
            "crs": _crs_text(crs),
            "noise_classes": list(noise_classes),
        }
    )


def fetch_tile(
    ds: EptDataset,
    tile: LidarTile,
    crs: CrsLike,
    params: LidarParams,
    cache: Cache,
    *,
    ept_srs: Callable[[], CrsLike],
    runner: PdalRunner | None = None,
    now: datetime | None = None,
) -> Path:
    """Return the cached LAZ for ``tile``, running PDAL to create it when needed.

    A tile is reused while its ``.meta.json`` signature (dataset URL, buffered bounds, CRS,
    noise classes) matches, unless ``cache.refresh``. A missing or mismatching tile with
    ``cache.offline`` raises :class:`CacheMiss`. ``ept_srs`` is called only when PDAL must run
    (it may hit the network). PDAL writes straight to a ``.part`` file beside the target, which
    is then moved into place, so points never pass through Python memory.
    """
    dest = tile_path(cache, ds, tile)
    signature = _signature(ds, tile, crs, params.noise_classes)
    if _pc.is_cached(dest) and (cache.offline or not cache.refresh):
        stored = _pc.read_meta(dest).get("params") or {}
        if stored.get("signature") == signature:
            return dest
        if cache.offline:
            raise CacheMiss(f"offline: cached tile {dest} was made with other settings")
    elif cache.offline:
        raise CacheMiss(f"offline: no cached LiDAR tile at {dest}")
    active = runner if runner is not None else PdalPythonRunner()
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f"{dest.stem}.part-{os.getpid()}{dest.suffix}")
    pipeline = build_pipeline(ds, tile, crs, params.noise_classes, part, ept_srs=ept_srs())
    _log.info("PDAL: reading %s tile %s", ds.name, tile.tile_id)
    try:
        count = active.write(pipeline)
        if not part.is_file():
            raise SourceError(f"PDAL did not write {part.name} for tile {tile.tile_id}")
        os.replace(part, dest)
    finally:
        with contextlib.suppress(OSError):
            part.unlink(missing_ok=True)
    if count == 0:
        _log.warning("tile %s of %s has no points after filtering", tile.tile_id, ds.name)
    moment = (now if now is not None else datetime.now(UTC)).astimezone(UTC)
    meta = {
        "url": ds.url,
        "params": {
            "signature": signature,
            "dataset": ds.name,
            "tile_id": tile.tile_id,
            "bounds": list(tile.bounds),
            "buffered": list(tile.buffered),
            "crs": _crs_text(crs),
            "noise_classes": list(params.noise_classes),
            "point_count": count,
            "pdal_version": active.version,
        },
        "fetched_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bytes": dest.stat().st_size,
    }
    _pc.atomic_write_text(_pc.meta_path(dest), _pc.canonical_json(meta) + "\n")
    return dest


def read_points(path: Path, runner: PdalRunner | None = None) -> PointArray:
    """Points of a cached LAZ as a structured array with :data:`POINT_DTYPE` fields.

    This is the array :func:`palmscan.detect.chm.build_chm` takes (X, Y, Z float64;
    Classification, ReturnNumber, NumberOfReturns uint8).
    """
    active = runner if runner is not None else PdalPythonRunner()
    raw = active.read({"pipeline": [{"type": "readers.las", "filename": Path(path).as_posix()}]})
    out = np.empty(len(raw), dtype=POINT_DTYPE)
    for name in POINT_DTYPE.names or ():
        if name not in (raw.dtype.names or ()):
            raise SourceError(f"{path.name}: point data has no {name} dimension")
        out[name] = raw[name]
    return out


class EptPointSource:
    """:class:`PointSource` backed by 3DEP EPT through PDAL, cached on disk."""

    def __init__(
        self,
        cfg: ScanConfig,
        cache: Cache,
        http: HttpClient,
        runner: PdalRunner | None = None,
        datasets: Sequence[EptDataset] | None = None,
    ) -> None:
        self.cfg = cfg
        self.cache = cache
        self.http = http
        self.runner = runner
        self._datasets = list(datasets) if datasets is not None else None
        self._srs: dict[str, pyproj.CRS] = {}
        self._tiles: list[tuple[EptDataset, LidarTile]] | None = None

    @property
    def crs(self) -> pyproj.CRS:
        return pyproj.CRS.from_user_input(self.cfg.region.crs())

    def ept_srs(self, ds: EptDataset) -> pyproj.CRS:
        if ds.url not in self._srs:
            self._srs[ds.url] = load_ept_srs(ds, self.cache, self.http)
        return self._srs[ds.url]

    def tiles(self) -> list[tuple[EptDataset, LidarTile]]:
        """Planned tiles, each paired with the newest selected dataset that covers it."""
        if self._tiles is not None:
            return self._tiles
        if self._datasets is None:
            self._datasets = load_boundaries(self.cache, self.http)
        bbox = self.cfg.region.bbox
        chosen = select_datasets(self._datasets, bbox, list(self.cfg.lidar.datasets))
        planned = plan_tiles(
            bbox, self.crs, self.cfg.lidar.tile_size_m, self.cfg.lidar.tile_buffer_m
        )
        result: list[tuple[EptDataset, LidarTile]] = []
        for tile in planned:
            area = shapely_box(*_envelope(tile.bounds, self.crs, WGS84))  # lon/lat envelope
            owner = next((d for d in chosen if d.footprint.intersects(area)), None)
            if owner is None:
                _log.warning("no selected 3DEP dataset covers tile %s; skipped", tile.tile_id)
                continue
            result.append((owner, tile))
        if not result:
            raise SourceError("no 3DEP EPT coverage for bbox")
        self._tiles = result
        return result

    def points(self, ds: EptDataset, tile: LidarTile) -> PointArray:
        path = fetch_tile(
            ds,
            tile,
            self.crs,
            self.cfg.lidar,
            self.cache,
            ept_srs=lambda: self.ept_srs(ds),
            runner=self.runner,
        )
        return read_points(path, self.runner)
