"""Build report: ``build_report.json`` (machine-readable) and ``build_report.md`` (same content).

The report is deterministic: keys are inserted in plan order, lists are sorted, floats are
rounded before they are stored, and the files are written as UTF-8 with ``\\n`` line endings.
The only volatile data are the ``timings`` and ``fspackagetool`` sections and ``inputs.*.path``;
``strip_volatile`` removes them for golden comparisons.
"""

from __future__ import annotations

import copy
import json
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

from palmcore.cache import atomic_write_text
from palmgen.model import Check, CompileResult, GenerateResult

REPORT_JSON_NAME: Final = "build_report.json"
REPORT_MD_NAME: Final = "build_report.md"

EXAMPLES_PER_CODE: Final = 20
VOLATILE_KEYS: Final = ("timings", "fspackagetool")

COUNT_KEYS: Final = (
    "palms_in",
    "dropped_outside_bbox",
    "dropped_by_mask",
    "dropped_in_building",
    "radius_defaulted",
    "radius_clamped",
    "clusters",
    "clusters_split",
    "polygons",
    "polygon_parts_from_clip",
    "objects",
    "scale_clamped",
    "species_fallback",
    "height_missing",
    "tiles",
)

# VERIFY: the error and warning line patterns come from the SPIKE-004 sample logs.
# Until that spike lands these are a conservative placeholder.
_ERROR_LINE_RE: Final = re.compile(r"\berror\b", re.IGNORECASE)
_WARNING_LINE_RE: Final = re.compile(r"\bwarning\b", re.IGNORECASE)


class ReportVersion(Protocol):
    """The version fields of ``GenerateResult.version`` (``PackageVersion``, GEN-007)."""

    package_version: str
    generator_version: str
    data_version: str


@dataclass(frozen=True)
class MaskStat:
    name: str
    kind: str
    palms_dropped: int
    polygons_clipped: int


@dataclass(frozen=True)
class ReportContext:
    """Facts the report needs that ``GenerateResult`` and ``CompileResult`` do not carry.

    ``inputs`` maps an input name (``palms``, ``buildings``, ``manifest``, ``config``,
    ``templates``) to ``(repo-relative path, sha256)``. ``bgl_by_tile`` maps a tile id to the
    BGL file name that ``check_outputs`` expected for it.
    """

    placement: str = ""
    models: str = ""
    inputs: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    masks: Sequence[MaskStat] = ()
    bgl_by_tile: Mapping[str, str] = field(default_factory=dict)


def _round(value: float, places: int) -> float:
    return round(float(value), places)


def _count_log_lines(log_path: Path) -> tuple[int, int]:
    """Return ``(warning_lines, error_lines)`` for a compile log; missing log gives zeros."""
    if not log_path.is_file():
        return 0, 0
    warnings = 0
    errors = 0
    with log_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if _ERROR_LINE_RE.search(line):
                errors += 1
            elif _WARNING_LINE_RE.search(line):
                warnings += 1
    return warnings, errors


def _variants(gen: GenerateResult) -> list[dict[str, Any]]:
    scales: dict[tuple[str, str], list[float]] = {}
    for tile in gen.tiles:
        for placement in tile.placements:
            scales.setdefault((placement.species, placement.variant), []).append(
                float(placement.scale)
            )
    rows: list[dict[str, Any]] = []
    for (species, variant), values in sorted(scales.items()):
        rows.append(
            {
                "species": species,
                "variant": variant,
                "count": len(values),
                "scale_min": _round(min(values), 4),
                "scale_median": _round(statistics.median(values), 4),
                "scale_max": _round(max(values), 4),
            }
        )
    return rows


def _warnings(gen: GenerateResult) -> list[dict[str, Any]]:
    by_code: dict[str, list[str]] = {}
    for warning in gen.warnings:
        by_code.setdefault(warning.code, []).append(warning.message)
    return [
        {"code": code, "count": len(messages), "examples": messages[:EXAMPLES_PER_CODE]}
        for code, messages in sorted(by_code.items())
    ]


def _fspackagetool(comp: CompileResult | None) -> dict[str, Any]:
    if comp is None:
        return {
            "path": None,
            "command": [],
            "exit_code": None,
            "log_path": None,
            "warning_lines": 0,
            "error_lines": 0,
        }
    warning_lines, error_lines = _count_log_lines(comp.log_path)
    return {
        "path": comp.command[0] if comp.command else "",
        "command": list(comp.command),
        "exit_code": comp.exit_code,
        "log_path": comp.log_path.as_posix(),
        "warning_lines": warning_lines,
        "error_lines": error_lines,
    }


