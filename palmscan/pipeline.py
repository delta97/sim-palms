"""The palmscan run pipeline (plan W11): inventory ingest to palms.geojson and the QA files.

Stages, in order: buildings, inventory ingest, cross-source dedupe, ``mask_out``, species priors,
LiDAR (tiles: CHM, peaks, crowns; palm rules; merge with the inventory; species tree or rules),
sizes / exclusion radius / building conflicts, palms.geojson, then ``buildings.geojson``,
``species_priors.yaml``, ``species_tree.json`` (when a tree is used), the QA files, the accuracy
files (``--eval-site``) and ``run.json``. The LiDAR stage runs when the region has
``sources.lidar: 3dep_ept`` and neither ``--no-lidar`` nor ``--only inventory`` is given.

Failures are raised as :class:`palmcore.errors.PalmfixError` subclasses; the CLI maps them to
exit codes (config 2, contract 3, source 4, cache miss 5). ``run.json`` is written for failed
runs too, with the exit code.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import numpy as np
import pyproj
import shapely
from shapely import STRtree
from shapely.geometry import mapping

from palmcore import contract
from palmcore.cache import atomic_write_text, canonical_json
from palmcore.errors import (
    EXIT_OK,
    CacheMiss,
    ConfigError,
    ContractError,
    PalmfixError,
    SourceError,
)
from palmcore.log import get_logger
from palmcore.palms import PalmsMeta, _resolve_generated_at
from palmscan import __version__, geo
from palmscan.attributes import assign_exclusion, assign_sizes, flag_building_conflicts
from palmscan.cache import Cache
from palmscan.classify.priors import compute_priors, merge_priors, priors_yaml, sample_species
from palmscan.config import ScanConfig
from palmscan.detect.dedupe import dedupe_cross_source, source_of
from palmscan.http import HttpClient
from palmscan.ingest import CONFIDENCE_SPECIES, IngestResult, ingest_inventory
from palmscan.mask import apply_masks, load_masks
from palmscan.model import LidarCandidate, PalmRecord, Reject, SourceVintage
from palmscan.output import (
    to_feature_collection,
    validate_palms,
    write_invalid,
    write_palms,
)
from palmscan.qa.accuracy import (
    accuracy_doc,
    accuracy_section_md,
    evaluate_site,
    fallback_height_error,
    load_evaluator,
    write_accuracy,
)
from palmscan.qa.gpkg import ConflictBuilding, vintage_grid, write_qa_gpkg
from palmscan.qa.rejects import write_rejects_csv
from palmscan.qa.summary import (
    ClassifierSummary,
    QaContext,
    SourceCounts,
    git_sha,
    write_summary,
)
from palmscan.sources.base import InventoryAdapter
from palmscan.sources.buildings import SOURCE_NOTICES, fetch_buildings
from palmscan.sources.lidar_ept import EptPointSource, PointSource

if TYPE_CHECKING:
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry

    from palmscan.classify.species import ShapeModel
    from palmscan.classify.tree_model import TrainReport, TreeModel
    from palmscan.detect.chm import ChmResult

__all__ = [
    "BUILDINGS_FILENAME",
    "PRIORS_FILENAME",
    "RUN_JSON_FILENAME",
    "RunOptions",
    "RunResult",
    "inventory_stages",
    "run",
    "species_level",
]

_log = get_logger(__name__)

BUILDINGS_FILENAME: Final = "buildings.geojson"
PRIORS_FILENAME: Final = "species_priors.yaml"
RUN_JSON_FILENAME: Final = "run.json"
SUMMARY_FILENAME: Final = "qa_summary.md"
GPKG_FILENAME: Final = "qa_map.gpkg"
REJECTS_FILENAME: Final = "qa_rejects.csv"
BUILDINGS_SCHEMA_VERSION: Final = "1.0"

PRIOR_CONFIDENCE: Final = 0.3
UNKNOWN_SPECIES: Final = "palm_unknown"
_COORD_DECIMALS: Final = 7
TREE_FILENAME: Final = "species_tree.json"
ACCURACY_FILENAME: Final = "accuracy.json"
LIDAR_SOURCE: Final = "3dep_ept"
EVAL_DIR: Final = "eval"
DEBUG_DIR: Final = "debug"
EVAL_NODATA: Final = -9999.0
EVAL_CHM_PAD_M: Final = 3.0  # CHM margin around the site so fill-heights can search past its edge
_OPTIONAL_OUTPUTS: Final = (TREE_FILENAME, ACCURACY_FILENAME)
_OUTPUTS: Final = (
    "palms.geojson",
    BUILDINGS_FILENAME,
    PRIORS_FILENAME,
    TREE_FILENAME,
    ACCURACY_FILENAME,
    SUMMARY_FILENAME,
    GPKG_FILENAME,
    REJECTS_FILENAME,
    RUN_JSON_FILENAME,
)


@dataclass(slots=True)
class RunOptions:
    out_dir: Path
    offline: bool = False
    refresh: bool = False
    no_lidar: bool = False
    only: str | None = None  # None | "inventory" | "lidar"
    eval_site: str | None = None
    generated_at: datetime | None = None  # None: SOURCE_DATE_EPOCH, then now
    debug: bool = False  # -vv: debug GeoTIFFs of every LiDAR tile under <out>/debug/
    repo_root: Path | None = None  # checkout holding tests/accuracy; None: current directory
    sites_root: Path | None = None  # ground-truth sites folder; None: <repo_root>/tests/accuracy


@dataclass(slots=True)
class RunResult:
    palms_path: Path
    counts: dict[str, Any]
    warnings: list[str]
    exit_code: int
    priors: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class InventoryStages:
    """What stages 2 to 4 produce; shared by ``run`` and ``palmscan priors``."""

    palms: list[PalmRecord]
    ingest: IngestResult
    rejects: list[Reject]
    source_counts: list[SourceCounts]
    timings: dict[str, float]
    stage_counts: dict[str, int]


class _Timings:
    """Per-stage seconds and counts, logged as one INFO line per stage."""

    def __init__(self) -> None:
        self.seconds: dict[str, float] = {}
        self.counts: dict[str, int] = {}
        self._t0 = time.perf_counter()

    def mark(self, name: str, count: int) -> None:
        now = time.perf_counter()
        self.seconds[name] = round(now - self._t0, 3)
        self.counts[name] = count
        _log.info("stage %s: %d in %.2fs", name, count, now - self._t0)
        self._t0 = now


def _reraise_cache_miss(exc: SourceError) -> None:
    """``ingest_inventory`` wraps adapter errors in ``SourceError``; keep a cache miss's code."""
    cause = exc.__cause__
    if isinstance(cause, CacheMiss):
        raise CacheMiss(str(exc)) from cause


