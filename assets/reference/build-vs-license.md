# Build vs license: inputs for DEC-002 (palm models)

**Task:** ASSET-002. **For:** DEC-002 (decision belongs to the user; this file recommends nothing and buys nothing).
**Pages read:** 2026-11-22 unless a row says otherwise. **Not legal advice.** `VERIFY:` marks anything not confirmed from a page read on that date. Prices and counts come only from pages or API responses actually read; marketplace listings that could not be read are marked VERIFY and carry no number.

**Builds on, does not repeat:** [docs/licenses/models-and-tools.md](../../docs/licenses/models-and-tools.md) (RISK-002). That file audited TurboSquid, CGTrader, Sketchfab store, Fab and CC BY, and found the "non-extractable" clauses. Section 2 below re-quotes the load-bearing clauses so this sheet stands alone, and adds sources RISK-002 did not cover (Superhive/Botaniq, SpeedTree, CC0 sites).

## 1. What the budgets mean for any licensed model

From `assets/budgets.yaml` (ASSET-006): LOD0 3000-6000 triangles, LOD1 800-1500, LOD2 150-300, LOD3 under 50; max 3 primitives per LOD (1 at LOD3); height within 2% of the species spec; textures capped at 2048x2048 (fronds albedo) and 1024-class elsewhere. W4 conventions apply to every source: origin at trunk base, Z up, 0.15 m ground sink, collections `<model>_LOD0..3`, one UV map, alpha-mask cutout fronds (never Blend). So a licensed model is only a starting point for LOD0 shape and textures.

## 2. Candidate sources and licence terms

Redistribution column = reading for "can the model file ship inside a Community package that other people install". Quotes are verbatim; see RISK-002 for fuller context on the first four.

