import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import pytest

from palmcore.assets import (
    NAMESPACE,
    Measured,
    build_manifest,
    dump_manifest,
    load_manifest,
    model_guid,
    model_name,
    simobject_title,
    validate_manifest,
)
from palmcore.assets.__main__ import main
from palmcore.errors import ConfigError, ContractError

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "palmcore" / "assets" / "manifest"
EXPECTED = FIXTURES / "manifest.json"
REGISTRY = FIXTURES / "species_keys.yaml"
TALL = "palmfix_washingtonia_robusta_tall"


@pytest.fixture(autouse=True)
def _schema_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PALMFIX_SCHEMA_DIR", str(Path(__file__).resolve().parents[3] / "schemas"))


def _built() -> dict[str, Any]:
    return build_manifest(FIXTURES)


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(dump_manifest(data), encoding="utf-8")
    return path


def _first_variants(data: dict[str, Any]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = data["species"]["washingtonia_robusta"]["variants"]
    return variants


# --- naming and GUIDs -------------------------------------------------------------------


def test_guid_is_deterministic_and_matches_the_policy() -> None:
    assert model_guid(TALL) == model_guid(TALL)
    assert model_guid(TALL) == str(uuid.uuid5(NAMESPACE, "palmfix-assets/" + TALL))
    assert model_guid(TALL) != model_guid(TALL.replace("tall", "short"))


def test_guid_hard_coded_value() -> None:
    # Changing this value is a breaking change: model GUIDs are permanent (GUID policy).
    assert str(NAMESPACE) == "3dc80026-4ad6-5492-895a-76442e34e939"
    assert model_guid(TALL) == "d4f3c899-5b05-5699-bd38-71fc386c5ecf"


def test_model_name() -> None:
    assert model_name("washingtonia_robusta", "medium_b") == "palmfix_washingtonia_robusta_medium_b"


@pytest.mark.parametrize(
    ("species", "variant", "expected"),
    [
        ("washingtonia_robusta", "medium", "PalmFix Washingtonia robusta Medium"),
        ("washingtonia_robusta", "medium_b", "PalmFix Washingtonia robusta Medium B"),
        ("phoenix_canariensis", "short", "PalmFix Phoenix canariensis Short"),
    ],
)
def test_simobject_title(species: str, variant: str, expected: str) -> None:
    assert simobject_title(species, variant) == expected


@pytest.mark.parametrize("variant", ["xtall", "tall_c", "Tall", ""])
def test_bad_variant_rejected(variant: str) -> None:
    with pytest.raises(ValueError, match="invalid variant"):
        model_name("washingtonia_robusta", variant)


# --- generation -------------------------------------------------------------------------


def test_draft_species_excluded_unless_requested() -> None:
    assert list(_built()["species"]) == ["washingtonia_robusta"]
    preview = build_manifest(FIXTURES, include_draft=True)
    assert list(preview["species"]) == ["phoenix_canariensis", "washingtonia_robusta"]


def test_variants_sorted_by_height_then_name() -> None:
    names = [v["variant"] for v in _first_variants(_built())]
    assert names == ["short", "medium", "medium_b", "tall"]


def test_alternate_crown_fields() -> None:
    by_name = {v["variant"]: v for v in _first_variants(_built())}
    assert by_name["medium_b"]["height_class"] == "medium"
    assert by_name["medium_b"]["alt"] == "b"
    assert by_name["medium"]["alt"] is None
    assert by_name["tall"]["lods"][3]["design_distance_m"] == 2000


def test_output_is_byte_identical_across_runs() -> None:
    assert dump_manifest(_built()) == dump_manifest(_built())


def test_fixture_manifest_reproduced_byte_for_byte() -> None:
    assert dump_manifest(_built()).encode("utf-8") == EXPECTED.read_bytes()


def test_no_timestamps_or_absolute_paths() -> None:
    text = dump_manifest(_built())
    assert str(FIXTURES) not in text
    assert "\\" not in text
    assert ":/" not in text
    assert "timestamp" not in text


def test_measure_hook_overrides_yaml_targets(tmp_path: Path) -> None:
    seen: list[Path] = []

    def measure(model_dir: Path) -> Measured:
        seen.append(model_dir)
        if model_dir.name == TALL:
            return Measured(
                native_height_m=27.861, crown_diam_m=4.414, triangles=(5480, 1310, 260, 8)
            )
        return Measured()

    data = build_manifest(FIXTURES, measure)
    tall = next(v for v in _first_variants(data) if v["model_name"] == TALL)
    assert tall["native_height_m"] == 27.86
    assert tall["crown_diam_m"] == 4.41
    assert [lod["triangles"] for lod in tall["lods"]] == [5480, 1310, 260, 8]
    assert any(p.name == TALL and p.parent.name == "washingtonia_robusta" for p in seen)
    assert validate_manifest(_write(tmp_path, data), registry_path=REGISTRY) == []


def test_missing_species_dir_or_bad_yaml_is_config_error(tmp_path: Path) -> None:
    shutil.copy(FIXTURES / "library.yaml", tmp_path / "library.yaml")
    (tmp_path / "species").mkdir()
    (tmp_path / "species" / "bad_key.yaml").write_text("species: other_key\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="file name must be"):
        build_manifest(tmp_path)


# --- loader -----------------------------------------------------------------------------


def test_load_manifest_returns_typed_objects() -> None:
    manifest = load_manifest(EXPECTED)
    assert manifest.package_version == "0.1.0"
    assert manifest.scale_limits.min == 0.85
    assert manifest.species_fallback["_default"] == "washingtonia_robusta"
    variant = manifest.species["washingtonia_robusta"].variants[0]
    assert variant.model_guid == model_guid("palmfix_washingtonia_robusta_short")
    assert len(variant.lods) == 4
    with pytest.raises(AttributeError):
        variant.model_guid = "x"  # type: ignore[misc]


def test_load_manifest_rejects_schema_violation(tmp_path: Path) -> None:
    data = _built()
    del data["species"]["washingtonia_robusta"]["variants"][0]["model_guid"]
    with pytest.raises(ContractError):
        load_manifest(_write(tmp_path, data))


# --- validate ---------------------------------------------------------------------------


def test_validate_accepts_fixture() -> None:
    assert validate_manifest(EXPECTED, registry_path=REGISTRY) == []


def test_validate_catches_duplicate_guid(tmp_path: Path) -> None:
    data = _built()
    v = _first_variants(data)
    v[1]["model_guid"] = v[0]["model_guid"]
    problems = validate_manifest(_write(tmp_path, data), registry_path=REGISTRY)
    assert any("duplicate model_guid" in p for p in problems)


def test_validate_catches_wrong_guid(tmp_path: Path) -> None:
    data = _built()
    _first_variants(data)[0]["model_guid"] = "3f0c2a8e-5b1d-5a7e-9c41-0d2f6b8e1a77"
    problems = validate_manifest(_write(tmp_path, data), registry_path=REGISTRY)
    assert any("!= uuid5 of name" in p for p in problems)


def test_validate_catches_bad_fallback_target(tmp_path: Path) -> None:
    data = _built()
    data["species_fallback"]["phoenix_canariensis"] = "phoenix_dactylifera"
    problems = validate_manifest(_write(tmp_path, data), registry_path=REGISTRY)
    assert any("phoenix_dactylifera: target is not in the manifest" in p for p in problems)


def test_validate_catches_schema_violation(tmp_path: Path) -> None:
    data = _built()
    del _first_variants(data)[0]["lods"][3]
    problems = validate_manifest(_write(tmp_path, data), registry_path=REGISTRY)
    assert problems
    assert all(p.startswith("schema:") for p in problems)


def test_validate_catches_species_missing_from_registry(tmp_path: Path) -> None:
    registry = tmp_path / "keys.yaml"
    registry.write_text("species:\n  - phoenix_canariensis\n", encoding="utf-8")
    problems = validate_manifest(EXPECTED, registry_path=registry)
    assert any("'washingtonia_robusta' is not in the registry" in p for p in problems)


def test_validate_registry_accepts_mapping_and_plain_list(tmp_path: Path) -> None:
    for text in (
        "washingtonia_robusta: {}\nphoenix_canariensis: {}\n",
        "- washingtonia_robusta\n- phoenix_canariensis\n",
        "species:\n  - key: washingtonia_robusta\n  - key: phoenix_canariensis\n",
    ):
        registry = tmp_path / "keys.yaml"
        registry.write_text(text, encoding="utf-8")
        assert validate_manifest(EXPECTED, registry_path=registry) == []


def test_validate_missing_registry_warns_but_passes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("WARNING", logger="palmfix")
    assert validate_manifest(EXPECTED, registry_path=tmp_path / "nope.yaml") == []
    assert "registry" in caplog.text


def test_validate_catches_package_version_mismatch(tmp_path: Path) -> None:
    manifest = _write(tmp_path, _built())
    definitions = tmp_path / "PackageDefinitions"
    definitions.mkdir()
    (definitions / "palmfix-assets.xml").write_text(
        "<Package><Version>0.2.0</Version></Package>", encoding="utf-8"
    )
    problems = validate_manifest(manifest, registry_path=REGISTRY)
    assert any("0.2.0" in p for p in problems)
    (definitions / "palmfix-assets.xml").write_text(
        "<Package><Version>0.1.0</Version></Package>", encoding="utf-8"
    )
    assert validate_manifest(manifest, registry_path=REGISTRY) == []


def test_validate_catches_non_decreasing_triangles(tmp_path: Path) -> None:
    data = _built()
    for lod, count in zip(_first_variants(data)[0]["lods"], (100, 200, 50, 8), strict=True):
        lod["triangles"] = count
    problems = validate_manifest(_write(tmp_path, data), registry_path=REGISTRY)
    assert any("strictly decrease" in p for p in problems)


# --- CLI --------------------------------------------------------------------------------


def test_cli_build_and_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "m.json"
    assert main(["build-manifest", "--assets-dir", str(FIXTURES), "--out", str(out)]) == 0
    assert out.read_bytes() == EXPECTED.read_bytes()
    assert (
        main(["build-manifest", "--assets-dir", str(FIXTURES), "--out", str(out), "--check"]) == 0
    )
    out.write_text(out.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert (
        main(["build-manifest", "--assets-dir", str(FIXTURES), "--out", str(out), "--check"]) == 1
    )
    assert "stale" in capsys.readouterr().err


def test_cli_check_on_missing_file_fails(tmp_path: Path) -> None:
    args = ["build-manifest", "--assets-dir", str(FIXTURES), "--out", str(tmp_path / "x.json")]
    assert main([*args, "--check"]) == 1


def test_cli_include_draft_preview(tmp_path: Path) -> None:
    out = tmp_path / "preview.json"
    args = ["build-manifest", "--assets-dir", str(FIXTURES), "--out", str(out), "--include-draft"]
    assert main(args) == 0
    assert "phoenix_canariensis" in json.loads(out.read_text(encoding="utf-8"))["species"]


def test_cli_validate_exit_codes(tmp_path: Path) -> None:
    assert main(["validate", "--manifest", str(EXPECTED)]) == 0
    data = _built()
    _first_variants(data)[0]["model_guid"] = "3f0c2a8e-5b1d-5a7e-9c41-0d2f6b8e1a77"
    assert main(["validate", "--manifest", str(_write(tmp_path, data))]) == 1
    assert main(["validate", "--manifest", str(tmp_path / "missing.json")]) == 2


def test_cli_missing_assets_dir_is_usage_error(tmp_path: Path) -> None:
    assert main(["build-manifest", "--assets-dir", str(tmp_path / "none")]) == 2