def species_level(palms: list[PalmRecord]) -> list[PalmRecord]:
    """Palms whose species came from a species-level name; genus-only names are left out.

    A genus-only name is stored with a default species (and ``<genus>_sp`` keys have no species
    at all), so counting them would inflate that default in the computed priors.
    """
    return [
        p
        for p in palms
        if p.species is not None
        and not p.species.endswith("_sp")
        and p.species_confidence == CONFIDENCE_SPECIES
    ]


def inventory_stages(
    cfg: ScanConfig,
    cache: Cache,
    http: HttpClient,
    adapters: list[InventoryAdapter] | None = None,
) -> InventoryStages:
    """Stages 2 to 4: ingest, cross-source dedupe, ``mask_out``."""
    clock = _Timings()
    try:
        ingest = ingest_inventory(cfg, cache, http, adapters)
    except SourceError as exc:
        _reraise_cache_miss(exc)
        raise
    clock.mark("ingest_inventory", len(ingest.palms))
    palms, dedupe_rejects = dedupe_cross_source(
        ingest.palms, cfg.dedupe_radius_m, ingest.source_order
    )
    clock.mark("dedupe", len(palms))
    masks = load_masks(cfg.mask_out, Path.cwd())
    palms, mask_rejects = apply_masks(palms, masks)
    clock.mark("apply_masks", len(palms))

    rejects = [*ingest.rejects, *dedupe_rejects, *mask_rejects]
    deduped = Counter(r.source for r in dedupe_rejects)
    masked = Counter(r.source for r in mask_rejects)
    kept = Counter(source_of(p.stable_key) for p in palms)
    source_counts = [
        SourceCounts(
            source=name,
            fetched=c["fetched"],
            non_tree=c["non_tree"],
            not_palm=c["not_palm"] + c["excluded"],
            palm=c["palm"],
            deduped=deduped[name],
            masked=masked[name],
            kept=kept[name],
        )
        for name, c in ingest.counts.items()
    ]
    return InventoryStages(palms, ingest, rejects, source_counts, clock.seconds, clock.counts)


# ----------------------------------------------------------------------------- stage helpers


def _assign_species(palms: list[PalmRecord], priors: dict[str, float], warnings: list[str]) -> int:
    """Give palms with no species a prior sample (confidence 0.3). Returns how many."""
    missing = [p for p in palms if p.species is None]
    if missing and not priors:
        warnings.append(
            f"{len(missing)} palms have no species and there are no species priors; "
            f"set to {UNKNOWN_SPECIES}"
        )
    for palm in missing:
        palm.species = (
            sample_species(priors, f"species|{palm.stable_key}") if priors else UNKNOWN_SPECIES
        )
        palm.species_confidence = PRIOR_CONFIDENCE
        palm.species_source = "prior"
    return len(missing)


