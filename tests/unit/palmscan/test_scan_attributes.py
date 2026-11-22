"""palmscan.attributes: height parsing, sizes, exclusion radius, building conflicts. Offline."""

from __future__ import annotations

from typing import Any

import pytest

from palmcore.config import ExclusionConfig
from palmcore.palms import PalmsMeta
from palmscan.attributes import (
    assign_exclusion,
    assign_sizes,
    default_size,
    flag_building_conflicts,
    parse_height,
)
from palmscan.config import ScanConfig, scan_config_from_mapping
from palmscan.geo import to_local, to_wgs84
from palmscan.model import PalmRecord
from palmscan.output import to_feature_collection
from tests.helpers.contract import check_palms_invariants

FT = 0.3048
SD_BBOX = [-117.28, 32.70, -117.15, 32.82]
ORIGIN = (-117.2, 32.75)
FOOT_MARK = chr(39)  # the ' unit suffix


def _source(name: str, units: str) -> dict[str, Any]:
    return {
        "name": name,
        "type": "arcgis_rest",
        "url": "https://example.invalid/arcgis/rest/services/x/MapServer/0",
        "species_field": "SPECIES",
        "height_field": "HEIGHT",
        "height_units": units,
    }


def make_cfg(**extra: Any) -> ScanConfig:
    raw: dict[str, Any] = {
        "region": "san-diego-coastal",
        "bbox": list(SD_BBOX),
        "sources": {"inventory": [_source("sd_ft", "ft"), _source("metric", "m")]},
        **extra,
    }
    return scan_config_from_mapping(raw)


CFG = make_cfg()
CRS = CFG.region.crs()


def palm(
    key: str = "sd_ft:1",
    species: str | None = "washingtonia_robusta",
    *,
    east_m: float = 0.0,
    **fields: Any,
) -> PalmRecord:
    x0, y0 = to_local(*ORIGIN, CRS)
    lon, lat = to_wgs84(x0 + east_m, y0, CRS)
    return PalmRecord(
        stable_key=key,
        lon=lon,
        lat=lat,
        x=x0 + east_m,
        y=y0,
        species=species,
        species_confidence=0.95,
        species_source="inventory",
        **fields,
    )


@pytest.mark.parametrize(
    ("raw", "units", "expected"),
    [
        ("35", "ft", 35 * FT),
        ("35.5", "ft", 35.5 * FT),
        (" 35 ", "ft", 35 * FT),
        ("30-45", "ft", 11.43),
        ("30 to 45", "ft", 11.43),
        ("30 - 45 ft", "ft", 11.43),
        ("10 m", "ft", 10.0),
        ("10m", "ft", 10.0),
        ("10", "m", 10.0),
        ("40" + FOOT_MARK, "m", 40 * FT),
        ("40 ft", "m", 40 * FT),
        ("12-18 m", "ft", 15.0),
        ("Large", "ft", None),
        ("Tall (30+)", "ft", None),
        ("10 ft-12 m", "ft", None),
        ("0", "ft", None),
        ("", "ft", None),
        (None, "ft", None),
    ],
)
def test_parse_height_table(raw: str | None, units: str, expected: float | None) -> None:
    got = parse_height(raw, units)
    if expected is None:
        assert got is None
    else:
        assert got == pytest.approx(expected, abs=0.01)


def test_parse_height_acceptance_example() -> None:
    assert parse_height("30-45", "ft") == pytest.approx(11.43, abs=0.01)


def test_parse_height_rejects_unknown_units() -> None:
    with pytest.raises(ValueError, match="units"):
        parse_height("10", "cm")


def test_inventory_height_used_with_source_units() -> None:
    feet = palm("sd_ft:1", height_raw="40")
    metres = palm("metric:1", height_raw="12")
    assign_sizes([feet, metres], CFG)
    assert (feet.height_m, feet.height_source) == (12.2, "inventory")
    assert (metres.height_m, metres.height_source) == (12.0, "inventory")


def test_ingested_inventory_height_is_range_checked_too() -> None:
    ok = palm(height_m=15.0, height_source="inventory")
    bad = palm("sd_ft:2", height_m=55.0, height_source="inventory")
    assign_sizes([ok, bad], CFG)
    assert (ok.height_m, ok.height_source) == (15.0, "inventory")
    assert (bad.height_m, bad.height_source) == (22.0, "species_default")


@pytest.mark.parametrize("raw", ["5", "200", "Large", None])
def test_out_of_range_or_unparsable_inventory_height_is_ignored(raw: str | None) -> None:
    p = palm(height_raw=raw)  # 5 ft = 1.5 m is below 3 m; 200 ft = 61 m is above 40 m
    assign_sizes([p], CFG)
    assert (p.height_m, p.height_source) == (22.0, "species_default")


