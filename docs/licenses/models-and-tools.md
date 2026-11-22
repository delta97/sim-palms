# Model, texture and tool licenses audit (RISK-002)

**Purpose.** Record the terms that govern palm assets: candidate 3D model sources, texture sources, the MSFS 2024 SDK terms and the Blender exporter's license. DEC-002 (build or license models) and DEC-008 (binary storage) decide from this file. Risks covered: R-12 (palm models look wrong or cheap; consider licensing), R-14 (licensing if published), R-19 (licensed files end up somewhere their license forbids).

**Not legal advice.** The author is not a lawyer. Terms are quoted as of the date checked (all pages read **2026-11-22**) and may change. This file states what the text says; it does not say what is allowed or forbidden. Open points are phrased as questions and collected in "Questions for the user" at the end.

**Conventions.** "Quote" means text copied from the page on the date checked. `VERIFY:` marks anything not confirmed from a primary page. Where a page could not be fetched or read, that is stated. The column "Usable if published?" is a reading of the quoted terms (terms clear / unclear / restrictive), not a permission.

**Project context.** Personal use is the default (DEC-001). A built MSFS package necessarily contains the model files (glTF plus binary data and textures) and is copied to every user who installs it, so the clause that matters most for a purchased model is the one on redistribution inside a distributed product. Plan section 5 states the same concern: "Many stock model licenses forbid redistributing the model file, and a mod package does redistribute it."

**What could not be read (summary).**
- Fab: only the license summary on https://www.fab.com/eula was readable; the full EULA text below it was not in the page. The Epic mirrors returned HTTP 403.
- CGTrader and TurboSquid product pages: CGTrader product pages returned HTTP 202 with an empty body and TurboSquid's returned 403 to automated fetch, so candidate-model details for those two came from web search result summaries, not the listing pages. Each such row is marked `VERIFY:`.
- blender.org pages (license, FAQ): HTTP 403 to automated fetch. Blender's own manual was read instead.

---

## 1. Marketplaces

### 1.1 TurboSquid (3D Model License)

| Field | Finding |
|---|---|
| Terms URL | https://blog.turbosquid.com/turbosquid-3d-model-license/ (page text read in full). Text says: "This 3D Model License is effective for use with 3D Models for use on or after March 16, 2023." |
| License name | "The 3D Model License" (royalty free: "TurboSquid 3D Models are royalty free unless otherwise noted."). |
| Use in games or mods | Section 7: "Subject to the following restrictions, you may incorporate 3D Models in Creations of Computer Games, virtual worlds, simulation and training environments; mobile, desktop and web applications". The Games Uses list: "Allowed games uses: Console, PC, web, mobile games; Virtual and augmented reality; Game mods; Closed MMOs and closed Virtual Worlds.." "Computer Game" is defined to include "game mods". |
| Redistribution inside a distributed product | 7(a): "Your inclusion of 3D Models within any such Creation is limited to uses where 3D Model is contained in an interactive experience for the user and not made available outside of the interactive experience." 7(b): "You must take all reasonable and industry standard measures to incorporate 3D Models within Creations to prevent other parties from gaining access to 3D Models. 3D Models must be contained in proprietary formats so that they cannot be opened or imported in a publicly available software application or framework, or extracted without reverse engineering." Quick Tips: "Giving away the 3D Model file itself is not allowed." |
| Extraction risk | Same 7(b) clause, and the Games Uses text: "In general, to prevent your end-users from obtaining TurboSquid 3D Models, you should use proprietary formats that cannot be extracted, exported, or decompiled without reverse engineering." 7(c): "You typically may NOT include 3D Models in Creations that have the general functionality for importing and/or exporting 3D Models." |
| Public repository / sharing | 10(b): "You may NOT re-distribute, publish, or make 3D Models available to any third party except in the form of a permitted Creation, or shared as authorized in this agreement." Sharing (II.3) is limited to employees of the purchasing entity and to external parties "working in collaboration" on your Creation, who "must take reasonable care to secure and limit access to 3D Models to that purpose." 10(a): "You may NOT publish, distribute, or make 3D Models available through any online clearinghouse infrastructure." No clause about a public source repository was found; a public repo would be a form of "make 3D Models available to any third party". |
| Modification | Quick Tips: "May I modify a 3D Model? Yup, you are allowed to modify 3D Models to make your Creations. Please keep in mind that no matter how much you modify a 3D Model, it still may only be distributed as a Creation and is subject to the rules of the 3D Model License." II.2 grants the right to "adapt ... create derivative works". |
| Other | Editorial-labelled models: "Merchandising. No physical product for resale, video game, etc." and "may not be modified so that it no longer contains Depicted Intellectual Property." Machine learning on Imagery needs prior authorization (6(d)). Indemnity (V.6) excludes the buyer's modifications. |
| Date checked | 2026-11-22 |
| Usable if published? | **Unclear to restrictive.** Game mods are named as allowed, but the model must be in a format that "cannot be opened or imported in a publicly available software application" or "extracted without reverse engineering". Whether an MSFS package (see section 4.3) meets that is not stated by TurboSquid. Questions 1, 2, 3. |

