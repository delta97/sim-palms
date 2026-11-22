"""palmscan.classify.species: rule boundaries, classification order, model fall-through."""

from __future__ import annotations

import numpy as np
import pytest

from palmscan.classify.priors import sample_species
from palmscan.classify.species import (
    DEFAULT_SHAPE_RULES,
    FEATURES,
    PRIOR_CONFIDENCE,
    ShapeRule,
    classify,
    features_of,
    shape_rules,
)
from palmscan.model import LidarCandidate, PalmRecord

PRIORS = {"phoenix_canariensis": 0.5, "sabal_palmetto": 0.5}


def cand(h: float, c: float, shared: float = 0.1) -> LidarCandidate:
    return LidarCandidate(
        candidate_id="d:t:1",
        dataset="d",
        x=0.0,
        y=0.0,
        lon=-117.2,
        lat=32.7,
        height_m=h,
        crown_area_m2=0.0,
        crown_diam_m=c,
        ratio=h / c,
        shared_boundary_frac=shared,
        ground_elev_m=None,
    )


def palm(
    key: str = "p1",
    species: str | None = None,
    lidar: LidarCandidate | None = None,
    source: str | None = None,
) -> PalmRecord:
    return PalmRecord(
        stable_key=key,
        lon=-117.2,
        lat=32.7,
        x=0.0,
        y=0.0,
        species=species,
        species_confidence=0.95 if species else None,
        species_source=source,
        lidar=lidar,
    )


class FakeModel:
    name = "lidar_tree"

    def __init__(self, answers: list[tuple[str | None, float]] | str | None) -> None:
        self.answers = answers
        self.seen: np.ndarray | None = None

    def predict(self, X: np.ndarray) -> list[tuple[str | None, float]]:
        self.seen = X
        if isinstance(self.answers, list):
            return self.answers
        return [(self.answers, 0.8)] * len(X)


@pytest.mark.parametrize(
    ("h", "c", "expected"),
    [
        (18.0, 5.0, ("washingtonia_robusta", 0.7)),
        (17.9, 5.0, (None, 0.0)),
        (18.0, 5.1, (None, 0.0)),
        (30.0, 1.0, ("washingtonia_robusta", 0.7)),
        (8.0, 7.0, ("phoenix_canariensis", 0.7)),
        (20.0, 12.0, ("phoenix_canariensis", 0.7)),
        (20.1, 7.0, (None, 0.0)),
        (7.9, 7.0, (None, 0.0)),
        (15.0, 6.9, ("syagrus_romanzoffiana", 0.5)),
        (8.0, 4.0, ("syagrus_romanzoffiana", 0.5)),
        (15.1, 6.0, (None, 0.0)),
        (12.0, 3.9, (None, 0.0)),
        (5.0, 2.0, (None, 0.0)),
    ],
)
def test_rule_boundaries(h: float, c: float, expected: tuple[str | None, float]) -> None:
    assert shape_rules(h, c) == expected


def test_overlap_goes_to_canariensis_not_syagrus() -> None:
    # 10 m / 7 m satisfies rules 2 and 3; rule order puts canariensis first.
    assert shape_rules(10.0, 7.0) == ("phoenix_canariensis", 0.7)


def test_rules_never_emit_filifera() -> None:
    species = {shape_rules(h / 2, c / 2)[0] for h in range(0, 80) for c in range(0, 40)}
    assert "washingtonia_filifera" not in species


def test_custom_rule_table_and_unregistered_key_rejected() -> None:
    table = (ShapeRule("phoenix_dactylifera", 0.6, height_min_m=1.0),)
    assert shape_rules(2.0, 2.0, table) == ("phoenix_dactylifera", 0.6)
    with pytest.raises(ValueError, match="species_keys"):
        shape_rules(2.0, 2.0, (ShapeRule("not_a_palm", 0.6),))
    with pytest.raises(ValueError, match="filifera"):
        shape_rules(2.0, 2.0, (ShapeRule("washingtonia_filifera", 0.6),))


def test_default_rules_use_registered_species() -> None:
    # A rule that emits an unregistered key raises when it matches; hit each default rule.
    probes = [(20.0, 4.0), (12.0, 8.0), (10.0, 5.0)]
    got = [shape_rules(h, c)[0] for h, c in probes]
    assert got == [rule.species for rule in DEFAULT_SHAPE_RULES]


