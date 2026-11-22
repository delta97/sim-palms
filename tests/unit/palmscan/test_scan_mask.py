"""palmscan.mask: mask_out loading (bbox, inline geometry, GeoJSON file) and palm removal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from palmcore.config import MaskArea
from palmcore.errors import ConfigError
from palmcore.geo import Bbox
from palmscan.mask import apply_masks, load_masks
from palmscan.model import PalmRecord

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-117.20, 32.70], [-117.19, 32.70], [-117.19, 32.71], [-117.20, 32.71]]],
}


def area(name: str, **kw: Any) -> MaskArea:
    fields: dict[str, Any] = {
        "kind": "mod",
        "bbox": None,
        "geometry": None,
        "path": None,
        "note": None,
    }
    fields.update(kw)
    return MaskArea(name=name, **fields)


def palm(key: str, lon: float, lat: float) -> PalmRecord:
    return PalmRecord(
        stable_key=key,
        lon=lon,
        lat=lat,
        x=0.0,
        y=0.0,
        species="washingtonia_robusta",
        species_confidence=0.95,
        species_source="inventory",
        species_raw="Washingtonia robusta",
    )


def test_bbox_mask_removes_palms_inside_with_reason(tmp_path: Path) -> None:
    masks = load_masks([area("airport-ish", bbox=Bbox(-117.30, 32.70, -117.25, 32.75))], tmp_path)
    palms = [palm("src:1", -117.27, 32.72), palm("src:2", -117.10, 32.72)]
    kept, rejects = apply_masks(palms, masks)
    assert [p.stable_key for p in kept] == ["src:2"]
    (rej,) = rejects
    assert (rej.stage, rej.reason, rej.source, rej.source_id) == (
        "mask",
        "mask_out:airport-ish",
        "src",
        "1",
    )
    assert rej.all_reasons == ["mask_out:airport-ish"]
    assert (rej.lon, rej.lat, rej.species_raw) == (-117.27, 32.72, "Washingtonia robusta")


def test_geojson_file_mask(tmp_path: Path) -> None:
    path = tmp_path / "mod.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": SQUARE}],
            }
        ),
        encoding="utf-8",
    )
    masks = load_masks([area("mod-a", path=path)], tmp_path)
    kept, rejects = apply_masks(
        [palm("s:in", -117.195, 32.705), palm("s:out", -117.18, 32.705)], masks
    )
    assert [p.stable_key for p in kept] == ["s:out"]
    assert rejects[0].reason == "mask_out:mod-a"


def test_inline_geometry_mask_and_edge_counts_as_inside(tmp_path: Path) -> None:
    masks = load_masks([area("g", geometry=SQUARE)], tmp_path)
    kept, rejects = apply_masks([palm("s:edge", -117.20, 32.705)], masks)
    assert kept == [] and len(rejects) == 1


def test_first_mask_wins_and_order_is_kept(tmp_path: Path) -> None:
    masks = load_masks(
        [area("one", bbox=Bbox(-117.3, 32.6, -117.0, 32.8)), area("two", geometry=SQUARE)],
        tmp_path,
    )
    palms = [palm(f"s:{i}", -117.195, 32.705 + i * 0.001) for i in range(3)]
    kept, rejects = apply_masks(palms, masks)
    assert kept == []
    assert [r.source_id for r in rejects] == ["0", "1", "2"]
    assert {r.reason for r in rejects} == {"mask_out:one"}


def test_every_kind_removes_palms(tmp_path: Path) -> None:
    bbox = Bbox(-117.3, 32.6, -117.0, 32.8)
    for kind in ("mod", "airport", "other"):
        masks = load_masks([area(f"k-{kind}", kind=kind, bbox=bbox)], tmp_path)
        kept, rejects = apply_masks([palm("s:1", -117.2, 32.7)], masks)
        assert kept == [] and rejects[0].reason == f"mask_out:k-{kind}"


def test_no_masks_keeps_everything() -> None:
    palms = [palm("s:1", -117.2, 32.7)]
    kept, rejects = apply_masks(palms, [])
    assert kept == palms and rejects == []


def test_bad_masks_raise_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no polygon area"):
        load_masks([area("empty")], tmp_path)
    with pytest.raises(ConfigError, match="cannot read"):
        load_masks([area("missing", path=tmp_path / "nope.geojson")], tmp_path)
    bad = tmp_path / "bad.geojson"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_masks([area("bad", path=bad)], tmp_path)
