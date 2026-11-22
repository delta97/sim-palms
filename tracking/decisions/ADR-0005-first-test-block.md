# ADR-0005: Use Pacific Beach (Mission Blvd to Sail Bay, San Diego) as the first test block

- **Status:** accepted
- **Date:** 2026-11-22
- **Decided by:** the user (in chat, 2026-11-22: asked the integrator to pick a palm-dense San Diego block, then confirmed "Yes, use it")
- **Task:** DEC-004

## Context

Every Phase 0 spike (SPIKE-002..007), test site T1 (TEST-100) and the first region bbox need one agreed block of
about 300-500 m with a row of palms and at least one palm next to a building wall
(`plans/detailed/07-risks-and-open-questions.md#dec-004-first-test-block`, `plans/05-phases.md` Phase 0).

The user did not name a street; the task's default applies (a palm-lined City of San Diego block inside the
`san-diego-coastal` bbox). Candidates came from the live City of San Diego street-tree layer
(`https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20`, read 2026-11-22): 27,627 standing
palms (status not `RM`, palm genera or "palm" in the common name) in `san-diego-coastal`, counted per 0.005-degree cell.
A first live `palmscan run --no-lidar` on the chosen block produced 387 valid palms (SCAN-100 Log).

## Options

1. **Mission Hills** `[-117.185, 32.750, -117.180, 32.755]`: densest cell, 464 palms. Inland residential streets; harder to
   find from the air.
2. **Pacific Beach, Mission Blvd to Sail Bay** `[-117.255, 32.790, -117.250, 32.795]`: second-densest cell, 392 palms in the
   count (387 after palmscan's filters). Coastline, Crystal Pier and Sail Bay make it easy to find and judge in the sim;
   commercial and beach area.
3. **Hillcrest / Balboa Park west** `[-117.165, 32.730, -117.160, 32.735]`: 336 palms. Near the KSAN approach path.

## Decision

Option 2: **Pacific Beach, between Mission Blvd and Sail Bay, just south of Crystal Pier.**

| Item | Value |
|---|---|
| Name | San Diego, Pacific Beach test block (`regions/sd-pacific-beach.yaml`, `id_prefix: sdpb`) |
| Centre (lon, lat) | -117.25250, 32.79250 |
| bbox `[lon_min, lat_min, lon_max, lat_max]` | `[-117.255, 32.790, -117.250, 32.795]` (about 470 m E-W x 555 m N-S) |
| Building-adjacent palm | 32.79346, -117.25441 (lat, lon): *Washingtonia robusta*, 9.1 m, 0.6 m from an OSM building outline. 13 palms in the block are within 3 m of an OSM building. |
| Slew start position | lat 32.78800, lon -117.26000, altitude 500 ft MSL (about 150 m), heading 055 true: over the water south-west of the block, about 0.9 km out, looking at the centre. VERIFY in the sim (SPIKE-002) and adjust. |

Criteria (from DEC-004):

| Criterion | Status |
|---|---|
| User knows the street in person | unknown: the user delegated the pick; judging by eye relies on imagery and the sim |
| Inside City of SD or City of LA inventory | met: City of San Diego layer 20, 387 standing palms |
| Inside photogrammetry with visible blobs in the sim | unknown: to confirm with a screenshot at the slew position (SPIKE-002 step 1) |
| A row of 10+ palms | met: continuous rows of *W. robusta* along the block's streets (Esri imagery overlay at zoom 20, 2026-11-22) |
| A palm within about 3 m of a building wall | met: 13 palms within 3 m of an OSM building; nearest 0.6 m (above). OSM building coverage here is incomplete, so there are likely more |
| Not inside an airport boundary | met: nearest airport boundary KSAN 7.4 km, KNZY 9.5 km (`docs/compat/airports-mask.geojson`) |
| Not inside a known palm mod area | met on this PC: the only Community add-on is a weather mod (RISK-003 Log); other mods unknown |
| Does not reveal the user's home address (repo is public) | met: chosen by data, a commercial/beach area |

## Consequences

- SPIKE-002 / SPIKE-003: draw the first Exclude TIN polygon and capture templates at the building-adjacent palm or a
  palm in a row in this block; start from the slew position above.
- SPIKE-007: the building-adjacent palm above is the "palm next to a building" case.
- TEST-100: site T1 is this block (bbox and viewpoints derived from it).
- First region bbox: `regions/sd-pacific-beach.yaml` (already used by the live palmscan test).
- GATE-P0 is judged on this block.
- If the sim shows no blobs here (criterion 3 fails), fall back to Option 1 (Mission Hills) and supersede this ADR.

## Links

- Task: `tracking/tasks/DEC-004.md`; evidence in `tracking/tasks/SCAN-100.md`, `DEC-009.md`, `RISK-003.md` Logs.
- Region config: `regions/sd-pacific-beach.yaml`.
- Live run output (not committed): `build/scan/sd-pacific-beach/` (palms.geojson, qa_summary.md, preview.html).
- Source: City of San Diego street trees, ArcGIS REST layer 20 (read 2026-11-22).
