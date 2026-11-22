---
id: ASSET-101
title: "Deliverable: SimObject wrapper package for every palm variant (only if live spawning is tested)"
status: todo
phase: 5
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w12-simobject-wrappers"
depends_on: [ASSET-071, ASSET-100]
requires: [windows-sim]
agent: msfs-sdk-specialist
estimate_h: 3
touches: [assets/simobjects/palmfix-assets-simobjects.xml, assets/simobjects/PackageDefinitions/, assets/simobjects/PackageSources/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmfix-assets-simobjects` builds and every manifest variant can be spawned by its `simobject_title`, so LIVE-101 and the Phase 5 bake-off can use live placement.

## Context

- An anchor that LIVE depends on. Keep the id. Only needed if the Phase 5 bake-off includes live spawning. If the user decides not to test live spawning, set this task to `dropped`, with the reason in the Log.
- Generator: ASSET-071. Layout: `assets/simobjects/README.md` (ASSET-070).
- `assets/manifest.json` isn't changed here. Titles are already in it.
- VERIFY (from ASSET-070): whether spawned objects can be scaled. Make sure LIVE knows the answer (log it and point LIVE-101 at the README).

## Steps

1. Run `python -m palmcore.assets simobjects --out assets/simobjects/PackageSources/` (or the subpath the README specifies).
2. Create `assets/simobjects/palmfix-assets-simobjects.xml` and `assets/simobjects/PackageDefinitions/palmfix-assets-simobjects.xml` following the ASSET-070 layout. Version = palmfix-assets version.
3. Build with fspackagetool and confirm exit 0.
4. With the package active, spawn each of the 12 titles once with SPIKE-005's script (a loop over titles from the manifest) at coordinates 20 m apart. Confirm all 12 are visible.
5. Log the title list and the result. Notify LIVE by logging on LIVE-101: `python3 scripts/tasks.py log LIVE-101 "SimObject wrappers ready: see assets/simobjects/README.md" --by <you>`.

## Acceptance criteria

- [ ] fspackagetool exits 0.
- [ ] All 12 titles spawn and are visible. Screenshot path in the Log.
- [ ] LIVE-101's Log points at the README.

## Verification

```bash
python -c "from palmcore.assets.manifest import load_manifest as l; m=l('assets/manifest.json'); print('\n'.join(v.simobject_title for s in m.species.values() for v in s.variants))"
```
On the sim PC:
```bat
fspackagetool assets\simobjects\palmfix-assets-simobjects.xml -outputdir build\palmfix-assets-simobjects -nopause
echo %ERRORLEVEL%   & rem 0
```
Then spawn each printed title with the SPIKE-005 script and confirm it's visible.

## Log

- 2026-11-21 [plan-breakdown] Task created.
