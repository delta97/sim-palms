---
id: SCAN-001
title: "Create palmscan package core: config, cache, HTTP, models, CLI skeleton"
status: done
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w1-package-core"
depends_on: [ARCH-001, ARCH-003, ARCH-004, ARCH-009]
requires: [none]
agent: python-architect
estimate_h: 3
touches: [pyproject.toml, palmscan/__init__.py, palmscan/config.py, palmscan/cache.py, palmscan/http.py, palmscan/geo.py, palmscan/model.py, palmscan/cli.py, palmscan/sources/__init__.py, palmscan/detect/__init__.py, palmscan/classify/__init__.py, palmscan/qa/__init__.py, tests/unit/palmscan/test_scan_config.py, tests/unit/palmscan/test_scan_cache.py, tests/unit/palmscan/test_scan_http.py, tests/unit/palmscan/test_scan_geo.py, tests/unit/palmscan/test_scan_cli.py]
owner: claude-agent
branch: task/scan-001-create-palmscan-package-core-config-cach
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-001"
updated: 2026-11-22
---

## Goal

The `palmscan` package exists with its typed config (every detection threshold as a default), the download cache under `data/`, an injectable HTTP client, local-CRS helpers, all internal dataclasses and an argparse CLI skeleton. Every other SCAN task builds on these, and defining all models now lets Phase 4 code start in parallel.

## Context

- Spec: plan_ref section W1, plus "Inputs: region config keys", "Internal data model" and "CLI" in the same file.
- ARCH-001 provides `pyproject.toml`, the `palmcore` package and test tooling; ARCH-003 provides the region YAML loader (`palmcore.config.load_region` -> `RegionConfig`); ARCH-004 provides `palmcore.cache` and `palmcore.log`; ARCH-005 provides `palmcore.geo`. Reuse them: `palmscan/geo.py` wraps `palmcore.geo` (`local_crs_for`, `to_local`, `to_wgs84`), `palmscan/cache.py` builds `Cache` on `palmcore.cache` (layout, `cache_key`, atomic writes, meta sidecar) and adds only `get_or_fetch`, offline and refresh. `CacheMiss` and `ConfigError` are imported from `palmcore.errors`, not redefined.
- Region-level keys are read from `RegionConfig`, not from the `palmscan:` block: `id_prefix` (top level, ARCH-003 default from region initials) and `exclusion.margin_m` / `radius_min_m` / `radius_max_m` (ARCH-003 defaults 1.5 / 1.0 / 8.0). `palmscan.exclusion` keeps only `building_overlap_min_m2`. Mask entries come from `RegionConfig.mask_out` (`palmcore.config.MaskArea`).
- `pyproject.toml`: ARCH-001 already declares every palmscan dependency, the `scan`/`lidar`/`pdal` extras and the `palmscan` script; ARCH-009 then adds `palmfix`. This task depends on ARCH-009 and edits `pyproject.toml` only if something is still missing (log what). `pdal` stays its own extra (ARCH Q4); `lidar` = rasterio, scikit-image, scikit-learn. FX-002 edits `pyproject.toml` after this task.
- Test file names use the `test_scan_` prefix to avoid clashes with other packages' tests. `tests/conftest.py` belongs to TEST; do not edit it.

## Steps

