"""Inventory ingest stage: adapters -> normalised, filtered :class:`PalmRecord` values.

Per record: non-tree rows (stumps, vacant sites, removed trees) become rejects; species are
normalised and run through the palm filter; palms get a stable key ``<source>:<source_id>``,
local metric coordinates, a species confidence and a data vintage. Inventory sources run in
config order (the priority order for dedupe); OSM trees run last when ``sources.osm_trees``.
An inventory failure raises :class:`palmcore.errors.SourceError`; an OSM failure is a warning.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from palmcore import cache as _pc
from palmcore.errors import ConfigError, SourceError
from palmcore.log import get_logger
from palmscan.cache import Cache
from palmscan.config import ScanConfig
from palmscan.filters import non_tree_reason, palm_filter
from palmscan.geo import local_crs, to_local
from palmscan.http import HttpClient
from palmscan.model import PalmRecord, Reject, SourceVintage, TreeRecord
from palmscan.sources.base import FetchResult, InventoryAdapter, parse_date
from palmscan.sources.registry import OSM_SOURCE_NAME, build_inventory_adapters, build_osm_adapter
from palmscan.species_names import GENERIC_KEY, clean_name, genus_set_members, normalize_species

__all__ = ["CONFIDENCE_GENUS", "CONFIDENCE_SPECIES", "IngestResult", "ingest_inventory"]

_log = get_logger(__name__)

CONFIDENCE_SPECIES = 0.95
CONFIDENCE_GENUS = 0.8

_COUNT_KEYS = ("fetched", "non_tree", "not_palm", "excluded", "palm")


@dataclass(slots=True)
class IngestResult:
    palms: list[PalmRecord]
    rejects: list[Reject]
    vintages: list[SourceVintage]
    # per source: fetched, non_tree, not_palm, excluded (excluded species or genus outside the
    # configured set), palm
    counts: dict[str, dict[str, int]]
    unmatched_palm_names: Counter[str]  # cleaned names containing "palm" that did not normalize
    warnings: list[str]
    source_order: list[str] = field(default_factory=list)  # dedupe priority, highest first


class _FreshnessCache(Cache):
    """A :class:`Cache` that enforces a source's ``cache_max_age_days``.

    A cached entry older than the limit is fetched again (like ``refresh``); offline it is used
    anyway and counted in :attr:`stale_offline`. Entries without a readable sidecar count as
    stale. Entries are checked one by one, so a run can mix refreshed and still-fresh files.
    """

    def __init__(self, base: Cache, max_age_days: float) -> None:
        super().__init__(base.root, base.offline, base.refresh)
        self.max_age_days = max_age_days
        self.refreshed = 0
        self.stale_offline = 0

    def _is_fresh(self, path: Path) -> bool:
        try:
            return _pc.is_fresh(path, self.max_age_days)
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def get_or_fetch(
        self,
        namespace: str,
        key: str,
        fetch: Callable[[Path], None],
        suffix: str = "",
        meta: Mapping[str, Any] | None = None,
    ) -> Path:
        path = self.path_for(namespace, key, suffix)
        if not self.refresh and self.has(namespace, key, suffix) and not self._is_fresh(path):
            if self.offline:
                self.stale_offline += 1
            else:
                self.refreshed += 1
                return Cache(self.root, False, True).get_or_fetch(
                    namespace, key, fetch, suffix, meta
                )
        return super().get_or_fetch(namespace, key, fetch, suffix, meta)


def _confidence(level: str) -> float | None:
    if level == "species":
        return CONFIDENCE_SPECIES
    if level == "genus":
        return CONFIDENCE_GENUS
    return None


def _check_genus_sets(cfg: ScanConfig) -> None:
    for name in cfg.palm_filter.genus_sets:
        try:
            genus_set_members(name)
        except ValueError as exc:
            raise ConfigError(f"palmscan.palm_filter.genus_sets: {exc}") from exc


def _unmatched_name(rec: TreeRecord) -> str | None:
    for raw in (rec.species_raw, rec.common_name_raw):
        cleaned = clean_name(raw)
        if "palm" in cleaned:
            return cleaned
    return None


def _data_vintage(rec: TreeRecord, vintage: SourceVintage, is_osm: bool) -> dict[str, str]:
    if is_osm:
        return {"osm": vintage.vintage} if vintage.vintage else {}
    when = parse_date(rec.date_raw)
    if when is not None:
        return {"inventory": f"{when.year:04d}"}
    return {"inventory": vintage.vintage[:4]} if vintage.vintage else {}


def _reject(out: IngestResult, name: str, rec: TreeRecord, reason: str) -> None:
    out.rejects.append(
        Reject(
            stage="inventory",
            source=name,
            source_id=rec.source_id,
            lon=rec.lon,
            lat=rec.lat,
            reason=reason,
            all_reasons=[reason],
            species_raw=rec.species_raw,
        )
    )


def _ingest_source(
    cfg: ScanConfig, result: FetchResult, name: str, is_osm: bool, out: IngestResult
) -> None:
    counts = out.counts.setdefault(name, dict.fromkeys(_COUNT_KEYS, 0))
    counts["fetched"] += len(result.records)
    origin = "osm" if is_osm else "inventory"
    palms: list[PalmRecord] = []
    for rec in result.records:
        stable_key = f"{name}:{rec.source_id}"
        reason = non_tree_reason(rec.species_raw, rec.status_raw)
        if reason is not None:
            counts["non_tree"] += 1
            _reject(out, name, rec, reason)
            continue
        ns = normalize_species(rec.species_raw, rec.common_name_raw)
        why = palm_filter(ns, cfg.palm_filter.genus_sets, cfg.palm_filter.exclude_species)
        if why == "not_palm":
            counts["not_palm"] += 1
            if cfg.qa.list_non_palms:
                _reject(out, name, rec, why)
            unmatched = _unmatched_name(rec) if ns.key is None else None
            if unmatched is not None:
                out.unmatched_palm_names[unmatched] += 1
            continue
        if why is not None:
            counts["excluded"] += 1
            _reject(out, name, rec, why)
            continue
        counts["palm"] += 1
        species = None if ns.key in (None, GENERIC_KEY) else ns.key
        palms.append(
            PalmRecord(
                stable_key=stable_key,
                lon=rec.lon,
                lat=rec.lat,
                x=0.0,
                y=0.0,
                species=species,
                species_confidence=_confidence(ns.level) if species else None,
                species_source=origin if species else None,
                detected_by=origin,
                source_ids=[stable_key],
                data_vintage=_data_vintage(rec, result.vintage, is_osm),
                species_raw=rec.species_raw,
                height_raw=rec.height_raw,
            )
        )
    if palms:
        xs, ys = to_local(
            np.array([p.lon for p in palms]),
            np.array([p.lat for p in palms]),
            local_crs(cfg.bbox),
        )
        for palm, x, y in zip(palms, xs, ys, strict=True):
            palm.x, palm.y = float(x), float(y)
        out.palms.extend(palms)


def _add_warnings(out: IngestResult, name: str, messages: Sequence[str]) -> None:
    for message in messages:
        out.warnings.append(message if message.startswith(f"{name}:") else f"{name}: {message}")


def _freshness_warnings(out: IngestResult, name: str, cache: Cache) -> None:
    if not isinstance(cache, _FreshnessCache):
        return
    if cache.refreshed:
        _log.info("%s: re-fetched %d cache entries older than the age limit", name, cache.refreshed)
    if cache.stale_offline:
        out.warnings.append(
            f"{name}: offline, used {cache.stale_offline} cached file(s) older than "
            f"cache_max_age_days={cache.max_age_days:g}"
        )


def ingest_inventory(
    cfg: ScanConfig,
    cache: Cache,
    http: HttpClient,
    adapters: Sequence[InventoryAdapter] | None = None,
    osm_adapter: InventoryAdapter | None = None,
) -> IngestResult:
    """Fetch every inventory source (config order), then OSM trees when enabled.

    ``adapters`` / ``osm_adapter`` replace the configured adapters (tests, offline runs). Each
    source's ``cache_max_age_days`` is enforced here: its adapter gets a cache view that
    refetches entries older than the limit (offline, stale entries are used and warned about).
    Raises :class:`SourceError` when an inventory source fails; an OSM failure is a warning.
    """
    _check_genus_sets(cfg)
    max_age = {s.name: s.cache_max_age_days for s in cfg.region.sources.inventory}
    chosen = list(adapters) if adapters is not None else build_inventory_adapters(cfg)
    names = [a.name for a in chosen]
    if len(set(names)) != len(names):
        raise ConfigError(f"inventory adapters have duplicate names: {sorted(names)}")
    if OSM_SOURCE_NAME in names and cfg.region.sources.osm_trees:
        raise ConfigError(f"an inventory source cannot be named {OSM_SOURCE_NAME!r}: reserved")

    out = IngestResult([], [], [], {}, Counter(), [], list(names))
    for adapter in chosen:
        limit = max_age.get(adapter.name)
        view: Cache = _FreshnessCache(cache, limit) if limit is not None else cache
        try:
            fetched = adapter.fetch(cfg.bbox, view, http)
        except SourceError as exc:
            raise SourceError(f"inventory source {adapter.name!r} failed: {exc}") from exc
        _log.info("%s: %d records", adapter.name, len(fetched.records))
        out.vintages.append(fetched.vintage)
        _add_warnings(out, adapter.name, fetched.warnings)
        _freshness_warnings(out, adapter.name, view)
        _ingest_source(cfg, fetched, adapter.name, False, out)

    if cfg.region.sources.osm_trees:
        osm = osm_adapter if osm_adapter is not None else build_osm_adapter(cfg, cache, http)
        try:
            fetched = osm.fetch(cfg.bbox, cache, http)
        except SourceError as exc:
            out.warnings.append(f"{osm.name}: tree fetch failed, continuing without OSM: {exc}")
        else:
            out.source_order.append(osm.name)
            out.vintages.append(fetched.vintage)
            _add_warnings(out, osm.name, fetched.warnings)
            _ingest_source(cfg, fetched, osm.name, True, out)
    return out
