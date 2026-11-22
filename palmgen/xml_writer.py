"""Render scene tiles from templates, prove they are well-formed, and write files safely.

Output is byte-deterministic: fixed-decimal numbers, no negative zero, polygons sorted by name
then placements by ``palm_id``, UTF-8 without BOM, and the line ending named in
``templates.yaml``. Files are replaced only when their bytes change.
"""

from __future__ import annotations

import math
import os
import uuid
from pathlib import Path
from typing import Any

from lxml import etree
from markupsafe import Markup

from palmgen import ids
from palmgen.errors import GenerationError
from palmgen.model import ExclusionPolygon, Placement, TileContent
from palmgen.templates import TemplateSet


def format_fixed(value: float, decimals: int) -> str:
    """Fixed-decimal text for ``value``; a value that rounds to zero never carries a minus sign."""
    if not math.isfinite(value):
        raise GenerationError(f"cannot format a non-finite number: {value!r}")
    text = f"{value:.{decimals}f}"
    if text.startswith("-") and not any(c in "123456789" for c in text):
        text = text[1:]
    return text


def format_heading(heading_deg: float, decimals: int) -> str:
    """Heading in ``[0, 360)``; 360 and values that round up to 360 print as zero."""
    if not math.isfinite(heading_deg):
        raise GenerationError(f"cannot format a non-finite heading: {heading_deg!r}")
    wrapped = heading_deg % 360.0
    if format_fixed(wrapped, decimals) == format_fixed(360.0, decimals):
        wrapped = 0.0
    return format_fixed(wrapped, decimals)


def _safe_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False
    )


def _parse(data: bytes, what: str) -> Any:
    try:
        return etree.fromstring(data, parser=_safe_parser())
    except etree.XMLSyntaxError as exc:
        raise GenerationError(f"{what}: output is not well-formed XML: {exc}") from exc


def _tile_item_name(region: str, tile_id: str) -> str:
    return f"gen/{ids.GUID_SCHEME}/tile/{region}/{tile_id}"


def _render_polygon(ts: TemplateSet, poly: ExclusionPolygon) -> str:
    fmt = ts.format
    vertices = [
        {
            "lat": format_fixed(lat, fmt.lat_decimals),
            "lon": format_fixed(lon, fmt.lon_decimals),
        }
        for lon, lat in poly.ring
    ]
    return ts.render(
        "exclusion_polygon",
        poly.name,
        name=poly.name,
        self_guid=poly.guid,
        vertices=vertices,
    )


def _render_object(ts: TemplateSet, region: str, tile_id: str, p: Placement) -> str:
    fmt = ts.format
    item_name = ids.object_name(region, tile_id, p.palm_id)
    return ts.render(
        "scenery_object",
        item_name,
        name=item_name,
        self_guid=p.guid,
        lat=format_fixed(p.lat, fmt.lat_decimals),
        lon=format_fixed(p.lon, fmt.lon_decimals),
        heading=format_heading(p.heading_deg, fmt.heading_decimals),
        scale=format_fixed(p.scale, fmt.scale_decimals),
        model_guid=p.model_guid,
    )


def _check_fragment(text: str, template: str, item: str) -> None:
    """Parse one child fragment inside a dummy root, so a failure names its template."""
    try:
        etree.fromstring(b"<r>" + text.encode("utf-8") + b"</r>", parser=_safe_parser())
    except etree.XMLSyntaxError as exc:
        raise GenerationError(
            f"template {template!r} (item {item!r}): output is not well-formed XML: {exc}"
        ) from exc


def render_tile(ts: TemplateSet, region: str, tile: TileContent) -> str:
    """Render one tile's scene file: polygons sorted by name, then placements by ``palm_id``.

    Raises ``GenerationError`` naming the template when a value is missing or the output is not
    well-formed XML.
    """
    newline = ts.format.newline
    fragments: list[str] = []
    for poly in sorted(tile.polygons, key=lambda p: p.name):
        fragments.append(_render_polygon(ts, poly))
        _check_fragment(fragments[-1], "exclusion_polygon", poly.name)
    for placement in sorted(tile.placements, key=lambda p: p.palm_id):
        fragments.append(_render_object(ts, region, tile.tile_id, placement))
        _check_fragment(
            fragments[-1],
            "scenery_object",
            ids.object_name(region, tile.tile_id, placement.palm_id),
        )
    body = Markup("".join(f if f.endswith("\n") else f + newline for f in fragments))
    item_name = _tile_item_name(region, tile.tile_id)
    text = ts.render(
        "scene_file",
        item_name,
        name=item_name,
        self_guid=ids.tile_guid(region, tile.tile_id),
        body=body,
    )
    _parse(text.encode("utf-8"), f"template 'scene_file' (tile {tile.tile_id!r})")
    return text


def write_if_changed(path: Path, text: str) -> bool:
    """Write ``text`` (UTF-8, no newline translation) unless the file already holds those bytes.

    Returns ``True`` when the file was written. An unchanged file is left alone, mtime included.
    A changed file is written to a temp file in the same folder and renamed over the target.
    """
    path = Path(path)
    data = text.encode("utf-8")
    try:
        if path.read_bytes() == data:
            return False
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return True


def count_elements(xml_text: str, xpath: str) -> int:
    """Number of nodes the XPath selects in ``xml_text`` (no namespace prefixes are bound)."""
    root = _parse(xml_text.encode("utf-8"), "count_elements")
    try:
        result = root.xpath(xpath)
    except etree.XPathError as exc:
        raise GenerationError(f"invalid XPath {xpath!r}: {exc}") from exc
    if not isinstance(result, list):
        raise GenerationError(f"XPath {xpath!r} must select nodes, got {result!r}")
    return len(result)