def _round_coords(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [_round_coords(v) for v in value]
    return round(float(value), _COORD_DECIMALS)


def _nearby_buildings(
    frame: gpd.GeoDataFrame, palms: list[PalmRecord], crs: str, radius_m: float
) -> gpd.GeoDataFrame:
    """Footprints that intersect a circle of ``radius_m`` around any palm, sorted by id."""
    if len(frame) == 0 or not palms:
        return frame.iloc[0:0]
    local = frame.to_crs(crs)
    geoms = np.array(
        [g if g.is_valid else shapely.make_valid(g) for g in local.geometry], dtype=object
    )
    xs, ys = geo.to_local([p.lon for p in palms], [p.lat for p in palms], crs)
    circles = shapely.buffer(shapely.points(np.asarray(xs), np.asarray(ys)), radius_m, quad_segs=8)
    _, bldg_idx = STRtree(geoms).query(circles, predicate="intersects")
    out = frame.iloc[np.unique(bldg_idx)]
    return out.sort_values("building_id").reset_index(drop=True)


def _buildings_doc(frame: gpd.GeoDataFrame, region: str) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for building_id, source, geom in zip(
        frame["building_id"], frame["source"], frame.geometry, strict=True
    ):
        shape = mapping(geom)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": shape["type"],
                    "coordinates": _round_coords(shape["coordinates"]),
                },
                "properties": {"building_id": str(building_id), "source": str(source)},
            }
        )
    sources = sorted({f["properties"]["source"] for f in features})
    return {
        "type": "FeatureCollection",
        "schema_version": BUILDINGS_SCHEMA_VERSION,
        "region": region,
        "notices": {s: dict(SOURCE_NOTICES[s]) for s in sources if s in SOURCE_NOTICES},
        "features": features,
    }


def _write_buildings(frame: gpd.GeoDataFrame, region: str, path: Path) -> None:
    doc = _buildings_doc(frame, region)
    report = contract.validate_buildings(doc)
    if report.errors:
        raise ContractError(
            "buildings.geojson is invalid: " + "; ".join(str(i) for i in report.errors[:5]),
            report.errors,
        )
    atomic_write_text(path, json.dumps(doc, indent=1, ensure_ascii=False) + "\n")


def _write_palms(fc: dict[str, Any], palms_path: Path, out_dir: Path) -> None:
    errors = validate_palms(fc)
    if errors:
        invalid = write_invalid(fc, out_dir)
        raise ContractError(
            f"palms.geojson failed validation ({len(errors)} errors); wrote {invalid}", errors
        )
    try:
        write_palms(fc, palms_path)
    except ContractError as exc:
        write_invalid(fc, out_dir)
        raise ContractError(
            f"{exc} (wrote {out_dir / 'palms.invalid.geojson'})", exc.issues
        ) from exc


def _lidar_requested(cfg: ScanConfig, opts: RunOptions) -> bool:
    return (
        cfg.region.sources.lidar.type != "none" and not opts.no_lidar and opts.only != "inventory"
    )


def _write_run_json(
    out_dir: Path,
    cfg: ScanConfig,
    moment: datetime,
    clock: _Timings,
    counts: dict[str, Any],
    warnings: list[str],
    exit_code: int,
    error: str | None = None,
) -> None:
    doc = {
        "palmscan_version": __version__,
        "git_sha": git_sha(),
        "region": cfg.region_name,
        "config_hash": cfg.config_hash(),
        "generated_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage_seconds": clock.seconds,
        "stage_counts": clock.counts,
        "counts": counts,
        "warnings": warnings,
        "outputs": [name for name in _OUTPUTS if (out_dir / name).is_file()],
        "exit_code": exit_code,
        "error": error,
    }
    atomic_write_text(out_dir / RUN_JSON_FILENAME, canonical_json(doc) + "\n")


# ----------------------------------------------------------------------------- LiDAR stage


@dataclass(slots=True)
class _EvalSite:
    """The labelled area (lon/lat polygon) of ``--eval-site`` and where its folder lives."""

    site: str
    root: Path
    area: BaseGeometry


