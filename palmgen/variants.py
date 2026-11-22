"""Variant selection, scaling and heading (GEN-011).

The asset manifest (``palmcore.assets``) owns the library: variants, ``scale_limits`` and
``species_fallback`` (ASSET-005, plan 03 "Scale limits and species fallback"). This module turns the
typed ``Manifest`` into a :class:`VariantLibrary`, adds GEN's checks, and picks one variant, a scale
and a heading per palm. It never parses the manifest JSON itself.

Selection rules, for a palm of species ``s`` and height ``h``:

1. Species: ``s`` if the manifest has variants for it; else ``species_fallback[s]``; else the
   region ``species_priors`` entry with the highest value that has variants (ties alphabetical),
   only when the priors are non-empty; else ``species_fallback["_default"]``.
2. Height missing: ``h`` is the median ``native_height_m`` of the chosen species' variants.
3. Variant: smallest ``abs(ln(h / native_height_m))``; ties go to the lower native height.
   Variants sharing that native height (alternate crowns) are sorted by name and one is chosen by
   ``unit_hash(palm_id, "alt")``.
4. Scale: ``h / native_height_m`` clamped to ``[1 - clamp, 1 + clamp]`` when the region sets
   ``placement.scale_clamp``, otherwise to the manifest ``scale_limits``.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from palmcore.assets import manifest as asset_manifest
from palmcore.errors import ConfigError, ContractError
from palmgen.errors import InputError
from palmgen.ids import unit_hash
from palmgen.model import BuildWarning, Palm

DEFAULT_FALLBACK_KEY: Final = asset_manifest.DEFAULT_KEY

SPECIES_FALLBACK: Final = "SPECIES_FALLBACK"
HEIGHT_MISSING: Final = "HEIGHT_MISSING"
SCALE_CLAMPED: Final = "SCALE_CLAMPED"

PLACEHOLDER_SPECIES: Final = "placeholder"
_TIE_DIGITS: Final = 9


@dataclass(frozen=True)
class Variant:
    species: str
    variant: str
    model_guid: str
    native_height_m: float
    simobject_title: str | None


@dataclass(frozen=True)
class Selection:
    variant: Variant
    scale: float
    scale_clamped: bool
    species_fallback: bool
    height_missing: bool


@dataclass(frozen=True)
class VariantLibrary:
    """Variants grouped by species (each list sorted by ``(native_height_m, variant)``) plus the
    manifest's scale limits and species fallback map."""

    variants: Mapping[str, tuple[Variant, ...]]
    scale_min: float
    scale_max: float
    species_fallback: Mapping[str, str] = field(default_factory=dict)
    package_version: str | None = None


@dataclass
class SelectionResult:
    """What :func:`select_all` returns: the selections, warnings and counters for the report."""

    placements: list[tuple[Palm, Selection]] = field(default_factory=list)
    warnings: list[BuildWarning] = field(default_factory=list)
    scale_clamped: int = 0
    species_fallback: int = 0
    height_missing: int = 0

    def counts(self) -> dict[str, int]:
        """The three build-report counters this stage owns."""
        return {
            "scale_clamped": self.scale_clamped,
            "species_fallback": self.species_fallback,
            "height_missing": self.height_missing,
        }


# --- loading -------------------------------------------------------------------------------


def _library_from_variants(
    variants: Iterable[Variant],
    scale_min: float,
    scale_max: float,
    species_fallback: Mapping[str, str],
    package_version: str | None = None,
) -> VariantLibrary:
    """Check and group ``variants``; raises ``InputError`` naming the offending entry."""
    by_species: dict[str, list[Variant]] = {}
    seen: set[tuple[str, str]] = set()
    for v in variants:
        where = f"manifest entry {v.species}/{v.variant}"
        if (v.species, v.variant) in seen:
            raise InputError(f"{where}: duplicate (species, variant)")
        seen.add((v.species, v.variant))
        if not v.model_guid:
            raise InputError(f"{where}: missing model_guid")
        if not v.native_height_m > 0:
            raise InputError(f"{where}: native_height_m must be > 0, got {v.native_height_m!r}")
        by_species.setdefault(v.species, []).append(v)
    if not by_species:
        raise InputError("manifest has no variants")
    if not 0 < scale_min <= scale_max:
        raise InputError(f"manifest scale_limits {scale_min}..{scale_max} are not valid")
    grouped = {
        species: tuple(sorted(vs, key=lambda v: (v.native_height_m, v.variant)))
        for species, vs in sorted(by_species.items())
    }
    return VariantLibrary(grouped, scale_min, scale_max, dict(species_fallback), package_version)


def load_manifest(path: Path) -> VariantLibrary:
    """Load ``path`` through ``palmcore.assets.manifest.load_manifest`` and apply GEN's checks.

    Raises ``InputError`` for an unreadable or schema-invalid manifest, a duplicate
    ``(species, variant)``, a variant whose ``native_height_m`` is missing or ``<= 0``, and a
    manifest with no variants.
    """
    try:
        manifest = asset_manifest.load_manifest(Path(path))
    except ContractError as exc:
        detail = "; ".join(str(i) for i in exc.issues[:5])
        raise InputError(f"{exc}" + (f": {detail}" if detail else "")) from exc
    except ConfigError as exc:
        raise InputError(str(exc)) from exc
    variants: list[Variant] = []
    for key, species in manifest.species.items():
        for v in species.variants:
            if v.native_height_m is None:
                raise InputError(
                    f"manifest entry {key}/{v.variant}: native_height_m is null "
                    "(model not measured; rebuild the manifest)"
                )
            variants.append(
                Variant(key, v.variant, v.model_guid, v.native_height_m, v.simobject_title)
            )
    return _library_from_variants(
        variants,
        manifest.scale_limits.min,
        manifest.scale_limits.max,
        manifest.species_fallback,
        manifest.package_version,
    )


