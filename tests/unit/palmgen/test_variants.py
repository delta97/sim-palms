from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from palmgen.errors import InputError
from palmgen.ids import unit_hash
from palmgen.inputs import load_gen_config, load_palms
from palmgen.model import Palm
from palmgen.variants import (
    HEIGHT_MISSING,
    SCALE_CLAMPED,
    SPECIES_FALLBACK,
    Variant,
    VariantLibrary,
    heading_deg,
    load_manifest,
    placeholder_selection,
    select_all,
    select_variant,
)
from tests.helpers.fixtures import FIXTURES_ROOT

FIX = FIXTURES_ROOT / "palmgen"
MANIFEST = FIX / "manifest_small.json"
REGION = "fixture-small"
ROBUSTA = "washingtonia_robusta"  # short 6, medium 12, medium_b 12
FILIFERA = "washingtonia_filifera"  # medium 10, tall 16
CANARY = "phoenix_canariensis"  # short 8, medium 14
UNKNOWN = "chamaedorea_unlisted"
PRIORS = {ROBUSTA: 0.6, FILIFERA: 0.2, CANARY: 0.2}


def palm(species: str = ROBUSTA, height: float | None = 12.0, palm_id: str = "p-1") -> Palm:
    return Palm(palm_id, -117.25, 32.78, species, height, 3.0, 2.0, False)


@pytest.fixture(scope="module")
def lib() -> VariantLibrary:
    return load_manifest(MANIFEST)


def test_load_manifest_groups_and_sorts(lib: VariantLibrary) -> None:
    assert set(lib.variants) == {ROBUSTA, FILIFERA, CANARY}
    assert [v.variant for v in lib.variants[ROBUSTA]] == ["short", "medium", "medium_b"]
    assert (lib.scale_min, lib.scale_max) == (0.85, 1.15)
    assert lib.species_fallback["_default"] == CANARY
    v = lib.variants[FILIFERA][1]
    assert (v.variant, v.native_height_m) == ("tall", 16.0)
    assert v.simobject_title == "PalmFix Washingtonia filifera Tall"


def test_closest_variant_by_log_ratio(lib: VariantLibrary) -> None:
    # Arithmetic midpoint of 10 and 16 is 13; the log-ratio midpoint is sqrt(160) = 12.65.
    assert select_variant(palm(FILIFERA, 12.0), lib, {}).variant.variant == "medium"
    assert select_variant(palm(FILIFERA, 13.0), lib, {}).variant.variant == "tall"
    assert select_variant(palm(CANARY, 7.0), lib, {}).variant.variant == "short"


def test_tie_goes_to_lower_native_height() -> None:
    lo = Variant("a_b", "short", "g1", 10.0, None)
    hi = Variant("a_b", "tall", "g2", 20.0, None)
    tied = VariantLibrary({"a_b": (lo, hi)}, 0.0001, 1000.0)
    sel = select_variant(Palm("p", 0, 0, "a_b", math.sqrt(200), None, None, False), tied, {})
    assert sel.variant.variant == "short"


def test_alternates_spread_by_hash_and_are_stable(lib: VariantLibrary) -> None:
    ids = [f"p-{i}" for i in range(60)]
    picks = {pid: select_variant(palm(height=12.0, palm_id=pid), lib, {}) for pid in ids}
    assert {s.variant.variant for s in picks.values()} == {"medium", "medium_b"}
    for pid, sel in picks.items():
        expected = ["medium", "medium_b"][int(unit_hash(pid, "alt") * 2)]
        assert sel.variant.variant == expected
        assert select_variant(palm(height=12.0, palm_id=pid), lib, {}) == sel


def test_scale_is_height_ratio_inside_limits(lib: VariantLibrary) -> None:
    sel = select_variant(palm(FILIFERA, 11.0), lib, {})
    assert sel.scale == pytest.approx(1.1)
    assert not sel.scale_clamped