class _EvalChm:
    """CHM of the eval site, mosaicked from the tiles on one grid at the CHM resolution."""

    def __init__(self, bounds: tuple[float, float, float, float], res: float, crs: pyproj.CRS):
        from palmscan.detect.chm import grid_for_bounds

        self.transform, height, width = grid_for_bounds(bounds, res)
        self.crs = crs
        self.res = res
        self.data = np.full((height, width), EVAL_NODATA, dtype=np.float32)
        self._xc = self.transform.c + (np.arange(width) + 0.5) * res
        self._yc = self.transform.f - (np.arange(height) + 0.5) * res

    def add(self, chm: ChmResult, tile_bounds: tuple[float, float, float, float]) -> None:
        """Copy the cells whose centre is inside the (unbuffered) tile from its CHM."""
        xmin, ymin, xmax, ymax = tile_bounds
        cols = np.nonzero((self._xc >= xmin) & (self._xc < xmax))[0]
        rows = np.nonzero((self._yc >= ymin) & (self._yc < ymax))[0]
        if cols.size == 0 or rows.size == 0:
            return
        t = chm.transform
        src_c = np.floor((self._xc[cols] - t.c) / chm.res).astype(np.int64)
        src_r = np.floor((t.f - self._yc[rows]) / chm.res).astype(np.int64)
        height, width = chm.chm.shape
        ok_c = (src_c >= 0) & (src_c < width)
        ok_r = (src_r >= 0) & (src_r < height)
        cols, src_c, rows, src_r = cols[ok_c], src_c[ok_c], rows[ok_r], src_r[ok_r]
        self.data[np.ix_(rows, cols)] = chm.chm[np.ix_(src_r, src_c)]

    def covered(self) -> bool:
        return bool((self.data != EVAL_NODATA).any())

    def write(self, path: Path) -> None:
        import rasterio

        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=self.data.shape[0],
            width=self.data.shape[1],
            count=1,
            dtype="float32",
            crs=self.crs,
            transform=self.transform,
            nodata=EVAL_NODATA,
            compress="deflate",
        ) as dst:
            dst.write(self.data, 1)


@dataclass(slots=True)
class _TileResult:
    candidates: list[LidarCandidate] = field(default_factory=list)
    crowns: list[tuple[str, BaseGeometry]] = field(default_factory=list)
    ground: dict[str, float] = field(default_factory=dict)  # inventory stable_key -> DTM metres
    vintages: dict[str, SourceVintage] = field(default_factory=dict)
    n_tiles: int = 0  # tiles that produced a CHM
    n_skipped: int = 0


@dataclass(slots=True)
class _LidarOutput:
    palms: list[PalmRecord]
    candidates: list[LidarCandidate]
    crowns: list[tuple[str, BaseGeometry]] | None
    rejects: list[Reject]
    classifier: ClassifierSummary
    region_medians: dict[str, float]
    vintages: list[SourceVintage]
    counts: dict[str, Any]


def _prepare_eval(opts: RunOptions, warnings: list[str]) -> _EvalSite | None:
    """Load the ``--eval-site`` labelled area up front, so a bad site fails before any work."""
    if not opts.eval_site:
        return None
    repo_root = opts.repo_root if opts.repo_root is not None else Path.cwd()
    evaluator = load_evaluator(repo_root)
    if evaluator is None:
        message = f"--eval-site {opts.eval_site}: tests.accuracy is not importable; skipped"
        _log.warning(message)
        warnings.append(message)
        return None
    root = opts.sites_root if opts.sites_root is not None else repo_root / "tests" / "accuracy"
    area = evaluator.gt.load_labeled_area(opts.eval_site, root)  # raises on a missing site
    return _EvalSite(opts.eval_site, root, area)


def _local_bounds(
    lon_lat: tuple[float, float, float, float], crs: pyproj.CRS, pad_m: float
) -> tuple[float, float, float, float]:
    lon_min, lat_min, lon_max, lat_max = lon_lat
    xs, ys = geo.to_local(
        [lon_min, lon_max, lon_min, lon_max], [lat_min, lat_min, lat_max, lat_max], crs
    )
    return (
        float(np.min(xs)) - pad_m,
        float(np.min(ys)) - pad_m,
        float(np.max(xs)) + pad_m,
        float(np.max(ys)) + pad_m,
    )


def _crown_polygons(
    chm: ChmResult, labels: np.ndarray, candidates: list[LidarCandidate]
) -> list[tuple[str, BaseGeometry]]:
    """WGS84 crown polygon of each candidate (the watershed segment of its label)."""
    import shapely
    from rasterio import features
    from shapely.geometry import shape
    from shapely.ops import unary_union

    wanted = {int(c.candidate_id.rsplit(":", 1)[1]): c.candidate_id for c in candidates}
    pieces: dict[int, list[BaseGeometry]] = {}
    for geom, value in features.shapes(
        labels.astype(np.int32), mask=labels > 0, transform=chm.transform
    ):
        label = int(value)
        if label in wanted:
            pieces.setdefault(label, []).append(shape(geom))
    to_wgs84 = pyproj.Transformer.from_crs(chm.crs, geo.WGS84, always_xy=True).transform

    def project(coords: np.ndarray) -> np.ndarray:
        lon, lat = to_wgs84(coords[:, 0], coords[:, 1])
        return np.column_stack((lon, lat))

    return [
        (wanted[label], shapely.transform(unary_union(pieces[label]), project))
        for label in sorted(pieces)
    ]


