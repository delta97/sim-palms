# 02. Detection Pipeline (`palmscan`)

## Summary

`palmscan` answers three questions for every palm in a region: where is it, how big is it, and what species is it. It combines four data sources, because none of them covers everything:

- **City tree inventories:** exact species, but street trees only.
- **LiDAR:** real heights and crown sizes everywhere, but no species.
- **Building footprints:** filter out false positives.
- **OSM trees:** occasional extra points.

Output: `palms.geojson` (schema in `01-architecture.md`).

---

## 1. Data sources

| Source | What it gives | Coverage gaps | Access | License note |
|---|---|---|---|---|
| LA County street trees (stiles/la-trees) | Point, species, sometimes size; 1.6M records across 40+ cities | Street right of way only; records age quickly | GeoJSON / CSV on GitHub | Collected via public records requests; check before redistributing |
| StreetsLA tree inventory (City of LA) | Location, species, size | City of LA only; street trees only | StreetsLA site / LA GeoHub | Check terms |
| City of San Diego street trees | Point, `SPECIES_NAME` field | Public trees only | ArcGIS REST query on MapServer layer 20 | Public; disclaimer on accuracy |
| USGS 3DEP LiDAR | Point cloud for heights and crown shape | Collection year varies by project; trees planted or removed since then are wrong | Entwine Point Tiles at `s3://usgs-lidar-public`, read with PDAL, no AWS account needed | Public domain |
| Building footprints | Polygons used to reject non-tree peaks | Small structures can be missing | OSM via Overpass, or Microsoft Global ML Building Footprints | OSM is ODbL (attribution) |
| OSM `natural=tree` | Points, sometimes `species` or `genus` tags | Patchy | Overpass API | ODbL |

**Important gap:** Beach and park palms are usually missing from street inventories. Venice and Santa Monica beach, Mission Beach and Pacific Beach boardwalks mostly depend on LiDAR (step 3).

---

## 2. Inventory ingest and palm filter

1. Pull every point in the region's bbox through the source adapter.
2. Normalize species names to one internal key, for example `Washingtonia robusta`, `WASHINGTONIA ROBUSTA` and `Mexican fan palm` all become `washingtonia_robusta`.
3. Keep only palm genera:
   - SoCal: *Washingtonia, Phoenix, Syagrus, Archontophoenix, Brahea, Butia, Livistona, Trachycarpus, Chamaerops, Dypsis*
   - Florida (later): *Sabal, Roystonea, Cocos, Wodyetia, Adonidia*
4. Drop records marked as stumps, vacant sites or removed.
5. Record data vintage per source, so the QA report can flag stale areas.

**Note on sizes:** Inventories usually give trunk diameter (DBH), not height. Palms don't thicken much as they grow taller, so DBH is a poor height predictor. Use LiDAR height when available. Otherwise use the species' median height from the matched palms in the same region.

---

## 3. LiDAR: canopy height model and palm candidates

This step finds palms the inventories miss and gives every palm a measured height.

**Build the canopy height model (CHM):**
1. Read 3DEP points for the bbox with PDAL's EPT reader.
2. Ground surface (DTM): ground-classified points (class 2), rasterized at 0.5 m.
3. Surface model (DSM): first returns, rasterized at 0.5 m.
4. CHM = DSM − DTM. Light Gaussian smoothing (about 1 pixel).

**Find candidate crowns:**
1. Local maxima with height ≥ 6 m and minimum spacing of about 3 m.
2. Watershed segmentation around each peak, masked to CHM > 2 m, to get the crown outline.
3. Crown diameter = equivalent circle diameter of the segment area.

**Palm test (starting rules, tuned in Phase 4):**

| Test | Starting threshold | Why |
|---|---|---|
| Height | 8–35 m | Mature SoCal palms |
| Crown diameter | 3–12 m | Fan palms are small; Canary Island date palms are large |
| Height ÷ crown | > 2.0 (fan palms usually much higher) | Palms are tall and narrow; broadleaf trees are wide |
| Isolation | Crown segment doesn't merge into continuous canopy | Palms stand alone; oaks and ficus form canopy |
| Building check | Peak not inside a building footprint buffered by 1 m | Rejects chimneys, rooftop equipment, towers |
| Pole check | Crown diameter ≥ 3 m | Light poles and flagpoles have almost no crown |

**Known false positives to watch for:** Italian cypress (tall and narrow, common in LA), eucalyptus, light poles, flagpoles. These get their own test site (see `06-testing.md`).

---

## 4. Merge and deduplicate

1. For each inventory palm, look for a LiDAR candidate within 3 m.
   - **Match:** keep the inventory species, take the LiDAR height and crown. `detected_by = inventory+lidar`.
   - **No match:** keep it with the species' median height. `detected_by = inventory`. The palm may have been planted after the LiDAR collection, or LiDAR missed it.
2. LiDAR candidates with no inventory match go in with species from step 5. `detected_by = lidar`.
3. OSM tree points with a palm genus tag are treated like inventory points.
4. Dedupe anything within 2 m that came from two sources.
5. Apply `mask_out` areas from the region config (areas other mods already cover).

---

## 5. Species classification

Applied in order. The first rule that gives an answer wins.

1. **Inventory or OSM species:** use it. Confidence 0.95.
2. **Shape rules from LiDAR** (starting values):

   | Shape | Species | Confidence |
   |---|---|---|
   | Height ≥ 18 m and crown ≤ 5 m | Mexican fan palm (*W. robusta*) | 0.7 |
   | Crown ≥ 7 m, height 8–20 m | Canary Island date palm (*P. canariensis*) | 0.7 |
   | Height 8–15 m, crown 4–7 m | Queen palm (*S. romanzoffiana*) | 0.5 |
   | Anything else | Use regional priors | 0.3 |

3. **Regional priors:** sample from the species mix observed in that region's inventory.

**Upgrade in Phase 4:** Every inventory-plus-LiDAR match is a labeled example (known species, measured shape). Train a small decision tree on those labels and replace the hand rules with it. Keep the rules as a fallback.

California fan palm (*W. filifera*) and Mexican fan palm look alike in LiDAR. Without inventory data, default to *W. robusta*, which is far more common in LA.

---

## 6. Exclusion radius and conflicts

For each palm:
- `exclusion_radius_m = crown_diam_m / 2 + margin_m` (margin from region config, default 1.5 m).
- Blobs are fatter than real crowns, so the margin gets tuned in Phase 2 against what the sim shows.
- `building_conflict = true` if the exclusion circle overlaps a building footprint. `palmgen` clips those circles so building meshes stay intact.

---

## 7. QA outputs

Every run writes these next to `palms.geojson`:

- `qa_summary.md`: counts by source and species, share of palms with LiDAR height, data vintage by area.
- `qa_map.gpkg`: palms, candidates rejected (with reason), building conflicts. Open in QGIS over aerial imagery for a quick visual check.
- `qa_rejects.csv`: every rejected LiDAR candidate and the rule that rejected it. Use it to tune thresholds.

---

## Recap

- Inventories give species, LiDAR gives height and catches missing palms, footprints remove false positives.
- Matching the two creates training labels for a better species classifier.
- Every run produces a QA map, so you can check results before building anything in the sim.
