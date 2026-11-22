---
id: TEST-100
title: "Define test sites T1-T5 (bbox, purpose, region, saved flights, three viewpoints each)"
status: todo
phase: 1
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#site-registry-format"
depends_on: [TEST-005, TEST-006, DEC-004]
requires: [human, windows-sim]
agent: test-engineer
estimate_h: 5
touches: [tests/sites/sites.yaml, tests/sites/T1/, tests/sites/T2/, tests/sites/T3/, tests/sites/T4/, tests/sites/T5/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`tests/sites/sites.yaml` holds five real, defined test sites, each with a saved flight (or position preset) and three reproducible viewpoints. Every visual, accuracy and perf test refers to these sites.

## Context

- Spec: `plans/detailed/06-testing.md#site-registry-format` (site purposes T1-T5) and the method chosen in `docs/findings/TEST-006.md`.
- T1 is normally the DEC-004 test block. Read DEC-004's decision.
- Each site's `region` must name a region config (`regions/<region>.yaml`, REGION area) whose bbox contains the site. If the region file doesn't exist yet, use the planned name (`san-diego-coastal` or `la-westside`) and note it in the Log.
- T5 must be outside photogrammetry coverage but inside a region bbox, so the package is active there.
- Use aerial imagery (QGIS or a web map) to pick bboxes, and the sim to confirm blobs (T1-T4) or no photogrammetry (T5).

## Steps

1. For each of T1-T5, pick a location that fits the purpose. Write `name`, `description`, `region`, `bbox` (200 m to 1 km a side), `photogrammetry`, `inventory_coverage`, `ground_truth` (true for T1, T2, T4).
   - T1: palm-lined street, inventory coverage, obvious blobs.
   - T2: beach or boardwalk palms, no inventory.
   - T3: palms within 3 m of building walls.
   - T4: Italian cypress, eucalyptus, light poles; few palms.
   - T5: outside photogrammetry.
2. In the sim, confirm each site: blobs visible (T1-T4); no photogrammetry (T5). One screenshot per site into the run notes is enough (not committed).
3. For each site, set up the flight state per TEST-006 (12:00 local, clear weather) and save it to `tests/sites/<site>/flights/` (or record the steps in `preset` if no file exists). Set `flight`.
4. For each site, choose VP1 (street, about 2 m), VP2 (oblique, about 150 m), VP3 (approach, about 600 m), pointing at the palms. Record lat, lon, alt, heading, pitch and the recall method in `preset`.
5. Set each site's `status: defined`. Run the loader; fix any range errors.
6. Add a 3-line `tests/sites/<site>/README.md` per site: what to look at, and anything odd (construction, seasonal changes).

## Acceptance criteria

- [ ] All five sites `status: defined` and `load_sites()` passes.
- [ ] Each site has a saved flight file or exact preset steps, and three viewpoints with recall method.
- [ ] T1 matches the DEC-004 block (or the Log says why not).
- [ ] T5 confirmed outside photogrammetry but inside a region bbox.

## Verification

```bash
python -c "from tests.helpers.sites import load_sites; s=load_sites(); assert all(x.status=='defined' for x in s.values()); print({k:(v.region, v.bbox) for k,v in s.items()})"
pytest tests/unit/helpers/test_sites.py -q
python3 scripts/tasks.py validate
```

Manual: reload T1's flight after a sim restart, recall VP1-VP3, and confirm the framing matches the description.

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] VP3 approach viewpoint standardized at ~600 m (was ~500 m) to match the asset acceptance checks and Phase 3 exit criteria: the three viewpoints are street level (~2 m), low oblique (~150 m) and approach (~600 m). Cross-area reconciliation.