def _lidar_tiles(
    source: PointSource,
    cfg: ScanConfig,
    inventory: list[PalmRecord],
    crs: pyproj.CRS,
    opts: RunOptions,
    eval_chm: _EvalChm | None,
    warnings: list[str],
    moment: datetime,
) -> _TileResult:
    """One tile at a time: CHM, peaks, crowns, candidates. Rasters are dropped after each tile.

    Only the candidates, the crown polygons (when ``qa.write_crowns``), the DTM elevation of the
    inventory palms inside the tile and, for ``--eval-site``, the site's CHM cells are kept.
    """
    from palmscan.detect.chm import build_chm, sample_ground, write_debug_rasters
    from palmscan.detect.peaks import crown_stats, find_peaks, segment_crowns

    params = cfg.lidar
    out = _TileResult()
    inv_x = np.array([p.x for p in inventory], dtype=np.float64)
    inv_y = np.array([p.y for p in inventory], dtype=np.float64)
    fetched_at = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    for ds, tile in source.tiles():
        points = source.points(ds, tile)
        if len(points) == 0:
            message = f"LiDAR tile {tile.tile_id} of {ds.name} has no points; skipped"
            _log.warning(message)
            warnings.append(message)
            out.n_skipped += 1
            continue
        try:
            chm = build_chm(
                points,
                tile.buffered,
                crs,
                res=params.resolution_m,
                smooth_sigma_px=params.smooth_sigma_px,
                use_building_class=params.use_building_class,
            )
        except SourceError as exc:
            message = f"LiDAR tile {tile.tile_id} of {ds.name} skipped: {exc}"
            _log.warning(message)
            warnings.append(message)
            out.n_skipped += 1
            continue
        finally:
            del points
        peaks = find_peaks(chm, cfg.peaks.min_height_m, cfg.peaks.min_distance_m)
        labels = segment_crowns(chm, peaks, cfg.peaks.crown_mask_height_m)
        found = crown_stats(chm, labels, peaks, ds.name, tile.tile_id, tile_bounds=tile.bounds)
        vintage = str(ds.year) if ds.year is not None else None
        for cand in found:
            cand.vintage = vintage
        out.candidates.extend(found)
        out.vintages.setdefault(
            ds.name, SourceVintage(f"lidar:{ds.name}", vintage, "dataset_name", fetched_at)
        )
        if cfg.qa.write_crowns:
            out.crowns.extend(_crown_polygons(chm, labels, found))
        if len(inv_x):
            xmin, ymin, xmax, ymax = tile.bounds
            inside = np.nonzero(
                (inv_x >= xmin) & (inv_x < xmax) & (inv_y >= ymin) & (inv_y < ymax)
            )[0]
            if inside.size:
                ground = sample_ground(chm, inv_x[inside], inv_y[inside])
                for i, g in zip(inside, ground, strict=True):
                    if np.isfinite(g):
                        out.ground[inventory[int(i)].stable_key] = float(g)
        if eval_chm is not None:
            eval_chm.add(chm, tile.bounds)
        if opts.debug:
            write_debug_rasters(chm, opts.out_dir / DEBUG_DIR / tile.tile_id)
        out.n_tiles += 1
        _log.info("LiDAR tile %s: %d candidates", tile.tile_id, len(found))
    return out


def _load_tree(cfg: ScanConfig) -> TreeModel:
    from palmscan.classify.tree_model import load_model

    path = Path(str(cfg.classify.tree_model_path))
    try:
        return load_model(path)
    except OSError as exc:
        raise ConfigError(f"classify.tree_model_path {path} cannot be read: {exc}") from exc
    except ValueError as exc:
        raise ConfigError(f"classify.tree_model_path {path} is not a species tree: {exc}") from exc


def _classifier_summary(
    model: TreeModel | None, report: TrainReport | None, loaded: str | None
) -> ClassifierSummary:
    if report is None:
        return ClassifierSummary("lidar_tree", reason=f"loaded from {loaded}")
    return ClassifierSummary(
        chosen_model="lidar_tree" if model is not None else "shape_rules",
        cv_acc_rules=report.cv_acc_rules if report.n_samples else None,
        cv_acc_tree=report.cv_acc_tree,
        n_samples=report.n_samples,
        reason=report.reason,
        confusion=report.confusion,
    )


