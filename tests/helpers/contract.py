"""palms.geojson contract conformance: schema (ARCH-002) plus cross-field invariants.

``validate_palms`` wraps ``palmcore.contract.validate_palms``. ``check_palms_invariants`` adds the
rules JSON Schema cannot express (plans/detailed/06-testing.md#contract-conformance). Warnings from
palmcore are not errors and are not returned.

CLI: ``python -m tests.helpers.contract <palms.geojson> [--region <region.yaml>]``
exit 0 when no errors, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from palmcore import contract
from palmcore.config import RegionConfig, load_region, load_region_dict
from palmcore.errors import ConfigError, ContractError
from tests.helpers.fixtures import REPO_ROOT

RADIUS_TOLERANCE_M = 0.01
MAX_ERRORS_SHOWN = 50

RegionArg = RegionConfig | Mapping[str, Any] | Path | str | None


def _resolve_region(region: RegionArg) -> RegionConfig | None:
    """Accept a loaded RegionConfig, a path to a region YAML, or a parsed region mapping."""
    if region is None or isinstance(region, RegionConfig):
        return region
    if isinstance(region, (str, Path)):
        return load_region(Path(region))
    if isinstance(region, Mapping):
        return load_region_dict(region, base_dir=REPO_ROOT)
    raise TypeError(f"region must be a RegionConfig, mapping or path, got {type(region).__name__}")


def _load_doc(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return doc


def _number(value: Any) -> float | None:
    """A finite int or float (bool excluded), else None. Malformed values are the schema's job."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def validate_palms(fc: Mapping[str, Any]) -> list[str]:
    """Schema and semantic errors from palmcore, as readable strings (warnings excluded)."""
    try:
        report = contract.validate_palms(fc)
    except ContractError as exc:
        return [str(exc)]
    return [str(issue) for issue in report.errors]


def check_palms_invariants(fc: Mapping[str, Any], *, region: RegionArg = None) -> list[str]:
    """Cross-field rules beyond the schema. Region-only rules run when ``region`` is given."""
    cfg = _resolve_region(region)
    problems: list[str] = []

    if cfg is not None and fc.get("region") != cfg.region:
        problems.append(
            f"region: file region {fc.get('region')!r} does not match region config {cfg.region!r}"
        )

    features = fc.get("features")
    if not isinstance(features, list):
        return [*problems, "features: must be a list"]

    seen_ids: dict[str, int] = {}
    file_regions: set[str] = set()
    for index, feature in enumerate(features):
        props = feature.get("properties") if isinstance(feature, Mapping) else None
        if not isinstance(props, Mapping):
            continue  # the schema reports a feature without properties
        palm_id = props.get("palm_id")
        label = f"features[{index}] {palm_id}"

        def add(path: str, message: str, _label: str = label) -> None:
            problems.append(f"{_label}: {path}: {message}")

        if isinstance(palm_id, str):
            if palm_id in seen_ids:
                add(
                    "properties.palm_id",
                    f"duplicate palm_id (first seen at features[{seen_ids[palm_id]}])",
                )
            else:
                seen_ids[palm_id] = index

        region_value = props.get("region")
        if isinstance(region_value, str):
            file_regions.add(region_value)
            if cfg is not None and region_value != cfg.region:
                add(
                    "properties.region",
                    f"region {region_value!r} does not match region config {cfg.region!r}",
                )

        geometry = feature.get("geometry")
        coords = geometry.get("coordinates") if isinstance(geometry, Mapping) else None
        if cfg is not None and isinstance(coords, list) and len(coords) == 2:
            lon, lat = (_number(c) for c in coords)
            if lon is not None and lat is not None:
                box = cfg.bbox
                inside = box.lon_min <= lon <= box.lon_max and box.lat_min <= lat <= box.lat_max
                if not inside:
                    bbox_text = [box.lon_min, box.lat_min, box.lon_max, box.lat_max]
                    add(
                        "geometry.coordinates",
                        f"point [{lon}, {lat}] lies outside region bbox {bbox_text}",
                    )

        radius = _number(props.get("exclusion_radius_m"))
        crown = _number(props.get("crown_diam_m"))
        if radius is not None and radius <= 0:
            add(
                "properties.exclusion_radius_m",
                f"exclusion_radius_m {radius} must be greater than 0",
            )
        if radius is not None and crown is not None:
            if cfg is not None:
                ex = cfg.exclusion
                expected = min(max(crown / 2 + ex.margin_m, ex.radius_min_m), ex.radius_max_m)
                if abs(radius - expected) > RADIUS_TOLERANCE_M:
                    add(
                        "properties.exclusion_radius_m",
                        f"exclusion_radius_m {radius} differs from {expected:.2f} "
                        "(clamp of crown_diam_m / 2 + margin_m to radius_min_m..radius_max_m)",
                    )
            elif radius < crown / 2:
                add(
                    "properties.exclusion_radius_m",
                    f"exclusion_radius_m {radius} is below crown_diam_m / 2 = {crown / 2}",
                )

        height = _number(props.get("height_m"))
        if height is not None and height <= 0:
            add("properties.height_m", f"height_m {height} must be greater than 0")

        confidence = _number(props.get("species_confidence"))
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            add(
                "properties.species_confidence",
                f"species_confidence {confidence} is outside [0, 1]",
            )

        detected = str(props.get("detected_by", "")).split("+")
        if props.get("height_source") == "lidar" and "lidar" not in detected:
            add(
                "properties.detected_by",
                f"height_source is 'lidar' but detected_by {props.get('detected_by')!r} "
                "does not include 'lidar'",
            )

    if len(file_regions) > 1:
        problems.append(f"features: region differs across features: {sorted(file_regions)}")
    return problems


def assert_palms_ok(path_or_fc: Path | Mapping[str, Any], *, region: RegionArg = None) -> None:
    """Raise AssertionError listing up to 50 problems (plus a count) unless the doc conforms."""
    if isinstance(path_or_fc, (str, Path)):
        fc: Mapping[str, Any] = _load_doc(Path(path_or_fc))
    else:
        fc = path_or_fc
    problems = validate_palms(fc) + check_palms_invariants(fc, region=region)
    if not problems:
        return
    shown = problems[:MAX_ERRORS_SHOWN]
    lines = [f"palms.geojson failed the contract: {len(problems)} problem(s)", *shown]
    if len(problems) > len(shown):
        lines.append(f"... and {len(problems) - len(shown)} more")
    raise AssertionError("\n".join(lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tests.helpers.contract",
        description="Check a palms.geojson against the schema and cross-field invariants.",
    )
    parser.add_argument("palms", type=Path, help="palms.geojson to check")
    parser.add_argument("--region", type=Path, default=None, help="region YAML (regions/<r>.yaml)")
    args = parser.parse_args(argv)
    try:
        fc = _load_doc(args.palms)
        cfg = _resolve_region(args.region)
    except (ValueError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    problems = validate_palms(fc) + check_palms_invariants(fc, region=cfg)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s) in {args.palms}", file=sys.stderr)
        return 1
    count = len(fc.get("features", [])) if isinstance(fc.get("features"), list) else 0
    print(f"OK: {args.palms} ({count} feature(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
