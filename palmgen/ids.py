"""GEN deterministic GUIDs and per-palm hashes.

Thin layer over ``palmcore.ids`` (ARCH-006). Every GUID is a UUIDv5 under
``palmcore.ids.NAMESPACE``; every hash comes from ``palmcore.ids.stable_unit_float``.
Nothing here defines its own namespace or digest.

Changing ``GUID_SCHEME`` or any derivation below changes every GUID in every
shipped package. Bump the scheme and the MAJOR version when that happens.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Final, cast

from palmcore import ids as core
from palmcore.ids import GuidStyle

GUID_SCHEME: Final = "v1"

_GUID_STYLES: Final = frozenset({"braces_upper", "braces_lower", "plain_upper", "plain_lower"})


def _members_key(member_ids: Sequence[str]) -> str:
    if not member_ids:
        raise ValueError("an exclusion polygon needs at least one member palm id")
    return ",".join(sorted(member_ids))


def polygon_name(region: str, tile_id: str, member_ids: Sequence[str], part: int = 0) -> str:
    """Name string of an exclusion polygon. Member order does not matter."""
    return f"gen/{GUID_SCHEME}/excl/{region}/{tile_id}/{_members_key(member_ids)}#{part}"


def object_name(region: str, tile_id: str, palm_id: str) -> str:
    """Name string of a scenery object (one palm)."""
    return f"gen/{GUID_SCHEME}/obj/{region}/{tile_id}/{palm_id}"


def polygon_guid(region: str, tile_id: str, member_ids: Sequence[str], part: int = 0) -> uuid.UUID:
    """GUID of an exclusion polygon. Member order does not matter; ``part`` is included."""
    return core.object_guid(
        "gen_excl", GUID_SCHEME, region, tile_id, _members_key(member_ids), str(part)
    )


def object_guid(region: str, tile_id: str, palm_id: str) -> uuid.UUID:
    """GUID of a scenery object."""
    return core.object_guid("gen_obj", GUID_SCHEME, region, tile_id, palm_id)


def tile_guid(region: str, tile_id: str) -> uuid.UUID:
    """GUID of a tile-level item."""
    return core.object_guid("gen_tile", GUID_SCHEME, region, tile_id)


def child_guid(parent_name: str, role: str) -> uuid.UUID:
    """GUID of a nested element, from its parent's name string and its role."""
    return core.object_guid("gen_child", GUID_SCHEME, parent_name, role)


def format_guid(u: uuid.UUID, style: str) -> str:
    """Render ``u`` in a style named in ``templates.yaml``; unknown styles raise ``ValueError``."""
    if style not in _GUID_STYLES:
        raise ValueError(f"unknown GUID style: {style!r}")
    return core.format_guid(u, cast(GuidStyle, style))


def unit_hash(palm_id: str, purpose: str) -> float:
    """Deterministic value in [0, 1) for one palm and one purpose (for example ``"heading"``)."""
    return core.stable_unit_float(purpose, palm_id)