def test_range_limits_come_from_config() -> None:
    cfg = make_cfg(palmscan={"inventory": {"height_min_m": 1.0, "height_max_m": 70.0}})
    p = palm(height_raw="5")
    assign_sizes([p], cfg)
    assert (p.height_m, p.height_source) == (1.5, "inventory")


def test_species_genus_default_fallback() -> None:
    species = palm("a:1", "phoenix_canariensis")
    genus_only = palm("a:2", "brahea_sp")
    unknown_genus = palm("a:3", "palm_unknown")
    none = palm("a:4", None)
    odd = palm("a:5", "zzz_unknown")
    assign_sizes([species, genus_only, unknown_genus, none, odd], CFG)
    assert (species.height_m, species.crown_diam_m) == (15.0, 10.0)
    assert (genus_only.height_m, genus_only.crown_diam_m) == (9.0, 4.0)
    for p in (unknown_genus, none, odd):
        assert (p.height_m, p.crown_diam_m) == (12.0, 5.0)
    assert {p.height_source for p in (species, genus_only, none)} == {"species_default"}
    assert default_size("brahea_edulis") == (9.0, 4.0)
    assert default_size(None) == (12.0, 5.0)


def test_region_median_beats_default_but_not_inventory() -> None:
    medians = {"washingtonia_robusta": 18.26}
    median = palm("a:1")
    other = palm("a:2", "phoenix_canariensis")
    inv = palm("sd_ft:3", height_raw="50")
    assign_sizes([median, other, inv], CFG, region_medians=medians)
    assert (median.height_m, median.height_source) == (18.3, "region_median")
    assert (other.height_m, other.height_source) == (15.0, "species_default")
    assert inv.height_source == "inventory"
    assert median.crown_diam_m == 4.0  # crown still from the species row


def test_lidar_palms_are_left_alone() -> None:
    p = palm(height_m=17.34, height_source="lidar", crown_diam_m=6.66, height_raw="40")
    assign_sizes([p], CFG, region_medians={"washingtonia_robusta": 20.0})
    assert (p.height_m, p.height_source, p.crown_diam_m) == (17.34, "lidar", 6.66)


def test_existing_crown_is_kept() -> None:
    p = palm(crown_diam_m=12.0)
    assign_sizes([p], CFG)
    assert p.crown_diam_m == 12.0


def test_assign_sizes_is_idempotent() -> None:
    p = palm(height_raw="40")
    assign_sizes([p], CFG)
    first = (p.height_m, p.height_source, p.crown_diam_m)
    assign_sizes([p], CFG)
    assert (p.height_m, p.height_source, p.crown_diam_m) == first


def _radius(crown: float | None, margin: float = 1.5) -> float | None:
    p = palm(crown_diam_m=crown)
    assign_exclusion([p], ExclusionConfig(margin_m=margin))
    return p.exclusion_radius_m


def test_radius_acceptance_examples() -> None:
    canary = palm("a:1", "phoenix_canariensis", crown_diam_m=12.0)
    huge = palm("a:2", "phoenix_canariensis", crown_diam_m=20.0)
    assign_exclusion([canary, huge], CFG.region.exclusion)
    assert canary.exclusion_radius_m == 7.5
    assert huge.exclusion_radius_m == 8.0


def test_radius_clamps_at_both_ends() -> None:
    assert _radius(0.5, margin=0.0) == 1.0
    assert _radius(20.0) == 8.0
    assert _radius(4.0) == 3.5


def test_radius_uses_region_clamps_not_hard_coded_values() -> None:
    ex = ExclusionConfig(margin_m=0.5, radius_min_m=2.0, radius_max_m=3.0)
    small = palm(crown_diam_m=1.0)
    big = palm("a:2", crown_diam_m=30.0)
    mid = palm("a:3", crown_diam_m=4.0)
    assign_exclusion([small, big, mid], ex)
    assert small.exclusion_radius_m == 2.0
    assert big.exclusion_radius_m == 3.0
    assert mid.exclusion_radius_m == 2.5


def test_radius_without_crown_is_default_radius() -> None:
    assert _radius(None) == 3.0


def test_radius_uses_crown_at_stored_precision() -> None:
    p = palm(crown_diam_m=4.04)
    assign_exclusion([p], ExclusionConfig())
    assert p.exclusion_radius_m == 3.5  # crown taken at the stored 0.1 m precision


