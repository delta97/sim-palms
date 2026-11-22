---
id: TEST-005
title: Add the test-site registry schema and loader
status: todo
phase: 1
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#site-registry-format"
depends_on: [TEST-001]
requires: [none]
agent: test-engineer
estimate_h: 2
touches: [tests/sites/sites.schema.json, tests/sites/sites.yaml, tests/helpers/sites.py, tests/unit/helpers/test_sites.py, tests/fixtures/helpers/sites/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A single registry `tests/sites/sites.yaml` describes T1-T5 (bbox, purpose, region, flight, three viewpoints), with a schema and a loader that the visual, accuracy and perf tools all use.

## Context

- Spec: `plans/detailed/06-testing.md#site-registry-format` and the sites part of `#helper-api`.
- This task writes a skeleton `sites.yaml` with T1-T5 present but placeholder coordinates (`0`) and `flight: null`. TEST-100 (human, sim) fills in real values.
- Skeleton must still validate: allow placeholder values, but add `status: placeholder | defined` per site so tools can refuse to run against a placeholder site.

## Steps

1. `tests/sites/sites.schema.json` (JSON Schema draft 2020-12): top-level `version: 1`, `sites` map keyed by `^T[0-9]+$`. Per site: `name`, `status` (placeholder|defined), `purpose` enum (happy_path, lidar_only, building_clip, false_positive, no_harm), `description`, `region` (string), `bbox` (4 numbers), `photogrammetry`, `inventory_coverage`, `ground_truth` (bools), `flight` (string or null), `time_local` (`HH:MM`), `weather`, `viewpoints` (exactly 3 items; ids VP1, VP2, VP3; kinds street, oblique, approach; numeric lat, lon, alt_m_agl, heading_deg, pitch_deg; `preset` string or null).
2. `tests/helpers/sites.py`: dataclasses `Viewpoint`, `Site` (add `status`), `SITES_FILE`, `load_sites(path)`, `get_site(site_id, path)`. Extra checks beyond schema for `status: defined`: bbox ordered (`lon_min < lon_max`, `lat_min < lat_max`), each side 100 m to 2 km, viewpoints inside the bbox expanded by 1 km, VP1 alt 1-5 m, VP2 100-200 m, VP3 400-700 m. Raise `ValueError` with site id and rule.
3. `tests/sites/sites.yaml`: skeleton with T1-T5, purposes and descriptions from the plan's site table, `status: placeholder`.
4. Fixtures `tests/fixtures/helpers/sites/valid.yaml` (one defined site, real-looking San Diego coordinates) and `bad_bbox.yaml`, `two_viewpoints.yaml`.
5. `tests/unit/helpers/test_sites.py`: repo `sites.yaml` loads; valid fixture loads with correct types; bad fixtures raise with a clear message; `get_site("T9")` raises `KeyError` listing known ids.

## Acceptance criteria

- [ ] `load_sites()` loads the committed skeleton.
- [ ] Defined sites are range-checked; placeholder sites are accepted but flagged by `status`.
- [ ] Self-tests pass.

## Verification

```bash
pytest tests/unit/helpers/test_sites.py -q
python -c "from tests.helpers.sites import load_sites; print(sorted(load_sites()))"   # ['T1', 'T2', 'T3', 'T4', 'T5']
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
