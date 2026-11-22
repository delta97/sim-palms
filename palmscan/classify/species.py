"""Species classification in the source plan's order (plan W18, ``species.py`` part).

Per palm, the first answer wins:

1. a species already set from inventory or OSM (species- or genus-level) is left alone;
2. a LiDAR shape plus a ``ShapeModel``: the model's answer, ``species_source="lidar_tree"``;
3. a LiDAR shape: :func:`shape_rules`, ``species_source="lidar_rules"``;
4. otherwise a draw from the regional priors (:func:`palmscan.classify.priors.sample_species`),
   confidence :data:`PRIOR_CONFIDENCE`, ``species_source="prior"``.

The rule thresholds are data (:data:`DEFAULT_SHAPE_RULES`), not logic, so a region can pass its own
table. Every species a rule or a model emits must be in ``palmscan/data/species_keys.yaml``, and
``washingtonia_filifera`` is never emitted (it looks like robusta in LiDAR; the priors sampler
folds it into robusta as well).
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

import numpy as np
import yaml

from palmcore.log import get_logger
from palmscan.classify.priors import FILIFERA, UNKNOWN_SPECIES, sample_species
from palmscan.model import PalmRecord
from palmscan.species_names import read_data_text

__all__ = [
    "DEFAULT_SHAPE_RULES",
    "FEATURES",
    "PRIOR_CONFIDENCE",
    "ShapeModel",
    "ShapeRule",
    "classify",
    "features_of",
    "shape_rules",
]

log = get_logger(__name__)

# Order of the columns of ``features_of``; SCAN-027 trains and predicts on this order.
FEATURES: Final = ["height_m", "crown_diam_m", "ratio", "shared_boundary_frac"]

PRIOR_CONFIDENCE: Final = 0.3  # source plan section 5: "anything else" -> priors at 0.3

SOURCE_MODEL: Final = "lidar_tree"
SOURCE_RULES: Final = "lidar_rules"
SOURCE_PRIOR: Final = "prior"


@dataclass(frozen=True, slots=True)
class ShapeRule:
    """One LiDAR shape rule. A ``None`` bound is open; bounds that are set are inclusive."""

    species: str
    confidence: float
    height_min_m: float | None = None
    height_max_m: float | None = None
    crown_min_m: float | None = None
    crown_max_m: float | None = None

    def matches(self, height_m: float, crown_diam_m: float) -> bool:
        return (
            (self.height_min_m is None or height_m >= self.height_min_m)
            and (self.height_max_m is None or height_m <= self.height_max_m)
            and (self.crown_min_m is None or crown_diam_m >= self.crown_min_m)
            and (self.crown_max_m is None or crown_diam_m <= self.crown_max_m)
        )


# Starting values from source plan section 5 (plans/02-detection-pipeline.md), first match wins.
# VERIFY: the plan gives these as starting values without a cited source, and the reference
# sheets under assets/reference/ (ASSET-001) do not carry species height/crown ranges yet.
# Check them against the sheets, and against labelled inventory-plus-LiDAR matches (SCAN-027).
DEFAULT_SHAPE_RULES: Final[tuple[ShapeRule, ...]] = (
    # Tall and narrow: Mexican fan palm.
    ShapeRule("washingtonia_robusta", 0.7, height_min_m=18.0, crown_max_m=5.0),
    # Wide crown, mid height: Canary Island date palm.
    ShapeRule("phoenix_canariensis", 0.7, height_min_m=8.0, height_max_m=20.0, crown_min_m=7.0),
    # Mid height, mid crown: queen palm.
    ShapeRule(
        "syagrus_romanzoffiana",
        0.5,
        height_min_m=8.0,
        height_max_m=15.0,
        crown_min_m=4.0,
        crown_max_m=7.0,
    ),
)


class ShapeModel(Protocol):
    """A trained shape classifier (SCAN-027's ``TreeModel`` implements this)."""

    name: str  # "lidar_tree"

    def predict(self, X: np.ndarray) -> list[tuple[str | None, float]]:
        """One ``(species, confidence)`` per row of ``X`` (columns as ``FEATURES``).

        ``None`` as the species means "no answer": the palm falls through to the rules.
        """
        ...


@functools.cache
def _registered_keys() -> frozenset[str]:
    data = yaml.safe_load(read_data_text("species_keys.yaml"))
    return frozenset(row["key"] for row in data["keys"])


def _check_emittable(species: str, origin: str) -> None:
    if species not in _registered_keys():
        raise ValueError(f"{origin} returned {species!r}, which is not in species_keys.yaml")
    if species == FILIFERA:
        raise ValueError(f"{origin} returned {FILIFERA}; shape classifiers never output it")


def shape_rules(
    height_m: float,
    crown_diam_m: float,
    rules: Sequence[ShapeRule] = DEFAULT_SHAPE_RULES,
) -> tuple[str | None, float]:
    """``(species, confidence)`` of the first matching rule, else ``(None, 0.0)``."""
    for rule in rules:
        if rule.matches(height_m, crown_diam_m):
            _check_emittable(rule.species, "shape rule")
            return rule.species, rule.confidence
    return None, 0.0


def features_of(palm: PalmRecord) -> np.ndarray:
    """The palm's LiDAR shape as a float row in ``FEATURES`` order."""
    cand = palm.lidar
    if cand is None:
        raise ValueError(f"palm {palm.stable_key} has no LiDAR shape")
    return np.array(
        [cand.height_m, cand.crown_diam_m, cand.ratio, cand.shared_boundary_frac], dtype=float
    )


def _has_species(palm: PalmRecord) -> bool:
    return palm.species is not None and palm.species != UNKNOWN_SPECIES


def _assign(palm: PalmRecord, species: str, confidence: float, source: str) -> None:
    palm.species = species
    palm.species_confidence = confidence
    palm.species_source = source


def classify(
    palms: list[PalmRecord],
    priors: dict[str, float],
    model: ShapeModel | None = None,
    rules: Sequence[ShapeRule] = DEFAULT_SHAPE_RULES,
) -> None:
    """Set ``species``, ``species_confidence`` and ``species_source`` in place, in plan order.

    Palms with a species from inventory or OSM are untouched; ``palm_unknown`` counts as no
    species. With empty ``priors`` a palm that nothing else classifies is left unclassified.
    """
    todo = [p for p in palms if not _has_species(p)]
    shaped = [p for p in todo if p.lidar is not None]

    answers: dict[str, tuple[str | None, float]] = {}
    if model is not None and shaped:
        X = np.vstack([features_of(p) for p in shaped])
        predicted = model.predict(X)
        if len(predicted) != len(shaped):
            raise ValueError(f"model returned {len(predicted)} answers for {len(shaped)} palms")
        answers = {p.stable_key: ans for p, ans in zip(shaped, predicted, strict=True)}

    n_unclassified = 0
    for palm in todo:
        if palm.lidar is not None:
            species, confidence = answers.get(palm.stable_key, (None, 0.0))
            if species is not None:
                _check_emittable(species, f"model {getattr(model, 'name', '?')}")
                _assign(palm, species, confidence, SOURCE_MODEL)
                continue
            species, confidence = shape_rules(palm.lidar.height_m, palm.lidar.crown_diam_m, rules)
            if species is not None:
                _assign(palm, species, confidence, SOURCE_RULES)
                continue
        if not priors:
            n_unclassified += 1
            continue
        _assign(palm, sample_species(priors, palm.stable_key), PRIOR_CONFIDENCE, SOURCE_PRIOR)

    if n_unclassified:
        log.warning("species: %d palms left unclassified, no priors configured", n_unclassified)