def test_scale_clamps_to_manifest_limits(lib: VariantLibrary) -> None:
    high = select_variant(palm(CANARY, 100.0), lib, {})
    assert (high.scale, high.scale_clamped) == (1.15, True)
    low = select_variant(palm(FILIFERA, 0.5), lib, {})
    assert (low.scale, low.scale_clamped) == (0.85, True)


def test_region_clamp_overrides_manifest_limits(lib: VariantLibrary) -> None:
    sel = select_variant(palm(FILIFERA, 11.0), lib, {}, clamp=0.05)
    assert sel.scale == pytest.approx(1.05)
    assert sel.scale_clamped
    wide = select_variant(palm(CANARY, 100.0), lib, {}, clamp=0.5)
    assert wide.scale == pytest.approx(1.5)


def test_known_species_is_not_a_fallback(lib: VariantLibrary) -> None:
    sel = select_variant(palm(), lib, PRIORS)
    assert not sel.species_fallback
    assert sel.variant.species == ROBUSTA


def test_fallback_order(lib: VariantLibrary) -> None:
    # 2. manifest species_fallback beats priors
    sel = select_variant(palm("syagrus_romanzoffiana"), lib, PRIORS)
    assert (sel.variant.species, sel.species_fallback) == (FILIFERA, True)
    # 3. priors when the species has no manifest fallback; ties alphabetical
    assert select_variant(palm(UNKNOWN), lib, PRIORS).variant.species == ROBUSTA
    tied = select_variant(palm(UNKNOWN), lib, {CANARY: 0.5, FILIFERA: 0.5})
    assert tied.variant.species == CANARY
    # priors naming species with no variants are skipped
    skip = select_variant(palm(UNKNOWN), lib, {"no_such_species": 0.9, FILIFERA: 0.1})
    assert skip.variant.species == FILIFERA
    # 4. _default when priors are empty or match nothing
    assert select_variant(palm(UNKNOWN), lib, {}).variant.species == CANARY
    nomatch = select_variant(palm(UNKNOWN), lib, {"no_such_species": 0.9})
    assert nomatch.variant.species == CANARY


def test_no_usable_fallback_raises() -> None:
    only = VariantLibrary({ROBUSTA: (Variant(ROBUSTA, "medium", "g", 12.0, None),)}, 0.85, 1.15)
    with pytest.raises(InputError, match=UNKNOWN):
        select_variant(palm(UNKNOWN), only, {})


def test_height_missing_uses_median_of_species(lib: VariantLibrary) -> None:
    sel = select_variant(palm(ROBUSTA, None), lib, {})  # median of 6, 12, 12 = 12
    assert sel.height_missing
    assert sel.variant.variant in {"medium", "medium_b"}
    assert sel.scale == 1.0
    # median of 10 and 16 is 13; closest by log ratio is tall (16), scale 13/16 clamps to 0.85
    two = select_variant(palm(FILIFERA, None), lib, {})
    assert two.variant.variant == "tall"
    assert two.scale == pytest.approx(0.85)
    assert two.scale_clamped


def test_height_missing_with_species_fallback(lib: VariantLibrary) -> None:
    sel = select_variant(palm(UNKNOWN, None), lib, {})
    assert sel.species_fallback and sel.height_missing
    assert sel.variant.species == CANARY


def test_heading_stable_and_in_range() -> None:
    values = [heading_deg(f"p-{i}") for i in range(500)]
    assert all(0.0 <= v < 360.0 for v in values)
    assert values == [heading_deg(f"p-{i}") for i in range(500)]
    assert len(set(values)) > 400
    assert heading_deg("p-7") == round(unit_hash("p-7", "heading") * 360, 1) % 360


def test_heading_rounding_to_360_wraps_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("palmgen.variants.unit_hash", lambda palm_id, purpose: 0.99999)
    assert heading_deg("x") == 0.0


def test_same_palm_same_selection_across_calls(lib: VariantLibrary) -> None:
    p = palm(height=12.0, palm_id="fs-0000000000000042")
    assert select_variant(p, lib, PRIORS) == select_variant(p, lib, PRIORS)
    assert heading_deg(p.palm_id) == heading_deg(p.palm_id)


