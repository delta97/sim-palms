"""Download cache for palmscan: ``palmcore.cache`` layout plus get-or-fetch, offline, refresh."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from palmcore import cache as _pc
from palmcore.cache import cache_key
from palmcore.errors import CacheMiss
from palmcore.log import get_logger

__all__ = ["Cache", "CacheMiss", "cache_key"]

_log = get_logger(__name__)


class Cache:
    """Cache under ``root`` (normally ``data/``).

    Layout, key hashing, atomic writes and the ``.meta.json`` sidecar are
    :mod:`palmcore.cache`. ``offline`` turns a missing entry into :class:`CacheMiss`;
    ``refresh`` ignores existing entries (it has no effect when ``offline``).
    """

    def __init__(
        self, root: Path | str = Path("data"), offline: bool = False, refresh: bool = False
    ) -> None:
        self.root = Path(root)
        self.offline = offline
        self.refresh = refresh

    def path_for(self, namespace: str, key: str, suffix: str = "") -> Path:
        return _pc.cache_path(self.root, namespace, key, suffix)

    def has(self, namespace: str, key: str, suffix: str = "") -> bool:
        return _pc.is_cached(self.path_for(namespace, key, suffix))

    def read_meta(self, path: Path) -> dict[str, Any]:
        return _pc.read_meta(path)

    def get_or_fetch(
        self,
        namespace: str,
        key: str,
        fetch: Callable[[Path], None],
        suffix: str = "",
        meta: Mapping[str, Any] | None = None,
    ) -> Path:
        """Return the cached file, calling ``fetch(tmp_path)`` to create it if needed.

        ``fetch`` writes the payload to the path it is given; the result is then stored
        atomically with a provenance sidecar. ``meta`` may hold ``url`` and ``params``; any
        other keys are recorded under ``params``.
        """
        path = self.path_for(namespace, key, suffix)
        if _pc.is_cached(path) and (self.offline or not self.refresh):
            return path
        if self.offline:
            raise CacheMiss(f"offline: no cached copy at {path}")
        _log.debug("cache miss %s/%s: fetching", namespace, key)
        tmp = path.with_name(path.name + f".part-{os.getpid()}")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            fetch(tmp)
            if not tmp.is_file():
                raise RuntimeError(f"fetch did not write {tmp.name}")
            data = tmp.read_bytes()
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
        info = dict(meta or {})
        url = info.pop("url", None)
        params = dict(info.pop("params", None) or {})
        params.update(info)
        _pc.write_cache(path, data, url=url, params=params or None)
        return path
