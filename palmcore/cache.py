"""On-disk download-cache layout, provenance sidecars and atomic writes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import palmcore

NAMESPACE_RE: Final = re.compile(r"^[a-z0-9_.-]+(/[a-z0-9_.-]+)*$")
_KEY_RE: Final = re.compile(r"^[0-9a-zA-Z_.-]{2,}$")
_SUFFIX_RE: Final = re.compile(r"^\.[a-z0-9.]{1,16}$")
_META_SUFFIX: Final = ".meta.json"


def canonical_json(obj: Any) -> str:
    """Stable JSON text: sorted keys, no spaces, no NaN."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def cache_key(identity: Mapping[str, Any] | str) -> str:
    """SHA-1 hex digest of the canonical JSON of ``identity`` (or of the string itself)."""
    text = identity if isinstance(identity, str) else canonical_json(identity)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def cache_path(data_dir: Path, namespace: str, key: str, suffix: str = "") -> Path:
    """``data_dir/<namespace>/<key[:2]>/<key><suffix>``."""
    if not NAMESPACE_RE.match(namespace) or ".." in namespace.split("/"):
        raise ValueError(f"invalid cache namespace {namespace!r}")
    if not _KEY_RE.match(key):
        raise ValueError(f"invalid cache key {key!r}")
    if suffix != "" and not _SUFFIX_RE.match(suffix):
        raise ValueError(f"invalid cache suffix {suffix!r}")
    return data_dir.joinpath(*namespace.split("/"), key[:2], f"{key}{suffix}")


def meta_path(path: Path) -> Path:
    """Sidecar path for a cached file."""
    return path.with_name(path.name + _META_SUFFIX)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via a same-directory temp file and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomic text write; no newline translation."""
    atomic_write_bytes(path, text.encode(encoding))


def write_cache(
    path: Path,
    data: bytes,
    *,
    url: str | None,
    params: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    """Write the data file, then its provenance sidecar."""
    moment = (now if now is not None else datetime.now(UTC)).astimezone(UTC)
    meta: dict[str, Any] = {
        "url": url,
        "params": dict(params) if params is not None else None,
        "fetched_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "palmfix_version": palmcore.__version__,
    }
    atomic_write_bytes(path, data)
    atomic_write_text(meta_path(path), canonical_json(meta) + "\n")


def read_meta(path: Path) -> dict[str, Any]:
    """Read the sidecar for a cached file."""
    loaded = json.loads(meta_path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"cache metadata for {path} is not a JSON object")
    return loaded


def is_cached(path: Path) -> bool:
    """True when both the data file and its sidecar exist."""
    return path.is_file() and meta_path(path).is_file()


def is_fresh(path: Path, max_age_days: float | None, now: datetime | None = None) -> bool:
    """False if not cached; True if no age limit; else age of ``fetched_at`` within limit."""
    if not is_cached(path):
        return False
    if max_age_days is None:
        return True
    fetched = datetime.fromisoformat(str(read_meta(path)["fetched_at"]).replace("Z", "+00:00"))
    moment = now if now is not None else datetime.now(UTC)
    return (moment - fetched).total_seconds() <= max_age_days * 86400