| # | Source / product | Species | Price | Licence | Redistribution clause (quoted) | Mod redistribution allowed? |
|---|---|---|---|---|---|---|
| A | Sketchfab, PlantCatalog "Realistic HD ..." series (CC BY). API read 2026-11-22: https://api.sketchfab.com/v3/models/94e5b980cb164cc6a8d56a3d5a004580 | robusta, filifera, canariensis; alexandrae (not cunninghamiana) | Free | CC BY 4.0 https://creativecommons.org/licenses/by/4.0/legalcode.txt | s2(a)(1): "reproduce and Share the Licensed Material, in whole or in part; and b. produce, reproduce, and Share Adapted Material." s3(a)(1): you must keep creator credit and "indicate if You modified the Licensed Material". API `requirements`: "Author must be credited. Commercial use is allowed." | **Yes**, with credit and a modification note. VERIFY: Sketchfab ToS for CC downloads; that the uploader could license under CC BY (RISK-002 Q4) |
| B | TurboSquid, 3D Model License https://blog.turbosquid.com/turbosquid-3d-model-license/ | all (individual listings) | VERIFY per listing (see section 3) | 3D Model License | 7(b): "3D Models must be contained in proprietary formats so that they cannot be opened or imported in a publicly available software application or framework, or extracted without reverse engineering." Quick Tips: "Giving away the 3D Model file itself is not allowed." Game mods are named as an allowed use. | **Unclear** (leans no). glTF in a package is openable; whether MSFS's packaged form counts is not stated |
| C | CGTrader, Royalty Free License https://www.cgtrader.com/pages/terms-and-conditions | all (individual listings) | VERIFY per listing | Royalty Free (21A) or per-listing Custom | 21A.2: "The Buyer's license to Product in this paragraph is strictly limited to Incorporated Product." 21A.6: "The resale or redistribution by the Buyer of any Product ... is expressly prohibited unless it is an Incorporated Product as licensed above." | **Unclear** (leans no) for the same extraction test; per-listing Custom License can change it |
| D | Fab Standard License https://www.fab.com/eula (summary only; full EULA unreadable) | robusta (modular set) | VERIFY | Fab Standard License | Summary: "Commercially distribute your Projects with the Fab assets incorporated into it"; may not "Resell or redistribute the asset for free on a standalone basis". Summary is "not legally binding". | **Unclear**. Favourable summary, binding text unread |
| E | Sketchfab store (Standard licence) https://sketchfab.com/licenses | queen palm (793k faces seen, not downloadable) | paid | Store licence | 2.2(b): not to "make available the Licensed Material as a stand-alone file ... or in a way that allows third parties to use, download, extract or access" it. | **No** as read (a package exposes the file). Dropped from consideration |
| F | Superhive Market (ex Blender Market): Botaniq (polygoniq) tropical palms; palms by Latin name not confirmed. https://superhivemarket.com/products/botaniq-trees/faq (read 2026-11-22) | VERIFY which species | Botaniq tiers read: $1.99 starter, $39.99 lite, $99.99 full (single seat) | Royalty Free, https://superhivemarket.com/page/royalty-free-license (read 2026-11-22) | "You may not resell, redistribute, or repackage the purchased product without explicit permission from the original creator" | **Unclear**. No game or extraction clause, but "redistribute, or repackage" is not defined. Assets are Blender-native (.paq pack); polygon counts not stated |
| G | SpeedTree (palm presets and SpeedTree-made palms). Unity support, "Can I sell assets made with SpeedTree" (updated June 12, 2026): https://support.unity.com/hc/en-us/articles/15723346606484-Can-I-sell-assets-made-with-SpeedTree | none confirmed by Latin name | not found | Unity Terms / SpeedTree Additional Terms (not read) | "Created Assets and Library Assets input into the SpeedTree Software can only be distributed in Licensed Productions." and "the sale or distribution of assets created within SpeedTree is strictly prohibited" | **Unclear** (leans no). Whether an MSFS add-on is a "Licensed Production" needs the unread terms. Search results also say a games licence tier exists (unverified) |
| H | OpenGameArt CC0 palms, e.g. "Exotic Palms Lowpoly style" https://opengameart.org/content/exotic-palms-lowpoly-style ; "Palm tree v2" https://opengameart.org/content/palm-tree-v2 (both read 2026-11-22); Quaternius "Ultimate Nature Pack" https://quaternius.itch.io/150-lowpoly-nature-models | generic palms, no SoCal species named | Free (Quaternius: "Name your own price") | CC0 | Exotic Palms: "This work is available in the public domain". Quaternius: "Creative Commons Zero v1.0 Universal". | **Yes** (CC0). Not species-accurate and low-poly stylised: not a fit for R-12 |

Not usable as a source at all: a Sketchfab search for CC0 palms (API, 2026-11-22) returned no usable palm tree (only a museum object and a fossil palm trunk).

## 3. Per-species candidate quality against the budgets

Face counts are Sketchfab API `faceCount` values (read 2026-11-22), assumed to be triangles (VERIFY: confirm in the downloaded glTF with `palmcore.assets` stats). Whole-series minimum/maximum come from paging the PlantCatalog series via the search API. LOD0 budget is 3000-6000 triangles.

