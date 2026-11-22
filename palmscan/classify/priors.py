"""Species priors from a region's inventory, and deterministic prior sampling (plan W8).

A prior is a mapping ``species_key -> share``. Palms whose species is unknown get a species
drawn from the priors by :func:`sample_species`, keyed on a stable key, so the same palm gets
the same species on every run and the result does not depend on input order.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Final

import yaml

from palmcore.log import get_logger
from palmscan.model import PalmRecord

log = get_logger(__name__)

# Same key pattern as the region ``species_priors`` schema (plan 01). Genus-level keys such as
# ``washingtonia`` have no underscore and do not match, so they are excluded by the pattern.
SPECIES_KEY_RE: Final = re.compile(r"^[a-z]+(_[a-z]+)+$")
UNKNOWN_SPECIES: Final = "palm_unknown"
FILIFERA: Final = "washingtonia_filifera"
ROBUSTA: Final = "washingtonia_robusta"

_SHARE_DECIMALS: Final = 2


class SpeciesMix(dict[str, float]):
    """Shares computed from inventory, with the number of palms they rest on.

    :func:`merge_priors` needs the palm count to apply ``min_n``, so :func:`compute_priors`
    returns this subclass rather than a plain dict.
    """

    def __init__(self, shares: Mapping[str, float], n_palms: int) -> None:
        super().__init__(shares)
        self.n_palms = n_palms


def compute_priors(palms: Iterable[PalmRecord], min_count: int = 1) -> SpeciesMix:
    """Shares of species-level keys among the given (inventory) palms.

    Palms with no species, genus-level values and ``palm_unknown`` are not counted. Species with
    fewer than ``min_count`` palms are dropped. Shares are rounded to 0.01 and renormalised; the
    result is sorted by share, descending, then by key, so it does not depend on input order.
    """
    counts: Counter[str] = Counter()
    for palm in palms:
        species = palm.species
        if species is None or species == UNKNOWN_SPECIES or not SPECIES_KEY_RE.match(species):
            continue
        counts[species] += 1

    kept = {key: n for key, n in counts.items() if n >= min_count}
    total = sum(kept.values())
    if total == 0:
        return SpeciesMix({}, 0)

    raw = {key: n / total for key, n in kept.items()}
    rounded = {key: round(share, _SHARE_DECIMALS) for key, share in raw.items()}
    positive = {key: share for key, share in rounded.items() if share > 0}
    if not positive:
        # Every share rounded to zero (very many species, few palms each): keep the exact shares.
        positive = raw
    norm = sum(positive.values())
    shares = {key: share / norm for key, share in positive.items()}
    ordered = dict(sorted(shares.items(), key=lambda item: (-item[1], item[0])))
    return SpeciesMix(ordered, total)


def merge_priors(
    computed: Mapping[str, float],
    configured: Mapping[str, float],
    min_n: int = 30,
    *,
    n_palms: int | None = None,
) -> dict[str, float]:
    """Use the computed mix when it rests on at least ``min_n`` palms, else the configured one.

    The palm count comes from ``computed.n_palms`` when ``computed`` is a :class:`SpeciesMix`;
    a plain mapping needs ``n_palms`` passed explicitly. The returned dict may be empty when the
    configured priors are empty too; :func:`sample_species` rejects that.
    """
    if isinstance(computed, SpeciesMix):
        count = computed.n_palms
    elif n_palms is not None:
        count = n_palms
    else:
        raise TypeError("merge_priors needs the palm count: pass a SpeciesMix or n_palms=")

    if computed and count >= min_n:
        log.info("species priors: computed from %d palms", count)
        return dict(computed)
    log.info("species priors: %d palms is below min_n=%d, using configured priors", count, min_n)
    return dict(configured)


def sample_species(priors: Mapping[str, float], key: str) -> str:
    """Pick a species from ``priors`` for ``key``. A pure function of its arguments.

    ``key`` should name the purpose as well as the palm, for example ``f"species|{stable_key}"``,
    so that other draws on the same palm do not correlate with this one.

    ``washingtonia_filifera`` weight is folded into ``washingtonia_robusta`` first, so
    filifera is never returned. ``u`` comes from SHA-1 of ``key``; the species are walked in
    alphabetical order and the first whose cumulative share exceeds ``u`` is returned.
    """
    if not priors:
        raise ValueError("cannot sample a species from empty priors")
    if not key:
        raise ValueError("sample_species needs a non-empty key")

    weights: dict[str, float] = {}
    for species, weight in priors.items():
        if not SPECIES_KEY_RE.match(species):
            raise ValueError(f"prior key is not a species key: {species!r}")
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"prior weight for {species!r} must be a finite value >= 0")
        weights[species] = float(weight)

    if FILIFERA in weights:
        folded = weights.pop(FILIFERA)
        weights[ROBUSTA] = weights.get(ROBUSTA, 0.0) + folded

    keys = sorted(species for species, weight in weights.items() if weight > 0)
    total = sum(weights[species] for species in keys)
    if total <= 0:
        raise ValueError("species priors must have a total weight above 0")

    u = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:12], 16) / 16**12
    cumulative = 0.0
    for species in keys:
        cumulative += weights[species] / total
        if cumulative > u:
            return species
    # Floating-point rounding can leave the total a hair under 1; the last key takes the rest.
    return keys[-1]


def priors_yaml(priors: Mapping[str, float]) -> str:
    """The ``species_priors:`` block, ready to paste into a region YAML."""
    for species in priors:
        if not SPECIES_KEY_RE.match(species):
            raise ValueError(f"prior key is not a species key: {species!r}")
    block = {"species_priors": {species: float(share) for species, share in priors.items()}}
    return yaml.safe_dump(block, sort_keys=False, default_flow_style=False, allow_unicode=True)