### 1.2 CGTrader (Royalty Free License)

| Field | Finding |
|---|---|
| Terms URL | https://www.cgtrader.com/pages/terms-and-conditions (read in full; no effective date shown in the text). Section 20.2: "If the Seller does not indicate any licensing conditions in his posting, terms of Royalty Free license (see section 21A "Royalty Free License") shall be applicable." |
| License name | Royalty Free License (21A); variant "Royalty Free License, No AI" (21B); Editorial License (22); Custom License (sellers may add terms per listing). |
| Use in games or mods | 21A.2 lists approved use: "as purchased by a game's creators as part of a game if the Product is contained inside a proprietary format and displays inside the game during play, but not for users to re-package as goods distributed or sold inside a virtual world". "Game mods" are not named in the text read. |
| Redistribution inside a distributed product | Definition 8: "Incorporated Product – Product that cannot be extracted from an application or other product, services, creative works, research, content, data, or other value-added materials, and used as a stand-alone object without the use of reverse engineering tools or techniques." 21A.2: "The Buyer's license to Product in this paragraph is strictly limited to Incorporated Product. Any use or republication, including sale or distribution of Product that is not Incorporated Product is strictly prohibited." 21A.6: "The resale or redistribution by the Buyer of any Product, obtained from the Site is expressly prohibited unless it is an Incorporated Product as licensed above." |
| Extraction risk | 21A.3: "If you use any Product in software products (such as video games, simulations, or VR-worlds) you must take all commercially reasonable measures to prevent the end user from gaining access to the Product." Methods listed include "using a proprietary Product format" and "using a proprietary and/or password protected database or resource file that stores the Product data". |
| Public repository / sharing | 21A.1: "Products may not be sold, given, or assigned to another person or entity in the form it is downloaded from the Site or in 3D printed physical form." No clause about a public repository was found; see the same reading as TurboSquid. |
| Modification | The text read does not state a buyer right to modify in the Royalty Free section (21A.5: "Absent a written grant of rights greater than that contained in section 21 "Royalty Free License", all other rights or sub-divisions of rights generally included in copyright are excluded from this license and remain the property of Seller."). The "Incorporated Product" definition and the "approved ... use" list suggest incorporation, but modification is not spelled out. `VERIFY:` whether sections 20-21A (the "General Terms of Licensing", which was not separately checked for a modification clause) grant modification. |
| Other | Custom License terms in a listing can add to or change the above (section 23). Free-download products: "The Buyer may not use Products which are offered as a free download for machine learning or training neural networks purposes." (19.2). |
| Date checked | 2026-11-22 |
| Usable if published? | **Unclear to restrictive.** Same "Incorporated Product" test as TurboSquid. Modification not clearly granted. Per-listing Custom License terms must be read for each candidate. Questions 1, 2, 3. |

### 1.3 Sketchfab (store: Standard / Editorial license) and CC-licensed downloads

