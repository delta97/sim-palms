---
id: SPIKE-003
title: "Capture Scenery Editor XML templates (Exclude TIN polygon, vegetation exclude, scenery object) into palmgen/templates/"
status: todo
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/04-fs2024-integration.md#spike-003-template-capture"
depends_on: [SPIKE-002, SPIKE-006]
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 2
touches: [palmgen/templates/captured/, docs/findings/SPIKE-003.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Unmodified XML files saved by the MSFS 2024 Scenery Editor sit in `palmgen/templates/captured/`, with `CAPTURE_NOTES.md` answering every format question. GEN-009 turns them into templates, TEST-016 reads element names from them, and ASSET-004 reuses the object fragment. Nothing in `palmgen` guesses the XML format.

## Context

- Exact file list and notes content: `plans/detailed/04-fs2024-integration.md#spike-003-template-capture`. This task must deliver all of it.
- Why captures and not hand-written XML: R-08 (generated XML rejected or subtly wrong). Round-trip tests in GEN-009 compare templates byte for byte with these files, so **never edit a captured file**. Copy the file the editor saved, as is.
- Use a fresh project `palmfix-capture` (lowercase, hyphens) so the captures are not mixed with the SPIKE-002/006/007 experiments. Use the same test block location.
- Stand-in object: the one recorded in `docs/findings/SPIKE-006.md`.
- How instance and constant GUIDs are told apart: a GUID that differs between the two polygons in `scene_two_polygons.xml` is per instance; one that is the same is a constant (plan 04, Template placeholder conventions).

## Steps

1. Create a new project `palmfix-capture` with the same steps as SPIKE-001 (copy the click list from `docs/findings/SPIKE-001.md`). Slew to the test block.
2. Save the empty scene. Copy the saved scene XML to the repo as `palmgen/templates/captured/scene_empty.xml`. (VERIFY: the scene file name and folder; SPIKE-001's `tree.txt` shows where it is.)
3. Add one polygon with 6 or more vertices, Exclude TIN on, vegetation exclude on. Save. Copy the scene file as `scene_one_polygon.xml`.
4. Turn the vegetation exclude off on that polygon. Save. Copy as `scene_polygon_tin_only.xml`. Turn it back on.
5. Add a second polygon with both flags on. Save. Copy as `scene_two_polygons.xml`.
6. Delete both polygons. Place the stand-in object (from SPIKE-006), snapped to ground, heading 37 degrees, scale 1.10 (VERIFY: where heading and scale are set; if scale is not offered, write that down). Save. Copy as `scene_one_object.xml`.
7. Add one polygon (both flags) around the object. Save. Copy as `scene_polygon_and_object.xml`.
8. Copy the project file as `project.xml` and `PackageDefinitions/<name>.xml` as `package_definition.xml`.
9. Build the project once from the editor to confirm this exact state builds. Note the result.
10. Write `palmgen/templates/captured/CAPTURE_NOTES.md`. Answer each item; write "not shown" or "unknown, tried X" instead of guessing:
    - sim version, SDK version, date;
    - project folder tree (where scene XML lives, so `scene_dir` is known);
    - stand-in object display name, GUID, approximate height;
    - vertex order (clockwise or counter-clockwise: compare the saved order with the order you clicked) and whether the first vertex is repeated at the end;
    - whether vertices carry altitude;
    - number formats: decimals for lat, lon, heading, scale; GUID braces and upper or lower case;
    - file encoding, BOM, line endings (open in an editor that shows them, for example Notepad++ status bar);
    - how heading, scale and snap-to-ground appear on the object, or that they don't;
    - whether a polygon can have holes (does the editor offer it?);
    - any vertex limit the editor shows or enforces;
    - whether the project lists scene files one by one or points to a folder;
    - the version field format in the package definition;
    - anything seen about declaring a dependency on another package.
11. Write `docs/findings/SPIKE-003.md`: a short note linking to `CAPTURE_NOTES.md`, listing the 8 files, and the build result from step 9.

Results checklist (tick in the findings note):

| File | Saved? |
|---|---|
| `scene_empty.xml` | |
| `scene_one_polygon.xml` | |
| `scene_polygon_tin_only.xml` | |
| `scene_two_polygons.xml` | |
| `scene_one_object.xml` | |
| `scene_polygon_and_object.xml` | |
| `project.xml` | |
| `package_definition.xml` | |
| `CAPTURE_NOTES.md` | |

## Acceptance criteria

- [ ] All 8 XML files and `CAPTURE_NOTES.md` exist in `palmgen/templates/captured/`, unedited from what the editor saved.
- [ ] `CAPTURE_NOTES.md` answers every item in step 10 (or says what was tried).
- [ ] `diff scene_one_polygon.xml scene_polygon_tin_only.xml` shows the vegetation flag and nothing unexpected (note any other differences).
- [ ] The `palmfix-capture` project in exactly the captured state builds, or the error is recorded.

## Verification

```bash
ls palmgen/templates/captured/
for f in palmgen/templates/captured/*.xml; do python3 -c "import sys,xml.dom.minidom as m; m.parse(sys.argv[1]); print('ok', sys.argv[1])" "$f"; done
diff palmgen/templates/captured/scene_one_polygon.xml palmgen/templates/captured/scene_polygon_tin_only.xml
grep -ciE "vertex|guid|line ending|encoding" palmgen/templates/captured/CAPTURE_NOTES.md
```

Every XML file parses; the diff is small and explained in the notes.

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