def _lidar_stages(
    cfg: ScanConfig,
    opts: RunOptions,
    source: PointSource,
    inventory: list[PalmRecord],
    buildings: gpd.GeoDataFrame,
    priors: dict[str, float],
    eval_site: _EvalSite | None,
    clock: _Timings,
    warnings: list[str],
    moment: datetime,
) -> _LidarOutput:
    """Tiles, palm rules, merge with the inventory, species classification."""
    from palmscan.classify.species import classify
    from palmscan.classify.tree_model import save_model, train
    from palmscan.detect.merge import merge
    from palmscan.detect.palm_rules import apply_palm_rules

    crs = pyproj.CRS.from_user_input(cfg.region.crs())
    # Inventory x/y come from the bbox's UTM zone; matching needs the CRS of the point source.
    if inventory:
        xs, ys = geo.to_local([p.lon for p in inventory], [p.lat for p in inventory], crs)
        for palm, x, y in zip(inventory, xs, ys, strict=True):
            palm.x, palm.y = float(x), float(y)

    eval_chm: _EvalChm | None = None
    if eval_site is not None:
        bounds = _local_bounds(eval_site.area.bounds, crs, EVAL_CHM_PAD_M)
        eval_chm = _EvalChm(bounds, cfg.lidar.resolution_m, crs)

    tiles = _lidar_tiles(source, cfg, inventory, crs, opts, eval_chm, warnings, moment)
    if tiles.n_tiles == 0:
        raise SourceError("LiDAR: no tile had usable points")
    clock.mark("lidar_tiles", len(tiles.candidates))
    if eval_chm is not None and eval_site is not None:
        if eval_chm.covered():
            eval_chm.write(opts.out_dir / EVAL_DIR / eval_site.site / "chm.tif")
        else:
            warnings.append(f"--eval-site {eval_site.site}: no LiDAR tile covers the site; no CHM")

    buildings_local = None
    if len(buildings):
        frame = buildings if buildings.crs is not None else buildings.set_crs(geo.WGS84)
        buildings_local = frame.to_crs(crs)
    candidates, rule_rejects = apply_palm_rules(tiles.candidates, cfg.rules, buildings_local)
    n_accepted = sum(c.accepted for c in candidates)
    clock.mark("lidar_rules", n_accepted)

    merged = merge(inventory, candidates, cfg.merge, cfg.dedupe_radius_m, cfg.peaks.min_height_m)
    palms = merged.palms
    for palm in palms:
        if palm.ground_elev_m is None and palm.stable_key in tiles.ground:
            palm.ground_elev_m = tiles.ground[palm.stable_key]
    clock.mark("merge", len(palms))

    model: TreeModel | None
    report: TrainReport | None = None
    loaded: str | None = None
    if cfg.classify.use_tree and cfg.classify.tree_model_path:
        model, loaded = _load_tree(cfg), str(cfg.classify.tree_model_path)
    else:
        model, report = train(merged.training, cfg.classify)
    if model is not None:
        save_model(model, opts.out_dir / TREE_FILENAME)
    # TreeModel.name is a ClassVar, which the ShapeModel protocol's plain attribute rejects.
    classify([p for p in palms if p.lidar is not None], priors, cast("ShapeModel | None", model))
    clock.mark("classify", sum(p.lidar is not None for p in palms))

    return _LidarOutput(
        palms=palms,
        candidates=candidates,
        crowns=tiles.crowns if cfg.qa.write_crowns else None,
        rejects=[*rule_rejects, *merged.rejects],
        classifier=_classifier_summary(model, report, loaded),
        region_medians=merged.region_medians,
        vintages=sorted(tiles.vintages.values(), key=lambda v: v.source),
        counts={
            "lidar_tiles": tiles.n_tiles,
            "lidar_tiles_skipped": tiles.n_skipped,
            "lidar_candidates": len(candidates),
            "lidar_accepted": n_accepted,
            "lidar_matched": sum(p.detected_by.endswith("+lidar") for p in palms),
            "lidar_only": sum(p.detected_by == "lidar" for p in palms),
            "species_model": "lidar_tree" if model is not None else "shape_rules",
        },
    )


def _accuracy(
    fc: dict[str, Any], eval_site: _EvalSite, opts: RunOptions, warnings: list[str]
) -> str | None:
    """Run TEST-010 through SCAN-029; write ``accuracy.json``; return the Accuracy section."""
    repo_root = opts.repo_root if opts.repo_root is not None else Path.cwd()
    profiles = evaluate_site(
        fc, eval_site.site, repo_root=repo_root, sites_root=eval_site.root, warnings=warnings
    )
    if not profiles:
        return None
    import geopandas as gpd

    props = [f["properties"] for f in fc["features"]]
    frame = gpd.GeoDataFrame(
        {
            "species": [p.get("species") for p in props],
            "height_m": [p.get("height_m") for p in props],
            "height_source": [p.get("height_source") for p in props],
        }
    )
    doc = accuracy_doc(
        eval_site.site, profiles, fallback_height_error_m=fallback_height_error(frame)
    )
    write_accuracy(doc, opts.out_dir)
    return accuracy_section_md(doc)


