from __future__ import annotations

import ast
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from palmcore import ids
from palmcore.errors import ContractError
from palmcore.ids import (
    NAMESPACE,
    PALM_ID_RE,
    assert_unique,
    cluster_key,
    format_guid,
    location_key,
    object_guid,
    palm_id,
    palm_key,
    seeded_rng,
    stable_unit_float,
)

# Golden vectors. Computed once in ARCH-006; changing any of them is a MAJOR contract change (WS10).
GOLDEN_PALM_ID_SRC = "sdc-a6924214cef25e3a"
GOLDEN_LOCATION_KEY = "loc:-118.49012,34.01234"
GOLDEN_PALM_ID_LOC = "law-a4b4b8ac510054ac"
GOLDEN_OBJECT_GUID = "eb5be31c-72d6-5896-91e5-ca35599d2b7a"
GOLDEN_GUID_STYLES = {
    "braces_upper": "{EB5BE31C-72D6-5896-91E5-CA35599D2B7A}",
    "braces_lower": "{eb5be31c-72d6-5896-91e5-ca35599d2b7a}",
    "plain_upper": "EB5BE31C-72D6-5896-91E5-CA35599D2B7A",
    "plain_lower": "eb5be31c-72d6-5896-91e5-ca35599d2b7a",
}
GOLDEN_UNIT_FLOAT = 0.5346597953208663
GOLDEN_RNG_FIRST = 0.6993357524480599


def test_namespace_matches_uuid5_derivation() -> None:
    assert uuid.uuid5(uuid.NAMESPACE_URL, "urn:palmfix:namespace:v1") == NAMESPACE


def test_golden_palm_id_from_source_key() -> None:
    assert palm_id("sdc", "src:sd_street_trees:48213") == GOLDEN_PALM_ID_SRC


def test_golden_palm_id_from_location_key() -> None:
    assert location_key(-118.49012, 34.01234) == GOLDEN_LOCATION_KEY
    assert palm_id("law", location_key(-118.49012, 34.01234)) == GOLDEN_PALM_ID_LOC


def test_golden_object_guid_and_styles() -> None:
    guid = object_guid(
        "polygon", "san-diego-coastal", "tile_a", "cluster:sdc-0000000000000001", "0"
    )
    assert str(guid) == GOLDEN_OBJECT_GUID
    for style, expected in GOLDEN_GUID_STYLES.items():
        assert format_guid(guid, style) == expected  # type: ignore[arg-type]


def test_golden_stable_unit_float_and_rng() -> None:
    assert stable_unit_float("heading", "sdc-0000000000000001") == GOLDEN_UNIT_FLOAT
    assert seeded_rng("variant", "sdc-0000000000000001").random() == GOLDEN_RNG_FIRST


def test_palm_key_prefers_smallest_source_id() -> None:
    assert palm_key(["sd:b", "sd:a", "sd:c"], "fallback") == "src:sd:a"
    assert palm_key(["x:2", "x:1"], "fallback") == "src:x:1"
    assert palm_key(["x:2", "x:1"], "fallback") == palm_key(["x:1", "x:2"], "fallback")


def test_palm_key_falls_back_when_no_ids() -> None:
    assert palm_key([], "loc:1.00000,2.00000") == "loc:1.00000,2.00000"


def test_palm_key_empty_fallback_raises() -> None:
    with pytest.raises(ValueError):
        palm_key([], "")


def test_location_key_normalises_negative_zero() -> None:
    assert location_key(-0.000001, -0.000001) == "loc:0.00000,0.00000"
    assert location_key(0.0, 0.0) == "loc:0.00000,0.00000"


def test_cluster_key_ignores_order_and_duplicates() -> None:
    a = cluster_key(["sdc-b", "sdc-a", "sdc-a"])
    b = cluster_key(["sdc-a", "sdc-b"])
    assert a == b == "cluster:sdc-a,sdc-b"


def test_cluster_key_empty_raises() -> None:
    with pytest.raises(ValueError):
        cluster_key([])


def test_object_guid_rejects_pipe_in_part() -> None:
    with pytest.raises(ValueError):
        object_guid("polygon", "a|b")


@pytest.mark.parametrize("kind", ["Polygon", "poly-gon", "", "poly1", "obj gect"])
def test_object_guid_rejects_bad_kind(kind: str) -> None:
    with pytest.raises(ValueError):
        object_guid(kind, "x")


def test_object_guid_requires_a_part() -> None:
    with pytest.raises(ValueError):
        object_guid("polygon")


def test_palm_id_rejects_bad_prefix_and_empty_key() -> None:
    for prefix in ["", "a", "toolongprefix", "ABC", "a1"]:
        with pytest.raises(ValueError):
            palm_id(prefix, "k")
    with pytest.raises(ValueError):
        palm_id("sdc", "")


def test_every_palm_id_matches_pattern() -> None:
    for i in range(200):
        assert PALM_ID_RE.match(palm_id("sdc", f"src:x:{i}"))


def test_100k_keys_give_100k_distinct_palm_ids() -> None:
    values = {palm_id("sdc", f"src:sd_street_trees:{i}") for i in range(100_000)}
    assert len(values) == 100_000


def test_stable_unit_float_in_unit_interval() -> None:
    for i in range(10_000):
        value = stable_unit_float("heading", f"sdc-{i:016x}")
        assert 0.0 <= value < 1.0


def test_seeded_rng_is_reproducible() -> None:
    first = [seeded_rng("variant", "p1").random() for _ in range(3)]
    second = [seeded_rng("variant", "p1").random() for _ in range(3)]
    assert first == second


def test_assert_unique_passes_on_unique_values() -> None:
    assert_unique(["a", "b", "c"])


def test_assert_unique_raises_with_duplicates() -> None:
    with pytest.raises(ContractError) as excinfo:
        assert_unique(["a", "b", "a", "b", "c"], what="palm_id")
    assert "palm_id" in str(excinfo.value)
    assert sorted(excinfo.value.issues) == ["a", "b"]


def test_assert_unique_limits_listed_duplicates() -> None:
    values = [f"d{i}" for i in range(30)] * 2
    with pytest.raises(ContractError) as excinfo:
        assert_unique(values)
    assert "and 10 more" in str(excinfo.value)


def test_subprocess_gives_same_palm_id() -> None:
    code = "from palmcore.ids import palm_id; print(palm_id('sdc', 'src:sd_street_trees:48213'))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    assert result.stdout.strip() == palm_id("sdc", "src:sd_street_trees:48213")
    assert result.stdout.strip() == GOLDEN_PALM_ID_SRC


def test_module_calls_no_nondeterministic_sources() -> None:
    tree = ast.parse(Path(ids.__file__).read_text(encoding="utf-8"))
    forbidden_names = {"hash", "uuid1", "uuid4"}
    forbidden_attrs = {"uuid1", "uuid4", "random", "choice", "randint", "shuffle", "uniform"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            assert func.id not in forbidden_names
        elif isinstance(func, ast.Attribute):
            assert func.attr not in forbidden_attrs or (
                func.attr == "random"
                and not (isinstance(func.value, ast.Name) and func.value.id == "random")
            )
