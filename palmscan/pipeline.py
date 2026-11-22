"""The palmscan run pipeline (plan W11): inventory ingest to palms.geojson and the QA files.

Phase 1 stages, in order: buildings, inventory ingest, cross-source dedupe, ``mask_out``,
(Phase 4: LiDAR), species priors, sizes / exclusion radius / building conflicts, palms.geojson,
then ``buildings.geojson``, ``species_priors.yaml``, the QA files and ``run.json``.

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
from typing import TYPE_CHECKING, Any, Final

import numpy as np
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
from palmscan.model import PalmRecord, Reject
from palmscan.output import (
    to_feature_collection,
    validate_palms,
    write_invalid,
    write_palms,
)
from palmscan.qa.gpkg import ConflictBuilding, vintage_grid, write_qa_gpkg
from palmscan.qa.rejects import write_rejects_csv
from palmscan.qa.summary import QaContext, SourceCounts, git_sha, write_summary
from palmscan.sources.base import InventoryAdapter
from palmscan.sources.buildings import SOURCE_NOTICES, fetch_buildings

if TYPE_CHECKING:
    import geopandas as gpd

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
_LIDAR_WARNING: Final = "LiDAR stage not implemented yet; inventory only"
_EVAL_WARNING: Final = "--eval-site needs the Phase 4 accuracy evaluator; ignored"
_OUTPUTS: Final = (
    "palms.geojson",
    BUILDINGS_FILENAME,
    PRIORS_FILENAME,
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


# --------------------------------------------------------------------------------- run


def run(
    cfg: ScanConfig,
    opts: RunOptions,
    cache: Cache,
    http: HttpClient,
    adapters: list[InventoryAdapter] | None = None,
    point_source: Any = None,
) -> RunResult:
    """Run stages 1 to 9 and write every Phase 1 output into ``opts.out_dir``.

    ``adapters`` replace the configured inventory adapters (tests). ``point_source`` is the hook
    for the Phase 4 LiDAR stage (SCAN-028) and is unused until then.
    """
    out_dir = opts.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    moment = _resolve_generated_at(opts.generated_at)
    clock = _Timings()
    warnings: list[str] = []
    counts: dict[str, Any] = {}
    try:
        result = _run(cfg, opts, cache, http, adapters, moment, clock, warnings, counts)
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
    if _lidar_requested(cfg, opts):
        _log.warning(_LIDAR_WARNING)
        warnings.append(_LIDAR_WARNING)
    if opts.eval_site:
        warnings.append(_EVAL_WARNING)

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
    # 5. LiDAR (Phase 4, SCAN-028): tiles, CHM, peaks, rules, merge, classify. Uses point_source.

    # 6. priors
    computed = compute_priors(species_level(palms))
    priors = merge_priors(computed, cfg.species_priors)
    if not priors:
        priors_used = "none"
    elif computed and priors == dict(computed):
        priors_used = "computed"
    else:
        priors_used = "configured"
    sampled = _assign_species(palms, priors, warnings)
    clock.mark("priors", sampled)
    stages.append("priors")

    # 7. sizes, exclusion radius, building conflicts
    assign_sizes(palms, cfg)
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

    # 9. buildings.geojson, priors, QA, run.json
    exclusion = cfg.region.exclusion
    near = _nearby_buildings(
        buildings, palms, crs, exclusion.radius_max_m + exclusion.clip_buffer_m
    )
    _write_buildings(near, cfg.region_name, out_dir / BUILDINGS_FILENAME)
    atomic_write_text(out_dir / PRIORS_FILENAME, priors_yaml(computed))
    if not palms:
        warnings.append("no palms found; palms.geojson is empty")
    qa = _QaInputs(stages, palms, rejects, ingest, source_counts, conflicts)
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


def _write_qa(
    cfg: ScanConfig,
    out_dir: Path,
    moment: datetime,
    qa: _QaInputs,
    computed: dict[str, float],
    priors_used: str,
    warnings: list[str],
) -> None:
    palms, rejects, ingest, conflicts = qa.palms, qa.rejects, qa.ingest, qa.conflicts
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
        source_vintages=ingest.vintages,
        vintage_grid=grid,
        unmatched_palm_names=dict(ingest.unmatched_palm_names),
        priors_computed=computed,
        priors_configured=dict(cfg.species_priors),
        priors_used=priors_used,
        warnings=warnings,
    )
    write_summary(ctx, out_dir / SUMMARY_FILENAME)
