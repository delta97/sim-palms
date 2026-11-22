# Data source licenses and terms audit (RISK-001)

**Purpose.** Record, for every data source the pipeline may use, the license or terms, the exact clauses on redistribution, derived works and attribution, and what is still unknown. DEC-009, DEC-001 and DEC-010 decide from this file. Risks covered: R-14 (licensing if published), R-15 (source disappears).

**Not legal advice.** The author is not a lawyer. Terms are quoted as of the date checked (all pages read **2026-11-22**) and may change. This file states what the text says; it does not say what is allowed or forbidden. Open points are phrased as questions and collected in "Questions for the user" at the end.

**Conventions.** "Quote" means text copied from the page on the date checked. `VERIFY:` marks anything not confirmed from a primary page. Where a page could not be fetched, that is stated.

**Project context.** Personal use is the default (DEC-001). The pipeline's likely outputs are (a) a database of palm positions and attributes derived from tree inventories and LiDAR, and (b) MSFS scenery packages built from it. Whether (a) or (b) would count as a "derived" thing under each license is the central question per source.

---

## 1. LA County street tree compilation (stiles/la-trees)

| Field | Finding |
|---|---|
| Terms URL | https://github.com/stiles/la-trees (README), https://raw.githubusercontent.com/stiles/la-trees/main/LICENSE |
| License | MIT License, "Copyright (c) 2024 Matt Stiles" (LICENSE file). The file does not say whether it covers the repository's code only or also the data. |
| Redistribution clause | MIT text: "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software". The MIT text refers to "Software"; it does not mention data. |
| Attribution | MIT: "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." README Sources section: "Records collected from municipalities via the California Public Records Act or official open-data portals. Population via the US Census Bureau." |
| Share-alike / derived data | None in the MIT text. No separate data-terms statement found in the README. |
| Accuracy disclaimer | README: "I can't guarantee the accuracy or completeness of the data." MIT: "THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND". |
| Date checked | 2026-11-22 |
| Alternate download (R-15) | Per-municipality files in the repo (geojson, shapefile, some csv); LA city street trees on the author's S3 (links in README, e.g. https://stilesdata.com/trees/los-angeles/la_street_trees_latlon.geojson, "current as of May 3, 2026"). The repo is a third-party copy; the municipalities are the original sources (see sections 2 and 3). |

**Other facts from the README (read 2026-11-22).** The repo holds "1.6 million records of individual trees in 40+ cities collected in recents years as a hobby project and during my time as a reporter at the Los Angeles Times". The LA city layer is downloaded by script from the city's TreeKeeper WFS service (`streetsla_UFDSpeciesLabel`). A separate NGA 2012 dataset (8.9M trees, no species) is mirrored; the README says the agency "took the data down" from its original USGS server after the author asked about timeouts. This is a concrete R-15 example.

**Unconfirmed.**
- `VERIFY:` Whether the MIT license reaches the data at all. The records originate with municipalities, so the compiler's license may not be the only terms that apply. The repo contains per-city folders; whether any folder carries its own license or README was not checked (only the root LICENSE and README were read).
- `VERIFY:` Terms of each source city for the cities used. Only LA city (section 2) and San Diego (section 3) were audited here.

---

## 2. StreetsLA (City of Los Angeles) tree inventory

| Field | Finding |
|---|---|
| Terms URL | Inventory page: https://streets.lacity.gov/resources/tree-inventory. Site disclaimer linked in its footer: https://disclaimer.lacity.org/disclaimer.htm. Fetched: inventory page yes (HTTP 200); the disclaimer page body did not load as text (no readable text retrieved); https://streets.lacity.gov/disclaimer returned HTTP 403 to WebFetch and a page with no disclaimer text to curl. |
| License | None stated on the inventory page. No license name found. |
| Redistribution clause | None found. Pages searched: the inventory page (text read in full), the streets.lacity.gov disclaimer page (no text retrieved), the LA GeoHub search API for "street trees" and "Davey tree inventory" (see below). |
| Attribution | None found on the pages above. |
| Share-alike / derived data | None found. |
| Accuracy disclaimer | None found on the inventory page. `VERIFY:` the citywide disclaimer text at https://disclaimer.lacity.org/disclaimer.htm could not be read. |
| Date checked | 2026-11-22 |
| Alternate download (R-15) | The city's TreeKeeper site is linked from the inventory page: https://losangelesca.treekeepersoftware.com/. The la-trees README (section 1) says its script pulls the same inventory from the city's WFS service and mirrors it to S3. LA GeoHub search (API query "street trees", 2026-11-22) returned a "Trees (Bureau of Street Services)" item with the description "This is an historical inventory of trees along the streets of the City" and the note "Please be aware that this dataset is not actively being maintained", with no license text. |

