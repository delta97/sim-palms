# MSFS 2024 Palm Blob Fix: Development Plan

**Date:** 2026-11-21
**Status:** Plan only. Nothing is built yet.

## What this project does

In photogrammetry areas, Microsoft Flight Simulator 2024 renders palm trees as solid green columns ("blobs"). This project:

1. Finds where the real palms are, using public tree data and LiDAR.
2. Removes the photogrammetry blob at each location.
3. Places a 3D palm of the right species and height in its place.

The goal is no hand-placing per city. You pick a region, the tools generate the fix, and you fly.

## The approach in brief

- **Detection happens outside the sim.** Photogrammetry streams from the cloud and can't be read or edited, so palm locations come from city tree inventories, USGS LiDAR, and building footprints.
- **Blob removal uses `ExcludeTIN` polygons.** This is the only supported way to cut photogrammetry. A Python generator writes the scenery XML, and `fspackagetool` compiles it into a Community folder package.
- **Palm placement is a decision we test, not assume.** The options are static scenery objects in the same package, or objects spawned live through SimConnect near the aircraft. Phase 5 measures both and picks one.
- **A companion app makes it feel on demand.** It turns regions on or off before launch and, if live spawning wins, manages palms during the flight.
- **The neural, image-layer approach is a separate experiment.** It's tested offline on screenshots first.

## Files in this plan

| File | What it covers |
|---|---|
| `01-architecture.md` | Components, data flow, tech stack, repo layout, data contract |
| `02-detection-pipeline.md` | Finding palms: data sources, LiDAR detection, merging, species classification |
| `03-palm-assets.md` | The 3D palm library: species, LODs, variants, toolchain |
| `04-fs2024-integration.md` | How everything plugs into FS2024: packages, XML generation, SimConnect, region activation |
| `05-phases.md` | Build order, with tasks, deliverables, exit criteria and effort for each phase |
| `06-testing.md` | Unit tests, data accuracy, in-sim visual tests, performance, regression after sim updates |
| `07-risks-and-open-questions.md` | What could break the plan, mitigations, and decisions needed from you |
| `08-image-layer-experiment.md` | The stretch goal: real-time erase and redraw on the rendered frame |

## Phase summary

| Phase | Goal | Rough effort (hobby hours) |
|---|---|---|
| 0. Feasibility spike | Prove one blob can be cut and replaced on the current sim update | 6–10 |
| 1. Detection MVP | Palm GeoJSON for one test neighborhood from inventory data | 8–15 |
| 2. Generator MVP | Auto-generated exclusion package with placeholder palms, built from the command line | 8–12 |
| 3. Palm asset library | 5 SoCal species, 2–3 height variants each, with LODs | 20–40 |
| 4. LiDAR enrichment | Real heights, plus palms the inventories miss (beaches, parks, yards) | 10–20 |
| 5. Placement bake-off and companion app | Static vs live placement measured; region manager built | 10–25 |
| 6. Scale-out | LA and San Diego regions packaged; Florida species later | 5–10 per region |
| 7. Image-layer experiment (optional) | Offline test of neural erase and redraw | 10–20 |

Effort estimates are rough. Phase 3 is the biggest unknown and shrinks a lot if you license palm models instead of building them.

## Recap

- Palm locations come from real-world data, not from the sim.
- Each palm gets a small photogrammetry cutout and a matching 3D model.
- A script generates the scenery and the SDK tool compiles it.
- Live spawning and image-layer rendering are tested, not assumed.

## Sources

- MSFS 2024 SDK, Polygon Objects (Exclude TIN, vegetation exclude): https://docs.flightsimulator.com/msfs2024/html/2_DevMode/Scenery_Editor/Objects/Polygon_Objects.htm
- MSFS 2024 SDK, Package Tool (`fspackagetool.exe`): https://docs.flightsimulator.com/msfs2024/html/8_SDK_Tools/Package_Tool/Package_Tool.htm
- MSFS 2024 SDK, Scenery XML properties: https://docs.flightsimulator.com/msfs2024/html/5_Content_Configuration/Environment/Scenery_Objects/Scenery_XML_Properties.htm
- MSFS 2024 SDK, `SimConnect_AICreateSimulatedObject_EX1`: https://docs.flightsimulator.com/msfs2024/retail/programming-apis/simconnect/api-reference/ai-object/simconnect_aicreatesimulatedobject_ex1/
- MSFS 2024 SDK, Blender plugins: https://docs.flightsimulator.com/msfs2024/html/3_Models_And_Textures/Plugins/Blender_Plugin/The_Blender_Plugin.htm
- DevSupport, exclusion bugs in 2024: https://devsupport.flightsimulator.com/t/su6-beta-exclusions-of-any-type-not-working-rectangle-water-etc/18156
- AVSIM, the manual ExcludeTIN method for photogrammetry trees: https://www.avsim.com/forums/topic/698087-large-rocks-in-photogrammetry/
- Prior art, LA palm enhancement mod: https://flightsim.to/addon/81258/los-angeles-palm-enhancement
- LA County street tree compilation (1.6M records, GeoJSON): https://github.com/stiles/la-trees
- City of San Diego street trees (ArcGIS REST): https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20
- StreetsLA tree inventory: https://streets.lacity.gov/resources/tree-inventory
- USGS 3DEP LiDAR on AWS: https://registry.opendata.aws/usgs-lidar/
- OpenTopography 3DEP notebooks (canopy height models): https://github.com/cmspeed/OT_3DEP_Workflows
- ReShade add-on API: https://crosire.github.io/reshade-docs/
- NVIDIA DLSS 5 neural rendering: https://www.nvidia.com/en-us/geforce/news/hogwarts-legacy-war-thunder-dlss-5-3d-guided-neural-rendering/
