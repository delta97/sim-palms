"""palmscan.config: defaults, overrides, unknown keys, bbox guard, hash."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from palmcore.errors import ConfigError
from palmscan.config import ScanConfig, load_scan_config, scan_config_from_mapping

REPO = Path(__file__).resolve().parents[3]
SD_BBOX = [-117.28, 32.70, -117.15, 32.82]


def _raw(**extra: Any) -> dict[str, Any]:
    return {"region": "san-diego-coastal", "bbox": list(SD_BBOX), **extra}


def test_minimal_mapping_has_every_plan_default() -> None:
    cfg = scan_config_from_mapping(_raw())
    assert isinstance(cfg, ScanConfig)
    assert cfg.id_prefix == "sdc"
    assert cfg.output_dir is None
    assert cfg.dedupe_radius_m == 2.0
    assert cfg.palm_filter.genus_sets == ("socal",)
    assert cfg.palm_filter.exclude_species == ()
    assert (cfg.inventory.height_min_m, cfg.inventory.height_max_m) == (3.0, 40.0)
    assert cfg.exclusion.building_overlap_min_m2 == 0.1
    assert cfg.lidar.datasets == ()
    assert cfg.lidar.tile_size_m == 500.0
    assert cfg.lidar.tile_buffer_m == 20.0
    assert cfg.lidar.resolution_m == 0.5
    assert cfg.lidar.smooth_sigma_px == 1.0
    assert cfg.lidar.noise_classes == (7, 18)
    assert cfg.lidar.use_building_class is True
    assert (cfg.peaks.min_height_m, cfg.peaks.min_distance_m) == (6.0, 3.0)
    assert cfg.peaks.crown_mask_height_m == 2.0
    r = cfg.rules
    assert (r.height_min_m, r.height_max_m, r.crown_min_m, r.crown_max_m) == (8.0, 35.0, 3.0, 12.0)
    assert (r.ratio_min, r.ratio_exempt_large_crown) == (2.0, True)
    assert (r.ratio_exempt_crown_min_m, r.ratio_exempt_ratio_min) == (7.0, 1.0)
    assert (r.shared_boundary_max, r.building_buffer_m) == (0.35, 1.0)
    assert (cfg.merge.match_radius_m, cfg.merge.region_median_min_n) == (3.0, 5)
    c = cfg.classify
    assert (c.use_tree, c.tree_max_depth, c.tree_min_samples_leaf) == (True, 4, 5)
    assert (c.tree_min_class_n, c.tree_min_total_n, c.tree_min_gain) == (15, 50, 0.05)
    assert c.tree_model_path is None
    assert (cfg.qa.vintage_grid_deg, cfg.qa.stale_years) == (0.01, 5)
    assert (cfg.qa.write_crowns, cfg.qa.list_non_palms) == (False, False)


def test_overrides_and_lists_become_tuples() -> None:
    cfg = scan_config_from_mapping(
        _raw(
            palmscan={
                "output_dir": "out/x",
                "rules": {"height_min_m": 5, "ratio_exempt_large_crown": False},
                "palm_filter": {"genus_sets": ["socal", "florida"]},
                "lidar": {"noise_classes": [7]},
            }
        )
    )
    assert cfg.output_dir == "out/x"
    assert cfg.rules.height_min_m == 5.0
    assert isinstance(cfg.rules.height_min_m, float)
    assert cfg.rules.ratio_exempt_large_crown is False
    assert cfg.rules.height_max_m == 35.0
    assert cfg.palm_filter.genus_sets == ("socal", "florida")
    assert cfg.lidar.noise_classes == (7,)


def test_typo_key_rejected_and_named() -> None:
    with pytest.raises(ConfigError, match="heigth_min_m") as info:
        scan_config_from_mapping(_raw(palmscan={"rules": {"heigth_min_m": 5}}))
    assert "height_min_m" in str(info.value)  # suggestion


def test_unknown_top_level_palmscan_key_rejected() -> None:
    with pytest.raises(ConfigError, match="bogus"):
        scan_config_from_mapping(_raw(palmscan={"bogus": 1}))


def test_id_prefix_in_palmscan_block_rejected() -> None:
    with pytest.raises(ConfigError, match="id_prefix") as info:
        scan_config_from_mapping(_raw(palmscan={"id_prefix": "x"}))
    assert "top-level" in str(info.value)


def test_exclusion_radius_in_palmscan_block_rejected() -> None:
    with pytest.raises(ConfigError, match="radius_min_m"):
        scan_config_from_mapping(_raw(palmscan={"exclusion": {"radius_min_m": 1}}))


@pytest.mark.parametrize(
    ("block", "needle"),
    [
        ({"rules": {"height_min_m": "tall"}}, "rules.height_min_m"),
        ({"rules": {"ratio_exempt_large_crown": 1}}, "ratio_exempt_large_crown"),
        ({"merge": {"region_median_min_n": 2.5}}, "region_median_min_n"),
        ({"palm_filter": {"genus_sets": "socal"}}, "genus_sets"),
        ({"rules": [1]}, "rules"),
        ({"rules": {"height_min_m": 40}}, "height_min_m"),
        ({"dedupe_radius_m": 0}, "dedupe_radius_m"),
    ],
)
def test_bad_values_rejected(block: dict[str, Any], needle: str) -> None:
    with pytest.raises(ConfigError, match=needle):
        scan_config_from_mapping(_raw(palmscan=block))


def test_large_bbox_rejected_unless_allowed() -> None:
    big = {"region": "big-region", "bbox": [-118.0, 32.0, -116.5, 33.0]}
    with pytest.raises(ConfigError, match="allow_large_bbox"):
        scan_config_from_mapping(big)
    cfg = scan_config_from_mapping({**big, "palmscan": {"allow_large_bbox": True}})
    assert cfg.allow_large_bbox is True


def test_prefix_priors_and_clamps_come_from_region_config() -> None:
    cfg = scan_config_from_mapping(
        _raw(
            id_prefix="abc",
            exclusion={"margin_m": 2.0, "radius_min_m": 1.5, "radius_max_m": 6.0},
            species_priors={"washingtonia_robusta": 3, "phoenix_canariensis": 1},
        )
    )
    assert cfg.id_prefix == "abc"
    assert cfg.region.exclusion.margin_m == 2.0
    assert cfg.region.exclusion.radius_min_m == 1.5
    assert cfg.region.exclusion.radius_max_m == 6.0
    assert sum(cfg.species_priors.values()) == pytest.approx(1.0)
    assert cfg.species_priors["washingtonia_robusta"] == pytest.approx(0.75)
    assert cfg.bbox.as_tuple() == tuple(SD_BBOX)


def test_default_prefix_from_region_initials() -> None:
    assert scan_config_from_mapping(_raw()).id_prefix == "sdc"


def test_config_hash_stable_and_sensitive() -> None:
    a = scan_config_from_mapping(_raw()).config_hash()
    assert a == scan_config_from_mapping(_raw()).config_hash()
    assert len(a) == 64
    changed = scan_config_from_mapping(_raw(palmscan={"rules": {"height_min_m": 9}}))
    assert changed.config_hash() != a
    moved = scan_config_from_mapping({**_raw(), "bbox": [-117.28, 32.70, -117.15, 32.81]})
    assert moved.config_hash() != a


def test_load_scan_config_from_regions_dir() -> None:
    cfg = load_scan_config("san-diego-coastal", REPO / "regions")
    assert cfg.region_name == "san-diego-coastal"
    assert cfg.id_prefix == "sdc"
    assert cfg.rules.height_min_m == 8.0


def test_load_scan_config_missing_region(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_scan_config("nowhere", tmp_path)
