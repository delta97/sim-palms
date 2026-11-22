"""Species-name normalisation: any inventory or OSM species string -> one internal species key.

Contract: ``plans/detailed/02-detection-pipeline.md`` (W2). The name tables are data files in
``palmscan/data/`` so new spellings need no code change. Normalisation only ever emits keys that
are listed in ``palmscan/data/species_keys.yaml``.
"""

from __future__ import annotations

import csv
import functools
import io
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from typing import Any, Final

import yaml

from palmcore.errors import ConfigError

__all__ = [
    "GENERIC_KEY",
    "NormalizedSpecies",
    "clean_name",
    "genus_set_members",
    "normalize_species",
    "read_data_text",
]

GENERIC_KEY: Final = "palm_unknown"
_DATA_PACKAGE: Final = "palmscan.data"

# Second words that mean "genus only" rather than an epithet ("Phoenix spp.", "Phoenix palm").
_NON_EPITHETS: Final = frozenset(
    {"sp", "spp", "species", "palm", "palms", "tree", "trees", "hybrid", "unknown", "unk", "other"}
)

_QUOTE_FOLD: Final = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00d7": " "}
)
_CULTIVAR_RE: Final = re.compile(r"""(?<![a-z0-9])'[^']*'|"[^"]*\"""")
_RANK_RE: Final = re.compile(r"\b(?:var|cv|ssp|subsp)\b.*$")
_PUNCT_RE: Final = re.compile(r"[_\-,.;:()\[\]/&]")
_HYBRID_X_RE: Final = re.compile(r"\bx\b")
_SPLIT_RE: Final = re.compile(r"\s-\s|/|\(|\)|,|;")
_BINOMIAL_RE: Final = re.compile(r"^([a-z]+) ([a-z]+)\b")
_GENUS_ONLY_RE: Final = re.compile(r"^([a-z]+)( spp?)?$")


@dataclass(frozen=True, slots=True)
class NormalizedSpecies:
    key: str | None  # e.g. "washingtonia_robusta", "brahea_sp", "palm_unknown", None
    genus: str | None
    is_palm: bool
    level: str  # "species" | "genus" | "generic" | "none"
    match: str  # "alias" | "binomial" | "genus" | "generic" | "none"


_NO_MATCH: Final = NormalizedSpecies(None, None, False, "none", "none")


