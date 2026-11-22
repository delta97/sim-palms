"""Offline checks on the example region files in ``regions/``. Never fetches their URLs."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from palmcore.config import check_regions, list_regions, load_region

REPO = Path(__file__).resolve().parents[3]
REGIONS = REPO / "regions"
ENVELOPE = (-125.0, 24.0, -66.0, 50.0)  # lon_min, lat_min, lon_max, lat_max (contiguous US)
EXPECTED_PREFIXES = {"san-diego-coastal": "sdc", "la-westside": "law"}


def test_example_regions_present() -> None:
    assert set(EXPECTED_PREFIXES) <= set(list_regions(REGIONS))


@pytest.mark.parametrize("stem", list_regions(REGIONS))
def test_region_loads_without_warnings(stem: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        cfg = load_region(stem, regions_dir=REGIONS)
    assert cfg.region == stem
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert cfg.sources.inventory, "example regions should have at least one inventory source"


@pytest.mark.parametrize("stem", list_regions(REGIONS))
def test_region_bbox_within_envelope(stem: str) -> None:
    cfg = load_region(stem, regions_dir=REGIONS)
    lon_min, lat_min, lon_max, lat_max = ENVELOPE
    b = cfg.bbox
    assert lon_min <= b.lon_min < b.lon_max <= lon_max
    assert lat_min <= b.lat_min < b.lat_max <= lat_max


def test_check_regions_clean() -> None:
    assert check_regions(REGIONS) == []


def test_id_prefixes_unique_and_expected() -> None:
    prefixes = {s: load_region(s, regions_dir=REGIONS).id_prefix for s in list_regions(REGIONS)}
    assert len(set(prefixes.values())) == len(prefixes)
    for stem, prefix in EXPECTED_PREFIXES.items():
        assert prefixes[stem] == prefix