def placeholder_selection(placeholder_model: Mapping[str, Any] | None) -> Selection:
    """Selection for ``--models placeholder``: the template's stand-in model at scale 1.0."""
    if not placeholder_model or not placeholder_model.get("model_guid"):
        raise InputError("templates.yaml placeholder_model has no model_guid")
    height = placeholder_model.get("native_height_m")
    variant = Variant(
        species=PLACEHOLDER_SPECIES,
        variant=str(placeholder_model.get("name") or PLACEHOLDER_SPECIES),
        model_guid=str(placeholder_model["model_guid"]),
        native_height_m=float(height) if height else 1.0,
        simobject_title=None,
    )
    return Selection(variant, 1.0, False, False, False)


# --- selection -----------------------------------------------------------------------------


def _resolve_species(
    species: str, library: VariantLibrary, priors: Mapping[str, float]
) -> str | None:
    """Species whose variants stand in for ``species`` (itself when it has variants)."""
    have = library.variants
    if species in have:
        return species
    target = library.species_fallback.get(species)
    if target in have:
        return target
    if priors:
        ranked = sorted((s for s in priors if s in have), key=lambda s: (-priors[s], s))
        if ranked:
            return ranked[0]
    target = library.species_fallback.get(DEFAULT_FALLBACK_KEY)
    return target if target in have else None


def select_variant(
    palm: Palm,
    library: VariantLibrary,
    priors: Mapping[str, float],
    clamp: float | None = None,
) -> Selection:
    """Pick the variant and scale for one palm. ``clamp`` is the region override (or ``None``)."""
    used = _resolve_species(palm.species, library, priors)
    if used is None:
        raise InputError(
            f"palm {palm.palm_id}: species {palm.species!r} has no variant and no usable "
            f"fallback (add species_fallback[{DEFAULT_FALLBACK_KEY!r}] to the manifest)"
        )
    candidates = library.variants[used]
    height_missing = palm.height_m is None
    if palm.height_m is None:
        target = statistics.median(v.native_height_m for v in candidates)
    else:
        target = palm.height_m
    if not target > 0:
        raise InputError(f"palm {palm.palm_id}: height_m must be > 0, got {palm.height_m!r}")

    def distance(v: Variant) -> tuple[float, float]:
        return (round(abs(math.log(target / v.native_height_m)), _TIE_DIGITS), v.native_height_m)

    best = min(candidates, key=distance)
    same_height = sorted(
        (v for v in candidates if v.native_height_m == best.native_height_m),
        key=lambda v: v.variant,
    )
    chosen = same_height[
        min(int(unit_hash(palm.palm_id, "alt") * len(same_height)), len(same_height) - 1)
    ]

    if clamp is None:
        lo, hi = library.scale_min, library.scale_max
    else:
        lo, hi = 1.0 - clamp, 1.0 + clamp
    raw = target / chosen.native_height_m
    scale = min(max(raw, lo), hi)
    return Selection(
        variant=chosen,
        scale=scale,
        scale_clamped=scale != raw,
        species_fallback=used != palm.species,
        height_missing=height_missing,
    )


def heading_deg(palm_id: str) -> float:
    """Stable heading in ``[0, 360)``, one decimal."""
    return round(unit_hash(palm_id, "heading") * 360, 1) % 360


def selection_warnings(palm: Palm, selection: Selection) -> list[BuildWarning]:
    """Build warnings for one selection, in a fixed order."""
    out: list[BuildWarning] = []
    v = selection.variant
    if selection.species_fallback:
        out.append(
            BuildWarning(
                SPECIES_FALLBACK,
                f"{palm.palm_id}: species {palm.species!r} has no variants, used {v.species!r}",
                palm.palm_id,
            )
        )
    if selection.height_missing:
        out.append(
            BuildWarning(
                HEIGHT_MISSING,
                f"{palm.palm_id}: height missing, used the median of {v.species!r} variants",
                palm.palm_id,
            )
        )
    if selection.scale_clamped:
        out.append(
            BuildWarning(
                SCALE_CLAMPED,
                f"{palm.palm_id}: height {palm.height_m} m needs more scaling than allowed, "
                f"scale clamped to {selection.scale:.3f} on {v.species}/{v.variant}",
                palm.palm_id,
            )
        )
    return out


def select_all(
    palms: Iterable[Palm],
    library: VariantLibrary,
    priors: Mapping[str, float],
    clamp: float | None = None,
) -> SelectionResult:
    """Select for every palm (in the order given) and count the report's selection counters."""
    result = SelectionResult()
    for palm in palms:
        sel = select_variant(palm, library, priors, clamp)
        result.placements.append((palm, sel))
        result.warnings.extend(selection_warnings(palm, sel))
        result.scale_clamped += sel.scale_clamped
        result.species_fallback += sel.species_fallback
        result.height_missing += sel.height_missing
    return result
