# Airports for default palm masks

Source: OpenStreetMap `aeroway=aerodrome` and `aeroway=heliport`, fetched from Overpass on 2026-11-22.
Machine-readable copy: `docs/compat/airports-mask.geojson` (60 features, unbuffered boundaries).
Task: RISK-004. Consumer: GEN-016 via `masks.airports.path`.

## Buffer rule

- The GeoJSON stores the unbuffered boundary. Palmgen applies the buffer.
- Buffer = `masks.airports.buffer_m` in the region config. ARCH-003 default is 100 m.
- The per-feature `buffer_m: 100` is a suggestion only. REGION tasks tune the config key, not the file.
- Manual extra masks are `mask_out` entries with `kind: airport`.

## Target regions

- San Diego coastal bbox `[-117.28, 32.70, -117.15, 32.82]` (from the task spec).
- LA Westside bbox `[-118.55, 33.85, -118.30, 34.10]`. **PROVISIONAL**: the spec says it is not fixed yet.
- `socal_other`: any airport inside the SoCal-wide bbox `[-119.0, 32.5, -116.9, 34.5]` that is not in the two bboxes above.
- The region is assigned from the centre of each polygon's vertex bounds. An airport near a bbox edge may need a manual check. VERIFY for KNZY, which sits near the south edge of the San Diego box.

## Code choice

- Preferred: `icao` tag. Fallback order: `faa`, `ref`, `iata`. The `code_source` property records which one was used.
- Features with no code were dropped (9 in the SoCal-wide pull, mostly private strips and small heliports). They are unnamed or unidentified and cannot be matched to an add-on. Re-add by hand if needed.
- Two features share code KRIV (March Air Reserve Base and March Inland Port Airport). Both are kept. Check the mask against the sim before relying on either.
- MMTJ (Tijuana) is outside the US. It is in the SoCal bbox, so it is kept. Remove it if the target scope is US only.

## Airport table

Add-on column: "searched 2026-11-22" means a web search was run for that airport. "not searched" means it was not checked, not that no add-on exists. Prices and compatibility come from search snippets only and must be checked on each store (VERIFY).