def test_written_palms_pass_contract_invariants() -> None:
    """sizes -> exclusion -> palms.geojson satisfies the TEST-004 radius-clamp invariant."""
    palms = [
        palm("sd_ft:1", "washingtonia_robusta", height_raw="40"),
        palm("sd_ft:2", "phoenix_canariensis", east_m=20.0),
        palm("sd_ft:3", None, east_m=40.0),
        palm("sd_ft:4", "palm_unknown", east_m=60.0, crown_diam_m=0.34),  # 0.3 after rounding
        palm("sd_ft:5", "phoenix_canariensis", east_m=80.0, crown_diam_m=19.97),  # to 8.0
        palm("sd_ft:6", "washingtonia_filifera", east_m=100.0, crown_diam_m=7.31),  # unrounded
    ]
    for p in palms:
        p.detected_by = "inventory"
        p.source_ids = [p.stable_key]
        p.data_vintage = {"inventory": "2024"}
    assign_sizes(palms, CFG)
    assign_exclusion(palms, CFG.region.exclusion)
    meta = PalmsMeta(
        schema_version="1.0",
        region=CFG.region_name,
        generated_at="2026-11-22T00:00:00Z",
        data_version="2026-11",
        generator_name="palmscan",
        generator_version="0.1.0",
        config_sha256=None,
    )
    fc = to_feature_collection(palms, CFG.region_name, id_prefix=CFG.id_prefix, meta=meta)
    assert check_palms_invariants(fc, region=CFG.region) == []
    radii = [f["properties"]["exclusion_radius_m"] for f in fc["features"]]
    assert 8.0 in radii


# --- building conflicts ----------------------------------------------------------------------


def _buildings(rects: dict[str, tuple[float, float, float, float]]) -> Any:
    """GeoDataFrame (EPSG:4326) of axis-aligned rectangles given in local metres."""
    import geopandas as gpd
    from shapely.geometry import box

    x0, y0 = to_local(*ORIGIN, CRS)
    local = gpd.GeoDataFrame(
        {
            "building_id": list(rects),
            "source": "test",
            "geometry": [box(x0 + a, y0 + b, x0 + c, y0 + d) for a, b, c, d in rects.values()],
        },
        crs=CRS,
    )
    return local.to_crs("EPSG:4326")


def _fenced(east_m: float = 0.0, radius: float = 3.0, key: str = "a:1") -> PalmRecord:
    p = palm(key, east_m=east_m)
    p.exclusion_radius_m = radius
    return p


def test_overlap_vs_edge_touch_threshold() -> None:
    # circle r=3: a wall at x=3.0 only touches, x=2.95 overlaps by ~0.04 m2, x=2.0 by ~1.3 m2.
    touching = _fenced(0.0, key="t:1")
    sliver = _fenced(100.0, key="t:2")
    overlap = _fenced(200.0, key="t:3")
    buildings = _buildings(
        {
            "b-touch": (3.0, -10, 10, 10),
            "b-sliver": (100 + 2.95, -10, 100 + 10, 10),
            "b-overlap": (200 + 2.0, -10, 200 + 10, 10),
        }
    )
    hit = flag_building_conflicts([touching, sliver, overlap], buildings, CRS)
    assert [p.building_conflict for p in (touching, sliver, overlap)] == [False, False, True]
    assert list(hit["building_id"]) == ["b-overlap"]


def test_threshold_is_configurable() -> None:
    p = _fenced(0.0)
    buildings = _buildings({"b1": (2.95, -10, 10, 10)})
    assert flag_building_conflicts([p], buildings, CRS, overlap_min_m2=0.01).shape[0] == 1
    assert p.building_conflict is True


def test_conflicting_buildings_returned_once_sorted_in_wgs84() -> None:
    palms = [_fenced(0.0, key="a:1"), _fenced(1.0, key="a:2"), _fenced(30.0, key="a:3")]
    buildings = _buildings(
        {
            "z-late": (-1, -1, 1, 1),  # hit by two palms
            "a-early": (31, -1, 33, 1),
            "m-far": (500, 500, 510, 510),
        }
    )
    hit = flag_building_conflicts(palms, buildings, CRS)
    assert list(hit["building_id"]) == ["a-early", "z-late"]
    assert hit.crs is not None and hit.crs.to_epsg() == 4326
    assert all(p.building_conflict for p in palms)


def test_conflict_flag_is_reset_and_empty_inputs_are_safe() -> None:
    p = _fenced(0.0)
    p.building_conflict = True
    far = _buildings({"far": (500, 500, 510, 510)})
    assert flag_building_conflicts([p], far.iloc[0:0], CRS).empty
    assert p.building_conflict is False
    assert flag_building_conflicts([p], far, CRS).empty
    assert flag_building_conflicts([], far, CRS).empty


def test_conflicts_need_a_radius() -> None:
    p = palm()
    with pytest.raises(ValueError, match="assign_exclusion"):
        flag_building_conflicts([p], _buildings({"b": (0, 0, 1, 1)}), CRS)