| Species | Best clearly-licensed candidate (CC BY) | Faces | Height | Over LOD0 max (6000) by | Notes |
|---|---|---|---|---|---|
| `washingtonia_robusta` | PlantCatalog 6/10 (smallest of 10): https://sketchfab.com/3d-models/realistic-hd-mexican-fan-palm-610-94e5b980cb164cc6a8d56a3d5a004580 | 89,834 | 3.3 m (infant) | 15x | Mature 8/10 is 14.0 m, 162,290 faces (27x). Series max 233,717. Paid alternatives (TurboSquid ~$34, CGTrader ~$38, Fab modular set 34,732 polys total) are search summaries only, VERIFY |
| `washingtonia_filifera` | PlantCatalog 11/25 (smallest of 25): https://sketchfab.com/3d-models/realistic-hd-california-fan-palm-1125-475bdeaeff984bc8a161ea81a1a33fe8 | 48,236 | 3.6 m (infant) | 8x | Series max 152,286. The 3.5 m 16/25 has 51,124. Taller stages not individually checked |
| `phoenix_canariensis` | PlantCatalog 11/40 (smallest of 39 found): https://sketchfab.com/3d-models/realistic-hd-canary-island-date-palm-1140-ecee8c86810940ff8e6a683155d226ce | 54,605 | 2.1 m (infant) | 9x | Mature 25/40 is 16.1 m, 391,893 faces (65x). Series max 625,511. Also Sketchfab "Phoenix Canariensis" by Herve Rey, CC BY, 3,676,316 faces (far too heavy) |
| `syagrus_romanzoffiana` | Sketchfab "Queen Palm Tree" (CC Attribution; also a "from Poly by Google" copy): https://sketchfab.com/3d-models/none-2128328672f6410f9a37a4e0e08c9f8f | 3,888 | not stated | within budget | Only candidate already inside LOD0 range. VERIFY species identity, texture quality and CC BY version; likely cartoon-grade (R-12). Paid XfrogPlants Queen Palm: price/counts unread |
| `archontophoenix_cunninghamiana` | None for this species. Closest: PlantCatalog "Alexander palm" (*A. alexandrae*, a different species): 1/30 https://sketchfab.com/3d-models/realistic-hd-alexander-palm-130-71d56caaf00f468ebd18d35f11101928 | 9,201 | 1.7 m (infant) | 1.5x | Series range 9,201-88,707 among those paged. Species substitution is a user call (visual accuracy vs bangalow). RenderHub *A. cunninghamiana*: 2,212,026 polygons, licence agreement unread (RISK-002 1.5) |

Findings:
- The cheapest-to-use models (CC BY) are 8x-65x over the LOD0 budget and the small ones are infants, not 10-28 m street palms (spec heights in plan W5). Decimation of geometry-leaf models does not give a good cutout silhouette; expect fronds to be rebuilt as alpha-mask cards (LOD0 detail from the model used as reference and as a texture bake source). This is an estimate, not measured.
- Texture resolution and download formats for PlantCatalog were not readable without a Sketchfab login (VERIFY). Listings state "LODs included: Yes" and "Mesh type: static" but not LOD triangle counts.
- Attribution under CC BY adds a credits file inside the package and a note that the model was modified.

## 4. Remaining work per licensed model (estimates)

Baseline from the plan 03 task index (hours as listed there):

| Part | Hours |
|---|---|
| Robusta pilot chain ASSET-010..016 (4+5+3+4+4+3+4) | 27 |
| Each of the other 4 species, ASSET-x0..x3 (3+6+4+2) | 15 each, 60 total |
| ASSET-100 integration | 3 |
| **Species build total** | **90** |
| (of which LOD0 modelling: ASSET-011 5, 012 3, four x1 tasks 6 each) | 32 |

Phase 3 as a whole is about 120 h per the plan, including toolchain and tooling tasks (ASSET-003..008, ASSET-001/002) that do not change with the decision. Plan 03 section 5 and `plans/05-phases.md` say 20-40 h; plan 03 open question 15 records the mismatch.

What licensing can change: only the LOD0 modelling tasks (plan W9: "ASSET-011/012 become import and adapt"). Spec/material/texture, LOD1-3 (ASSET-x2/013), export, in-sim review and acceptance stay. Per licensed model, steps that still apply:

| Step | Estimate (h) | Basis |
|---|---|---|
| Download, inspect, check licence/credits, import into the species `.blend` | 0.5-1 | estimate |
| Scale/origin/ground-sink fixes to W4 | 0.5 | estimate |
| Reduce 50k-400k faces to 3-6k with alpha cards for fronds, bark bake | 3-6 | estimate; not measured, exceeds "import" |
| Per-height-variant rebuilds (W5 says a variant is a rebuild, not a rescale; licensed models come in fixed maturity stages) | 1-3 per variant | estimate |
| LOD1-3, materials, export | unchanged from build (ASSET-x2, x0) | plan |

Arithmetic bound: if LOD0 work cost nothing, licensing would save at most 32 of 90 h (about 35%). With the conversion steps above, any saving is likely a fraction of that. The 2-5 h per variant difference is not measurable until the robusta pilot (ASSET-011/012) records actual hours. These figures are planning estimates, not measurements.

