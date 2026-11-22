"""palmscan.species_names: name table, normalizer and the species-key registry."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pytest
import yaml

from palmcore.assets import load_library, validate_manifest
from palmcore.assets.manifest import REGISTRY_REL_PATH
from palmscan.species_names import (
    GENERIC_KEY,
    NormalizedSpecies,
    clean_name,
    genus_set_members,
    normalize_species,
    read_data_text,
)

REPO = Path(__file__).resolve().parents[3]
REGISTRY_PATH = REPO / REGISTRY_REL_PATH
MANIFEST_FIXTURE = (
    REPO / "tests" / "fixtures" / "palmcore" / "assets" / "manifest" / "manifest.json"
)
SPECIES_PATTERN = re.compile(r"^[a-z]+(_[a-z]+)+$")  # ARCH-002 species key pattern


def _registry() -> list[dict[str, object]]:
    rows = yaml.safe_load(read_data_text("species_keys.yaml"))["keys"]
    assert isinstance(rows, list)
    return rows


def _registry_keys() -> set[str]:
    return {str(r["key"]) for r in _registry()}


def _alias_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(read_data_text("species_aliases.csv"))))


# --- clean_name ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("WASHINGTONIA  ROBUSTA", "washingtonia robusta"),
        ("PALM, MEXICAN FAN", "palm mexican fan"),
        ("Phoenix spp.", "phoenix spp"),
        ("Syagrus romanzoffiana 'Silver'", "syagrus romanzoffiana"),
        ('Phoenix canariensis "Sunrise" tall', "phoenix canariensis tall"),
        ("Butia capitata var. odorata", "butia capitata"),
        ("Washingtonia filifera x robusta", "washingtonia filifera robusta"),
        ("Washingtonia \u00d7 filibusta", "washingtonia filibusta"),
        ("Pal\u00ee_Mexican-Fan;Palm", "pali mexican fan palm"),
        ("Traveler\u2019s palm", "travelers palm"),
        ("Traveler's palm 'Foo'", "travelers palm"),
    ],
)
def test_clean_name(raw: str | None, expected: str) -> None:
    assert clean_name(raw) == expected


# --- acceptance cases ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "Washingtonia robusta",
        "WASHINGTONIA ROBUSTA",
        "Mexican fan palm",
        "PALM, MEXICAN FAN",
        "  mexican   fan palm  ",
        "Mexican Fan Palm Tree",
        "Washingtonia robusta (Mexican Fan Palm)",
        "Mexican Fan Palm (Washingtonia robusta)",
        "Washingtonia robusta - Mexican fan palm",
        "Washingtonia robusta / Mexican fan palm",
        "Washingtonia_robusta",
        "Washingtona robusta",
        "washingtonia robusta 'Compacta'",
        "Washingtonia robusta Mexican fan palm",
        "Palm (Mexican fan)",
    ],
)
def test_mexican_fan_palm_variants(raw: str) -> None:
    ns = normalize_species(raw)
    assert ns.key == "washingtonia_robusta"
    assert ns.genus == "washingtonia"
    assert ns.is_palm
    assert ns.level == "species"


def test_exact_structure_for_scientific_name() -> None:
    assert normalize_species("Washingtonia robusta") == NormalizedSpecies(
        "washingtonia_robusta", "washingtonia", True, "species", "alias"
    )


def test_cultivar_suffix_is_dropped() -> None:
    assert normalize_species("Syagrus romanzoffiana 'Silver'").key == "syagrus_romanzoffiana"
    assert normalize_species("Phoenix canariensis var. foo").key == "phoenix_canariensis"


def test_cocos_plumosa_is_a_queen_palm_not_cocos() -> None:
    ns = normalize_species("Cocos plumosa")
    assert ns.key == "syagrus_romanzoffiana"
    assert ns.genus == "syagrus"
    assert normalize_species("COCOS PLUMOSA").key == "syagrus_romanzoffiana"
    assert normalize_species("Arecastrum romanzoffianum").key == "syagrus_romanzoffiana"
    assert normalize_species("Cocos nucifera").key == "cocos_nucifera"


@pytest.mark.parametrize(
    "raw",
    [
        "Sago palm",
        "SAGO PALM",
        "Ponytail palm",
        "Cycas revoluta",
        "Cabbage tree",
        "Cordyline australis",
        "Yucca",
        "Dracaena",
        "Traveler's palm",
        "Ravenala madagascariensis",
    ],
)
def test_non_palms_with_palm_in_the_name(raw: str) -> None:
    ns = normalize_species(raw)
    assert ns.is_palm is False
    assert ns.key is None
    assert ns.genus is None


def test_phoenix_spp_is_genus_level_with_default_species() -> None:
    ns = normalize_species("Phoenix spp.")
    assert (ns.key, ns.genus, ns.level, ns.match) == (
        "phoenix_canariensis",
        "phoenix",
        "genus",
        "genus",
    )
    assert normalize_species("Phoenix").key == "phoenix_canariensis"
    assert normalize_species("Phoenix palm").level == "genus"


def test_genus_without_default_becomes_genus_sp() -> None:
    ns = normalize_species("Brahea")
    assert (ns.key, ns.genus, ns.level, ns.is_palm) == ("brahea_sp", "brahea", "genus", True)
    assert normalize_species("Brahea spp").key == "brahea_sp"
    assert normalize_species("Sabal").key == "sabal_sp"
    assert normalize_species("Livistona species").key == "livistona_sp"


def test_unlisted_epithet_keeps_the_genus_only() -> None:
    ns = normalize_species("Phoenix rupicola")
    assert ns.key == "phoenix_sp"
    assert ns.level == "genus"
    assert ns.match == "binomial"
    assert normalize_species("Syagrus schizophylla").key == "syagrus_sp"


@pytest.mark.parametrize(
    "raw", ["Palm", "palms", "Palm tree", "PALM SPP.", "Unknown palm", "palm sp"]
)
def test_generic_palm(raw: str) -> None:
    ns = normalize_species(raw)
    assert (ns.key, ns.genus, ns.is_palm, ns.level, ns.match) == (
        GENERIC_KEY,
        None,
        True,
        "generic",
        "generic",
    )


@pytest.mark.parametrize(
    "raw", ["Quercus agrifolia", "Jacaranda mimosifolia", "Pinus", "Oak", "Tree"]
)
def test_other_trees_are_not_palms(raw: str) -> None:
    assert normalize_species(raw) == NormalizedSpecies(None, None, False, "none", "none")


@pytest.mark.parametrize("raw", [None, "", "   ", "-", "()"])
def test_empty_input(raw: str | None) -> None:
    assert normalize_species(raw) == NormalizedSpecies(None, None, False, "none", "none")
    assert normalize_species(raw, None).is_palm is False


def test_common_name_column_is_a_fallback() -> None:
    assert normalize_species("zzz unknown", "Queen Palm").key == "syagrus_romanzoffiana"
    assert normalize_species(None, "Mexican Fan Palm").key == "washingtonia_robusta"
    assert normalize_species("", "Pygmy date palm").key == "phoenix_roebelenii"
    # A real match in `raw` wins over `common`.
    assert normalize_species("Phoenix canariensis", "Queen Palm").key == "phoenix_canariensis"
    # A generic palm in `raw` is refined by `common`, but never replaced by a worse match.
    assert normalize_species("Palm", "King palm").key == "archontophoenix_cunninghamiana"
    assert normalize_species("Palm", "Oak").key == GENERIC_KEY
    assert normalize_species("Oak", "Sago palm").is_palm is False


# --- common names, misspellings, inventory styles ------------------------------------------


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("California fan palm", "washingtonia_filifera"),
        ("Washingtonia filifera x robusta", "washingtonia_filibusta"),
        ("Canary Island Date Palm", "phoenix_canariensis"),
        ("PALM, CANARY ISLAND DATE", "phoenix_canariensis"),
        ("Pheonix canariensis", "phoenix_canariensis"),
        ("Phoenix canarensis", "phoenix_canariensis"),
        ("Date palm", "phoenix_dactylifera"),
        ("Palm, Date", "phoenix_dactylifera"),
        ("Pygmy Date Palm", "phoenix_roebelenii"),
        ("Phoenix roebelinii", "phoenix_roebelenii"),
        ("Queen Palm", "syagrus_romanzoffiana"),
        ("PALM, QUEEN", "syagrus_romanzoffiana"),
        ("Syagrus romanzofiana", "syagrus_romanzoffiana"),
        ("King palm", "archontophoenix_cunninghamiana"),
        ("Archontophoenix cunninghamiana", "archontophoenix_cunninghamiana"),
        ("Mexican Blue Palm", "brahea_armata"),
        ("Guadalupe palm", "brahea_edulis"),
        ("Pindo palm", "butia_capitata"),
        ("Jelly Palm", "butia_capitata"),
        ("Chinese Fan Palm", "livistona_chinensis"),
        ("Livistonia chinensis", "livistona_chinensis"),
        ("Windmill Palm", "trachycarpus_fortunei"),
        ("Trachycarpus fortunei", "trachycarpus_fortunei"),
        ("Mediterranean Fan Palm", "chamaerops_humilis"),
        ("Chamaerops humilis", "chamaerops_humilis"),
        ("Areca palm", "dypsis_lutescens"),
        ("Chrysalidocarpus lutescens", "dypsis_lutescens"),
        ("Triangle Palm", "dypsis_decaryi"),
        ("Sabal palmetto", "sabal_palmetto"),
        ("Cabbage palm", "sabal_palmetto"),
        ("Royal Palm", "roystonea_regia"),
        ("Coconut palm", "cocos_nucifera"),
        ("Foxtail Palm", "wodyetia_bifurcata"),
        ("Christmas Palm", "adonidia_merrillii"),
        ("Veitchia merrillii", "adonidia_merrillii"),
        ("Rhapis excelsa", "rhapis_excelsa"),
    ],
)
def test_common_names_synonyms_and_misspellings(raw: str, key: str) -> None:
    assert normalize_species(raw).key == key


def test_fan_palm_alone_is_generic_palm() -> None:
    ns = normalize_species("Fan palm")
    assert (ns.key, ns.level) == (GENERIC_KEY, "generic")


def test_real_palm_genus_outside_the_modelled_sets_is_still_a_palm() -> None:
    ns = normalize_species("Howea forsteriana")
    assert ns.is_palm
    assert ns.genus == "howea"
    assert genus_set_members("other") >= {"howea"}
    assert normalize_species("Caryota urens").key == "caryota_sp"


def test_unknown_genus_set_raises() -> None:
    with pytest.raises(ValueError, match="unknown genus set"):
        genus_set_members("atlantis")


def test_normalize_is_cached_and_pure() -> None:
    a = normalize_species("Queen palm")
    assert normalize_species("Queen palm") is a


# --- the alias table -----------------------------------------------------------------------


def test_alias_csv_is_sorted_unique_and_cleaned() -> None:
    aliases = [r["alias"] for r in _alias_rows()]
    assert aliases == sorted(aliases)
    assert len(aliases) == len(set(aliases))
    for alias in aliases:
        assert clean_name(alias) == alias, f"alias {alias!r} is not in cleaned form"


def test_alias_csv_columns_and_flags() -> None:
    text = read_data_text("species_aliases.csv")
    assert text.splitlines()[0] == "alias,species_key,is_palm,notes"
    for row in _alias_rows():
        assert row["is_palm"] in {"true", "false"}
        assert (row["is_palm"] == "true") == bool(row["species_key"]), row


@pytest.mark.parametrize("row", _alias_rows(), ids=lambda r: r["alias"])
def test_every_alias_row_round_trips(row: dict[str, str]) -> None:
    ns = normalize_species(row["alias"])
    assert ns.key == (row["species_key"] or None)
    assert ns.is_palm == (row["is_palm"] == "true")


# --- the species-key registry --------------------------------------------------------------


def test_registry_shape_sorted_unique_and_pattern() -> None:
    data = yaml.safe_load(read_data_text("species_keys.yaml"))
    assert data["version"] == 1
    keys = [str(r["key"]) for r in data["keys"]]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    for row in data["keys"]:
        assert SPECIES_PATTERN.match(row["key"]), row
        assert row["set"] in {"socal", "florida", "other"}
        assert row["level"] in {"species", "genus", "generic"}
        if row["level"] == "generic":
            assert row["key"] == GENERIC_KEY
            assert row["genus"] is None
        else:
            assert row["key"].startswith(f"{row['genus']}_")
            if row["level"] == "genus":
                assert row["key"] == f"{row['genus']}_sp"
    assert GENERIC_KEY in keys


def test_registry_has_the_required_keys() -> None:
    keys = _registry_keys()
    required = {
        "washingtonia_robusta",
        "washingtonia_filifera",
        "phoenix_canariensis",
        "syagrus_romanzoffiana",
        "archontophoenix_cunninghamiana",
        "sabal_palmetto",
        "roystonea_regia",
        "cocos_nucifera",
        "wodyetia_bifurcata",
        "adonidia_merrillii",
        "phoenix_dactylifera",
        GENERIC_KEY,
    }
    assert required <= keys


def test_registry_has_a_genus_sp_key_for_every_genus_and_matching_sets() -> None:
    genera = yaml.safe_load(read_data_text("palm_genera.yaml"))
    rows = {str(r["key"]): r for r in _registry()}
    for set_name, members in genera["genus_sets"].items():
        for genus in members:
            assert rows[f"{genus}_sp"]["set"] == set_name
            assert rows[f"{genus}_sp"]["genus"] == genus
    in_registry = {str(r["genus"]) for r in _registry() if r["genus"]}
    all_genera = {g for members in genera["genus_sets"].values() for g in members}
    assert in_registry == all_genera
    # The plan's genus sets for the SoCal and Florida regions.
    assert set(genera["genus_sets"]["socal"]) == {
        "washingtonia", "phoenix", "syagrus", "archontophoenix", "brahea",
        "butia", "livistona", "trachycarpus", "chamaerops", "dypsis",
    }  # fmt: skip
    assert set(genera["genus_sets"]["florida"]) == {
        "sabal",
        "roystonea",
        "cocos",
        "wodyetia",
        "adonidia",
    }


def test_alias_keys_are_in_the_registry() -> None:
    keys = _registry_keys()
    for row in _alias_rows():
        assert not row["species_key"] or row["species_key"] in keys, row


def test_genus_defaults_and_species_defaults_are_in_the_registry() -> None:
    keys = _registry_keys()
    genera = yaml.safe_load(read_data_text("palm_genera.yaml"))
    for genus, key in genera["genus_default_species"].items():
        assert key in keys
        assert key.startswith(f"{genus}_")
    defaults = yaml.safe_load(read_data_text("species_defaults.yaml"))
    species_rows = {k for k in defaults if not k.startswith("_")}
    assert species_rows <= keys
    all_genera = {g for members in genera["genus_sets"].values() for g in members}
    assert set(defaults["_genus"]) == all_genera
    assert "_default" in defaults
    for row in [
        *(defaults[k] for k in species_rows),
        *defaults["_genus"].values(),
        defaults["_default"],
    ]:
        assert set(row) == {"height_m", "crown_diam_m"}
        assert row["height_m"] > 0
        assert row["crown_diam_m"] > 0


def test_genus_aliases_point_at_known_genera() -> None:
    genera = yaml.safe_load(read_data_text("palm_genera.yaml"))
    all_genera = {g for members in genera["genus_sets"].values() for g in members}
    for old, genus in genera["genus_aliases"].items():
        assert genus in all_genera
        assert old not in all_genera


def test_every_emittable_key_is_in_the_registry() -> None:
    keys = _registry_keys()
    samples = [r["alias"] for r in _alias_rows()]
    samples += [
        "Phoenix", "Brahea", "Sabal", "Howea", "Palm", "Phoenix rupicola", "Cocos romanzoffiana",
        "Washingtonia hybrid", "Caryota urens", "Livistona decora",
    ]  # fmt: skip
    for raw in samples:
        ns = normalize_species(raw)
        assert ns.key is None or ns.key in keys, raw


# --- palmcore.assets (ASSET-005) validates against this registry ---------------------------


def test_registry_path_matches_the_asset_validator() -> None:
    assert REGISTRY_PATH.is_file()
    assert REGISTRY_PATH.parent == Path(__import__("palmscan").__file__).parent / "data"


def test_asset_manifest_validation_passes_against_the_registry() -> None:
    assert validate_manifest(MANIFEST_FIXTURE, registry_path=REGISTRY_PATH) == []


def test_asset_library_fallback_keys_are_in_the_registry() -> None:
    library = load_library(REPO / "assets")
    keys = _registry_keys()
    named = {k for k in library.species_fallback if k != "_default"} | set(
        library.species_fallback.values()
    )
    assert named
    assert named <= keys