def test_placeholder_selection() -> None:
    sel = placeholder_selection({"name": "stand_in", "model_guid": "{G}", "native_height_m": 5})
    assert sel.variant.model_guid == "{G}"
    assert sel.variant.simobject_title is None
    assert (sel.scale, sel.scale_clamped, sel.species_fallback, sel.height_missing) == (
        1.0,
        False,
        False,
        False,
    )
    for bad in (None, {}, {"name": "x", "model_guid": ""}):
        with pytest.raises(InputError):
            placeholder_selection(bad)


def test_select_all_counts_and_warnings(lib: VariantLibrary) -> None:
    palms = [
        palm(ROBUSTA, 12.0, "a"),
        palm(CANARY, 100.0, "b"),  # clamped
        palm(UNKNOWN, None, "c"),  # fallback + height missing
    ]
    result = select_all(palms, lib, PRIORS)
    assert [p.palm_id for p, _ in result.placements] == ["a", "b", "c"]
    assert result.counts() == {"scale_clamped": 1, "species_fallback": 1, "height_missing": 1}
    assert [(w.code, w.palm_id) for w in result.warnings] == [
        (SCALE_CLAMPED, "b"),
        (SPECIES_FALLBACK, "c"),
        (HEIGHT_MISSING, "c"),
    ]


def test_fixture_palms_select_cleanly(lib: VariantLibrary) -> None:
    cfg = load_gen_config(REGION, FIX / "region_small.yaml")
    palms, _ = load_palms(FIX / "palms_small.geojson", REGION)
    result = select_all(palms, lib, cfg.species_priors, cfg.scale_clamp)
    assert len(result.placements) == len(palms)
    unknown = [s for p, s in result.placements if p.species == UNKNOWN]
    assert len(unknown) == 1
    assert unknown[0].species_fallback
    assert unknown[0].variant.species == ROBUSTA  # highest prior
    assert result.species_fallback == 1


# --- manifest validation -------------------------------------------------------------------


def _manifest(tmp_path: Path, edit: Any) -> Path:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    edit(data)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_native_height_not_positive_is_input_error(tmp_path: Path) -> None:
    def edit(d: dict[str, Any]) -> None:
        d["species"][FILIFERA]["variants"][1]["native_height_m"] = 0

    with pytest.raises(InputError, match="native_height_m"):
        load_manifest(_manifest(tmp_path, edit))


def test_native_height_null_names_entry(tmp_path: Path) -> None:
    def edit(d: dict[str, Any]) -> None:
        d["species"][FILIFERA]["variants"][1]["native_height_m"] = None

    with pytest.raises(InputError, match=f"{FILIFERA}/tall"):
        load_manifest(_manifest(tmp_path, edit))


def test_duplicate_variant_names_entry(tmp_path: Path) -> None:
    def edit(d: dict[str, Any]) -> None:
        variants = d["species"][FILIFERA]["variants"]
        variants.append(dict(variants[0]))

    with pytest.raises(InputError, match=f"{FILIFERA}/medium.*duplicate"):
        load_manifest(_manifest(tmp_path, edit))


def test_schema_failure_is_input_error(tmp_path: Path) -> None:
    def edit(d: dict[str, Any]) -> None:
        del d["species"][FILIFERA]["variants"][0]["model_guid"]

    with pytest.raises(InputError, match="model_guid"):
        load_manifest(_manifest(tmp_path, edit))


def test_missing_and_malformed_files(tmp_path: Path) -> None:
    with pytest.raises(InputError):
        load_manifest(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputError):
        load_manifest(bad)


def test_empty_manifest_is_input_error(tmp_path: Path) -> None:
    def edit(d: dict[str, Any]) -> None:
        d["species"] = {}

    with pytest.raises(InputError, match="no variants"):
        load_manifest(_manifest(tmp_path, edit))