1. Read `plans/detailed/02-detection-pipeline.md` sections W1, Inputs, Internal data model, CLI.
2. `pyproject.toml`: check that ARCH-001/009 cover `geopandas`, `shapely>=2`, `pyproj`, `pyogrio`, `numpy`, `scipy`, `requests`, `pyyaml`, the `lidar` extra (rasterio, scikit-image, scikit-learn), the separate `pdal` extra and the `palmscan` script. Add only what is missing; otherwise leave the file untouched and say so in the Log.
3. `palmscan/__init__.py` with `__version__ = "0.1.0"`.
4. `palmscan/model.py`: `TreeRecord`, `LidarCandidate`, `PalmRecord`, `Reject`, `SourceVintage` exactly as in the plan.
5. `palmscan/config.py`: frozen dataclasses for every `palmscan:` block (`ScanConfig`, `PalmFilterParams`, `InventoryParams`, `ExclusionParams` with only `building_overlap_min_m2`, `LidarParams`, `PeakParams`, `RuleParams`, `MergeParams`, `ClassifyParams`, `QaParams`) with the plan's defaults; `ScanConfig.region` holds the `RegionConfig` (inventory sources, masks, `id_prefix`, `exclusion`, priors, bbox come from it); `scan_config_from_mapping(raw)` (via `palmcore.config.load_region_dict`); `load_scan_config(region, regions_dir)` via `palmcore.config.load_region`; unknown keys in `palmscan:` raise `palmcore.errors.ConfigError` (so `palmscan: {id_prefix: ...}` is rejected with a hint to use the top-level key); the 1.0 deg bbox guard and `allow_large_bbox`; `config_hash()`.
6. `palmscan/cache.py`: `Cache` on top of `palmcore.cache` (layout `data/<namespace>/<key[:2]>/<key><suffix>`, atomic write and `.meta.json` sidecar come from palmcore; do not reimplement them), adding `get_or_fetch`, `offline` (raises `palmcore.errors.CacheMiss`) and `refresh`.
7. `palmscan/http.py`: `HttpClient` (`get_json`, `post_text`, `download`), retries on connection errors and 429/5xx with exponential backoff and `Retry-After`, `HttpError`, generic User-Agent `palmscan/<version>`.
8. `palmscan/geo.py`: thin wrappers over `palmcore.geo`: `local_crs(bbox)` (UTM zone of bbox centre), `to_local`, `to_wgs84` on numpy arrays.
9. `palmscan/cli.py`: `main(argv=None) -> int` with subcommands `run`, `priors`, `eval` and all flags from the CLI section; handlers print "not implemented" and return 1 for now.
10. Create empty `__init__.py` in `palmscan/sources`, `palmscan/detect`, `palmscan/classify`, `palmscan/qa`.
11. Tests: config defaults and overrides, typo key rejected, `palmscan: {id_prefix: x}` and `palmscan: {exclusion: {radius_min_m: 1}}` rejected, large bbox rejected, prefix and clamps read from `RegionConfig`, hash stable; cache hit/miss/offline/refresh/atomic write (use `tmp_path`); HTTP retry logic with a monkeypatched `requests.Session.request` (no sockets); `local_crs` returns EPSG:32611 for a San Diego bbox and round-trips a point within 1 mm.

## Acceptance criteria

- [x] `python -c "import palmscan, palmscan.config, palmscan.cache, palmscan.http, palmscan.model, palmscan.geo"` succeeds.
- [x] `palmscan --help` lists `run`, `priors`, `eval`.
- [x] A region mapping with only `region` and `bbox` yields a `ScanConfig` with every plan default.
- [x] `palmscan: {rules: {heigth_min_m: 5}}` raises `ConfigError` naming `heigth_min_m`.
- [x] Cache in offline mode raises `CacheMiss` for a missing entry; no test opens a network socket.
- [x] All new tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_config.py tests/unit/palmscan/test_scan_cache.py tests/unit/palmscan/test_scan_http.py tests/unit/palmscan/test_scan_geo.py -q
palmscan --help
python -c "from palmscan.config import scan_config_from_mapping as f; c=f({'region':'san-diego-coastal','bbox':[-117.28,32.70,-117.15,32.82]}); print(c.id_prefix, c.rules.height_min_m)"   # expect: sdc 8.0
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Depends on ARCH-009 (pyproject order) and ARCH-004 (cache helpers). Cache now delegates layout/atomic write/meta to palmcore.cache, errors come from palmcore.errors, geo wraps palmcore.geo; id_prefix and exclusion clamps read from RegionConfig (ARCH-003), removed from the palmscan: block; pdal stays a separate extra per ARCH; script entry already declared by ARCH-001. Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-001-create-palmscan-package-core-config-cach worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-001
- 2026-11-22 [claude-agent] Implemented palmscan core (config, cache, http, geo, model, cli, subpackages) in 5bf7591. pyproject.toml untouched: ARCH-001/009 already declare geopandas, shapely, pyproj, pyogrio, numpy, scipy, requests, pyyaml, lidar and pdal extras, palmscan script. Verification: pytest 698 passed 1 skipped (56 palmscan); ruff check/format clean; mypy clean (41 files); import check OK; palmscan --help lists run/priors/eval; sdc 8.0 printed; offline Cache raises CacheMiss; HTTP tests monkeypatch requests.Session.request (no sockets). Acceptance ticked.
- 2026-11-22 [claude-agent] Spec notes: (1) added tests/unit/palmscan/test_scan_cli.py to touches. (2) scan_config_from_mapping defaults config_version to 1 because palmcore.load_region_dict requires it and the Verification one-liner passes only region and bbox. (3) Plan sketch defines CacheMiss(Exception) in palmscan/cache.py; it is re-exported from palmcore.errors (subclass of SourceError, exit 5) per the reconcile note. (4) Cache.get_or_fetch reads the fetched file back into memory to hand to palmcore.write_cache; fine for JSON, revisit in the LiDAR task if tiles are large. (5) HttpClient retries HTTP 500 too, per plan.
- 2026-11-22 [claude-agent] Status in_progress -> review.
- 2026-11-22 [integrator] Status review -> done.