def build_report_dict(
    gen: GenerateResult,
    comp: CompileResult | None,
    checks: Iterable[Check],
    context: ReportContext | None = None,
) -> dict[str, Any]:
    """Assemble the report in plan order. ``comp`` is None when the compile was skipped."""
    ctx = context if context is not None else ReportContext()
    check_rows = sorted(checks, key=lambda c: c.name)
    exit_code = comp.exit_code if comp is not None else 0
    failed = any(not c.passed for c in check_rows)
    version: ReportVersion = gen.version

    generate_s = _round(gen.timings.get("generate_s", 0.0), 3)
    checks_s = _round(gen.timings.get("checks_s", 0.0), 3)
    compile_s = _round(comp.duration_s if comp is not None else 0.0, 3)

    return {
        "result": "FAIL" if failed or exit_code != 0 else "PASS",
        "region": gen.region,
        "package_name": gen.package_name,
        "version": f"{version.generator_version}+data{version.data_version}",
        "package_version": version.package_version,
        "generator_version": version.generator_version,
        "data_version": version.data_version,
        "placement": ctx.placement,
        "models": ctx.models,
        "inputs": {
            name: {"path": ctx.inputs[name][0], "sha256": ctx.inputs[name][1]}
            for name in sorted(ctx.inputs)
        },
        "counts": {key: int(gen.counts.get(key, 0)) for key in COUNT_KEYS},
        "masks": [
            {
                "name": mask.name,
                "kind": mask.kind,
                "palms_dropped": mask.palms_dropped,
                "polygons_clipped": mask.polygons_clipped,
            }
            for mask in sorted(ctx.masks, key=lambda m: m.name)
        ],
        "variants": _variants(gen),
        "tiles": [
            {
                "tile_id": tile.tile_id,
                "polygons": len(tile.polygons),
                "objects": len(tile.placements),
                "bgl": ctx.bgl_by_tile.get(tile.tile_id),
            }
            for tile in sorted(gen.tiles, key=lambda t: t.tile_id)
        ],
        "timings": {
            "generate_s": generate_s,
            "compile_s": compile_s,
            "checks_s": checks_s,
            "total_s": _round(generate_s + compile_s + checks_s, 3),
        },
        "fspackagetool": _fspackagetool(comp),
        "checks": [
            {"name": c.name, "expected": c.expected, "actual": c.actual, "passed": c.passed}
            for c in check_rows
        ],
        "warnings": _warnings(gen),
    }


def strip_volatile(report: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of ``report`` without ``timings``, ``fspackagetool`` and ``inputs.*.path``."""
    out: dict[str, Any] = copy.deepcopy({k: v for k, v in report.items() if k not in VOLATILE_KEYS})
    inputs = out.get("inputs")
    if isinstance(inputs, dict):
        for info in inputs.values():
            info.pop("path", None)
    return out


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("\n", " ").replace("|", "\\|")


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    if not rows:
        return ["_None._"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(v) for v in row) + " |" for row in rows)
    return lines


def _section(title: str, body: list[str]) -> list[str]:
    return [f"## {title}", "", *body, ""]


def render_report_md(report: Mapping[str, Any]) -> str:
    """Render the report as Markdown: title, identity bullets, then one table per section."""
    lines: list[str] = [
        f"# Build report: {report['package_name']}",
        "",
        f"- Result: **{report['result']}**",
        f"- Region: {report['region']}",
        f"- Package: {report['package_name']}",
        f"- Version: {report['version']}",
        f"- Package version: {report['package_version']}",
        f"- Generator version: {report['generator_version']}",
        f"- Data version: {report['data_version']}",
        f"- Placement: {report['placement']}",
        f"- Models: {report['models']}",
        "",
    ]
    inputs = report.get("inputs", {})
    lines += _section(
        "Inputs",
        _table(
            ["Input", "Path", "SHA-256"],
            [(name, info.get("path", ""), info["sha256"]) for name, info in inputs.items()],
        ),
    )
    lines += _section("Counts", _table(["Count", "Value"], list(report["counts"].items())))
    lines += _section(
        "Masks",
        _table(
            ["Mask", "Kind", "Palms dropped", "Polygons clipped"],
            [
                (m["name"], m["kind"], m["palms_dropped"], m["polygons_clipped"])
                for m in report["masks"]
            ],
        ),
    )
    lines += _section(
        "Variants",
        _table(
            ["Species", "Variant", "Count", "Scale min", "Scale median", "Scale max"],
            [
                (
                    v["species"],
                    v["variant"],
                    v["count"],
                    f"{v['scale_min']:.4f}",
                    f"{v['scale_median']:.4f}",
                    f"{v['scale_max']:.4f}",
                )
                for v in report["variants"]
            ],
        ),
    )
    lines += _section(
        "Tiles",
        _table(
            ["Tile", "Polygons", "Objects", "BGL"],
            [(t["tile_id"], t["polygons"], t["objects"], t["bgl"]) for t in report["tiles"]],
        ),
    )
    timings = report.get("timings", {})
    lines += _section(
        "Timings",
        _table(
            ["Stage", "Seconds"],
            [(stage, f"{seconds:.3f}") for stage, seconds in timings.items()],
        ),
    )
    tool = report.get("fspackagetool", {})
    lines += _section(
        "fspackagetool",
        _table(
            ["Field", "Value"],
            [
                (
                    key,
                    " ".join(str(part) for part in value) if key == "command" else value,
                )
                for key, value in tool.items()
            ],
        ),
    )
    lines += _section(
        "Checks",
        _table(
            ["Check", "Expected", "Actual", "Passed"],
            [(c["name"], c["expected"], c["actual"], c["passed"]) for c in report["checks"]],
        ),
    )
    lines += _section(
        "Warnings",
        _table(
            ["Code", "Count", "Examples"],
            [(w["code"], w["count"], "; ".join(w["examples"])) for w in report["warnings"]],
        ),
    )
    return "\n".join(lines[:-1]) + "\n"


def report_json_text(report: Mapping[str, Any]) -> str:
    """JSON text in insertion order (plan order), UTF-8 content, ``\\n`` line endings."""
    return json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _write_if_changed(path: Path, text: str) -> None:
    data = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return
    atomic_write_text(path, text)


def write_reports(project_dir: Path, report: Mapping[str, Any]) -> None:
    """Write ``build_report.json`` and ``build_report.md`` into ``project_dir``.

    A file whose bytes would not change is left alone (its mtime is kept).
    """
    _write_if_changed(project_dir / REPORT_JSON_NAME, report_json_text(report))
    _write_if_changed(project_dir / REPORT_MD_NAME, render_report_md(report))