def read_data_text(name: str) -> str:
    """Text of a file in ``palmscan/data`` (source tree or installed wheel)."""
    return resources.files(_DATA_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def _load_yaml(name: str) -> Any:
    try:
        return yaml.safe_load(read_data_text(name))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load palmscan data file {name}: {exc}") from exc


@dataclass(frozen=True)
class _Tables:
    aliases: Mapping[str, tuple[str | None, bool]]  # cleaned alias -> (species_key, is_palm)
    key_genus: Mapping[str, str | None]
    key_level: Mapping[str, str]
    genus_sets: Mapping[str, frozenset[str]]
    all_genera: frozenset[str]
    genus_default: Mapping[str, str]
    genus_aliases: Mapping[str, str]
    generic_names: frozenset[str]


@functools.cache
def _tables() -> _Tables:
    registry = _load_yaml("species_keys.yaml")
    key_genus: dict[str, str | None] = {}
    key_level: dict[str, str] = {}
    for row in registry["keys"]:
        key_genus[row["key"]] = row["genus"]
        key_level[row["key"]] = row["level"]

    genera = _load_yaml("palm_genera.yaml")
    genus_sets = {name: frozenset(members) for name, members in genera["genus_sets"].items()}
    all_genera = frozenset().union(*genus_sets.values())
    genus_default: dict[str, str] = dict(genera["genus_default_species"])
    genus_aliases: dict[str, str] = dict(genera["genus_aliases"])
    for genus, key in genus_default.items():
        if genus not in all_genera or key not in key_genus:
            raise ConfigError(f"palm_genera.yaml: bad genus_default_species {genus}: {key}")
    for old, genus in genus_aliases.items():
        if genus not in all_genera:
            raise ConfigError(f"palm_genera.yaml: genus_aliases {old} -> unknown genus {genus}")

    aliases: dict[str, tuple[str | None, bool]] = {}
    reader = csv.DictReader(io.StringIO(read_data_text("species_aliases.csv")))
    for row in reader:
        alias = row["alias"]
        is_palm = row["is_palm"].strip().lower() == "true"
        akey = row["species_key"].strip() or None
        if alias in aliases:
            raise ConfigError(f"species_aliases.csv: duplicate alias {alias!r}")
        if is_palm != (akey is not None) or (akey is not None and akey not in key_genus):
            raise ConfigError(f"species_aliases.csv: bad row for alias {alias!r}")
        aliases[alias] = (akey, is_palm)

    return _Tables(
        aliases=aliases,
        key_genus=key_genus,
        key_level=key_level,
        genus_sets=genus_sets,
        all_genera=all_genera,
        genus_default=genus_default,
        genus_aliases=genus_aliases,
        generic_names=frozenset(genera["generic_palm_names"]),
    )


def genus_set_members(name: str) -> frozenset[str]:
    """Genera of one configured set (``socal``, ``florida``, ``other``); ValueError if unknown."""
    try:
        return _tables().genus_sets[name]
    except KeyError:
        known = ", ".join(sorted(_tables().genus_sets))
        raise ValueError(f"unknown genus set {name!r} (known: {known})") from None


def clean_name(raw: str | None) -> str:
    """Fold a raw name to the form used in the alias table (lower-case ASCII words)."""
    if not raw:
        return ""
    text = raw.translate(_QUOTE_FOLD)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = _CULTIVAR_RE.sub(" ", text)
    text = _RANK_RE.sub(" ", text)
    text = text.replace("'", "").replace('"', "")
    text = _PUNCT_RE.sub(" ", text)
    text = _HYBRID_X_RE.sub(" ", text)
    return " ".join(text.split())


def _variants(text: str) -> list[str]:
    """Spelling forms of a cleaned name to try against the alias table, exact form first."""
    bases = [text]
    if text.endswith(" tree"):
        bases.append(text[: -len(" tree")])
    out: list[str] = []
    for base in bases:
        forms = [base]
        if base.endswith(" palms"):
            forms.append(base[: -len("s")])
        if base.endswith(" palm"):
            forms.append(base[: -len(" palm")])
        else:
            forms.append(f"{base} palm")
        for form in forms:
            if form and form not in out:
                out.append(form)
    return out


def _from_key(tables: _Tables, key: str | None, is_palm: bool, match: str) -> NormalizedSpecies:
    if key is None:
        return NormalizedSpecies(None, None, is_palm, "none", match)
    return NormalizedSpecies(key, tables.key_genus[key], True, tables.key_level[key], match)


def _alias_lookup(tables: _Tables, text: str) -> NormalizedSpecies | None:
    for form in _variants(text):
        hit = tables.aliases.get(form)
        if hit is not None:
            return _from_key(tables, hit[0], hit[1], "alias")
    return None


def _structural(tables: _Tables, text: str) -> NormalizedSpecies | None:
    """Binomial (step 5) and genus-only (step 6) forms of one cleaned string."""
    binom = _BINOMIAL_RE.match(text)
    if binom:
        genus = tables.genus_aliases.get(binom.group(1), binom.group(1))
        epithet = binom.group(2)
        if genus in tables.all_genera:
            if epithet not in _NON_EPITHETS:
                key = f"{genus}_{epithet}"
                if tables.key_level.get(key) == "species":
                    return _from_key(tables, key, True, "binomial")
                # Unlisted epithet: keep the genus, never emit a key outside the registry.
                return _from_key(tables, f"{genus}_sp", True, "binomial")
            return _genus_only(tables, genus)
    only = _GENUS_ONLY_RE.match(text)
    if only:
        genus = tables.genus_aliases.get(only.group(1), only.group(1))
        if genus in tables.all_genera:
            return _genus_only(tables, genus)
    return None


def _genus_only(tables: _Tables, genus: str) -> NormalizedSpecies:
    key = tables.genus_default.get(genus, f"{genus}_sp")
    return NormalizedSpecies(key, genus, True, "genus", "genus")


def _match_one(tables: _Tables, raw: str) -> NormalizedSpecies | None:
    """Steps 2 to 7 on one string."""
    full = clean_name(raw)
    if not full:
        return None
    parts = [p for p in (clean_name(x) for x in _SPLIT_RE.split(raw)) if p]
    # 2 and 3: alias table on the whole string, then on each part.
    hit = _alias_lookup(tables, full)
    if hit is None:
        for part in parts:
            hit = _alias_lookup(tables, part)
            if hit is not None:
                break
    # 4: "PALM, MEXICAN FAN" -> "mexican fan palm".
    if hit is None and full.startswith("palm "):
        hit = _alias_lookup(tables, full[len("palm ") :])
    if hit is not None:
        return hit
    # 5 and 6: binomial and genus-only, whole string first, then each part.
    for text in (full, *parts):
        hit = _structural(tables, text)
        if hit is not None:
            return hit
    # 7: generic palm names.
    for text in (full, *parts):
        if text in tables.generic_names:
            return NormalizedSpecies(GENERIC_KEY, None, True, "generic", "generic")
    return None


@functools.lru_cache(maxsize=4096)
def normalize_species(raw: str | None, common: str | None = None) -> NormalizedSpecies:
    """Map ``raw`` (and the optional separate common-name column ``common``) to a species key.

    Steps 2 to 7 run on ``raw``; if they find nothing, or only a generic "palm", they run on
    ``common``. Pure function, tables load once.
    """
    tables = _tables()
    result = _match_one(tables, raw) if raw else None
    if common and (result is None or result.level == "generic"):
        from_common = _match_one(tables, common)
        if from_common is not None and (result is None or from_common.level != "generic"):
            result = from_common
    return result if result is not None else _NO_MATCH
