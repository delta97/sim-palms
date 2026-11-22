---
id: SCAN-001
title: "Create palmscan package core: config, cache, HTTP, models, CLI skeleton"
status: todo
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w1-package-core"
depends_on: [ARCH-001, ARCH-003]
requires: [none]
agent: python-architect
estimate_h: 3
touches: [pyproject.toml, palmscan/__init__.py, palmscan/config.py, palmscan/cache.py, palmscan/http.py, palmscan/geo.py, palmscan/model.py, palmscan/cli.py, palmscan/sources/__init__.py, palmscan/detect/__init__.py, palmscan/classify/__init__.py, palmscan/qa/__init__.py, tests/unit/palmscan/test_scan_config.py, tests/unit/palmscan/test_scan_cache.py, tests/unit/palmscan/test_scan_http.py, tests/unit/palmscan/test_scan_geo.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The `palmscan` package exists with its typed config (every detection threshold as a default), the download cache under `data/`, an injectable HTTP client, local-CRS helpers, all internal dataclasses and an argparse CLI skeleton. Every other SCAN task builds on these, and defining all models now lets Phase 4 code start in parallel.

## Context

- Spec: plan_ref section W1, plus "Inputs: region config keys", "Internal data model" and "CLI" in the same file.
- ARCH-001 provides `pyproject.toml`, the `palmcore` package and test tooling; ARCH-003 provides the region YAML loader. Read both before starting and reuse their conventions (CLI library, logging, palmcore geo helpers). If `palmcore` already has local-CRS helpers, `palmscan/geo.py` wraps them.
- This is the only SCAN task allowed to edit `pyproject.toml`: add the palmscan dependencies and the `lidar` extra listed in W1 if ARCH-001 left them out, and the `palmscan = "palmscan.cli:main"` script entry.
- Test file names use the `test_scan_` prefix to avoid clashes with other packages' tests. `tests/conftest.py` belongs to TEST; do not edit it.

## Steps

1. Read `plans/detailed/02-detection-pipeline.md` sections W1, Inputs, Internal data model, CLI.
2. `pyproject.toml`: add missing deps (`geopandas`, `shapely>=2`, `pyproj`, `pyogrio`, `numpy`, `scipy`, `requests`, `pyyaml`), extra `lidar = [pdal, rasterio, scikit-image, scikit-learn]`, and the `palmscan` console script.
3. `palmscan/__init__.py` with `__version__ = "0.1.0"`.
4. `palmscan/model.py`: `TreeRecord`, `LidarCandidate`, `PalmRecord`, `Reject`, `SourceVintage` exactly as in the plan.
5. `palmscan/config.py`: frozen dataclasses for every block (`ScanConfig`, `InventorySourceCfg`, `MaskArea`, `PalmFilterParams`, `InventoryParams`, `ExclusionParams`, `LidarParams`, `PeakParams`, `RuleParams`, `MergeParams`, `ClassifyParams`, `QaParams`) with the plan's defaults; `ConfigError`; `scan_config_from_mapping(raw)`; `load_scan_config(region, regions_dir)` via the ARCH-003 loader; unknown keys in `palmscan:` raise `ConfigError`; bbox checks incl. the 1.0 deg guard and `allow_large_bbox`; priors normalized; `id_prefix` default from region initials; `config_hash()`.
6. `palmscan/cache.py`: `Cache`, `CacheMiss`, layout `data/<namespace>/<key[:2]>/<key><suffix>`, atomic write via `.tmp` + `os.replace`, `.meta.json` sidecar, `offline` and `refresh` flags.
7. `palmscan/http.py`: `HttpClient` (`get_json`, `post_text`, `download`), retries on connection errors and 429/5xx with exponential backoff and `Retry-After`, `HttpError`, generic User-Agent `palmscan/<version>`.
8. `palmscan/geo.py`: `local_crs(bbox)` (UTM zone of bbox centre), `to_local`, `to_wgs84` on numpy arrays.
9. `palmscan/cli.py`: `main(argv=None) -> int` with subcommands `run`, `priors`, `eval` and all flags from the CLI section; handlers print "not implemented" and return 1 for now.
10. Create empty `__init__.py` in `palmscan/sources`, `palmscan/detect`, `palmscan/classify`, `palmscan/qa`.
11. Tests: config defaults and overrides, typo key rejected, bad bbox rejected, prefix derivation, hash stable; cache hit/miss/offline/refresh/atomic write (use `tmp_path`); HTTP retry logic with a monkeypatched `requests.Session.request` (no sockets); `local_crs` returns EPSG:32611 for a San Diego bbox and round-trips a point within 1 mm.

## Acceptance criteria

- [ ] `python -c "import palmscan, palmscan.config, palmscan.cache, palmscan.http, palmscan.model, palmscan.geo"` succeeds.
- [ ] `palmscan --help` lists `run`, `priors`, `eval`.
- [ ] A region mapping with only `region` and `bbox` yields a `ScanConfig` with every plan default.
- [ ] `palmscan: {rules: {heigth_min_m: 5}}` raises `ConfigError` naming `heigth_min_m`.
- [ ] Cache in offline mode raises `CacheMiss` for a missing entry; no test opens a network socket.
- [ ] All new tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_config.py tests/unit/palmscan/test_scan_cache.py tests/unit/palmscan/test_scan_http.py tests/unit/palmscan/test_scan_geo.py -q
palmscan --help
python -c "from palmscan.config import scan_config_from_mapping as f; c=f({'region':'san-diego-coastal','bbox':[-117.28,32.70,-117.15,32.82]}); print(c.id_prefix, c.rules.height_min_m)"   # expect: sdc 8.0
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
