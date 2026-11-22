# Status

**Updated:** 2026-11-22 · **Phase:** 0 (sim work not started) with Linux code ahead through Phase 4 and Phase 7 Stage A under the proposed ADR-0013 · **Newest log:** [2026-11-22 integrator, part 2](logs/2026-11-22-integrator-orchestration-2.md)

## Where things stand

- **74 of 214 tasks done** (plus FX-014 merged as code but `blocked` on FX-026), all merged to `main` and pushed. GitHub issues are synced from the task files by `python scripts/issues.py sync` (bodies, labels, open/closed); done issues are closed with a link to the merge commit. Board: [BOARD.md](BOARD.md). Changelog: [CHANGELOG.md](../CHANGELOG.md).
- **Phase 1 code (palmscan) is complete on fixtures.** `palmscan run` goes ingest → dedupe → species → priors → sizes/exclusion/buildings/masks → `palms.geojson` + QA outputs, offline and byte-reproducible (`SOURCE_DATE_EPOCH`). Adapters: geojson/CSV file, ArcGIS REST, Overpass/OSM, building footprints. Live samples are recorded in `tests/fixtures/palmscan/recorded/` (SCAN-007).
- **Phase 2 code (palmgen) has its building blocks:** inputs, GUIDs, tiling, exclusion geometry + building clipping, masks, variant/scale/heading, template engine on *fake* templates, build reports. The real Scenery Editor XML (SPIKE-003) and package build (SPIKE-004) need the sim PC.
- **Shared core (palmcore):** contracts and schemas, region config, ids, geo, cache, logging, CLI plumbing, palms.geojson I/O, asset manifest + glTF checks.
- **Tests:** 1,822 passing locally. **GitHub Actions is disabled** (user request, 2026-11-22); `python scripts/ci.py` is the CI now and gates every merge to `main`. Harness, golden files, contract checks, geometry helpers, accuracy metrics, ground-truth format, visual protocol and post-update regression routine are in `tests/`.
- **Phase 4 (LiDAR) code is complete on fixtures:** 3DEP EPT adapter (injectable PDAL runner), CHM, peaks/crowns, palm rule filter, inventory–LiDAR merge, species rules + decision-tree classifier, in-run accuracy and `palmscan eval`, all wired into `palmscan run`. Real PDAL and real 3DEP tiles are untested (SCAN-021, SCAN-030).
- Nothing about the sim, the SDK or SimConnect has been confirmed. Every such claim in code or docs is marked `VERIFY:` and waits for the SPIKE tasks.

## Waiting on the user

Everything else that is ready needs you, the sim PC, or Blender:

1. ~~DEC-004~~ **decided:** first test block is Pacific Beach, Mission Blvd to Sail Bay ([ADR-0005](decisions/ADR-0005-first-test-block.md), `regions/sd-pacific-beach.yaml`). A live `palmscan` run there gave 387 valid palms (SCAN-100 Log).
2. **SPIKE-001** on the sim PC: install the MSFS 2024 SDK and make an empty Dev Mode project. Then SPIKE-002..007 runbooks, TEST-006 (repeatable camera/screenshot method), SPIKE-005 using the console app in `spikes/simconnect-persist/` (build: see its README).
3. **Review the proposed ADRs:** ADR-0001 (tracking structure) and ADR-0013 (Linux code ahead of Phase 0, which this session relied on).
4. **Decisions with evidence ready:**
   - DEC-002 build or license palm models: `assets/reference/build-vs-license.md`, `docs/licenses/models-and-tools.md`.
   - DEC-009 building footprint source (OSM vs Microsoft): `docs/licenses/data-sources.md`, SCAN-007 findings (Microsoft tiles are 78–171 MB per region).
   - DEC-008 asset storage (Git LFS or external), DEC-005 performance budget.
   - The open questions at the end of `docs/licenses/data-sources.md` and `docs/licenses/models-and-tools.md` (ODbL share-alike, San Diego indemnity, retail model non-extractability).
5. **RISK-003:** which other palm/tree mods you use (for default masks).
6. **FX-026** ([#215](https://github.com/delta97/sim-palms/issues/215)): OK to download and load the LaMa model weights on a machine with torch (CPU is fine), so the LaMa backend can be pinned and run. It blocks FX-014 (#202), which blocks FX-015, FX-017 and FX-018.

## Known gaps found this session (not yet tasks)

- No StreetsLA WFS adapter; LA Westside relies on the stiles/la-trees county file (627 MB, common names only, row-index ids, no heights). Per-city files differ (Santa Monica is EPSG:2229 with height classes).
- Microsoft footprints come as quadkey `.csv.gz` tiles; there is no downloader yet (SCAN-006 reads a local file).
- `palmgen/masks.py` has its own Overpass fetch; it should move onto `palmscan.sources.overpass` later.
- `ingest_inventory` wraps an offline `CacheMiss` as `SourceError` (exit 4 vs 5); SCAN-013 works around it in the pipeline.

## Next

1. Phase 7 Stage A (offline image-layer experiment) code is built on synthetic data: scaffold, camera model, depth decoder (shader untested in ReShade), synthetic scene generator, session ingest with pose interpolation, calibration (click UI not yet run on a display), masks by projection and by depth/colour heuristics, mask metrics, inpainting (Telea tested; LaMa untested, FX-014 blocked on FX-026, #215). Capture formats are placeholders (VERIFY) until FX-001/FX-006/FX-007 on the sim.
2. The user does SPIKE-001 on the sim PC (this PC: MSFS 2024 Steam edition, SDK not installed yet; see the SPIKE-001 Log). Phase 2 build and validation tasks unblock from the SPIKE results.