**What the page says about the data.** "StreetsLA contracted Davey Resource Group to conduct the first inventory of our tree canopy in decades", covering "over 660,000 street trees". The page links the inventory of trees on streets, managed by StreetsLA, and in parks, managed by the Department of Recreation and Parks (the links go to the TreeKeeper site and an ArcGIS StoryMap). The footer shows "(c) Copyright 2026 City of Los Angeles. All rights reserved." (site footer, not a statement about the inventory data).

**Unconfirmed.** `VERIFY:` the TreeKeeper site's terms (not fetched), and whether the inventory data is published under any open-data terms. The la-trees README notes "gnarly authentication and rate-limiting issues" for TreeKeeper's internal APIs. The compiler's README names the California Public Records Act as the route used for other cities.

---

## 3. City of San Diego street trees

| Field | Finding |
|---|---|
| Terms URLs | Layer: https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20 (name "Trees (Street Trees)"; item info at `.../MapServer/20/iteminfo?f=pjson`). Portal terms: https://data.sandiego.gov/help/guides/terms/. Portal FAQ: https://data.sandiego.gov/help/guides/faq/. Site disclaimers: https://www.sandiego.gov/disclaimers. All fetched OK. |
| License | No named license on the layer. The layer's `licenseInfo` (item info) is a disclaimer text (below), not a license grant. The portal Terms of Use contain no license grant: "These Terms of Use do not grant You any title or right to any patent, copyright, or other such intellectual property rights that the City or others may have in the Data." (Section IV). |
| Redistribution clause | None specific to this layer. Portal FAQ: "There are no limitations on usage or redistribution of the data available here. However, please review the portal's Terms of Use for complete details." The Terms define "Derivative Work" as "a work that is based in any way or to any extent on the Data including without limitation any work that uses any of the Data in a modified form" (Section III) and bind users on download or use: "Downloading or using any of the Data or any Derivative Work, in which case you understand and agree that the City will treat your download or use of the Data or a Derivative Work as an acceptance of the Terms of Use" (Section II.A). Section VII: "For certain of the Data, there may be additional terms and conditions that are stated in the file containing such Data or on the page from which such Data is accessed. You understand and agree that You are bound by such additional terms and conditions." |
| Attribution | No attribution requirement found in the Terms or FAQ. The layer's `copyrightText`: "This layer was created and is maintained by the City of San Diego's Transportation Department. Data sources include SanGIS, city records, aerial imagery, and field surveys. The data was processed and managed using ArcGIS software from Esri." |
| Share-alike / derived data | None. Indemnity reaches derived works: "You shall indemnify and save harmless the City, from any claim, loss, damage, injury or liability of any kind ... that arise directly or indirectly, in whole or in part, from Your use of the Data, including without limitation Your use of the Data in a Derivative Work." (Section VI.B). |
| Accuracy disclaimer | Terms V.A: "The City makes no representation or warranty that the information contained in the Data is accurate, true or correct." Layer `licenseInfo`: "This data is provided on an "AS IS", "AS AVAILABLE" and "WITH ALL FAULTS" basis." and "In using these data, you further agree to indemnify, defend, and hold harmless SanGIS and City of San Diego for any and all liability of any nature arising out of or resulting from the lack of accuracy or correctness of the data, or the use of the data." Layer description: "Users are encouraged to contact the City of San Diego's Street Division if discrepancies are found between dataset attributes and physical observations." |
| Date checked | 2026-11-22 |
| Alternate download (R-15) | The ArcGIS REST layer itself (supports query and export). `VERIFY:` whether the trees dataset is also listed on data.sandiego.gov; a web search found other datasets there under an Open Data Commons PDDL license, but no confirmed trees dataset page. The URL pattern tried (`/datasets/trees/`) returned 404. |