| Field | Finding |
|---|---|
| Terms URL | https://sketchfab.com/licenses (store "License Agreement", read in full; no effective date in the text). The page says "Sketchfab is a division of Epic Games, Inc." |
| License names | Store: "standard" and "editorial" licenses. Separately, many free downloadable models are published under Creative Commons licenses chosen by the author (see 1.3.1). |
| Use in games or mods | The store agreement text read does not name games or mods; it grants a license to "Reproductions" and "Licensee Work". `VERIFY:` the "Rights Granted" clause 2.1, not copied here. |
| Redistribution inside a distributed product | Simple version: "You may not use the 3D asset in a way that allows others to use or access the 3D asset as a stand-alone file (for instance, no sub-license or sale by you to others is allowed)." 2.2(b): not to "sell, license, distribute or otherwise make available the Licensed Material as a stand-alone file (or group of files) or in a way that allows third parties to use, download, extract or access the Licensed Material as a stand-alone file (or group of files)". 2.2(c): not to distribute the Licensee Work "if ... (ii) the primary value of the Licensed Work lies with the Licensed Material itself". |
| Extraction risk | The 2.2(b) wording "download, extract or access". Also: "Licensee shall maintain a robust firewall to safeguard against unauthorized third-party access to the Licensed Material." |
| Public repository / sharing | Same 2.2(b); also "Licensee may not make additional high-resolution copies of the Licensed Material ... Licensee may make one (1) high-resolution backup copy of the Licensed Material for security purposes only." |
| Modification | Simple version: "You may edit an asset only if its editorial quality is not altered" applies to editorial assets only; for the standard license the text read lists "What is forbidden?" items but no general ban on modification. Editorial: "shall not otherwise be altered under any circumstances" (2.4). |
| Date checked | 2026-11-22 |
| Usable if published? | **Restrictive** for store models: "primary value ... lies with the Licensed Material itself" and "extract or access" language are hard to meet when a package ships the model. Questions 1, 2. See 1.3.1 for CC downloads. |

#### 1.3.1 Creative Commons models on Sketchfab (PlantCatalog)

Several palm models listed in section 2 are free downloads under "CC Attribution". Sketchfab's API (https://api.sketchfab.com/v3/models/<uid>, read 2026-11-22) reports for the PlantCatalog models: license "CC Attribution", `url` http://creativecommons.org/licenses/by/4.0/, `requirements` "Author must be credited. Commercial use is allowed.", `isDownloadable` true.

