"""palmscan.filters: non-tree markers and the palm genus filter."""

from __future__ import annotations

import pytest

from palmscan.filters import non_tree_reason, palm_filter
from palmscan.species_names import normalize_species


@pytest.mark.parametrize(
    ("species", "status", "reason"),
    [
        ("Vacant Site", None, "vacant"),
        ("VACANT PLANTING SITE", "", "vacant"),
        ("Vacant site - large", None, "vacant"),
        ("Washingtonia robusta", "STUMP", "stump"),
        ("Stump", None, "stump"),
        ("Stump removal", None, "stump"),
        ("Queen palm", "Removed", "removed"),
        ("Queen palm", "Tree removed 2019", "removed"),
        ("Phoenix canariensis", "Stump (grind)", "stump"),
        ("Removed", None, "removed"),
        (None, "vacant", "vacant"),
    ],
)
def test_non_tree_reason_hits(species: str | None, status: str | None, reason: str) -> None:
    assert non_tree_reason(species, status) == reason


@pytest.mark.parametrize(
    ("species", "status"),
    [
        ("Washingtonia robusta", None),
        ("Washingtonia robusta", ""),
        ("Washingtonia robusta", "Dead"),  # dead palms can still stand
        ("Washingtonia robusta", "Good"),
        ("Stumpy tree", None),  # a marker must be the whole species or a leading phrase
        (None, None),
        ("", ""),
    ],
)
def test_non_tree_reason_misses(species: str | None, status: str | None) -> None:
    assert non_tree_reason(species, status) is None


def test_stump_wins_over_removed() -> None:
    assert non_tree_reason(None, "Removed - stump") == "stump"


def test_vacant_site_is_never_a_palm_row() -> None:
    assert non_tree_reason("Vacant Site", None) is not None
    assert normalize_species("Vacant Site").is_palm is False


def test_palm_filter_keeps_modelled_socal_palm() -> None:
    ns = normalize_species("Washingtonia robusta")
    assert palm_filter(ns, ["socal"], []) is None


def test_palm_filter_not_palm() -> None:
    assert palm_filter(normalize_species("Quercus agrifolia"), ["socal"], []) == "not_palm"
    assert palm_filter(normalize_species("Sago palm"), ["socal", "florida"], []) == "not_palm"
    assert palm_filter(normalize_species(None), ["socal"], []) == "not_palm"


def test_florida_genus_needs_the_florida_set() -> None:
    ns = normalize_species("Sabal palmetto")
    assert palm_filter(ns, ["socal"], []) == "genus_not_in_set"
    assert palm_filter(ns, ["socal", "florida"], []) is None
    assert palm_filter(ns, ("florida",), []) is None


def test_other_genus_needs_the_other_set() -> None:
    ns = normalize_species("Howea forsteriana")
    assert palm_filter(ns, ["socal", "florida"], []) == "genus_not_in_set"
    assert palm_filter(ns, ["other"], []) is None


def test_excluded_species() -> None:
    ns = normalize_species("Pygmy date palm")
    assert palm_filter(ns, ["socal"], ["phoenix_roebelenii"]) == "excluded_species"
    assert palm_filter(ns, ["socal"], ["phoenix_canariensis"]) is None
    # The exclusion is checked before the genus-set test.
    assert (
        palm_filter(normalize_species("Sabal palmetto"), ["socal"], ["sabal_palmetto"])
        == "excluded_species"
    )


def test_generic_palm_is_kept() -> None:
    assert palm_filter(normalize_species("Palm"), ["socal"], []) is None
    assert palm_filter(normalize_species("Palm"), ["socal"], ["palm_unknown"]) == "excluded_species"


def test_genus_level_name_uses_the_genus() -> None:
    ns = normalize_species("Phoenix spp.")
    assert palm_filter(ns, ["socal"], []) is None
    assert palm_filter(ns, ["florida"], []) == "genus_not_in_set"


def test_unknown_genus_set_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown genus set"):
        palm_filter(normalize_species("Phoenix spp."), ["atlantis"], [])