**Notes.** Layer metadata shows the source table as TSD.TREE and a metadata date of 2026-06-30 (from `.../MapServer/20/metadata`). The Terms page shows no effective date; Section VIII.E says changes are "effective upon posting".

**Unconfirmed.** `VERIFY:` whether the portal Terms of Use (a click-through for the open data portal) apply to a layer downloaded from the webmaps REST service rather than the portal. The layer's own `licenseInfo` names "SanGIS and City of San Diego"; SanGIS's own terms pages tried (https://sangis.org/disclaimer/ and /download/) returned 404.

---

## 4. OpenStreetMap

| Field | Finding |
|---|---|
| Terms URLs | https://www.openstreetmap.org/copyright ; license text https://opendatacommons.org/licenses/odbl/1-0/ ; attribution guideline https://osmfoundation.org/wiki/Licence/Attribution_Guidelines (page "last edited on 10 September 2026"). All fetched OK. |
| License | Open Data Commons Open Database License (ODbL) 1.0. OSM page: "OpenStreetMap is open data, licensed under the Open Data Commons Open Database License (ODbL) by the OpenStreetMap Foundation (OSMF)." |
| Redistribution clause | OSM page: "You are free to copy, distribute, transmit and adapt our data, as long as you credit OpenStreetMap and its contributors. If you alter or build upon our data, you may distribute the result only under the same license." ODbL 4.2: "If You Publicly Convey this Database, any Derivative Database, or the Database as part of a Collective Database, then You must: a. Do so only under the terms of this License or another license permitted under Section 4.4; b. Include a copy of this License (or, as applicable, a license permitted under Section 4.4) or its Uniform Resource Identifier (URI) with the Database or Derivative Database, including both in the Database or Derivative Database and in any relevant documentation; and c. Keep intact any copyright or Database Right notices and notices that refer to this License." |
| Attribution | OSM page: "Where you use OpenStreetMap data, you are required to do the following two things: Provide credit to OpenStreetMap by displaying our attribution notice. Make clear that the data is available under the Open Database License." ODbL 4.3: "Creating and Using a Produced Work does not require the notice in Section 4.2. However, if you Publicly Use a Produced Work, You must include a notice associated with the Produced Work reasonably calculated to make any Person that uses, views, accesses, interacts with, or is otherwise exposed to the Produced Work aware that Content was obtained from the Database, Derivative Database, or the Database as part of a Collective Database, and that it is available under this License." Example notice (4.3a): "Contains information from DATABASE NAME, which is made available here under the Open Database License (ODbL)." OSMF guideline: "Attribution must be to "OpenStreetMap". Attribution must also make it clear that the data is available under the Open Database License." |
| Share-alike / derived data | Definitions (ODbL 1.0): "Derivative Database" means "a database based upon the Database, and includes any translation, adaptation, arrangement, modification, or any other alteration of the Database or of a Substantial part of the Contents. This includes, but is not limited to, Extracting or Re-utilising the whole or a Substantial part of the Contents in a new Database." "Produced Work" means "a work (such as an image, audiovisual material, text, or sounds) resulting from using the whole or a Substantial part of the Contents (via a search or other query) from this Database, a Derivative Database, or this Database as part of a Collective Database." "Collective Database" means "this Database in unmodified form as part of a collection of independent databases in themselves that together are assembled into a collective whole." 4.4a: "Any Derivative Database that You Publicly Use must be only under the terms of: i. This License; ii. A later version of this License similar in spirit to this License; or iii. A compatible license." 4.4c: "A Derivative Database is Publicly Used and so must comply with Section 4.4. if a Produced Work created from the Derivative Database is Publicly Used." 4.5: "The requirements of Section 4.4 do not apply in the following: ... b. Using this Database, a Derivative Database, or this Database as part of a Collective Database to create a Produced Work does not create a Derivative Database for purposes of Section 4.4; and c. Use of a Derivative Database internally within an organisation is not to the public and therefore does not fall under the requirements of Section 4.4." 4.6: "If You Publicly Use a Derivative Database or a Produced Work from a Derivative Database, You must also offer to recipients of the Derivative Database or Produced Work a copy in a machine readable form of: a. The entire Derivative Database; or b. A file containing all of the alterations made to the Database or the method of making the Derivative Database". |
| Accuracy disclaimer | ODbL 7.1: "The Database is licensed by the Licensor "as is" and without any warranty of any kind ... Licensor specifically disclaims any and all implied warranties or conditions of title, non-infringement, accuracy or completeness". |
| Date checked | 2026-11-22 |
| Alternate download (R-15) | Planet file, regional extracts and the Overpass API. `VERIFY:` current endpoint URLs; not fetched. The OSM copyright page says of its own services: "we cannot provide a free-of-charge map API or map tiles for third-parties" (see its API, tile and Nominatim usage policies, not read). |

**Guideline text relevant to a game or sim (OSMF guideline, read 2026-11-22).** Splash screen: "Attribution text on a splash screen must be easily legible and visible such that the typical viewer has time to comprehend the attribution, though it may appear on the screen at the same time as other attribution (e.g., for the game's renderer)." Databases: "You must include attribution to OpenStreetMap and either the text of the ODbL or a link to it as part of the database, derivative database, or database as part of a collective database." Machine learning: "Training datasets that are substantial extractions from OpenStreetMap data are considered Derivative Databases and need to be made available on ODbL terms if publicly used." and "Predictions made using such a model are not implicated by ODbL." The guideline also says: "These guidelines are not a substitute for the legal text itself. If the two texts disagree, the legal text takes precedence."

**Unconfirmed.** `VERIFY:` what the pipeline uses OSM for (DEC-009 candidates: building outlines as a mask or a source). Whether a merged palm-position database that incorporates OSM-derived geometry would be a Derivative Database, and whether scenery packages would be a Produced Work, are questions 5 and 6 below, not conclusions.

---

## 5. Microsoft Global ML Building Footprints

| Field | Finding |
|---|---|
| Terms URL | https://github.com/microsoft/GlobalMLBuildingFootprints (README and LICENSE read from raw.githubusercontent.com); license text https://cdla.dev/permissive-2-0/ |
| License | README: "This data is licensed by Microsoft under the CDLA Permissive 2.0." The LICENSE file says: "Data in this repository has been licensed by Microsoft under CLDA Permissive 2.0." (the file text has the typo "CLDA"; the README link is to CDLA Permissive 2.0). |
| Redistribution clause | CDLA-Permissive-2.0 1.1: "A Data Recipient may use, modify, and share the Data made available by Data Provider(s) under this agreement if that Data Recipient follows the terms of this agreement." 2.1: "A Data Recipient may share Data, with or without modifications, so long as the Data Recipient makes available the text of this agreement with the shared Data." |
| Attribution | No attribution clause in the CDLA text read. README: "The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks." |
| Share-alike / derived data | 3.1: "This agreement does not impose any restriction or obligations with respect to the use, modification, or sharing of Results." "Results" means "any outcome obtained by computational analysis of Data, including for example machine learning models and models' insights" (5.4). |
| Accuracy disclaimer | CDLA 4.1: "THE DATA IS PROVIDED ON AN "AS IS" BASIS, WITHOUT REPRESENTATIONS, WARRANTIES OR CONDITIONS OF ANY KIND". README: "False positive rate for this dataset is ~1% based on a 4k structure sample" (one release; the README also has a per-country false-positive table) and "the data does vary in quality from place to place". Vintage: "depends on the vintage of the underlying imagery", Bing imagery including Maxar and Airbus. |
| Date checked | 2026-11-22 |
| Alternate download (R-15) | README change log records hosting moves (2024-11-07 and 2026-07-24); current index `https://bfppub.blob.core.windows.net/%24web/2026-07-24/dataset-links.csv`; the README says older versions will not be moved. The latest change-log entry is dated 2026-11-12. `VERIFY:` mirrors (for example Source Cooperative, Overture Maps) were not checked. |

**Unconfirmed.** `VERIFY:` whether any Microsoft footprints in the target area include records derived from other datasets with their own terms (the change log mentions Vexcel imagery-derived additions in the US in 2025 and 2026; the README text read does not describe third-party terms for them).

---

## 6. USGS 3DEP LiDAR

| Field | Finding |
|---|---|
| Terms URLs | Registry entry: https://registry.opendata.aws/usgs-lidar/ (fetched OK). USGS terms FAQ it points to: https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map (fetched through WebFetch; direct curl returned 403 "Request blocked"). USGS Copyrights and Credits page https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits: not read (HTTP 403). |
| License | Registry: "License US Government Public Domain" with the USGS terms FAQ link above. |
| Redistribution clause | USGS FAQ: "Map services and data downloaded from The National Map are free and in the public domain." and "There are no restrictions on downloaded data." `VERIFY:` these quotes were returned by an automated page summariser, not copied from raw HTML; the page is about The National Map generally, and whether its wording covers 3DEP point clouds on AWS specifically was not seen. |
| Attribution | Credit is requested, not stated as required, in the text returned: "Map services and data available from U.S. Geological Survey, National Geospatial Program." (for data, the FAQ wording starts "Data available from"). The registry gives a citation form: "USGS 3DEP LiDAR Point Clouds was accessed on DATE from https://registry.opendata.aws/usgs-lidar." |
| Share-alike / derived data | None found. |
| Accuracy disclaimer | None found in the text read. `VERIFY:` the USGS site-policy disclaimers (linked from the FAQ, not read). Per-project LiDAR quality and vintage vary by USGS project (not checked here). |
| Date checked | 2026-11-22 |
| Alternate download (R-15) | Two AWS buckets (registry text): public Entwine Point Tiles `s3://usgs-lidar-public/` (us-west-2, no AWS account required) and a Requester Pays bucket of raw LAZ 1.4. The registry says "Managed By ... Hobu, Inc." (documentation https://github.com/hobu/usgs-lidar/). The USGS original source (The National Map / TNM Access) was not checked. |

**Unconfirmed.** `VERIFY:` Requester Pays bucket costs. The registry also says the raw bucket "is not a complete 3DEP" archive (registry wording, abbreviated).

---

## 7. County and city building outline datasets (DEC-009, terms only)

### 7a. LA County Countywide Building Outlines (LARIAC)

| Field | Finding |
|---|---|
| Terms URL | https://egis-lacounty.hub.arcgis.com/pages/terms-of-use (text read through the ArcGIS item data for the hub page, item `799d631faeae4703949b0061cef7a611`; the hub page itself is script-rendered). |
| License | Terms of Use, no named standard license. Items on the LA County eGIS hub (API search "Countywide Building Outlines": 2014, 2017, 2020 vintages; read 2026-11-22) carry a `licenseInfo` that points to these Terms. |
| Redistribution clause | "Subject to these Terms of Use, you are granted a license to copy, publish, distribute and/or transmit the Data, to adapt the Data and to exploit the Data for commercial and/or personal use (collectively, "License"). No ownership interest in the Data is bestowed on you ... The License will be automatically voided and terminated without notice to you if you violate these Terms of Use. The License does not grant you any right to use the Data in any way that suggests County's endorsement of your use." |
| Attribution | A recommended citation format (not stated as a requirement): "Organization or Author. Year. Title of Dataset: Subtitle [dataset]. Name of Archive, Repository or Database. Accessed Month Date, Year. Link." |
| Share-alike / derived data | None found in the text read. |
| Accuracy disclaimer | Item text: "The data herein is for informational purposes, and may not have been prepared for or be suitable for legal, engineering, or surveying intents. The County of Los Angeles reserves the right to change, restrict, or discontinue access at any time." Terms: "We provide the Website and Data to you on an "as is" basis without any warranties of any kind". |
| Date checked | 2026-11-22 |

**Unconfirmed.** `VERIFY:` the page text beyond the License, Citation, No Warranties and start of Limitation of Liability sections (about 6 KB was read). A "2023 Buildings with DINS data" item found in the same search has the licenseInfo "LARIAC Members only" (as returned by the API), which suggests newer LARIAC products are not under the open terms above. `VERIFY:` which LARIAC vintages are public.

### 7b. SanGIS (San Diego region)

Terms not found. The SanGIS pages tried (https://sangis.org/disclaimer/, https://sangis.org/download/) returned HTTP 404 on 2026-11-22. The San Diego tree layer's own `licenseInfo` (section 3) names "SanGIS and City of San Diego" and includes an AS IS disclaimer and an indemnity sentence. `VERIFY:` SanGIS building data availability and terms.

---

## Summary table

"Redistribution terms clear?" records whether the text found answers the question, not whether a use is permitted.

| Source | License | Attribution needed | Redistribution terms clear? | Questions |
|---|---|---|---|---|
| LA County compilation (stiles/la-trees) | MIT (repo LICENSE); unclear if it covers the data | MIT notice if the license applies; README credits municipalities | unclear | Q1, Q2 |
| StreetsLA tree inventory | None stated | None found | unclear | Q1, Q3 |
| City of San Diego street trees | Portal Terms of Use (no grant clause); layer disclaimer with indemnity | None found | unclear | Q1, Q4 |
| OpenStreetMap | ODbL 1.0 | Yes: "OpenStreetMap" credit plus ODbL notice | yes, with conditions (notices, share-alike, offer of derived data) | Q5, Q6 |
| Microsoft Global ML Building Footprints | CDLA Permissive 2.0 | No attribution clause in the CDLA text; agreement text must accompany shared Data | yes | Q7 |
| USGS 3DEP LiDAR | US Government public domain (per AWS registry and USGS FAQ) | Credit requested, not stated as required | yes (see VERIFY on the USGS page wording) | Q8 |
| LA County building outlines (LARIAC) | eGIS Terms of Use (grant clause) | Recommended citation | unclear (newer vintages "Members only") | Q9 |
| SanGIS building data | Not found | Not found | unclear | Q9 |

---

## Questions for the user

1. (Sections 1-3) For city tree inventories, the compiler's MIT license, the city's own terms and a public-records route could each apply. Do you want the pipeline to take trees only from the original city sources, or is the la-trees copy acceptable as an input? Should we ask the cities (or the compiler) whether a published derived palm layer is within their terms? See [section 1](#1-la-county-street-tree-compilation-stilesla-trees).
2. (Section 1) Should a follow-up read the per-city folders in la-trees for city-specific terms, for the cities in the target regions?
3. (Section 2) StreetsLA publishes no terms on the pages read. Should the TreeKeeper site and the citywide disclaimer be read in a browser (the disclaimer page did not render for automated fetch), or should a contact or records request go to StreetsLA? See [section 2](#2-streetsla-city-of-los-angeles-tree-inventory).
4. (Section 3) San Diego's portal Terms of Use include an indemnity clause covering use of the Data "in a Derivative Work". Is that acceptable for a personal-only project, and does it change anything if you publish (DEC-001)? Which terms apply to the REST layer as opposed to the portal download? See [section 3](#3-city-of-san-diego-street-trees).
5. (Section 4) ODbL share-alike applies to a "Derivative Database" that is "Publicly Used". If OSM geometry (for example building outlines or road masks) ends up inside the palm-position database, and that database or a package built from it is shared, is that the arrangement you want to take on? The alternative is to keep OSM out of any shared database and use it only for local masks. See [section 4](#4-openstreetmap).
6. (Section 4) If scenery packages are published, ODbL 4.3 asks for a notice with a "Produced Work" and the OSMF guideline has splash-screen text for games. Where should such a notice go in an MSFS package and on the flightsim.to page (DEC-010)?
7. (Section 5) CDLA Permissive 2.0 asks that the agreement text accompany shared Data. Are you comfortable adding that text beside any footprint-derived file you share? See [section 5](#5-microsoft-global-ml-building-footprints).
8. (Section 6) The USGS pages that carry the public-domain statement were partly blocked to automated fetch. Do you want a manual read of https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits in a browser to confirm the exact credit line? See [section 6](#6-usgs-3dep-lidar).
9. (Section 7) For DEC-009: which building-outline source do you prefer to evaluate first (OSM, Microsoft, LA County, SanGIS), given the terms above? Are LARIAC "Members only" vintages out of scope? See [section 7](#7-county-and-city-building-outline-datasets-dec-009-terms-only).
10. (R-15, all sources) Do you want local archived copies of each source kept (outside git, per the asset-storage rules) so a source going away does not stop the project? The la-trees README already records one agency removing a dataset.
