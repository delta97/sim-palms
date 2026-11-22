"""Self-tests for tests/helpers/sites.py: the committed registry and range checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.fixtures import fixture_path
from tests.helpers.sites import (
    SITES_FILE,
    Site,
    SiteRegistryError,
    Viewpoint,
    get_site,
    load_sites,
)

VALID = fixture_path("helpers", "sites/valid.yaml")
VALID_TEXT = VALID.read_text(encoding="utf-8")


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sites.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_committed_skeleton_loads() -> None:
    sites = load_sites()
    assert sorted(sites) == ["T1", "T2", "T3", "T4", "T5"]
    assert all(site.status == "placeholder" for site in sites.values())
    assert sites["T5"].purpose == "no_harm"
    assert sites["T5"].photogrammetry is False
    for site in sites.values():
        assert [vp.id for vp in site.viewpoints] == ["VP1", "VP2", "VP3"]
        assert site.flight is None


def test_valid_fixture_loads_with_types() -> None:
    sites = load_sites(VALID)
    assert list(sites) == ["T1"]
    site = sites["T1"]
    assert isinstance(site, Site)
    assert site.status == "defined"
    assert site.purpose == "happy_path"
    assert site.bbox == (-117.2560, 32.7870, -117.2500, 32.7920)
    assert all(isinstance(v, float) for v in site.bbox)
    assert site.photogrammetry is True and site.inventory_coverage is True
    assert site.ground_truth is False
    assert site.flight is None
    assert isinstance(site.viewpoints, tuple) and len(site.viewpoints) == 3
    vp1 = site.viewpoints[0]
    assert isinstance(vp1, Viewpoint)
    assert (vp1.id, vp1.kind, vp1.alt_m_agl, vp1.preset) == ("VP1", "street", 2.0, None)
    assert [vp.kind for vp in site.viewpoints] == ["street", "oblique", "approach"]


def test_bad_bbox_fixture_raises_with_site_and_rule() -> None:
    with pytest.raises(ValueError, match=r"site T1: bbox .*lon_min.*lon_max") as info:
        load_sites(fixture_path("helpers", "sites/bad_bbox.yaml"))
    assert isinstance(info.value, SiteRegistryError)


def test_two_viewpoints_fixture_fails_schema() -> None:
    with pytest.raises(SiteRegistryError, match=r"sites\.T1\.viewpoints"):
        load_sites(fixture_path("helpers", "sites/two_viewpoints.yaml"))


@pytest.mark.parametrize(
    ("old", "new", "rule"),
    [
        # VP1 altitude band is 1-5 m.
        ("alt_m_agl: 2,", "alt_m_agl: 30,", "VP1 alt_m_agl 30 is outside 1 to 5 m"),
        # VP2 altitude band is 100-200 m.
        ("alt_m_agl: 150,", "alt_m_agl: 50,", "VP2 alt_m_agl 50 is outside 100 to 200 m"),
        # Bbox is about 550 m wide; 0.056 degrees of longitude is about 5 km.
        (
            "bbox: [-117.2560, 32.7870, -117.2500, 32.7920]",
            "bbox: [-117.3060, 32.7870, -117.2500, 32.7920]",
            "bbox width",
        ),
        # Viewpoints must lie within the bbox expanded by 1 km.
        (
            "lat: 32.7895, lon: -117.2530, alt_m_agl: 600",
            "lat: 33.5, lon: -117.2530, alt_m_agl: 600",
            "VP3 (33.5, -117.253) is outside the bbox expanded by 1000 m",
        ),
    ],
)
def test_defined_site_range_rules(tmp_path: Path, old: str, new: str, rule: str) -> None:
    text = VALID_TEXT.replace(old, new, 1)
    assert text != VALID_TEXT, "test edit did not apply"
    with pytest.raises(SiteRegistryError) as info:
        load_sites(_write(tmp_path, text))
    assert "site T1" in str(info.value)
    assert rule in str(info.value)


def test_placeholder_site_skips_range_checks(tmp_path: Path) -> None:
    # Zero coordinates and an inverted bbox are fine while status is placeholder.
    text = VALID_TEXT.replace("status: defined", "status: placeholder", 1)
    text = text.replace("bbox: [-117.2560, 32.7870, -117.2500, 32.7920]", "bbox: [0, 0, 0, 0]")
    site = load_sites(_write(tmp_path, text))["T1"]
    assert site.status == "placeholder"
    assert site.bbox == (0.0, 0.0, 0.0, 0.0)


def test_get_site_returns_site() -> None:
    assert get_site("T1", VALID).name == "Fixture street, San Diego"


def test_get_site_unknown_id_lists_known_ids() -> None:
    with pytest.raises(KeyError, match="T9") as info:
        get_site("T9", SITES_FILE)
    message = str(info.value)
    assert all(f"T{n}" in message for n in range(1, 6))
