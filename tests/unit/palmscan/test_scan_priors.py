"""palmscan.classify.priors: computed shares, min_n switch, deterministic sampling, YAML."""

from __future__ import annotations

from collections import Counter

import pytest
import yaml

from palmscan.classify.priors import (
    SpeciesMix,
    compute_priors,
    merge_priors,
    priors_yaml,
    sample_species,
)
from palmscan.model import PalmRecord

KNOWN = {
    "phoenix_canariensis": 0.5,
    "sabal_palmetto": 0.3,
    "washingtonia_robusta": 0.2,
}


def palm(i: int, species: str | None) -> PalmRecord:
    return PalmRecord(
        stable_key=f"src:inv-{i:06d}",
        lon=-117.2,
        lat=32.7,
        x=0.0,
        y=0.0,
        species=species,
        species_confidence=None,
        species_source="inventory" if species else None,
    )


def inventory(counts: dict[str | None, int]) -> list[PalmRecord]:
    palms: list[PalmRecord] = []
    for species, n in counts.items():
        for _ in range(n):
            palms.append(palm(len(palms), species))
    return palms


def test_compute_shares_from_known_list() -> None:
    palms = inventory(
        {
            "washingtonia_robusta": 6,
            "washingtonia_filifera": 3,
            "phoenix_canariensis": 1,
            "palm_unknown": 4,
            "washingtonia": 5,  # genus-level
            "Washingtonia": 2,  # not a species key
            None: 7,
        }
    )
    priors = compute_priors(palms)
    assert isinstance(priors, SpeciesMix)
    assert priors.n_palms == 10
    assert dict(priors) == pytest.approx(
        {"washingtonia_robusta": 0.6, "washingtonia_filifera": 0.3, "phoenix_canariensis": 0.1}
    )
    assert list(priors) == ["washingtonia_robusta", "washingtonia_filifera", "phoenix_canariensis"]
    assert sum(priors.values()) == pytest.approx(1.0)


def test_compute_is_independent_of_input_order() -> None:
    palms = inventory({"phoenix_canariensis": 4, "sabal_palmetto": 4, "washingtonia_robusta": 2})
    forward = compute_priors(palms)
    backward = compute_priors(list(reversed(palms)))
    assert list(forward.items()) == list(backward.items())


def test_compute_min_count_and_empty() -> None:
    palms = inventory({"phoenix_canariensis": 3, "sabal_palmetto": 1})
    priors = compute_priors(palms, min_count=2)
    assert dict(priors) == {"phoenix_canariensis": 1.0}
    assert priors.n_palms == 3
    empty = compute_priors([palm(0, None), palm(1, "palm_unknown")])
    assert dict(empty) == {}
    assert empty.n_palms == 0


def test_merge_switches_on_min_n() -> None:
    configured = {"sabal_palmetto": 1.0}
    small = compute_priors(inventory({"phoenix_canariensis": 29}))
    assert small.n_palms == 29
    assert merge_priors(small, configured, min_n=30) == configured
    enough = compute_priors(inventory({"phoenix_canariensis": 30}))
    assert merge_priors(enough, configured, min_n=30) == {"phoenix_canariensis": 1.0}


def test_merge_with_plain_mapping_needs_n_palms() -> None:
    computed = {"phoenix_canariensis": 1.0}
    configured = {"sabal_palmetto": 1.0}
    assert merge_priors(computed, configured, min_n=30, n_palms=30) == computed
    assert merge_priors(computed, configured, min_n=30, n_palms=5) == configured
    with pytest.raises(TypeError):
        merge_priors(computed, configured, min_n=30)


def test_sample_is_a_pure_function_of_priors_and_key() -> None:
    picks = [sample_species(KNOWN, "species|src:inv-000001") for _ in range(5)]
    assert len(set(picks)) == 1
    copy_priors = dict(KNOWN)
    assert sample_species(copy_priors, "species|src:inv-000001") == picks[0]


def test_sample_distribution_matches_priors_over_10000_keys() -> None:
    counts: Counter[str] = Counter(
        sample_species(KNOWN, f"species|src:inv-{i:06d}") for i in range(10_000)
    )
    assert set(counts) <= set(KNOWN)
    for species, share in KNOWN.items():
        assert abs(counts[species] / 10_000 - share) <= 0.02


def test_filifera_folds_into_robusta_and_is_never_returned() -> None:
    priors = {"washingtonia_filifera": 0.4, "washingtonia_robusta": 0.2, "phoenix_canariensis": 0.4}
    counts: Counter[str] = Counter(
        sample_species(priors, f"species|src:inv-{i:06d}") for i in range(10_000)
    )
    assert "washingtonia_filifera" not in counts
    assert abs(counts["washingtonia_robusta"] / 10_000 - 0.6) <= 0.02
    assert abs(counts["phoenix_canariensis"] / 10_000 - 0.4) <= 0.02


def test_only_filifera_gives_robusta() -> None:
    assert sample_species({"washingtonia_filifera": 1.0}, "species|x") == "washingtonia_robusta"


def test_sample_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        sample_species({}, "species|x")
    with pytest.raises(ValueError):
        sample_species({"phoenix_canariensis": 0.0}, "species|x")
    with pytest.raises(ValueError):
        sample_species({"phoenix": 1.0}, "species|x")  # genus-level key
    with pytest.raises(ValueError):
        sample_species({"phoenix_canariensis": -0.1, "sabal_palmetto": 1.1}, "species|x")
    with pytest.raises(ValueError):
        sample_species(KNOWN, "")


def test_priors_yaml_round_trips() -> None:
    priors = dict(
        compute_priors(
            inventory({"phoenix_canariensis": 7, "sabal_palmetto": 3, "washingtonia_robusta": 1})
        )
    )
    text = priors_yaml(priors)
    assert text.startswith("species_priors:")
    loaded = yaml.safe_load(text)
    assert loaded == {"species_priors": priors}
    assert list(loaded["species_priors"]) == list(priors)
    assert yaml.safe_load(priors_yaml({})) == {"species_priors": {}}
    with pytest.raises(ValueError):
        priors_yaml({"phoenix": 1.0})
