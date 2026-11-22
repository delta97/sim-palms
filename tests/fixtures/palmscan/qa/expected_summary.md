# palmscan QA: test-region

- Run time (UTC): 2026-11-22T12:00:00Z
- palmscan version: 0.1.0
- git sha: abc1234
- Config hash: deadbeef
- Stages run: fetch_buildings, ingest_inventory, dedupe, masks
- Output: build/scan/test-region

## Counts by source

| source | fetched | non-tree | not palm | palm | deduped | masked | kept |
|---|---|---|---|---|---|---|---|
| osm | 5 | 0 | 1 | 4 | 0 | 0 | 4 |
| sd_street_trees | 100 | 10 | 60 | 30 | 2 | 1 | 27 |

## Counts by species

| species | count | share | mean height_m | species_source |
|---|---|---|---|---|
| washingtonia_robusta | 2 | 50.0% | 12.0 | inventory:2 |
| phoenix_canariensis | 1 | 25.0% | - | prior:1 |
| unknown | 1 | 25.0% | 12.0 | none:1 |

## Detection

| detected_by | count |
|---|---|
| inventory | 4 |

## Heights

Palms with height_source lidar: 0 of 4 (0.0%)

| height_source | count |
|---|---|
| inventory | 3 |
| none | 1 |

## Building conflicts

- Palms with a building conflict: 1
- Buildings in conflict: 1

## Data vintage

| source | vintage | basis | fetched_at |
|---|---|---|---|
| osm | unknown | fetched | 2026-11-22T00:00:00Z |
| sd_street_trees | 2019 | record_dates | 2026-11-22T00:00:00Z |

Stale cells: 1 of 3

Oldest 2 cells:

| cell_id | palms | inventory_vintage | lidar_vintage | stale |
|---|---|---|---|---|
| n32p78_w117p27 | 2 | 2016.0 | - | yes |
| n32p79_w117p25 | 1 | 2024.0 | - | no |

## Unmatched names containing "palm"

| name | count |
|---|---|
| Palmetto\|odd | 7 |
| Fan palm | 3 |
| Palm sp. | 3 |

## Species priors

Used: merged

| species | computed | configured |
|---|---|---|
| phoenix_canariensis | 0.30 | - |
| washingtonia_robusta | 0.70 | 0.50 |

## Warnings

- LiDAR stage not implemented yet; inventory only
