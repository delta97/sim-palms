"""Read triangle counts, bounding boxes, materials and image URIs from a ``.gltf`` file.

Only the JSON is parsed: ``.bin`` buffers are never read. POSITION accessors must carry
``min``/``max`` (required by the glTF 2.0 spec); bounding boxes come from those, transformed
through the node hierarchy. Binary ``.glb`` is not supported yet (ASSET-007 adds it if needed).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote

from palmcore.errors import ConfigError
from palmcore.log import get_logger

log = get_logger("assets.gltf_stats")

Vec3 = tuple[float, float, float]
Matrix = tuple[tuple[float, ...], ...]

_IDENTITY: Final[Matrix] = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)
_MODE_TRIANGLES: Final = 4
_MODE_STRIP: Final = 5
_MODE_FAN: Final = 6
_MAX_DEPTH: Final = 256


class GltfError(ConfigError):
    """A glTF or PNG file cannot be read, or does not carry what the checks need."""


@dataclass(frozen=True)
class GltfMaterial:
    name: str
    alpha_mode: str
    double_sided: bool


@dataclass(frozen=True)
class GltfStats:
    """Stats for one glTF file.

    ``triangles`` and ``primitives`` count every node instance of a mesh (an instanced mesh
    draws twice). ``bbox_min``/``bbox_max`` are ``None`` when the scene has no geometry.
    ``image_uris`` are percent-decoded and as written (relative to the glTF file, or a
    ``data:`` URI); images stored in a buffer view are skipped with a warning.
    """

    triangles: int
    primitives: int
    bbox_min: Vec3 | None
    bbox_max: Vec3 | None
    materials: tuple[GltfMaterial, ...]
    image_uris: tuple[str, ...]
    warnings: tuple[str, ...] = ()


# --- matrices (row lists; glTF stores matrices column-major) --------------------------------


def _mat_mul(a: Matrix, b: Matrix) -> Matrix:
    return tuple(
        tuple(sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)) for r in range(4)
    )


def _from_column_major(values: Sequence[float]) -> Matrix:
    return tuple(tuple(float(values[c * 4 + r]) for c in range(4)) for r in range(4))


def _from_trs(t: Sequence[float], q: Sequence[float], s: Sequence[float]) -> Matrix:
    """Compose ``T * R * S``."""
    x, y, z, w = q
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0:
        raise GltfError("node rotation is a zero quaternion")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    rot = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )
    rows = tuple(
        (rot[i][0] * s[0], rot[i][1] * s[1], rot[i][2] * s[2], float(t[i])) for i in range(3)
    )
    return (*rows, (0.0, 0.0, 0.0, 1.0))


def _local_matrix(node: Mapping[str, Any]) -> Matrix:
    if "matrix" in node:
        values = node["matrix"]
        if not isinstance(values, list) or len(values) != 16:
            raise GltfError("node matrix must be a list of 16 numbers")
        return _from_column_major(values)
    return _from_trs(
        node.get("translation", (0.0, 0.0, 0.0)),
        node.get("rotation", (0.0, 0.0, 0.0, 1.0)),
        node.get("scale", (1.0, 1.0, 1.0)),
    )


def _transform_box(m: Matrix, lo: Sequence[float], hi: Sequence[float]) -> tuple[Vec3, Vec3]:
    """Transform all 8 corners of a box; return the axis-aligned box around them."""
    xs: list[list[float]] = [[], [], []]
    for cx in (lo[0], hi[0]):
        for cy in (lo[1], hi[1]):
            for cz in (lo[2], hi[2]):
                for i in range(3):
                    xs[i].append(m[i][0] * cx + m[i][1] * cy + m[i][2] * cz + m[i][3])
    return (
        (min(xs[0]), min(xs[1]), min(xs[2])),
        (max(xs[0]), max(xs[1]), max(xs[2])),
    )


# --- reading ------------------------------------------------------------------------------


def _items(doc: Mapping[str, Any], key: str) -> list[Any]:
    value = doc.get(key, [])
    if not isinstance(value, list):
        raise GltfError(f"glTF {key!r} must be a list")
    return value


def _get(seq: list[Any], index: Any, what: str) -> Any:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(seq):
        raise GltfError(f"{what} index {index!r} is out of range")
    return seq[index]


def _accessor_count(accessors: list[Any], index: Any) -> int:
    count = _get(accessors, index, "accessor").get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise GltfError(f"accessor {index} has no valid count")
    return count


def _primitive_triangles(
    prim: Mapping[str, Any], accessors: list[Any], warnings: list[str], where: str
) -> int:
    """Mode 4: n/3. Modes 5 and 6: n-2. Other modes: 0 and a warning."""
    mode = prim.get("mode", _MODE_TRIANGLES)
    if mode not in (_MODE_TRIANGLES, _MODE_STRIP, _MODE_FAN):
        warnings.append(f"{where}: primitive mode {mode} is not a triangle mode; counted 0")
        return 0
    if "indices" in prim:
        count = _accessor_count(accessors, prim["indices"])
    else:
        position = prim.get("attributes", {}).get("POSITION")
        if position is None:
            warnings.append(f"{where}: primitive has no POSITION; counted 0 triangles")
            return 0
        count = _accessor_count(accessors, position)
    if mode == _MODE_TRIANGLES:
        return count // 3
    return max(count - 2, 0)


def _position_box(
    prim: Mapping[str, Any], accessors: list[Any], where: str
) -> tuple[Sequence[float], Sequence[float]] | None:
    position = prim.get("attributes", {}).get("POSITION")
    if position is None:
        return None
    acc = _get(accessors, position, "accessor")
    lo, hi = acc.get("min"), acc.get("max")
    if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == 3 and len(hi) == 3):
        raise GltfError(f"{where}: POSITION accessor {position} lacks min/max (glTF 2.0 requires)")
    return lo, hi


def _root_nodes(doc: Mapping[str, Any], nodes: list[Any]) -> list[int]:
    scenes = _items(doc, "scenes")
    if scenes:
        scene = _get(scenes, doc.get("scene", 0), "scene")
        return [int(i) for i in scene.get("nodes", [])]
    children = {int(c) for n in nodes for c in n.get("children", [])}
    return [i for i in range(len(nodes)) if i not in children]


def _materials(doc: Mapping[str, Any]) -> tuple[GltfMaterial, ...]:
    return tuple(
        GltfMaterial(
            name=str(mat.get("name", f"material_{i}")),
            alpha_mode=str(mat.get("alphaMode", "OPAQUE")),
            double_sided=bool(mat.get("doubleSided", False)),
        )
        for i, mat in enumerate(_items(doc, "materials"))
    )


def _image_uris(doc: Mapping[str, Any], warnings: list[str]) -> tuple[str, ...]:
    uris: list[str] = []
    for i, image in enumerate(_items(doc, "images")):
        uri = image.get("uri")
        if isinstance(uri, str):
            uris.append(uri if uri.startswith("data:") else unquote(uri))
        else:
            warnings.append(f"image {i} has no uri (buffer view image); not checked")
    return tuple(uris)


def read_gltf(path: Path) -> GltfStats:
    """Parse ``path`` (a ``.gltf`` file) into :class:`GltfStats`. Raises :class:`GltfError`."""
    if path.suffix.lower() == ".glb":
        raise GltfError(f"{path}: binary .glb is not supported yet; export .gltf (ASSET-007)")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GltfError(f"cannot read {path}: {exc}") from exc
    except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
        raise GltfError(f"{path} is not valid glTF JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise GltfError(f"{path}: glTF root must be an object")
    try:
        stats = _read_document(doc, path.name)
    except GltfError as exc:
        raise GltfError(f"{path}: {exc}") from exc
    except (TypeError, KeyError, ValueError, AttributeError) as exc:
        raise GltfError(f"{path}: malformed glTF ({exc!r})") from exc
    for message in stats.warnings:
        log.warning("%s", message)
    return stats


def _read_document(doc: Mapping[str, Any], name: str) -> GltfStats:
    nodes = _items(doc, "nodes")
    meshes = _items(doc, "meshes")
    accessors = _items(doc, "accessors")
    warnings: list[str] = []
    totals = {"triangles": 0, "primitives": 0}
    box: list[list[float] | None] = [None, None]  # running min and max

    def visit(index: int, parent: Matrix, path: tuple[int, ...]) -> None:
        if index in path or len(path) > _MAX_DEPTH:
            raise GltfError(f"node {index} is part of a cycle")
        node = _get(nodes, index, "node")
        world = _mat_mul(parent, _local_matrix(node))
        if "mesh" in node:
            where = f"{name} node {index}"
            for prim in _get(meshes, node["mesh"], "mesh").get("primitives", []):
                totals["primitives"] += 1
                totals["triangles"] += _primitive_triangles(prim, accessors, warnings, where)
                local = _position_box(prim, accessors, where)
                if local is None:
                    continue
                lo, hi = _transform_box(world, *local)
                cur_lo, cur_hi = box
                box[0] = (
                    list(lo)
                    if cur_lo is None
                    else [min(a, b) for a, b in zip(cur_lo, lo, strict=True)]
                )
                box[1] = (
                    list(hi)
                    if cur_hi is None
                    else [max(a, b) for a, b in zip(cur_hi, hi, strict=True)]
                )
        for child in node.get("children", []):
            visit(int(child), world, (*path, index))

    for root in _root_nodes(doc, nodes):
        visit(root, _IDENTITY, ())

    lo_all, hi_all = box
    return GltfStats(
        triangles=totals["triangles"],
        primitives=totals["primitives"],
        bbox_min=None if lo_all is None else (lo_all[0], lo_all[1], lo_all[2]),
        bbox_max=None if hi_all is None else (hi_all[0], hi_all[1], hi_all[2]),
        materials=_materials(doc),
        image_uris=_image_uris(doc, warnings),
        warnings=tuple(warnings),
    )


# --- PNG ----------------------------------------------------------------------------------

_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"


def read_png_size(path: Path) -> tuple[int, int]:
    """Return ``(width, height)`` from the PNG IHDR chunk (bytes 16 to 24, big-endian)."""
    try:
        with path.open("rb") as fh:
            head = fh.read(24)
    except OSError as exc:
        raise GltfError(f"cannot read {path}: {exc}") from exc
    if len(head) < 24 or head[:8] != _PNG_SIGNATURE or head[12:16] != b"IHDR":
        raise GltfError(f"{path} is not a PNG file")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
