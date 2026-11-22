"""palmscan.cache: hit, miss, offline, refresh, atomic write. No network."""

from __future__ import annotations

from pathlib import Path

import pytest

from palmcore.errors import CacheMiss as CoreCacheMiss
from palmscan.cache import Cache, CacheMiss, cache_key


class Fetcher:
    def __init__(self, payload: bytes = b"hello") -> None:
        self.calls = 0
        self.payload = payload

    def __call__(self, dest: Path) -> None:
        self.calls += 1
        dest.write_bytes(self.payload)


def test_cachemiss_is_the_palmcore_class() -> None:
    assert CacheMiss is CoreCacheMiss


def test_miss_then_hit(tmp_path: Path) -> None:
    cache = Cache(tmp_path)
    fetch = Fetcher(b"payload")
    key = cache_key("https://example.test/x")
    path = cache.get_or_fetch("overpass", key, fetch, suffix=".json", meta={"url": "u"})
    assert path == tmp_path / "overpass" / key[:2] / f"{key}.json"
    assert path.read_bytes() == b"payload"
    assert fetch.calls == 1
    again = cache.get_or_fetch("overpass", key, fetch, suffix=".json")
    assert again == path
    assert fetch.calls == 1


def test_meta_sidecar(tmp_path: Path) -> None:
    cache = Cache(tmp_path)
    path = cache.get_or_fetch(
        "arcgis_rest", "abcdef", Fetcher(b"12345"), meta={"url": "http://x", "params": {"a": 1}}
    )
    meta = cache.read_meta(path)
    assert meta["url"] == "http://x"
    assert meta["params"] == {"a": 1}
    assert meta["bytes"] == 5
    assert len(meta["sha256"]) == 64
    assert meta["fetched_at"].endswith("Z")


def test_offline_miss_raises_cachemiss(tmp_path: Path) -> None:
    cache = Cache(tmp_path, offline=True)
    fetch = Fetcher()
    with pytest.raises(CacheMiss):
        cache.get_or_fetch("overpass", "abcdef", fetch)
    assert fetch.calls == 0
    assert not list(tmp_path.rglob("*"))  # nothing created


def test_offline_hit_returns_cached(tmp_path: Path) -> None:
    Cache(tmp_path).get_or_fetch("overpass", "abcdef", Fetcher(b"x"))
    path = Cache(tmp_path, offline=True).get_or_fetch("overpass", "abcdef", Fetcher(b"y"))
    assert path.read_bytes() == b"x"


def test_refresh_refetches(tmp_path: Path) -> None:
    Cache(tmp_path).get_or_fetch("overpass", "abcdef", Fetcher(b"old"))
    fetch = Fetcher(b"new")
    path = Cache(tmp_path, refresh=True).get_or_fetch("overpass", "abcdef", fetch)
    assert fetch.calls == 1
    assert path.read_bytes() == b"new"


def test_failed_fetch_leaves_no_entry(tmp_path: Path) -> None:
    def boom(dest: Path) -> None:
        dest.write_bytes(b"partial")
        raise RuntimeError("download died")

    cache = Cache(tmp_path)
    with pytest.raises(RuntimeError):
        cache.get_or_fetch("overpass", "abcdef", boom)
    assert not cache.has("overpass", "abcdef")
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_failed_refresh_keeps_old_entry(tmp_path: Path) -> None:
    cache = Cache(tmp_path)
    path = cache.get_or_fetch("overpass", "abcdef", Fetcher(b"good"))

    def boom(dest: Path) -> None:
        dest.write_bytes(b"partial")
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        Cache(tmp_path, refresh=True).get_or_fetch("overpass", "abcdef", boom)
    assert path.read_bytes() == b"good"


def test_fetch_that_writes_nothing_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        Cache(tmp_path).get_or_fetch("overpass", "abcdef", lambda dest: None)


def test_namespace_with_slash_and_bad_namespace(tmp_path: Path) -> None:
    cache = Cache(tmp_path)
    path = cache.get_or_fetch("lidar/ds1", "tile_0_0", Fetcher())
    assert path.parent == tmp_path / "lidar" / "ds1" / "ti"
    with pytest.raises(ValueError):
        cache.path_for("../evil", "abcdef")


def test_cache_key_matches_palmcore() -> None:
    assert cache_key({"b": 1, "a": 2}) == cache_key({"a": 2, "b": 1})
    assert len(cache_key("x")) == 40
