# 06. Testing Strategy

## Summary

Five layers of testing, from cheap and automatic to slow and visual:

1. **Unit tests:** code correctness, run on every change.
2. **Data accuracy:** are the palms in the right places, with the right heights?
3. **Build checks:** did the package compile completely?
4. **In-sim visual tests:** does it look right, at fixed viewpoints?
5. **Performance and regression:** does it cost too much, and does it still work after a sim update?

---

## 1. Unit tests (pytest, xUnit)

| Area | What to test |
|---|---|
| Source adapters | Parsing saved sample responses (no live network calls in tests); species name normalization |
| Palm filter | Genus list, stump and vacant-site removal |
| Merge | Inventory-to-LiDAR matching radius, dedupe, mask-out areas |
| Species rules | Each rule boundary; fallback to priors |
| Geometry | Circles valid and closed, unions correct, building clip never produces invalid or empty polygons, radius within bounds |
| XML writer | Golden-file tests: generated XML for a fixed input matches a saved expected file exactly |
| GUIDs | Same input gives the same GUIDs; different palms never collide |
| Data contract | Every `palms.geojson` validates against the JSON Schema |
| Spawn manager (C#) | Runs on recorded flight tracks with a fake SimConnect adapter: spawns inside radius, removes outside radius plus hysteresis, never exceeds the cap, cleans up on shutdown |

---

## 2. Data accuracy

**Ground truth:** at each test site, hand-label every palm you can see on aerial imagery (point and rough height class). About 200 palms across two sites is enough to start.

**Metrics:**

| Metric | Starting target |
|---|---|
| Detection precision (palms we place that are real palms) | ≥ 90% |
| Detection recall (real palms we found) | ≥ 80% LiDAR-only, ≥ 90% with inventory |
| Position error | Median under 2 m |
| Height error vs LiDAR on matched palms | Median under 2 m |
| Species accuracy (rules vs inventory labels) | Report it; no hard target until Phase 4 |

**Test sites:**

| Site | Purpose |
|---|---|
| T1: palm-lined street with inventory coverage | Main happy path |
| T2: beach or boardwalk palms | No inventory; tests LiDAR detection |
| T3: palms right next to buildings | Tests building clipping and wall damage |
| T4: area with Italian cypress, eucalyptus and light poles, few palms | False positive test |
| T5: area outside photogrammetry coverage | Confirms the package does no harm where there are no blobs |

---

## 3. Build checks (every `palmgen build`)

- `fspackagetool` exit code is 0.
- One BGL per tile.
- Polygon and object counts in the generated XML match the input.
- Build time logged in `build_report.md`, so slowdowns show up over time.

---

## 4. In-sim visual tests

**Setup per test site:**
- A saved flight with fixed time of day (noon) and clear weather.
- Three fixed drone-camera viewpoints: street level (about 2 m), low oblique (about 150 m), approach (about 500 m).
- Same graphics settings every time; note them in the test log.

**Protocol:**
1. Screenshot every viewpoint with no fix package.
2. Screenshot every viewpoint with the fix package.
3. Save both sets under `tests/visual/<site>/<date>/`.
4. Fill in the checklist.

**Checklist:**
- [ ] Blobs gone at all three viewpoints
- [ ] A palm at every former blob, at a believable height
- [ ] No floating or sunken palm bases
- [ ] No building walls cut or missing
- [ ] No autogen trees appearing in the holes
- [ ] Ground under cuts looks acceptable (no obvious hole edges or color seams)
- [ ] LOD transitions don't pop distractingly on a slow pass
- [ ] Species look right for the area

**Later, optional:** automate screenshot comparison with a simple image-diff score per viewpoint, so regressions show up as numbers.

---

## 5. Performance

**Fixed test flight:** a 5-minute low pass over the densest palm area at 150–300 m, same aircraft and same path every time (autopilot route or replay).

**Measure** with PresentMon or CapFrameX:
- Average FPS
- 1% low FPS
- 99th percentile frametime
- Stutter events (frames over 2× median)

**Runs:** 3 runs each for: no fix, static fix, live fix. Clear outliers, report averages.

**Starting budget:** the fix should cost no more than about 5% in average frametime and must not add stutter. Tune after the first measurement.

**Live spawner only:** a 1-hour soak flight. Spawned object count should stay under the cap and return to zero after shutdown.

---

## 6. Regression after sim updates

Exclusion behavior has broken in past 2024 updates and betas, so after every sim update or SDK update:

1. Rerun the Phase 0 single-blob test.
2. Rebuild one region with the current SDK.
3. Run the visual protocol at T1 and T3.
4. If anything changed, run the full visual suite and the performance flight.

Keep a short log: date, sim version, SDK version, pass/fail per check.

---

## Recap

- Unit and golden-file tests protect the code.
- Hand-labeled sites measure whether the palms are real and in the right place.
- Fixed viewpoints and a checklist make the visual check repeatable.
- A fixed flight path measures performance, and a short regression routine runs after every sim update.
