"""Regenerate the SYNTHETIC metrics fixtures (TEST-010).

Run: python tests/fixtures/accuracy/metrics/make_fixtures.py

Everything here is invented geometry at Null Island (0, 0) for site T9; none of it is a real
palm, label or survey. Distances are laid out with a geodesic so "2.5 m north" really is 2.5 m.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyproj import Geod

HERE = Path(__file__).resolve().parent
GEOD = Geod(ellps="WGS84")
REGION = "synthetic-test"
ORIGIN = (0.0, 0.0)


def at(east_m: float, north_m: float) -> list[float]:
    """lon/lat of a point east_m / north_m from the origin, 7 decimals (about 1 cm)."""
    lon, lat = ORIGIN
    if east_m:
        lon, lat, _ = GEOD.fwd(lon, lat, 90.0, east_m)
    if north_m:
        lon, lat, _ = GEOD.fwd(lon, lat, 0.0, north_m)
    return [round(lon, 7), round(lat, 7)]


def write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=1) + "\n")


def gt_feature(n: int, east: float, props: dict[str, Any]) -> dict[str, Any]:
    base = {
        "gt_id": f"T9-gt-{n:04d}",
        "height_ref_m": None,
        "species_basis": "inventory",
        "context": "street",
        "confidence": "high",
        "note": "SYNTHETIC fixture point, not a real palm label",
    }
    base.update(props)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": at(east, 0.0)},
        "properties": base,
    }


def area_doc(west: float, east: float) -> dict[str, Any]:
    ring = [at(west, -20), at(east, -20), at(east, 20), at(west, 20), at(west, -20)]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"note": "SYNTHETIC area"},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }


def meta_text() -> str:
    return (
        "# SYNTHETIC fixture for tests/unit/accuracy/test_metrics.py. Not a real site or label.\n"
        "site: T9\n"
        "imagery:\n"
        "  source: SYNTHETIC (no imagery)\n"
        '  date: "2026-11-22"\n'
        "  resolution_m: 0.6\n"
        "labelers:\n"
        '  - "synthetic-fixture"\n'
        'labeled_on: "2026-11-22"\n'
        'notes: "SYNTHETIC test fixture. Coordinates are Null Island, not a real street."\n'
    )


def pred_feature(n: int, east: float, north: float, props: dict[str, Any]) -> dict[str, Any]:
    pid = f"syn-{n:016x}"
    base: dict[str, Any] = {
        "palm_id": pid,
        "species_confidence": 0.8,
        "height_source": "lidar" if "lidar" in props["detected_by"] else "species_default",
        "crown_diam_m": 4.0,
        "ground_elev_m": None,
        "source_ids": [f"synthetic:{n}"],
        "exclusion_radius_m": 2.5,
        "building_conflict": False,
        "data_vintage": {"inventory": "2026-11"},
        "region": REGION,
    }
    base.update(props)
    return {
        "type": "Feature",
        "id": pid,
        "geometry": {"type": "Point", "coordinates": at(east, north)},
        "properties": base,
    }


def pred_doc(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "schema_version": "1.0",
        "region": REGION,
        "generated_at": "2026-11-22T00:00:00Z",
        "data_version": "2026-11",
        "generator": {"name": "synthetic-fixture", "version": "0"},
        "config_sha256": None,
        "features": features,
    }


# --- row: 6 palms 8 m apart ---------------------------------------------------------------

ROW_GT = [
    (1, {"height_class": "M", "height_ref_m": 10.0, "species": "washingtonia_robusta"}),
    (2, {"height_class": "M", "height_ref_m": 12.0, "species": "washingtonia_robusta"}),
    (3, {"height_class": "T", "height_ref_m": 18.0, "species": "phoenix_canariensis"}),
    (
        4,
        {
            "height_class": "S",
            "species": "washingtonia_filifera",
            "species_basis": "imagery",
            "context": "beach",
        },
    ),
    (
        5,
        {
            "height_class": "X",
            "height_ref_m": 26.0,
            "species": "unknown",
            "species_basis": "unknown",
            "context": "park",
        },
    ),
    (6, {"height_class": "M", "species": "washingtonia_robusta"}),
]
# (detected_by, species, species_source, height_m); matches the labels except where noted.
ROW_PRED = [
    ("inventory", "washingtonia_robusta", "inventory", 10.0),
    ("inventory", "washingtonia_robusta", "inventory", 12.0),
    ("inventory+lidar", "phoenix_canariensis", "inventory", 18.0),
    ("lidar", "washingtonia_robusta", "lidar_rules", 6.0),  # wrong species on purpose
    ("lidar", "phoenix_canariensis", "lidar_tree", 26.0),  # label species is unknown
    ("inventory", "washingtonia_robusta", "inventory", 11.0),
]


def row_preds(north: float = 0.0, skip: int | None = None, extra: bool = False) -> dict[str, Any]:
    feats = []
    for i, (det, sp, src, h) in enumerate(ROW_PRED):
        if i == skip:
            continue
        props = {"detected_by": det, "species": sp, "species_source": src, "height_m": h}
        feats.append(pred_feature(i + 1, 8.0 * i, north, props))
    if extra:
        props = {
            "detected_by": "lidar",
            "species": "washingtonia_robusta",
            "species_source": "lidar_rules",
            "height_m": 9.0,
        }
        feats.append(pred_feature(99, 100.0, 0.0, props))
    return pred_doc(feats)


def main() -> None:
    row = HERE / "row"
    write(
        row / "T9" / "ground_truth.geojson",
        {
            "type": "FeatureCollection",
            "features": [gt_feature(n, 8.0 * (n - 1), p) for n, p in ROW_GT],
        },
    )
    write(row / "T9" / "labeled_area.geojson", area_doc(-20, 120))
    (row / "T9" / "meta.yaml").write_text(meta_text(), encoding="utf-8", newline="\n")
    write(row / "pred_exact.geojson", row_preds())
    write(row / "pred_shift_2p5.geojson", row_preds(north=2.5))
    write(row / "pred_shift_3p5.geojson", row_preds(north=3.5))
    write(row / "pred_missing_extra.geojson", row_preds(skip=3, extra=True))

    # Greedy trap: ground truth at 0, 3, 6 m; predictions at 2, 5, 8 m (all within 3 m).
    # Nearest-first greedy pairs 2 with 3 and 5 with 6, then strands 8 and 0: 2 matches, not 3.
    trap = HERE / "trap"
    gts = [(n, {"height_class": "M", "species": "washingtonia_robusta"}) for n in (1, 2, 3)]
    write(
        trap / "T9" / "ground_truth.geojson",
        {
            "type": "FeatureCollection",
            "features": [gt_feature(n, 3.0 * (n - 1), p) for n, p in gts],
        },
    )
    write(trap / "T9" / "labeled_area.geojson", area_doc(-20, 40))
    (trap / "T9" / "meta.yaml").write_text(meta_text(), encoding="utf-8", newline="\n")
    pred = [
        pred_feature(
            n,
            2.0 + 3.0 * (n - 1),
            0.0,
            {
                "detected_by": "inventory",
                "species": "washingtonia_robusta",
                "species_source": "inventory",
                "height_m": 10.0,
            },
        )
        for n in (1, 2, 3)
    ]
    write(trap / "pred_trap.geojson", pred_doc(pred))


if __name__ == "__main__":
    main()
