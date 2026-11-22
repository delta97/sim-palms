"""Adapter registry: config source ``type`` -> adapter class, in config (priority) order."""

from __future__ import annotations

from collections.abc import Callable

from palmcore.errors import ConfigError
from palmscan.cache import Cache
from palmscan.config import InventorySourceCfg, ScanConfig
from palmscan.http import HttpClient
from palmscan.sources.arcgis_rest import ArcGisRestAdapter
from palmscan.sources.base import InventoryAdapter
from palmscan.sources.geojson_file import GeoJsonFileAdapter
from palmscan.sources.osm_overpass import OsmTreesAdapter
from palmscan.sources.overpass import OverpassClient

__all__ = ["ADAPTERS", "OSM_SOURCE_NAME", "build_inventory_adapters", "build_osm_adapter"]

# The ``type`` names here must match the inventory ``type`` values palmcore.config accepts.
ADAPTERS: dict[str, Callable[[InventorySourceCfg], InventoryAdapter]] = {
    "arcgis_rest": ArcGisRestAdapter,
    "geojson_file": GeoJsonFileAdapter,
}

OSM_SOURCE_NAME = "osm"

# Buildings are not an inventory source: SCAN-006 exposes ``fetch_buildings(cfg, cache, http)``
# in ``palmscan/sources/buildings.py`` and the pipeline (SCAN-013) calls it directly, so it is
# deliberately NOT registered in ``ADAPTERS``. Integrator hook: if that adapter should be
# listed here after SCAN-006 merges, add it as a separate ``BUILDINGS_ADAPTERS`` mapping, not
# to ``ADAPTERS`` (its ``fetch`` returns a GeoDataFrame, not ``FetchResult``).


def build_inventory_adapters(cfg: ScanConfig) -> list[InventoryAdapter]:
    """One adapter per ``sources.inventory[]`` entry, in config order (= priority order)."""
    adapters: list[InventoryAdapter] = []
    for source in cfg.region.sources.inventory:
        factory = ADAPTERS.get(source.type)
        if factory is None:
            known = ", ".join(sorted(ADAPTERS))
            raise ConfigError(
                f"sources.inventory: source {source.name!r} has unknown type {source.type!r} "
                f"(known: {known})"
            )
        adapters.append(factory(source))
    return adapters


def build_osm_adapter(cfg: ScanConfig, cache: Cache, http: HttpClient) -> OsmTreesAdapter:
    """The OSM tree adapter, using the region's ``overpass_url``."""
    client = OverpassClient(http, cache, cfg.region.sources.overpass_url)
    return OsmTreesAdapter(client, OSM_SOURCE_NAME)
