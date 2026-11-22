# ruff: noqa: E501  (spike script: XML template lines and doc URLs)
"""Generate the SPIKE-002 test scene: two 12-sided exclusion polygons around two palms.

Polygon A: ExcludeTIN only.  Polygon B: ExcludeTIN + VegetationDensity 0.
Element and attribute names, GUIDs and types are copied from the MSFS 2024 SDK docs, read 2026-11-22:
  https://docs.flightsimulator.com/msfs2024/retail/content-configuration/environment/scenery-objects/scenery-xml-properties/
  https://docs.flightsimulator.com/msfs2024/retail/content-configuration/environment/scenery-objects/scenery-editor-xml-examples/
VERIFY (SPIKE-002): that VegetationDensity 0 is what the Scenery Editor's vegetation "Exclude" writes.

Usage:  python spikes/palmfix-spike/make_scene.py OUT_SCENE_XML [--xsd PATH_TO_bglcomp.xsd]
"""

from __future__ import annotations

import argparse
import math
import sys
import uuid
from pathlib import Path

from pyproj import Transformer

# Docs: "Scenery XML Properties", <Polygon> attribute table.
UNIQUE_GUID = "{359C73E8-06BE-4FB2-ABCB-EC942F7761D0}"
EXCLUDE_TIN = "{18B58CBF-AE02-4A19-8AA9-3809E8E73400}"
VEGETATION_DENSITY = "{41EFF715-C392-4B31-A457-50A504353A90}"  # 0 = 0 %, 31 = 100 %, 62 = 200 %

# Two isolated 15.2 m Washingtonia robusta from build/scan/sd-pacific-beach/palms.geojson (2026-11-22),
# >= 22 m from OSM buildings. Ground altitude: USGS EPQS (3DEP), metres.
PALMS = [
    {
        "key": "A",
        "palm_id": "sdpb-8a03f7f6752f55c8",
        "lat": 32.794425,
        "lon": -117.251520,
        "alt": 5.64,
        "label": "palmfix A: ExcludeTIN",
        "veg_density_zero": False,
    },
    {
        "key": "B",
        "palm_id": "sdpb-e6ea40b0410d50ac",
        "lat": 32.794239,
        "lon": -117.252341,
        "alt": 4.73,
        "label": "palmfix B: ExcludeTIN + vegetation 0",
        "veg_density_zero": True,
    },
]
RADIUS_M = 6.0  # generous: inventory points can sit a few metres off the photogrammetry blob
SIDES = 12
NS = uuid.UUID("1e4715d1-de00-51bf-a07a-679b67048e4f")  # palmcore.ids.NAMESPACE


def ring(lat: float, lon: float, radius_m: float, sides: int) -> list[tuple[float, float]]:
    to_utm = Transformer.from_crs(4326, 32611, always_xy=True)
    to_ll = Transformer.from_crs(32611, 4326, always_xy=True)
    x0, y0 = to_utm.transform(lon, lat)
    pts = []
    for i in range(sides):  # counter-clockwise from east
        a = 2 * math.pi * i / sides
        lo, la = to_ll.transform(x0 + radius_m * math.cos(a), y0 + radius_m * math.sin(a))
        pts.append((la, lo))
    return pts


def scene_xml() -> str:
    out = ['<?xml version="1.0"?>', '<FSData version="9.0">']
    for i, p in enumerate(PALMS, start=1):
        guid = "{" + str(uuid.uuid5(NS, f"spike002|{p['palm_id']}")).upper() + "}"
        out.append(
            f'    <Polygon displayName="{p["label"]}" groupIndex="{i}" altitude="{p["alt"]:.2f}">'
        )
        out.append(
            f'        <Attribute name="UniqueGUID" guid="{UNIQUE_GUID}" type="GUID" value="{guid}"/>'
        )
        out.append(
            f'        <Attribute name="ExcludeTIN" guid="{EXCLUDE_TIN}" type="UINT8" value="1"/>'
        )
        if p["veg_density_zero"]:
            out.append(
                f'        <Attribute name="VegetationDensity" guid="{VEGETATION_DENSITY}" type="UINT32" value="0"/>'
            )
        for la, lo in ring(p["lat"], p["lon"], RADIUS_M, SIDES):
            out.append(f'        <Vertex lat="{la:.8f}" lon="{lo:.8f}"/>')
        out.append("    </Polygon>")
    out.append("</FSData>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("out", type=Path)
    ap.add_argument("--xsd", type=Path, help="validate against bglcomp.xsd (needs lxml)")
    a = ap.parse_args()
    text = scene_xml()
    if a.xsd:
        from lxml import etree

        schema = etree.XMLSchema(etree.parse(str(a.xsd)))
        doc = etree.fromstring(text.encode("utf-8"))
        if not schema.validate(doc):
            print("INVALID against", a.xsd, file=sys.stderr)
            for e in schema.error_log:
                print(f"  line {e.line}: {e.message}", file=sys.stderr)
            return 1
        print("valid against", a.xsd)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