## 5. Options

| | Build | License | Hybrid |
|---|---|---|---|
| What | All five species modelled in Blender (plan baseline) | Convert licensed models for LOD0, authoring LOD1-3 on top | Build some species, license others, or licensed LOD0 + hand-made LOD1-3 |
| Species build hours | 90 (plan, 27 pilot + 60 + 3) | no lower than 58 (90 minus all 32 LOD0 hours, a floor not a forecast); likely 70-88 (estimate) | between the two |
| Out-of-pocket cost | $0 | CC BY: $0. Paid listings: VERIFY (search summaries put them at about $5-39 each; unread). Botaniq read at $39.99-$99.99 | CC BY $0 + any paid |
| Redistribution risk | None | CC BY: low (credit and modification note). TurboSquid/CGTrader/Fab/Sketchfab store/Botaniq/SpeedTree: unclear to no (section 2) | Depends on which parts are licensed |
| Species gaps | None | No CC BY *A. cunninghamiana*; queen palm only a 3,888-face model of unverified quality | Build the gaps (king, queen) |
| Quality | Depends on Blender hours; R-12 risk | Higher fidelity reference; still needs cards and bake | Realistic CC BY reference for three species, build the rest |
| Reversibility | n/a | Replacing a licensed asset after publication means a package update | Same |

CC BY palms (robusta, filifera, canariensis) are the only paid-nothing, redistributable-by-licence route found; the hybrid line "CC BY for those three, build the other two" is therefore the cleanest licence story, but this is a description of the evidence, not a recommendation.

## 6. Open questions for the user (feed DEC-002)

1. DEC-001 provisional publish intent (yes / no / maybe)? Personal use leaves clauses B, C, D, E, F, G mostly moot; publishing makes the "extractable file" clauses central. Under "maybe", only CC BY, CC0 and self-built assets are safe by the quoted text.
2. Is substituting *A. alexandrae* for bangalow acceptable if licensing, or build king palm?
3. Is a credits/attribution file in the package acceptable (CC BY requirement)?
4. Budget for paid models, if any, and weekly Blender hours (decides how much the 90 h matters).
5. Does DEC-008 (storage) allow committing licensed source files? TurboSquid 10(b): "You may NOT re-distribute, publish, or make 3D Models available to any third party except in the form of a permitted Creation" (RISK-002 audited this); a public repo is therefore a separate risk from the package.
6. Accept the pilot default: build robusta first, record actual hours (ASSET-010..015), then re-decide for the other four.

## 7. VERIFY list

- Download formats and texture sizes of PlantCatalog models (needs Sketchfab login; not read).
- Whether Sketchfab `faceCount` equals triangles.
- Prices, counts and licence text for the CGTrader, TurboSquid and Fab listings named in RISK-002 section 2 (pages returned empty, 403, or are script-rendered).
- SpeedTree and Botaniq: species coverage by Latin name, full terms, any games tier.
- Queen palm CC BY model: species identity, texture quality.
- Everything in RISK-002's own VERIFY list (Fab full EULA, Sketchfab store clause 2.1, RenderHub agreement).

## Sources (all read 2026-11-22)

- https://api.sketchfab.com/v3/models/<uid> and /v3/search (PlantCatalog and queen palm facts)
- https://creativecommons.org/licenses/by/4.0/legalcode.txt
- https://blog.turbosquid.com/turbosquid-3d-model-license/ , https://www.cgtrader.com/pages/terms-and-conditions , https://sketchfab.com/licenses , https://www.fab.com/eula (via RISK-002)
- https://superhivemarket.com/page/royalty-free-license , https://superhivemarket.com/products/botaniq-trees/faq
- https://support.unity.com/hc/en-us/articles/15723346606484-Can-I-sell-assets-made-with-SpeedTree
- https://opengameart.org/content/exotic-palms-lowpoly-style , https://opengameart.org/content/palm-tree-v2 , https://opengameart.org/content/palm-tree-v2-low-poly-edition , https://quaternius.itch.io/150-lowpoly-nature-models
