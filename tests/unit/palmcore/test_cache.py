from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from palmcore.cache import (
    atomic_write_bytes,
    atomic_write_text,
    cache_key,
    cache_path,
    canonical_json,
    is_cached,
    is_fresh,
    meta_path,
    read_meta,
    write_cache,
)


def test_cache_key_order_independent() -> None:
    a = cache_key({"x": 1, "y": [1, 2]})
    assert a == cache_key({"y": [1, 2], "x": 1})
    assert a != cache_key({"x": 2, "y": [1, 2]})
    assert len(a) == 40


def test_cache_key_string_is_sha1_of_the_string() -> None:
    # Matches SCAN's sha1(url) / sha1(query text) usage: the str is hashed as given.
    assert cache_key("abc") == hashlib.sha1(b"abc").hexdigest()


def test_canonical_json() -> None:
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
    with pytest.raises(ValueError):
        canonical_json({"v": float("nan")})


def test_cache_path(tmp_path: Path) -> None:
    key = "ab12" + "0" * 36
    assert cache_path(tmp_path, "lidar/ds_1", key, ".json") == (
        tmp_path / "lidar" / "ds_1" / "ab" / f"{key}.json"
    )
    assert cache_path(tmp_path, "arcgis_rest", key) == tmp_path / "arcgis_rest" / "ab" / key


@pytest.mark.parametrize("ns", ["../x", "A B", "", "a//b", "a/../b", "/abs"])
def test_bad_namespace(tmp_path: Path, ns: str) -> None:
    with pytest.raises(ValueError):
        cache_path(tmp_path, ns, "abcd")


@pytest.mark.parametrize("suffix", ["json", ".JSON", "./x", ".", "." + "a" * 17])
def test_bad_suffix(tmp_path: Path, suffix: str) -> None:
    with pytest.raises(ValueError):
        cache_path(tmp_path, "ns", "abcd", suffix)


def test_bad_key(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        cache_path(tmp_path, "ns", "a")
    with pytest.raises(ValueError):
        cache_path(tmp_path, "ns", "ab/cd")


def test_write_cache_and_meta(tmp_path: Path) -> None:
    p = cache_path(tmp_path, "ns", cache_key("k"), ".bin")
    when = datetime(2026, 11, 21, 18, 4, 5, tzinfo=UTC)
    write_cache(p, b"hello", url="https://example.test/x", params={"a": 1}, now=when)
    assert p.read_bytes() == b"hello"
    assert is_cached(p)
    meta = read_meta(p)
    assert set(meta) == {"url", "params", "fetched_at", "bytes", "sha256", "palmfix_version"}
    assert meta["sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert meta["bytes"] == 5
    assert meta["fetched_at"] == "2026-11-21T18:04:05Z"
    assert meta["params"] == {"a": 1}
    assert not [f for f in p.parent.iterdir() if ".tmp-" in f.name]


def test_data_without_meta_not_cached(tmp_path: Path) -> None:
    p = tmp_path / "ns" / "ab" / "abcd.bin"
    atomic_write_bytes(p, b"x")
    assert not is_cached(p)
    assert not is_fresh(p, None)
    assert meta_path(p).name == "abcd.bin.meta.json"


def test_is_fresh(tmp_path: Path) -> None:
    p = tmp_path / "ab" / "abcd.bin"
    fetched = datetime(2026, 11, 1, tzinfo=UTC)
    write_cache(p, b"x", url=None, now=fetched)
    assert is_fresh(p, None)
    assert is_fresh(p, 1, now=fetched + timedelta(hours=23))
    assert not is_fresh(p, 1, now=fetched + timedelta(days=2))


def test_atomic_failure_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "f.txt"
    atomic_write_text(p, "old")

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("boom")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="boom"):
        atomic_write_bytes(p, b"new")
    monkeypatch.undo()
    assert p.read_text(encoding="utf-8") == "old"
    assert [f.name for f in tmp_path.iterdir()] == ["f.txt"]


def test_atomic_text_no_newline_translation(tmp_path: Path) -> None:
    p = tmp_path / "t.txt"
    atomic_write_text(p, "a\nb\n")
    assert p.read_bytes() == b"a\nb\n"
