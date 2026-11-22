# 05. Development Phases

## Summary

Eight phases. Each one ends with a check you can see in the sim or measure, so a phase that fails stops the project cheaply. Phase 0 is the most important: it confirms the core trick still works on the current sim update before anything else gets built.

Effort is rough hobby time.

---

## Phase 0. Feasibility spike (6–10 hours)

**Goal:** prove one blob can be cut and replaced on the current sim update, by hand, and capture the XML templates everything else will reuse.

**Pick a test block:** a street you know well, with a row of obvious palm blobs, inside a city with a tree inventory (City of San Diego or City of LA). Knowing the block makes it easy to judge what's right.

**Tasks:**
1. Install the MSFS 2024 SDK. Create an empty scenery project in Dev Mode.
2. Draw one polygon around one blob. Turn on Exclude TIN and the vegetation exclude. Build and look.
3. Place one default library tree (any stand-in) in the hole. Build and look.
4. Repeat for a blob right next to a building, to see what a cut does to walls.
5. Save the scene. Copy the saved XML for the polygon and the object into `palmgen/templates/`.
6. Build the same project with `fspackagetool` from the command line. Time it.
7. Generate a dummy XML with 1,000 small polygons and time that build too.
8. Try running `fspackagetool` with the sim open. Note what happens.
9. Write a 50-line C# SimConnect script that spawns one default static SimObject on the ground at a coordinate, then disconnects. Check whether the object stays.

**Questions this phase answers:**

| Question | Why it matters |
|---|---|
| Does Exclude TIN work in a native 2024 project on this update? | If not, the project is blocked until it's fixed |
| What's left under the cut, at street level and from 300 m? | Decides whether cuts look acceptable |
| Do autogen trees appear in the hole? Does the vegetation exclude stop them? | Avoids double trees |
| How long does a 1,000-polygon build take? | Decides whether "build on demand" is realistic |
| Can builds run with the sim open? | Decides the companion app's flow |
| Do SimConnect objects survive a client disconnect? | Decides cleanup logic for live spawning |

**Deliverables:** XML templates, a one-page findings note with screenshots, and a go/no-go decision.

**Exit criteria:** one blob removed cleanly, a stand-in tree placed, a command-line build working.

---

## Phase 1. Detection MVP (8–15 hours)

**Goal:** `palms.geojson` for the Phase 0 neighborhood, from inventory data only.

**Tasks:**
1. Set up the repo, `pyproject.toml`, and the region YAML for the test area.
2. Write the inventory adapter (ArcGIS REST for San Diego, or GeoJSON for the LA compilation).
3. Species normalization and the palm genus filter.
4. Building footprint adapter and the building-conflict flag.
5. Write `palms.geojson`, validated against the JSON Schema.
6. QA outputs: `qa_summary.md` and `qa_map.gpkg`.

**Deliverables:** `palmscan run --region <test>` works end to end.

**Exit criteria:** open the QA map over aerial imagery. At least 90% of the palms you can see along inventory streets have a point within 3 m.

---

## Phase 2. Generator MVP (8–12 hours)

**Goal:** an auto-generated region package that removes the blobs in the test neighborhood and drops in stand-in trees.

**Tasks:**
1. Geometry: circles, unions within `merge_gap_m`, building clipping.
2. XML writer filling the Phase 0 templates; deterministic GUIDs.
3. Tiling, package project and definition files.
4. `fspackagetool` wrapper with output checks and `build_report.md`.
5. Golden-file tests for XML output.
6. In-sim review in Dev Mode. Tune `margin_m` until blobs disappear fully without oversized holes.

**Deliverables:** `palmgen build --region <test>` produces a working Community package.

**Exit criteria (test neighborhood):**
- At least 90% of visible palm blobs gone.
- No building walls visibly cut.
- No autogen trees appearing in the holes.

---

## Phase 3. Palm asset library (20–40 hours)

**Goal:** real palm models replace the stand-ins.

**Tasks:**
1. Decide build vs license (see `03-palm-assets.md`).
2. Start with Mexican fan palm: model, LODs, materials, export, package as a model library.
3. Swap it into the test neighborhood and review. Fix the pipeline before doing the other species.
4. The other four SoCal species.
5. Variant selection and scaling in `palmgen`.

**Deliverables:** `palmfix-assets` package; region package using real models.

**Exit criteria:** each species passes the acceptance checks in `03-palm-assets.md`; the test neighborhood looks right at street level, 150 m and 600 m.

---

## Phase 4. LiDAR enrichment (10–20 hours)

**Goal:** real heights for every palm, plus palms the inventories miss.

**Tasks:**
1. PDAL pipeline: EPT read, DTM, DSM, CHM at 0.5 m.
2. Peak detection, crown segmentation, palm rules.
3. Inventory-to-LiDAR matching and merging.
4. Shape-rule species classifier; then train a decision tree on matched palms.
5. Add a beach or park test site with no inventory coverage.
6. Hand-label ground truth at two sites for accuracy metrics.

**Exit criteria (starting targets):**
- LiDAR-only detection precision at least 90% and recall at least 80% against hand labels.
- Median height error under 2 m on matched palms.
- Beach site visibly fixed in the sim.

---

## Phase 5. Placement bake-off and companion app (10–25 hours)

**Goal:** decide static vs live palm placement with numbers, then build the companion app.

**Bake-off:**
1. Build three setups for the densest test area: no fix, static placement, live spawning (exclusions in both fix setups).
2. Run the fixed performance flight three times each (see `06-testing.md`).
3. Compare frametime, 1% lows, stutter and visual results (pop-in, LOD transitions).
4. Pick the winner. Default to static if they're close, because it has fewer moving parts.

**Companion app:**
1. Region manager: list, activate, deactivate (folder links), warn if the sim is running.
2. Optional: build a region from the app (calls `palmscan` and `palmgen`).
3. Optional: the live spawner, if it won the bake-off.

**Exit criteria:** a written decision with the measurements; switching regions takes one click and needs no file copying.

---

## Phase 6. Scale-out (5–10 hours per region)

**Goal:** full coverage for target metros.

**Order:** San Diego coastal → LA Westside and beaches → rest of LA basin → other SoCal photogrammetry cities. Florida after the Florida species set exists.

**Per region:**
1. Region YAML (sources, priors, masks for other mods and airports).
2. `palmscan` run and QA review.
3. `palmgen` build and spot checks at three random locations.
4. Performance check over the densest part.

---

## Phase 7. Image-layer experiment (optional, 10–20 hours)

See `08-image-layer-experiment.md`. Offline first; the real-time version only if offline results look convincing.

---

## Decision points

| After phase | Decision | Default if unclear |
|---|---|---|
| 0 | Go / no-go on Exclude TIN | Stop and file a bug report if exclusions don't work |
| 3 | Build vs license models | Build one species first, then decide |
| 5 | Static vs live placement | Static |
| 6 | Publish or keep personal | Personal until data and model licenses are checked |

---

## Recap

- Phase 0 proves the basic trick works before anything else gets built.
- Phases 1 and 2 give a working, auto-generated fix with stand-in trees.
- Phases 3 and 4 make it look right and cover the gaps.
- Phase 5 settles static vs live with measurements.