| Code | Name | Target region | Code source | OSM id | MSFS 2024 add-on known |
|---|---|---|---|---|---|
| 05CA | Lost Hills Sheriffs Station Heliport | SoCal, other (outside the two named bboxes) | faa | way/888038129 | not searched |
| 13CA | Heaps Peak USFS Heliport | SoCal, other (outside the two named bboxes) | faa | way/887681175 | not searched |
| 2CA4 | Blackinton Airport | SoCal, other (outside the two named bboxes) | faa | way/621631345 | not searched |
| 2CN3 | Tenaja Valley Airport | SoCal, other (outside the two named bboxes) | faa | way/618707094 | not searched |
| 37CA | Billy Joe Airport | SoCal, other (outside the two named bboxes) | faa | relation/326307 | not searched |
| 37CL | Lyall-Roberts Airport | SoCal, other (outside the two named bboxes) | faa | way/621631368 | not searched |
| 46CN | Crystal Airport | SoCal, other (outside the two named bboxes) | faa | way/621816683 | not searched |
| 64CL | Goodyear Blimp Base Airport | SoCal, other (outside the two named bboxes) | faa | way/107755131 | not searched |
| 81L | Sheriff's Wayside Heliport | SoCal, other (outside the two named bboxes) | faa | way/888038145 | not searched |
| 8CA5 | Pines Airpark | SoCal, other (outside the two named bboxes) | faa | way/618707095 | not searched |
| 8CL1 | Lake Wohlford Resort Airstrip | SoCal, other (outside the two named bboxes) | faa | way/44500649 | not searched |
| CA42 | Mc Conville Airstrip | SoCal, other (outside the two named bboxes) | faa | way/518627320 | not searched |
| CA84 | Torrey Pines Gliderport | SoCal, other (outside the two named bboxes) | faa | way/459665610 | not searched |
| CA89 | Skylark Field Airport | SoCal, other (outside the two named bboxes) | faa | way/44486540 | not searched |
| CL33 | Pauma Valley Air Park | SoCal, other (outside the two named bboxes) | faa | way/621631364 | not searched |
| F70 | French Valley Airport | SoCal, other (outside the two named bboxes) | faa | way/91482992 | not searched |
| KAJO | Corona Municipal Airport | SoCal, other (outside the two named bboxes) | icao | way/44486232 | not searched |
| KAVX | Catalina Airport | SoCal, other (outside the two named bboxes) | icao | way/400895117 | not searched |
| KBUR | Hollywood Burbank Airport | SoCal, other (outside the two named bboxes) | icao | way/208935822 | not searched |
| KCCB | Cable Airport | SoCal, other (outside the two named bboxes) | icao | way/146651169 | not searched |
| KCNO | Chino Airport | SoCal, other (outside the two named bboxes) | icao | way/614643429 | not searched |
| KCPM | Compton / Woodley Airport | SoCal, other (outside the two named bboxes) | icao | way/49577646 | not searched |
| KCRQ | McClellan-Palomar Airport | SoCal, other (outside the two named bboxes) | icao | way/171278464 | not searched |
| KEMT | San Gabriel Valley Airport | SoCal, other (outside the two named bboxes) | icao | way/80877748 | not searched |
| KFUL | Fullerton Municipal Airport | SoCal, other (outside the two named bboxes) | icao | way/190180862 | not searched |
| KHHR | Hawthorne Municipal Airport | LA Westside (provisional bbox) | icao | way/141973105 | not searched |
| KHMT | Hemet-Ryan Airport | SoCal, other (outside the two named bboxes) | icao | way/44486176 | not searched |
| KLAX | Los Angeles International Airport | LA Westside (provisional bbox) | icao | way/649268639 | Yes: iniBuilds LAX Enhanced, MSFS 2024 (paid) https://inibuilds.com/products/inibuilds-los-angeles-klax-msfs-2024 ; FeelThere KLAX, listed for 2020 and 2024 but install problems reported (VERIFY) https://www.aerosoft.com/de/microsoft-flight-simulator/msfs-szenerien/3687/feelthere-klax-los-angeles-airport-msfs |
| KLGB | Long Beach Airport | SoCal, other (outside the two named bboxes) | icao | way/311520978 | Yes: ShorePilotSim KLGB, 2020 and 2024 (paid) https://forums.flightsimulator.com/t/new-release-shorepilotsim-klgb-long-beach-airport-for-msfs2020-msfs2024/769607 ; XWind Studios KLGB, 2024 only (paid) https://fselite.net/content/xwind-studios-releases-long-beach-airport-for-msfs-2024/ ; Skyline Simulations KLGB, 2020 and 2024 (paid) https://www.aerosoft.com/en/shop/flight/microsoft-flight-simulator/msfs-sceneries/msfs-north-america/3544/skyline-simulations-klgb-long-beach-airport-msfs |
| KMYF | Montgomery Field | SoCal, other (outside the two named bboxes) | icao | relation/3248254 | not searched |
| KNFG | Marine Corps Air Station Camp Pendleton | SoCal, other (outside the two named bboxes) | icao | relation/19720714 | not searched |
| KNKX | MCAS Miramar Airfield | SoCal, other (outside the two named bboxes) | icao | relation/13902660 | not searched |
| KNRS | Naval Outlying Landing Field Imperial Beach | SoCal, other (outside the two named bboxes) | icao | relation/13587778 | not searched |
| KNUC | Naval Auxiliary Landing Field San Clemente Island | SoCal, other (outside the two named bboxes) | icao | way/534911782 | not searched |
| KNXF | MCOLF Camp Pendleton (Red Beach) Airport | SoCal, other (outside the two named bboxes) | icao | way/621631343 | not searched |
| KNZY | Naval Air Station North Island | SoCal, other (outside the two named bboxes) | icao | way/31929333 | Yes: SundownerSim NAS North Island, MSFS 2024 (paid, VERIFY store) https://msfsaddons.com/2026/08/28/not-just-an-airfield-sundownersims-nas-north-island-brings-a-whole-naval-fleet-to-msfs/ ; julysfire KNZY Halsey Field, 2020 and 2024 (freeware, VERIFY) https://flightsim.to/addon/87/knzy-north-island-naval-air-station-halsey-field |
| KOKB | Oceanside Municipal Airport | SoCal, other (outside the two named bboxes) | icao | relation/326552 | not searched |
| KONT | Ontario International Airport | SoCal, other (outside the two named bboxes) | icao | way/321769511 | not searched |
| KPOC | Brackett Field | SoCal, other (outside the two named bboxes) | icao | way/621816684 | not searched |
| KRAL | Riverside Municipal Airport | SoCal, other (outside the two named bboxes) | icao | way/127837011 | not searched |
| KREI | Redlands Municipal Airport | SoCal, other (outside the two named bboxes) | icao | way/17012632 | not searched |
| KRIR | Flabob Airport | SoCal, other (outside the two named bboxes) | icao | way/44486246 | not searched |
| KRIV | March Air Reserve Base | SoCal, other (outside the two named bboxes) | icao | way/126516433 | not searched |
| KRIV | March Inland Port Airport | SoCal, other (outside the two named bboxes) | icao | way/1465007780 | not searched |
| KRNM | Ramona Airport | SoCal, other (outside the two named bboxes) | icao | way/44501276 | not searched |
| KSAN | San Diego International Airport | San Diego coastal | icao | way/209694794 | Yes: Glideslope Pro KSAN, native MSFS 2024 (paid) https://flightsim.to/store/product/ksan-san-diego-airport-msfs-2024 ; LatinVFR KSAN, listed as MSFS 2024 compatible (VERIFY) https://secure.simmarket.com/latinvfr-san-diego-intl-ksan-msfs.phtml |
| KSBD | San Bernardino International Airport | SoCal, other (outside the two named bboxes) | icao | way/384693364 | not searched |
| KSDM | Brown Field Municipal Airport | SoCal, other (outside the two named bboxes) | icao | way/101603157 | not searched |
| KSEE | Gillespie Field | SoCal, other (outside the two named bboxes) | icao | way/162328604 | not searched |
| KSLI | Joint Forces Training Base - Los Alamitos | SoCal, other (outside the two named bboxes) | icao | relation/6566347 | not searched |
| KSMO | Santa Monica Municipal Airport | LA Westside (provisional bbox) | icao | way/142010684 | Yes: AG Sim KSMO (paid, Aerosoft; listing shows 2020 path, 2024 support VERIFY) https://www.aerosoft.com/en/shop/flight/microsoft-flight-simulator/msfs-2020/msfs-sceneries/msfs-north-america/3887/ag-sim-ksmo-santa-monica-airport ; VTOL Aviation KSMO (freeware, tagged 2020 and 2024, VERIFY) https://flightsim.to/addon/4067/vtol-aviation-s-ksmo-santa-monica-municipal-airport |
| KSNA | John Wayne Airport | SoCal, other (outside the two named bboxes) | icao | relation/19620500 | not searched |
| KTOA | Zamperini Field | SoCal, other (outside the two named bboxes) | icao | way/223887375 | not searched |
| KVNY | Van Nuys Airport | SoCal, other (outside the two named bboxes) | icao | way/312331907 | not searched |
| KWHP | Whiteman Airport | SoCal, other (outside the two named bboxes) | icao | way/362084327 | not searched |
| L18 | Fallbrook Community Airpark | SoCal, other (outside the two named bboxes) | faa | way/139812612 | not searched |
| L26 | Hesperia Airport | SoCal, other (outside the two named bboxes) | faa | way/614643419 | not searched |
| L65 | Perris Valley Airport | SoCal, other (outside the two named bboxes) | faa | way/618707097 | not searched |
| L70 | Agua Dulce Airpark | SoCal, other (outside the two named bboxes) | faa | way/135245540 | not searched |
| MMTJ | Aeropuerto Internacional de Tijuana (Tijuana, Mexico) | SoCal, other (outside the two named bboxes) | icao | relation/6714045 | not searched |


## Licence and attribution

OpenStreetMap data (c) OpenStreetMap contributors, ODbL 1.0. Keep attribution when the geometry is shipped.
See `docs/licenses/data-sources.md` for the full source list.
VERIFY: `docs/licenses/data-sources.md` does not exist in this worktree (checked 2026-11-22). Create it through RISK-001 or check it on main.

## Add-on search

Searched 2026-11-22 with web search. Only KSAN, KLAX, KSMO, KLGB and KNZY were searched. The other airports are marked not searched. Add-on store listings and their compatibility claims are not confirmed in the sim (VERIFY).