# --------------------------------------------------------------------------------- run


def run(
    cfg: ScanConfig,
    opts: RunOptions,
    cache: Cache,
    http: HttpClient,
    adapters: list[InventoryAdapter] | None = None,
    point_source: PointSource | None = None,
) -> RunResult:
    """Run the pipeline and write every output into ``opts.out_dir``.

    ``adapters`` replace the configured inventory adapters and ``point_source`` replaces the 3DEP
    EPT point source of the LiDAR stage (tests).
    """
    out_dir = opts.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    moment = _resolve_generated_at(opts.generated_at)
    clock = _Timings()
    warnings: list[str] = []
    counts: dict[str, Any] = {}
    try:
        result = _run(
            cfg, opts, cache, http, adapters, point_source, moment, clock, warnings, counts
        )
    except PalmfixError as exc:
        _write_run_json(out_dir, cfg, moment, clock, counts, warnings, exc.exit_code, str(exc))
        raise
    _write_run_json(out_dir, cfg, moment, clock, counts, warnings, result.exit_code)
    return result


def _run(
    cfg: ScanConfig,
    opts: RunOptions,
    cache: Cache,
    http: HttpClient,
    adapters: list[InventoryAdapter] | None,
    point_source: PointSource | None,
    moment: datetime,
    clock: _Timings,
    warnings: list[str],
    counts: dict[str, Any],
) -> RunResult:
    out_dir = opts.out_dir
    crs = geo.local_crs(cfg.bbox).to_string()
    stages: list[str] = []

    if opts.only == "lidar" and opts.no_lidar:
        raise ConfigError("--only lidar and --no-lidar cannot be combined")
    lidar_type = cfg.region.sources.lidar.type
    if opts.only == "lidar" and lidar_type == "none":
        raise ConfigError("--only lidar needs sources.lidar in the region file")
    if lidar_type not in ("none", LIDAR_SOURCE):
        raise ConfigError(f"unknown sources.lidar type {lidar_type!r}; use {LIDAR_SOURCE!r}")
    for name in _OPTIONAL_OUTPUTS:  # left over from an earlier run with other options
        (out_dir / name).unlink(missing_ok=True)
    eval_site = _prepare_eval(opts, warnings)

    # 1. buildings
    buildings, building_warnings = fetch_buildings(cfg, cache, http)
    warnings.extend(building_warnings)
    clock.mark("buildings", len(buildings))
    stages.append("buildings")

    # 2-4. inventory, dedupe, masks
    if opts.only == "lidar":
        palms: list[PalmRecord] = []
        rejects: list[Reject] = []
        ingest = IngestResult([], [], [], {}, Counter(), [])
        source_counts: list[SourceCounts] = []
    else:
        inv = inventory_stages(cfg, cache, http, adapters)
        palms, rejects, ingest, source_counts = (
            inv.palms,
            inv.rejects,
            inv.ingest,
            inv.source_counts,
        )
        clock.seconds.update(inv.timings)
        clock.counts.update(inv.stage_counts)
        warnings.extend(ingest.warnings)
        stages.extend(["ingest_inventory", "dedupe", "apply_masks"])
    # 5. priors (from the inventory only; the LiDAR classifier falls back to them)
    computed = compute_priors(species_level(palms))
    priors = merge_priors(computed, cfg.species_priors)
    if not priors:
        priors_used = "none"
    elif computed and priors == dict(computed):
        priors_used = "computed"
    else:
        priors_used = "configured"

    # 6. LiDAR: tiles, CHM, peaks, palm rules, merge with the inventory, species classification
    lidar: _LidarOutput | None = None
    region_medians: dict[str, float] = {}
    if _lidar_requested(cfg, opts):
        source = point_source if point_source is not None else EptPointSource(cfg, cache, http)
        lidar = _lidar_stages(
            cfg, opts, source, palms, buildings, dict(priors), eval_site, clock, warnings, moment
        )
        palms = lidar.palms
        rejects = [*rejects, *lidar.rejects]
        region_medians = lidar.region_medians
        counts.update(lidar.counts)
        stages.extend(["lidar_tiles", "lidar_rules", "merge", "classify"])
    sampled = _assign_species(palms, priors, warnings)
    clock.mark("priors", sampled)
    stages.append("priors")

    # 7. sizes, exclusion radius, building conflicts
    assign_sizes(palms, cfg, region_medians)
    assign_exclusion(palms, cfg.region.exclusion)
    conflicts = flag_building_conflicts(
        palms, buildings, crs, cfg.exclusion.building_overlap_min_m2
    )
    n_conflict = sum(p.building_conflict for p in palms)
    clock.mark("attributes", n_conflict)
    stages.append("attributes")

    # 8. palms.geojson
    palms_path = out_dir / "palms.geojson"
    meta = PalmsMeta(
        schema_version=contract.PALMS_SCHEMA_VERSION,
        region=cfg.region_name,
        generated_at=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        data_version=moment.strftime("%Y-%m"),
        generator_name="palmscan",
        generator_version=__version__,
        config_sha256=cfg.config_hash(),
    )
    fc = to_feature_collection(palms, cfg.region_name, id_prefix=cfg.id_prefix, meta=meta)
    _write_palms(fc, palms_path, out_dir)
    clock.mark("write_palms", len(palms))
    stages.append("write_palms")

    accuracy_md = _accuracy(fc, eval_site, opts, warnings) if eval_site is not None else None
    if accuracy_md is not None:
        clock.mark("accuracy", 1)
        stages.append("accuracy")

    # 9. buildings.geojson, priors, QA, run.json
    exclusion = cfg.region.exclusion
    near = _nearby_buildings(
        buildings, palms, crs, exclusion.radius_max_m + exclusion.clip_buffer_m
    )
    _write_buildings(near, cfg.region_name, out_dir / BUILDINGS_FILENAME)
    atomic_write_text(out_dir / PRIORS_FILENAME, priors_yaml(computed))
    if not palms:
        warnings.append("no palms found; palms.geojson is empty")
    qa = _QaInputs(stages, palms, rejects, ingest, source_counts, conflicts, lidar, accuracy_md)
    _write_qa(cfg, out_dir, moment, qa, dict(computed), priors_used, warnings)
    clock.mark("write_outputs", len(near))

    counts.update(
        palms=len(palms),
        rejects=len(rejects),
        building_conflicts=n_conflict,
        buildings_written=len(near),
        species_sampled=sampled,
        priors_used=priors_used,
        sources={s.source: s.kept for s in source_counts},
    )
    _log.info("wrote %d palms to %s", len(palms), palms_path)
    return RunResult(palms_path, counts, warnings, EXIT_OK, dict(priors))