def test_features_of_order() -> None:
    p = palm(lidar=cand(20.0, 4.0, 0.2))
    assert FEATURES == ["height_m", "crown_diam_m", "ratio", "shared_boundary_frac"]
    assert features_of(p).tolist() == [20.0, 4.0, 5.0, 0.2]
    with pytest.raises(ValueError):
        features_of(palm())


def test_inventory_species_never_overwritten() -> None:
    inv = palm("a", "sabal_palmetto", cand(20.0, 4.0), source="inventory")
    genus = palm("b", "phoenix_sp", cand(20.0, 4.0), source="osm")
    model = FakeModel("phoenix_canariensis")
    classify([inv, genus], PRIORS, model)
    assert (inv.species, inv.species_confidence, inv.species_source) == (
        "sabal_palmetto",
        0.95,
        "inventory",
    )
    assert genus.species == "phoenix_sp"
    assert model.seen is None


def test_model_answer_sets_lidar_tree() -> None:
    p = palm(lidar=cand(20.0, 4.0))
    model = FakeModel("phoenix_dactylifera")
    classify([p], PRIORS, model)
    assert (p.species, p.species_confidence, p.species_source) == (
        "phoenix_dactylifera",
        0.8,
        "lidar_tree",
    )
    assert model.seen is not None and model.seen.shape == (1, len(FEATURES))


def test_model_none_falls_through_to_rules() -> None:
    p = palm(lidar=cand(20.0, 4.0))
    classify([p], PRIORS, FakeModel(None))
    assert (p.species, p.species_confidence, p.species_source) == (
        "washingtonia_robusta",
        0.7,
        "lidar_rules",
    )


def test_per_palm_fall_through_in_one_batch() -> None:
    a, b = palm("a", lidar=cand(20.0, 4.0)), palm("b", lidar=cand(10.0, 7.0))
    classify([a, b], PRIORS, FakeModel([("phoenix_dactylifera", 0.6), (None, 0.0)]))
    assert (a.species_source, b.species_source) == ("lidar_tree", "lidar_rules")
    assert b.species == "phoenix_canariensis"


def test_no_model_uses_rules() -> None:
    p = palm(lidar=cand(10.0, 7.0))
    classify([p], PRIORS)
    assert (p.species, p.species_source) == ("phoenix_canariensis", "lidar_rules")


def test_rule_miss_falls_back_to_priors() -> None:
    p = palm("k1", lidar=cand(5.0, 2.0))
    classify([p], PRIORS)
    assert p.species == sample_species(PRIORS, "k1")
    assert p.species_confidence == PRIOR_CONFIDENCE == 0.3
    assert p.species_source == "prior"


def test_no_lidar_goes_to_priors_even_with_model() -> None:
    p = palm("k2")
    model = FakeModel("phoenix_dactylifera")
    classify([p], PRIORS, model)
    assert p.species_source == "prior"
    assert model.seen is None


def test_palm_unknown_is_reclassified() -> None:
    p = palm("k3", "palm_unknown", cand(20.0, 4.0), source="inventory")
    classify([p], PRIORS)
    assert (p.species, p.species_source) == ("washingtonia_robusta", "lidar_rules")


def test_priors_fold_filifera_and_ignore_input_order() -> None:
    palms = [palm(f"k{i}") for i in range(20)]
    classify(palms, {"washingtonia_filifera": 1.0})
    assert {p.species for p in palms} == {"washingtonia_robusta"}

    forward = [palm(f"k{i}") for i in range(20)]
    backward = [palm(f"k{i}") for i in reversed(range(20))]
    classify(forward, PRIORS)
    classify(backward, PRIORS)
    assert {p.stable_key: p.species for p in forward} == {p.stable_key: p.species for p in backward}


def test_empty_priors_leave_palm_unclassified() -> None:
    p = palm("k4")
    classify([p], {})
    assert (p.species, p.species_source) == (None, None)


def test_bad_model_output_rejected() -> None:
    with pytest.raises(ValueError, match="species_keys"):
        classify([palm(lidar=cand(20.0, 4.0))], PRIORS, FakeModel("not_a_palm"))
    with pytest.raises(ValueError, match="filifera"):
        classify([palm(lidar=cand(20.0, 4.0))], PRIORS, FakeModel("washingtonia_filifera"))
    with pytest.raises(ValueError, match="answers"):
        classify([palm(lidar=cand(20.0, 4.0))], PRIORS, FakeModel([]))
