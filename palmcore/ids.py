"""Deterministic ids and seeded randomness.

Every value here is a pure function of its inputs: no ``hash()`` (salted per process),
no ``uuid1``/``uuid4``, no unseeded ``random``. Rebuilds therefore produce the same
palm ids, object GUIDs, headings and variant picks on every machine.

Changing any derivation in this module is a MAJOR contract change (plan WS10); the
golden vectors in ``tests/unit/palmcore/test_ids.py`` exist to catch accidental changes.
"""

from __future__ import annotations

import hashlib
import random
import re
import uuid
from collections.abc import Iterable, Sequence
from typing import Final, Literal

from palmcore.errors import ContractError

GuidStyle = Literal["braces_upper", "braces_lower", "plain_upper", "plain_lower"]

# uuid5(NAMESPACE_URL, "urn:palmfix:namespace:v1"), frozen as a literal.
NAMESPACE: Final = uuid.UUID("1e4715d1-de00-51bf-a07a-679b67048e4f")

PALM_ID_RE: Final = re.compile(r"^[a-z]{2,6}-[0-9a-f]{16}$")
ID_PREFIX_RE: Final = re.compile(r"^[a-z]{2,6}$")
_KIND_RE: Final = re.compile(r"^[a-z_]+$")

_ASSERT_UNIQUE_LIMIT: Final = 20


def palm_key(stable_source_ids: Sequence[str], fallback_key: str) -> str:
    """Return the key a palm id is derived from.

    Uses the smallest stable source id when there is one, so the key does not depend on
    the order the sources were read in. Otherwise falls back to ``fallback_key``.
    """
    ids = [s for s in stable_source_ids if s]
    if ids:
        return "src:" + min(ids)
    if not fallback_key:
        raise ValueError("fallback_key must be non-empty when there are no stable source ids")
    return fallback_key


def location_key(lon: float, lat: float) -> str:
    """Generic fallback key: a grid of about 1 m (five decimals of degrees).

    Negative zero is written as ``0.00000`` so the key never depends on the sign of zero.
    """
    lon_s = f"{lon:.5f}"
    lat_s = f"{lat:.5f}"
    if lon_s == "-0.00000":
        lon_s = "0.00000"
    if lat_s == "-0.00000":
        lat_s = "0.00000"
    return f"loc:{lon_s},{lat_s}"


def palm_id(prefix: str, key: str) -> str:
    """Return ``<prefix>-<16 hex>``, derived from ``key`` with UUIDv5."""
    if not ID_PREFIX_RE.match(prefix):
        raise ValueError(f"invalid palm id prefix: {prefix!r}")
    if not key:
        raise ValueError("palm id key must be non-empty")
    digest = uuid.uuid5(NAMESPACE, "palm|" + key).hex[:16]
    return f"{prefix}-{digest}"


def cluster_key(palm_ids: Iterable[str]) -> str:
    """Key for a cluster of palms: order and duplicates do not matter."""
    unique = sorted(set(palm_ids))
    if not unique:
        raise ValueError("cluster_key needs at least one palm id")
    return "cluster:" + ",".join(unique)


def object_guid(kind: str, *parts: str) -> uuid.UUID:
    """UUIDv5 for a scenery object, from its kind and identifying parts."""
    if not _KIND_RE.match(kind):
        raise ValueError(f"invalid object kind: {kind!r}")
    if not parts:
        raise ValueError("object_guid needs at least one part")
    for part in parts:
        if "|" in part:
            raise ValueError(f"object_guid part must not contain '|': {part!r}")
    return uuid.uuid5(NAMESPACE, "|".join([kind, *parts]))


def format_guid(u: uuid.UUID, style: GuidStyle = "braces_upper") -> str:
    """Render a GUID in one of four text styles.

    The style GEN needs is not confirmed yet (SPIKE-003), so all four are supported.
    """
    text = str(u)
    if style == "braces_upper":
        return "{" + text.upper() + "}"
    if style == "braces_lower":
        return "{" + text.lower() + "}"
    if style == "plain_upper":
        return text.upper()
    if style == "plain_lower":
        return text.lower()
    raise ValueError(f"unknown GUID style: {style!r}")


def _digest(parts: Sequence[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def stable_unit_float(*parts: str) -> float:
    """Map ``parts`` to a float in [0, 1), the same on every run."""
    return int(_digest(parts)[:13], 16) / 16**13


def seeded_rng(*parts: str) -> random.Random:
    """A ``random.Random`` seeded from ``parts``, the same on every run."""
    return random.Random(int(_digest(parts)[:16], 16))


def assert_unique(ids: Iterable[str], what: str = "id") -> None:
    """Raise ``ContractError`` if any value appears more than once."""
    seen: set[str] = set()
    dup_set: set[str] = set()
    duplicates: list[str] = []
    for value in ids:
        if value in seen and value not in dup_set:
            dup_set.add(value)
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        shown = duplicates[:_ASSERT_UNIQUE_LIMIT]
        more = len(duplicates) - len(shown)
        suffix = f" (and {more} more)" if more > 0 else ""
        raise ContractError(
            f"duplicate {what}: {', '.join(shown)}{suffix}",
            issues=duplicates,
        )
