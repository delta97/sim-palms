---
id: SPIKE-008
title: Write the fspackagetool benchmark project generator (1 and 1,000 polygons, broken and CRLF variants)
status: todo
phase: 0
area: SPIKE
kind: build
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [SPIKE-003]
requires: [none]
agent: msfs-sdk-specialist
estimate_h: 2
touches: [spikes/fspackagetool-bench/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

A small standard-library Python script that clones the captured polygon XML into the benchmark projects SPIKE-004 needs, so the user only has to copy a folder to the sim PC and run `fspackagetool`. A Linux agent can do this while the user is away from the sim.

## Context

- Phase 0 task 7 (dummy XML with 1,000 polygons) in `plans/05-phases.md`; measurement list in `plans/detailed/04-fs2024-integration.md#spike-004-fspackagetool-measurements`.
- Inputs (read-only): `palmgen/templates/captured/scene_one_polygon.xml`, `project.xml`, `package_definition.xml`, `CAPTURE_NOTES.md` from SPIKE-003.
- This is throwaway spike code. It is not `palmgen` and must not import it. Standard library only (`xml.etree.ElementTree` or plain string templating, `uuid`, `math`, `argparse`).
- Keep the captured number formats, GUID style and line endings exactly as `CAPTURE_NOTES.md` describes. Where the notes say "unknown", choose the format seen in the capture and add a `# VERIFY:` comment.
- Output goes to `build/spike-bench/` (never committed; `build/` is gitignored).

## Steps

1. Create `spikes/fspackagetool-bench/make_bench.py` with `--center LON,LAT` (default: the ADR-0005 centre point if readable, else required), `--out build/spike-bench`, `--radius-m 3`, `--spacing-m 15`, `--self-check`.
2. Polygon geometry: a 12-sided circle of `--radius-m` around each centre, centres on a square grid at `--spacing-m`, starting at `--center`. Use a flat-earth metre-to-degree conversion (good enough for a 500 m grid). Vertex order and closure per `CAPTURE_NOTES.md`.
3. GUIDs: deterministic, `uuid.uuid5(NAMESPACE, f"bench-{variant}-{i}")`, formatted per the captured style. Replace only GUIDs that are per instance (differ between the two polygons in `scene_two_polygons.xml`); keep constants.
4. Write one complete project folder per variant under `--out`:
   - `p1/`: 1 polygon in one scene file.
   - `p1000x1/`: 1,000 polygons in one scene file.
   - `p1000x10/`: 1,000 polygons split over 10 scene files (100 each).
   - `two-files/`: 2 scene files with 1 polygon each (shows whether each scene file gets its own BGL).
   - `broken/`: `p1` with the scene XML cut off half way (invalid XML).
   - `p1-crlf/` and `p1-lf/`: `p1` with CRLF and LF line endings.
   If `CAPTURE_NOTES.md` says the project lists scene files one by one, add each file to `project.xml`; if it points to a folder, put them in that folder. If unknown, write both styles as `two-files-listed/` and `two-files-folder/`.
5. Write `spikes/fspackagetool-bench/README.md`: what each variant is for, how to run the script, and the exact commands SPIKE-004 will use.
6. `--self-check`: parse every generated XML file except `broken/`, count polygon elements (element name from the capture), and print a table variant, files, polygons. Exit 1 if any count is wrong.

## Acceptance criteria

- [ ] `python3 spikes/fspackagetool-bench/make_bench.py --center <lon,lat> --out build/spike-bench --self-check` exits 0 and prints counts 1, 1000, 1000 (10 files), 2, 1, 1 for the valid variants.
- [ ] Two runs produce byte-identical output (`diff -r`).
- [ ] `p1/` scene XML differs from `captured/scene_one_polygon.xml` only in vertex coordinates and instance GUIDs.
- [ ] README lists every variant and the SPIKE-004 measurement it serves.

## Verification

```bash
python3 spikes/fspackagetool-bench/make_bench.py --center -117.25,32.79 --out build/spike-bench --self-check
python3 spikes/fspackagetool-bench/make_bench.py --center -117.25,32.79 --out build/spike-bench2
diff -r build/spike-bench build/spike-bench2 && echo deterministic
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
