# 04. FS2024 Integration

## Summary

Everything reaches the sim through four supported surfaces. No memory hacking, cache editing or stream interception.

| Surface | What it's used for |
|---|---|
| **Community folder packages** | The region fix: exclusion polygons plus (if static) palm placements |
| **Dev Mode Project Editor** | Development loop: build and review a package inside the running sim |
| **`fspackagetool.exe`** | Command-line builds from `palmgen` |
| **SimConnect** | Optional live palm spawning, and reading aircraft position |

---

## 1. Region package layout

One package per region, for example `palmfix-san-diego-coastal`.

```
build/palmfix-san-diego-coastal/
  palmfix-san-diego-coastal.xml        # package project file
  PackageDefinitions/
    palmfix-san-diego-coastal.xml      # package definition
  PackageSources/
    scene/
      tile_n32p79_w117p26.xml          # one scenery XML per tile
      tile_n32p79_w117p25.xml
      ...
```

- **Tiling:** split scenery XML into tiles of about 0.01° (about 1 km). It keeps files manageable and makes a rebuild of one area fast.
- **Palm models:** the model library lives in its own package (`palmfix-assets`) that every region package depends on. Model updates then don't require rebuilding every region.
- **Versioning:** package version = data version plus generator version, for example `1.3.0+data2026-11`.

---

## 2. What `palmgen` writes per palm

**Rule one:** don't write XML from scratch. The SDK warns against hand-made scenery XML and recommends using the Scenery Editor. So Phase 0 creates each object type once in the Scenery Editor, saves it, and copies the saved XML into `palmgen/templates/`. The generator only fills in coordinates, sizes and GUIDs.

**Per palm (or per merged cluster):**

1. **Exclusion polygon**
   - A 12-sided circle, radius `exclusion_radius_m`.
   - Attributes copied from the Phase 0 template:
     - Exclude TIN (removes the photogrammetry blob)
     - Vegetation exclude (stops autogen trees appearing in the hole once the photogrammetry is gone)
   - Clipped against building footprints when `building_conflict = true`, so building meshes stay intact.

2. **Palm placement** (static option only)
   - A scenery object referencing the model library GUID for the chosen species variant.
   - Scale = target height ÷ variant height (clamped to ±15%).
   - Random heading, seeded by `palm_id` so rebuilds are stable.
   - Snapped to ground. Altitude comes from the sim, not from LiDAR, because the sim's terrain under the cutout is what the palm has to sit on.

**Merging:** palms whose circles come within `merge_gap_m` of each other get one unioned polygon. A row of 40 palms along a median becomes a few polygons, not 40. Fewer polygons means faster builds and less load in the sim.

**Unique GUIDs:** every polygon and object gets a deterministic GUID (UUIDv5 from `palm_id` and tile). Rebuilds produce the same IDs, which keeps diffs clean and avoids duplicates.

---

## 3. Building

```
palmgen build --region san-diego-coastal
```

Under the hood:
1. Write the project, package definition and tile XML files.
2. Run `fspackagetool <project.xml> -outputdir <out> -nopause`.
3. Check the exit code, confirm a BGL exists for every tile, and compare object and polygon counts against the input.
4. Write `build_report.md` with counts, build time and warnings.

**Constraints to confirm in Phase 0:**
- `fspackagetool` drives a partial sim instance, so it only runs on the Windows PC with the sim installed.
- Unknown: whether it can run while the full sim is running. If not, builds must happen before launch.
- Unknown: build time per 1,000 polygons. Phase 0 measures it with dummy data.

---

## 4. Development loop in Dev Mode

During development, skip the Community folder:
1. Open the generated project in Dev Mode's Project Editor.
2. Build. The package loads into the running sim.
3. Fly or slew to the test site and inspect.
4. Fix the generator, regenerate, rebuild.

This makes each iteration minutes instead of a full sim restart.

---

## 5. Region activation (companion app, `palmlive`)

**What it does:**
- Lists built regions, their data date and package version.
- Activates a region by creating a folder link from the build output into the Community folder. Deactivating removes the link. Nothing gets copied or deleted.
- Picks regions automatically from a flight plan or destination, if you want it to.
- Warns if the sim is running, because Community packages load at startup.

**Why links:** the build output stays in one place, switching is instant, and turning a region off can't damage anything.

---

## 6. Live spawning option (`palmlive` spawner)

Only built if Phase 5 shows it beats static placement.

**Loop (about once per second):**
1. Read aircraft lat, lon and altitude above ground through SimConnect.
2. Spawn radius scales with height: about 1.5 km at street level up to about 4 km at 1,000 m AGL. Starting values, tuned in testing.
3. Query the region's spatial index for palms inside the radius.
4. Spawn missing ones with `SimConnect_AICreateSimulatedObject_EX1`, using the SimObject container title for the species variant, positioned on the ground.
5. Remove palms beyond radius + 20% (hysteresis stops spawn/remove flicker at the edge) with `SimConnect_AIRemoveObject`.
6. Hard cap on live objects (starting value: 2,000). Closest palms win.

**Things to verify early:**
- Whether spawned objects get removed automatically when the app disconnects. If not, the app tracks every object ID and cleans up on exit and on restart.
- How spawned static SimObjects sit on terrain. A 2020-era forum report found they don't orient to terrain slope, which doesn't matter for upright palms.
- CPU cost of thousands of SimObjects. They take part in the simulation, unlike plain scenery objects.

**Important:** even with live spawning, the exclusion polygons still come from the region package. SimConnect can add objects but can't remove photogrammetry.

---

## 7. Compatibility

- **Other palm and tree mods** (for example the LA palm enhancement mod, Bijan's Seasons 2024 Enhanced): add their coverage areas to `mask_out` to avoid duplicate palms. Overlapping exclusions are harmless.
- **Airport add-ons:** exclusions near airports could clash with airport scenery. Mask airport boundaries by default.
- **Sim updates:** exclusion behavior has broken in past 2024 updates and betas. Rerun the regression suite after every update (`06-testing.md`).

---

## Recap

- Region fixes ship as Community packages built from the command line.
- XML is built from templates the Scenery Editor saved, not written from scratch.
- The companion app switches regions with folder links and can spawn palms live.
- Exclusions always come from the package; SimConnect can only add objects.