CC BY 4.0 legal code (https://creativecommons.org/licenses/by/4.0/legalcode.txt), section 2(a)(1): "the Licensor hereby grants You a worldwide, royalty-free, non-sublicensable, non-exclusive, irrevocable license to exercise the Licensed Rights in the Licensed Material to: a. reproduce and Share the Licensed Material, in whole or in part; and b. produce, reproduce, and Share Adapted Material." Section 3(a)(1): "If You Share the Licensed Material (including in modified form), You must: a. retain the following if it is supplied by the Licensor with the Licensed Material: i. identification of the creator(s)... b. indicate if You modified the Licensed Material and retain an indication of any previous modifications".

Reading: the CC BY text permits sharing and adapting with credit and a modification note; it has no "no extraction" clause. `VERIFY:` Sketchfab's own terms of service for CC downloads (not read), whether the uploader (PlantCatalog, an e-on software product line per the description link https://info.e-onsoftware.com/plantcatalog/) had the right to license under CC BY, and whether the license on each model is still CC BY at download time. Question 4.

### 1.4 Fab (Fab Standard License)

| Field | Finding |
|---|---|
| Terms URL | https://www.fab.com/eula. **Only the summary was readable**; the full EULA text was not in the fetched page. https://www.epicgames.com/site/en-US/fab-eula and https://www.unrealengine.com/en-US/eula/fab returned HTTP 403. |
| License name | "Fab Standard License" (EULA), plus CC-BY for items whose seller picks it. |
| Summary text (not legally binding, per the page) | "Note: This summary of license terms is for your convenience only and is not legally binding. Please be aware that the full text of the Fab EULA below explains the Fab Standard License and is what is binding legally." You may: "Use the assets commercially or privately"; "Modify and adjust the assets in order to incorporate them into your Projects"; "Commercially distribute your Projects with the Fab assets incorporated into it"; "Use the assets with any compatible tools (usage is not limited to Unreal Engine)"; "Share the asset (directly, via a private repository or in the Project) with your collaborators that are working on the Project with you". You may not: "Resell or redistribute the asset for free on a standalone basis or allow others to do the same". |
| Use in games or mods | Summary says "Projects" and "any compatible tools"; mods are not named. `VERIFY:` full text. |
| Redistribution inside a distributed product | Summary: "Commercially distribute your Projects with the Fab assets incorporated into it". The summary says nothing on extraction protection. `VERIFY:` full text. |
| Public repository | Summary mentions only a "private repository" for collaborators. A public repository is not addressed. |
| Modification | Summary: "Modify and adjust the assets in order to incorporate them into your Projects". |
| Date checked | 2026-11-22 (summary only) |
| Usable if published? | **Unclear.** The summary reads favourably for incorporation into a distributed Project and unfavourably for standalone redistribution, but the binding text is unread. Question 5. |

### 1.5 Not audited

RenderHub (the only listing found for Archontophoenix cunninghamiana at high resolution, section 2) says on the listing: "This item comes with our Extended Use Licensing. This means that you may use the model for both non-commercial and commercial purposes, in a variety of mediums and applications. For full license terms, see our 3D Content Licensing Agreement". The agreement was not read (the URL tried, https://www.renderhub.com/info/licensing, returned 404; the agreement page was not located). `VERIFY:` its terms before considering that listing.

---

## 2. Candidate models

Per species, up to 2 candidates. Sources: Sketchfab's API (facts read directly) unless marked "search summary", which means the product page itself could not be read and the details come from a web search result and must be confirmed (`VERIFY:`). Prices were not available for Sketchfab downloads (free). "LODs" means the listing states LODs are included; no LOD count or triangle count per LOD was checked.

**Washingtonia robusta (Mexican fan palm)**

| # | Candidate | Price | Triangles / polys | Formats | LODs | License | Usable if published? |
|---|---|---|---|---|---|---|---|
| 1 | Sketchfab "Realistic HD Mexican fan palm (8/10)" by PlantCatalog. https://sketchfab.com/3d-models/realistic-hd-mexican-fan-palm-810-00bd2ea54eb1405bb056eac3f1e14673 . Adult, 14.0 m, "Mesh type: static", "exported at 40% of its maximum mesh resolution". | Free download | 162,290 faces, 113,452 vertices (API); description: "Better used for Hi Poly workflows!" | `VERIFY:` download formats (not queried) | "LODs included: Yes" | CC BY 4.0 | Terms clear (CC BY), see 1.3.1; asset heavy for MSFS LOD0. |
| 2 | Fab "Modular Mexican Fan Palm Tree - Washingtonia Robusta" (KangaroOz 3D). https://www.fab.com/listings/4b4f6075-c756-4d86-a78f-1770f141f615 . Modular set. | `VERIFY:` price (page is script-rendered, not captured) | "Polygons : 34732" (whole set, 35 objects) | Listing: "LODs : Yes (inside FBX for Unity & Unreal)"; Blender native 3.1 | "Numbers of LODs : 5" (LOD5 is a billboard) | Fab Standard License (assumed from marketplace; the listing's "License terms" were not read) `VERIFY:` | Unclear (section 1.4). |

Other listings seen (search results, not read): TurboSquid "Washingtonia robusta" https://www.turbosquid.com/3d-models/washingtonia-robusta-415521 ($34 per summary), CGTrader "Washingtonia robusta Mexican Fan Palm" (Balance Connected, $38, 6 variations per summary). `VERIFY:` all.

**Washingtonia filifera (California fan palm)**

| # | Candidate | Price | Triangles / polys | Formats | LODs | License | Usable if published? |
|---|---|---|---|---|---|---|---|
| 1 | Sketchfab "Realistic HD California fan palm (16/25)" by PlantCatalog. https://sketchfab.com/3d-models/realistic-hd-california-fan-palm-1625-4713907b63c0432599389b613e85d9e0 . Infant, 3.5 m, 2808 leaves. | Free download | 51,124 faces, 39,868 vertices (API) | `VERIFY:` | "LODs included: Yes" | CC BY 4.0 | Terms clear (CC BY), see 1.3.1. Young palm only; other maturity stages exist in the same series (not checked). |
| 2 | CGTrader "Washingtonia filifera California fan palm" (Balance Connected), https://www.cgtrader.com/3d-models/plant/bush/washingtonia-filifera-california-fan-palm . | $39.00 (search summary) `VERIFY:` | `VERIFY:` | FBX (search summary) | `VERIFY:` | Royalty Free License (search summary) | Unclear to restrictive (section 1.2). |

**Phoenix canariensis (Canary Island date palm)**

| # | Candidate | Price | Triangles / polys | Formats | LODs | License | Usable if published? |
|---|---|---|---|---|---|---|---|
| 1 | Sketchfab "Realistic HD Canary Island date palm (25/40)" by PlantCatalog. https://sketchfab.com/3d-models/realistic-hd-canary-island-date-palm-2540-2b4a6b2b78164048a7fde77c7387735d . Old, 16.1 m, 61,698 leaves. | Free download | 391,893 faces, 335,579 vertices (API) | `VERIFY:` | "LODs included: Yes" | CC BY 4.0 | Terms clear (CC BY); very heavy mesh. |
| 2 | TurboSquid "AV Plant Phoenix Canariensis Palm Tree 03", https://www.turbosquid.com/3d-models/3d-av-plant-phoenix-canariensis-palm-tree-03-2629020 (an "-model-2609155" listing also exists). | $5 (search summary) `VERIFY:` | `VERIFY:` | 3ds Max, Blender, OBJ, FBX (search summary) | `VERIFY:` | TurboSquid 3D Model License (section 1.1) | Unclear to restrictive. |

**Syagrus romanzoffiana (queen palm)**

| # | Candidate | Price | Triangles / polys | Formats | LODs | License | Usable if published? |
|---|---|---|---|---|---|---|---|
| 1 | Sketchfab "Queen Palm Tree" (also "Queen Palm Tree from Poly by Google"). https://sketchfab.com/3d-models/none-2128328672f6410f9a37a4e0e08c9f8f (uid 2128328672f6410f9a37a4e0e08c9f8f), published 2021-04-06. | Free download | 3,888 faces (API) | `VERIFY:` | None stated | CC BY 4.0 per API label "CC Attribution" (license version not read) | Terms clear (CC BY) if the model is correctly species-identified. `VERIFY:` the model's species (title only, no Latin name in the description read); it is a very low-poly model that likely will not meet street-level quality (R-12). |
| 2 | CGTrader "XfrogPlants Queen Palm", https://cgtrader.com/3d-models/plant/other/xfrogplants-queen-palm . | $19.99 (search summary) `VERIFY:` | `VERIFY:` | Maya, OBJ, FBX, Cinema 4D (search summary) | `VERIFY:` | "Royalty Free License, No AI" (search summary) | Unclear to restrictive (section 1.2). |

Sketchfab store models found for this species (e.g. "GTV queen palm mature A", 793,300 faces, license "Standard", `isDownloadable` false) are store assets under section 1.3 and were not considered further.

**Archontophoenix cunninghamiana (bangalow / king palm)**

No PlantCatalog model exists in the Sketchfab search results for this species; the CC-licensed "Realistic HD Alexander palm" series is *Archontophoenix alexandrae*, a different species, and is not listed. Many marketplace listings titled "king palm" are alexandrae (search summary), so the Latin name must be checked on each.

| # | Candidate | Price | Triangles / polys | Formats | LODs | License | Usable if published? |
|---|---|---|---|---|---|---|---|
| 1 | RenderHub "Archontophoenix Cunninghamiana - King Palm" by moradalia, published Sep 12, 2024. https://www.renderhub.com/moradalia/archontophoenix-cunninghamiana-king-palm | `VERIFY:` price (not captured) | "Polygons:2,212,026", "Vertices:1,347,023" ("Game Ready: Yes" on the listing) | Download size 95.7 MB; `VERIFY:` formats | None stated | "Extended Use License" (agreement not read, section 1.5) | Unclear. |
| 2 | CGTrader "XfrogPlants Bangalow Palm", https://www.cgtrader.com/3d-models/plant/other/xfrogplants-bangalow-palm | `VERIFY:` | `VERIFY:` | `VERIFY:` | `VERIFY:` | "royalty-free license" (search summary) | Unclear to restrictive (section 1.2). |

**Findings across species.** Only the free Sketchfab PlantCatalog models (CC BY) have a license that reads as clear for redistribution. They are very high triangle counts for MSFS LOD0 (51k to 392k faces), so they would need LOD authoring or decimation (note CC BY requires a modification notice). No CC-licensed model was found for *Archontophoenix cunninghamiana* or a confirmed one for *Syagrus romanzoffiana* at usable quality. Paid models were not read at the listing level for CGTrader or TurboSquid.

---

## 3. Textures

### 3.1 Poly Haven

| Field | Finding |
|---|---|
| Terms URL | https://polyhaven.com/license (read in full) |
| License | CC0. "Our assets are all licensed as CC0, which is effectively Public Domain even in jurisdictions that do not support the Public Domain." |
| Redistribution / games | "You can use our assets for any purpose, including commercial work." "You can redistribute them, share them around, include them when sharing your own work, or even in a product you sell." "You do not need to give credit or attribution when using them (although it is appreciated)." |
| Site terms | "All content on this website, excluding the CC0 assets themselves, is protected by intellectual property laws." (4.1; example content includes asset example renders.) "Web scraping or data mining without express permission" is listed under disruption of the site (3.2); bulk download should use their API under separate API Terms (5), `VERIFY:` those API terms (not read). |
| Date checked | 2026-11-22 |
| Usable if published? | **Terms clear** (CC0). Includes 3D models and textures; palm-specific bark or frond assets were not searched on the site. |

### 3.2 ambientCG

| Field | Finding |
|---|---|
| Terms URL | https://docs.ambientcg.com/license/ (read in full) |
| License | "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License. This applies to the downloadable asset files and the material preview renders shown for each asset on the site." |
| Redistribution / games | "You can copy, modify, distribute and perform the assets, even for commercial purposes, all without asking permission. You can include the raw files in your project, for example a video game." Credit not required ("You don't need to give credit but I would of course appreciate it"), suggested text: "Created using <asset name> from ambientCG.com, licensed under the Creative Commons CC0 1.0 Universal License." |
| Date checked | 2026-11-22 |
| Usable if published? | **Terms clear** (CC0). |

### 3.3 Bark and frond texture sources

No palm-specific bark or frond texture source was audited. The model listings above carry their own textures under the model's license (for example the Fab set states "All textures are PBR ready and available in 2K"). Candidates to check if needed: a Poly Haven or ambientCG search for palm bark (not done); photographs taken by the user (no third-party terms). `VERIFY:` whether either site offers CC0 palm frond alpha textures; this was not searched.

---

## 4. Tools

### 4.1 MSFS 2024 SDK terms

| Field | Finding |
|---|---|
| Terms URL | https://docs.flightsimulator.com/msfs2024/retail/introduction/sdk-eula/ ("SDK EULA", page footer "(c)2026 Microsoft"). An older copy of the same text for the 2020 SDK is at https://docs.flightsimulator.com/html/Introduction/SDK_EULA.htm. Both read; the 2024 text refers to "MSFS 2024 Add-Ons". |
| Scope | "'MSFS 2024 Add-Ons' – add-ons, modifications, and plugins for MSFS 2024"; "'Purpose' – to develop MSFS 2024 Add-Ons"; "You may install and use the Software solely for the Purpose stated above." |
| Ownership of your add-ons | "Subject to Microsoft's existing ownership rights in the Software, you will retain any ownership rights you may have in your MSFS 2024 Add-Ons." |
| Sample content | "The Software may include sample content (e.g., models, meshes, gauges, and sound files). You may use such content solely internally and for assisting with the Purpose. You are expressly prohibited from using the sample content for any other purpose, including any external distribution, display, or performance of the sample content." Relevance: SDK sample palms or textures must not be shipped in a published package. |
| Distribution of built packages | The EULA text read contains no clause on distributing packages built with `fspackagetool`, and no statement on the license of build output. The prohibition on distributing the Software has an exception: "share, publish, distribute, or lend the Software (except for any distributable code, subject to the terms above)"; the EULA does not define what is "distributable code". |
| Restrictions touching this project | "You are prohibited from using the Software, including any of its components, for the development of a competing flight simulator product or for the purpose of competitive benchmarking, competitive analysis, AI or machine learning, or intelligence gathering." and "Microsoft may disqualify any MSFS 2024 Add-Ons for any reason, including security, reputational or compatibility concerns." |
| Package tool | https://docs.flightsimulator.com/msfs2024/retail/sdk-tools/package-tool/ (index page read; it holds no license text). `VERIFY:` whether the built package format (what the Community folder or flightsim.to download actually contains) stores model files as readable glTF/bin or in a protected form. Not found in the pages read. This decides whether the "proprietary format / cannot be extracted" clauses in section 1 are met. |
| Third-party EULAs on distribution channels | Not read: Microsoft Flight Simulator Marketplace content-creator terms; the flightsim.to creator terms (a PDF appeared in search results at https://flightsim.to/attachments/creators-program-terms.pdf, not fetched). `VERIFY:` |
| Date checked | 2026-11-22 |
| Usable if published? | **Unclear.** The EULA says nothing about distributing built add-ons, other than that you keep ownership of your add-ons and may not distribute sample content. Questions 2, 6. |

### 4.2 Blender exporter `io_scene_gltf2_msfs_2024`

| Field | Finding |
|---|---|
| Where it comes from | SDK docs (https://docs.flightsimulator.com/msfs2024/retail/models-and-textures/plugins/blender-plugin/the-blender-plugins/): "The SDK installation supplies two separate plugins for blender available in the following locations: [SDK ROOT]\Tools\Blender\addons\io_scene_gltf2_msfs_2024". |
| License of the 2024 exporter | **Not confirmed.** The SDK is not installed in this checkout, so the license file in `[SDK ROOT]\Tools\Blender\addons\io_scene_gltf2_msfs_2024` was not read. `VERIFY:` read the license file or header comment there. No public repository named io_scene_gltf2_msfs_2024 was found (GitHub search for the name returned 0 repositories). |
| License of the 2020 exporter (same maker, public repo) | https://github.com/AsoboStudio/Microsoft-Flight-Simulator-2020-glTF-Blender-IO (formerly glTF-Blender-IO-MSFS; GitHub API license field: "Apache License 2.0", SPDX Apache-2.0; LICENSE.md starts "Apache License Version 2.0, January 2004"). Source header of `addons/io_scene_gltf2_msfs_2020/__init__.py`: "Copyright 2021-2022 The glTF-Blender-IO-MSFS-2020 authors. # Licensed under the Apache License, Version 2.0". README: "This repository contains the current version of the official Microsoft Flight Simulator 2020 Blender Import/Export plugin." Branches include `update_to_blender_4_5`; the repository was last pushed 2026-06-01. The README says the add-on needs the "Import-Export: gltf 2.0 format" (Khronos) add-on enabled. This is the 2020 plugin; it does not show the 2024 plugin's terms. |
| Output files | The SDK docs say the exporter "will create the *.gltf, *.bin and *.xml files required for a MSFS 2024 package". No statement on output licensing was found in the pages read. Whether the 2024 plugin carries the same Apache-2.0 terms as the 2020 one is unconfirmed. |
| Other terms | Auto LOD: "You must be in possession of a licensed copy of the Simplygon SDK to be able to use this feature. The Simplygon Licence should be installed here: C:\Users\<Username>\AppData\Local\Microsoft\SimplygonSDK" (exporter page, https://docs.flightsimulator.com/msfs2024/retail/models-and-textures/plugins/blender-plugin/the-blender-exporter/). Relevant if Auto LOD is used. `VERIFY:` how a Simplygon license is obtained. |
| Date checked | 2026-11-22 |
| Usable if published? | **Unclear** for the 2024 exporter (license unread); **terms clear** (Apache-2.0) for the 2020 sibling. Question 7. |

### 4.3 Blender

| Field | Finding |
|---|---|
| Terms URL | Blender manual, "About Free Software and the GPL", https://docs.blender.org/manual/en/latest/getting_started/about/license.html (read; "Last updated on 2026-11-22"). blender.org's own license page and FAQ returned HTTP 403, so Blender's FAQ statement on output could not be quoted; this manual page is the quote source. |
| License | GPL (Blender application). Manual: "When a program is licensed under the GNU General Public License (the GPL): You have the right to use the program for any purpose. ... You must provide a copy of the GPL with the program, so that recipients are aware of their rights under the license." |
| Output files | Manual note: "The GPL only applies to the Blender application and not the artwork you create with it; for more info see the Blender License." The "Blender License" page (https://www.blender.org/about/license/) was not readable. `VERIFY:` its wording and the FAQ entry on files created with Blender. |
| Python add-ons | Blender's own blog (https://code.blender.org/2019/06/blender-is-free-software/): "Blender's scripting API is an integral part of the software. Blender add-ons work, look and feel like Blender features." and "Paying for an add-on can only mean access to the add-on download service… offering it to you as GNU GPL." This is a developer's opinion post, not a license text. It matters only if the project writes its own Blender add-on and distributes it. |
| Date checked | 2026-11-22 |
| Usable if published? | **Terms clear** for models authored in Blender per the manual note, with `VERIFY:` on the primary blender.org page. |

---

## Summary table

| Source | License | Redistribution of the model file in a package | Usable if published? | Questions |
|---|---|---|---|---|
| TurboSquid | 3D Model License | Allowed only in a form that "cannot be opened or imported in a publicly available software application or framework, or extracted without reverse engineering" | unclear to restrictive | Q1, Q2, Q3 |
| CGTrader | Royalty Free (and Custom per listing) | Only as "Incorporated Product" (cannot be extracted without reverse engineering) | unclear to restrictive | Q1, Q2, Q3 |
| Sketchfab store | Standard / Editorial | Not as a file or in a way that allows "download, extract or access" | restrictive | Q1, Q2 |
| Sketchfab CC BY downloads | CC BY 4.0 | Sharing and adapting allowed with credit and a modification note | terms clear | Q4 |
| Fab | Fab Standard License (summary only read) | Summary: projects with assets incorporated may be distributed; standalone redistribution not | unclear | Q5 |
| Poly Haven | CC0 | Free to redistribute | terms clear | none |
| ambientCG | CC0 | Free to redistribute | terms clear | none |
| MSFS 2024 SDK EULA | Microsoft SDK terms | No clause on packages; sample content may not be distributed | unclear | Q2, Q6 |
| Exporter `io_scene_gltf2_msfs_2024` | Not confirmed (2020 sibling: Apache-2.0) | n/a | unclear | Q7 |
| Blender | GPL (application); artwork not covered, per manual | n/a | terms clear (VERIFY primary page) | Q8 |

---

## Questions for the user

1. (Sections 1.1, 1.2, 1.3) TurboSquid, CGTrader and Sketchfab store terms all hinge on whether a model "cannot be extracted" from the distributed product. If you want to publish a package, are you willing to ask the vendor (or TurboSquid at use@turbosquid.com, which the 3D Model License gives for "New Use" requests) to confirm in writing that an MSFS package is acceptable, before buying?
2. (Sections 1.1-1.3, 4.1) Can someone confirm what a built MSFS 2024 package physically contains (readable .gltf/.bin and textures, or a protected container)? I could not find this in the SDK pages read. Do you want a task to inspect a package from the SDK samples (without redistributing any sample content)?
3. (Section 1) Retail licenses say that sharing is allowed only with collaborators on the project. If DEC-008 puts models in a repository, should that repository stay private, with only manifests and a download script public?
4. (Section 1.3.1) The free PlantCatalog CC BY palms (species 1, 2 and 3 in section 2) read as the cleanest option but are heavy (51k to 392k faces). Do you want to pursue them (credit text, modification note, own LODs) as the first-species candidate under DEC-002? Also, should someone check Sketchfab's terms and PlantCatalog's rights to license them?
5. (Section 1.4) Fab's full EULA could not be read. Can you read https://www.fab.com/eula in a browser and paste the clauses on distribution, extraction and mods, or confirm that a Fab model may be used in a free MSFS mod?
6. (Section 4.1) The SDK EULA is silent on distributing built add-ons. Should the Marketplace and flightsim.to creator terms be read next (the flightsim.to PDF URL is in section 4.1)? Which channel do you intend (DEC-010)?
7. (Section 4.2) Please check the license file inside `[SDK ROOT]\Tools\Blender\addons\io_scene_gltf2_msfs_2024` on a machine that has the SDK installed and paste it (or confirm the SDK path so a session can read it).
8. (Section 4.3) Blender's license and FAQ pages were blocked to automated fetch. Do you want a manual read of https://www.blender.org/about/license/ to confirm the output-files wording?
9. (Section 2) For *Archontophoenix cunninghamiana* and *Syagrus romanzoffiana*, no cleanly licensed, well-identified model was found. Is it acceptable to build these two from scratch (DEC-002 "build"), or should a license for a retail model be pursued after question 1 is answered?
10. (Section 2) Do you want the CGTrader and TurboSquid listings (price, triangle count, LODs, any Custom License terms) read in a browser? They were not readable by automated fetch, so their details are search-summary level only.
