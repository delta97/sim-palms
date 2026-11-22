"""Row filters applied before palms are accepted: non-tree markers and the palm genus filter."""

from __future__ import annotations

import functools
from collections.abc import Sequence

import yaml

from palmcore.errors import ConfigError
from palmscan.species_names import NormalizedSpecies, clean_name, genus_set_members, read_data_text

__all__ = ["non_tree_reason", "palm_filter"]


@functools.cache
def _markers() -> tuple[tuple[str, tuple[str, ...]], ...]:
    data = yaml.safe_load(read_data_text("non_tree_markers.yaml"))
    reasons = data.get("reasons") if isinstance(data, dict) else None
    if not isinstance(reasons, dict):
        raise ConfigError("non_tree_markers.yaml: missing 'reasons' mapping")
    return tuple(
        (str(reason), tuple(clean_name(str(m)) for m in markers))
        for reason, markers in reasons.items()
    )


def non_tree_reason(species_raw: str | None, status_raw: str | None) -> str | None:
    """``stump``, ``vacant`` or ``removed`` for a row that is not a standing tree, else ``None``.

    Species text matches a marker exactly or as a leading phrase; status text matches by substring.
    """
    species = clean_name(species_raw)
    status = clean_name(status_raw)
    for reason, markers in _markers():
        for marker in markers:
            if not marker:
                continue
            if species and (species == marker or species.startswith(marker + " ")):
                return reason
            if status and marker in status:
                return reason
    return None


def palm_filter(
    ns: NormalizedSpecies, genus_sets: Sequence[str], exclude_species: Sequence[str]
) -> str | None:
    """Return ``None`` to keep, else a reject reason: ``not_palm``, ``excluded_species`` or
    ``genus_not_in_set``. A generic "palm" (no genus known) is kept."""
    if not ns.is_palm:
        return "not_palm"
    if ns.key is not None and ns.key in exclude_species:
        return "excluded_species"
    if ns.genus is not None:
        allowed: set[str] = set()
        for name in genus_sets:
            allowed |= genus_set_members(name)
        if ns.genus not in allowed:
            return "genus_not_in_set"
    return None