@dataclass(slots=True)
class _QaInputs:
    stages: list[str]
    palms: list[PalmRecord]
    rejects: list[Reject]
    ingest: IngestResult
    source_counts: list[SourceCounts]
    conflicts: gpd.GeoDataFrame
    lidar: _LidarOutput | None = None
    accuracy_md: str | None = None


def _write_qa(
    cfg: ScanConfig,
    out_dir: Path,
    moment: datetime,
    qa: _QaInputs,
    computed: dict[str, float],
    priors_used: str,
    warnings: list[str],
) -> None:
    palms, rejects, ingest, conflicts, lidar = (
        qa.palms,
        qa.rejects,
        qa.ingest,
        qa.conflicts,
        qa.lidar,
    )
    grid = vintage_grid(palms, cfg.qa.vintage_grid_deg, moment.year, cfg.qa.stale_years)
    conflict_buildings = [
        ConflictBuilding(str(b), str(s), g)
        for b, s, g in zip(
            conflicts["building_id"], conflicts["source"], conflicts.geometry, strict=True
        )
    ]
    write_qa_gpkg(
        out_dir / GPKG_FILENAME,
        palms,
        rejects,
        conflict_buildings,
        grid,
        lidar.candidates if lidar else None,
        lidar.crowns if lidar else None,
        id_prefix=cfg.id_prefix,
        crs=geo.local_crs(cfg.bbox),
    )
    write_rejects_csv(rejects, out_dir / REJECTS_FILENAME)
    ctx = QaContext(
        region=cfg.region_name,
        run_time=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        palmscan_version=__version__,
        config_hash=cfg.config_hash(),
        stages=qa.stages,
        output_path=str(out_dir),
        palms=palms,
        git_sha=git_sha(),
        source_counts=qa.source_counts,
        conflict_building_count=len(conflict_buildings),
        source_vintages=[*ingest.vintages, *(lidar.vintages if lidar else [])],
        vintage_grid=grid,
        unmatched_palm_names=dict(ingest.unmatched_palm_names),
        priors_computed=computed,
        priors_configured=dict(cfg.species_priors),
        priors_used=priors_used,
        classifier=lidar.classifier if lidar else None,
        accuracy_md=qa.accuracy_md,
        warnings=warnings,
    )
    write_summary(ctx, out_dir / SUMMARY_FILENAME)
