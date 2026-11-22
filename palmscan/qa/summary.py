"""``qa_summary.md``: a readable report of one palmscan run (plan W10).

:func:`render_summary` is a pure function of a :class:`QaContext`, so identical input gives
identical text. Optional sections (Classifier, Accuracy) are left out when their data is absent.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from palmscan.model import PalmRecord, SourceVintage

if TYPE_CHECKING:
    import geopandas as gpd

__all__ = [
    "ClassifierSummary",
    "QaContext",
    "SourceCounts",
    "git_sha",
    "render_summary",
    "write_summary",
]

_OLDEST_CELLS: Final = 10
_TOP_UNMATCHED: Final = 20
RUN_TIME_LABEL: Final = "Run time (UTC)"


@dataclass(slots=True)
class SourceCounts:
    """Record counts for one source as it moves through the inventory stages."""

    source: str
    fetched: int = 0
    non_tree: int = 0
    not_palm: int = 0
    palm: int = 0
    deduped: int = 0
    masked: int = 0
    kept: int = 0


@dataclass(slots=True)
class ClassifierSummary:
    """Phase 4 species classifier report (rules vs decision tree)."""

    chosen_model: str
    cv_acc_rules: float | None = None
    cv_acc_tree: float | None = None
    n_samples: int = 0
    reason: str = ""
    confusion: Mapping[str, Mapping[str, int]] = field(default_factory=dict)


@dataclass(slots=True)
class QaContext:
    """Everything the summary sections need."""

    region: str
    run_time: str  # ISO 8601 UTC, e.g. "2026-11-22T12:00:00Z"
    palmscan_version: str
    config_hash: str | None
    stages: Sequence[str]
    output_path: str
    palms: Sequence[PalmRecord]
    git_sha: str | None = None
    source_counts: Sequence[SourceCounts] = ()
    conflict_building_count: int = 0
    source_vintages: Sequence[SourceVintage] = ()
    vintage_grid: gpd.GeoDataFrame | None = None
    unmatched_palm_names: Mapping[str, int] = field(default_factory=dict)
    priors_computed: Mapping[str, float] = field(default_factory=dict)
    priors_configured: Mapping[str, float] = field(default_factory=dict)
    priors_used: str = "none"  # "computed" | "configured" | "merged" | "none"
    classifier: ClassifierSummary | None = None
    accuracy_md: str | None = None  # rendered by the accuracy module (SCAN-029)
    warnings: Sequence[str] = ()


def git_sha(cwd: Path | None = None) -> str | None:
    """Short sha from ``git rev-parse --short HEAD``; ``None`` when git or a repo is missing."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = done.stdout.strip()
    return sha if done.returncode == 0 and sha else None


# ---------------------------------------------------------------------------------------------
# Formatting helpers


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(header: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def _pct(part: int, whole: int) -> str:
    return f"{100.0 * part / whole:.1f}%" if whole else "-"


def _num(value: float | None, decimals: int) -> str:
    return "-" if value is None else f"{value:.{decimals}f}"


def _split(counter: Counter[str]) -> str:
    return ", ".join(f"{k}:{counter[k]}" for k in sorted(counter)) or "-"


def _by_count(counter: Mapping[str, int]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------------------------
# Sections


def _header(ctx: QaContext) -> list[str]:
    return [
        f"# palmscan QA: {ctx.region}",
        "",
        f"- {RUN_TIME_LABEL}: {ctx.run_time}",
        f"- palmscan version: {ctx.palmscan_version}",
        f"- git sha: {ctx.git_sha or 'unavailable'}",
        f"- Config hash: {ctx.config_hash or 'unavailable'}",
        f"- Stages run: {', '.join(ctx.stages) if ctx.stages else 'none'}",
        f"- Output: {ctx.output_path}",
    ]


def _counts_by_source(ctx: QaContext) -> list[str]:
    header = ["source", "fetched", "non-tree", "not palm", "palm", "deduped", "masked", "kept"]
    rows = [
        [c.source, c.fetched, c.non_tree, c.not_palm, c.palm, c.deduped, c.masked, c.kept]
        for c in sorted(ctx.source_counts, key=lambda c: c.source)
    ]
    return ["## Counts by source", "", *(_table(header, rows) if rows else ["No sources."])]


def _counts_by_species(ctx: QaContext) -> list[str]:
    groups: dict[str, list[PalmRecord]] = {}
    for palm in ctx.palms:
        groups.setdefault(palm.species or "unknown", []).append(palm)
    total = len(ctx.palms)
    rows = []
    for species, group in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        heights = [p.height_m for p in group if p.height_m is not None]
        mean = sum(heights) / len(heights) if heights else None
        split = Counter(p.species_source or "none" for p in group)
        rows.append([species, len(group), _pct(len(group), total), _num(mean, 1), _split(split)])
    header = ["species", "count", "share", "mean height_m", "species_source"]
    return ["## Counts by species", "", *(_table(header, rows) if rows else ["No palms."])]


def _detection(ctx: QaContext) -> list[str]:
    counts = Counter(p.detected_by for p in ctx.palms)
    rows = [[key, n] for key, n in _by_count(counts)]
    return [
        "## Detection",
        "",
        *(_table(["detected_by", "count"], rows) if rows else ["No palms."]),
    ]


def _heights(ctx: QaContext) -> list[str]:
    total = len(ctx.palms)
    counts = Counter(p.height_source or "none" for p in ctx.palms)
    lines = [
        "## Heights",
        "",
        f"Palms with height_source lidar: {counts.get('lidar', 0)} of {total} "
        f"({_pct(counts.get('lidar', 0), total)})",
    ]
    if counts:
        lines += ["", *_table(["height_source", "count"], [[k, n] for k, n in _by_count(counts)])]
    return lines


def _building_conflicts(ctx: QaContext) -> list[str]:
    palms = sum(1 for p in ctx.palms if p.building_conflict)
    return [
        "## Building conflicts",
        "",
        f"- Palms with a building conflict: {palms}",
        f"- Buildings in conflict: {ctx.conflict_building_count}",
    ]


def _grid_rows(grid: gpd.GeoDataFrame) -> list[dict[str, object]]:
    records: list[dict[str, object]] = grid.drop(columns=grid.geometry.name).to_dict("records")
    return records


def _vintage_value(value: object) -> float | None:
    if isinstance(value, (int, float)) and value == value:  # NaN is not equal to itself
        return float(value)
    return None


def _data_vintage(ctx: QaContext) -> list[str]:
    lines = ["## Data vintage", ""]
    rows = [
        [v.source, v.vintage or "unknown", v.basis, v.fetched_at]
        for v in sorted(ctx.source_vintages, key=lambda v: v.source)
    ]
    header = ["source", "vintage", "basis", "fetched_at"]
    lines += _table(header, rows) if rows else ["No sources."]
    lines.append("")
    if ctx.vintage_grid is None:
        lines.append("Vintage grid: not available.")
        return lines
    cells = _grid_rows(ctx.vintage_grid)
    stale = [c for c in cells if c.get("stale")]
    lines.append(f"Stale cells: {len(stale)} of {len(cells)}")

    def oldest_key(cell: dict[str, object]) -> tuple[float, str]:
        years = [
            y
            for y in (
                _vintage_value(cell.get("inventory_vintage")),
                _vintage_value(cell.get("lidar_vintage")),
            )
            if y is not None
        ]
        return (min(years) if years else float("inf"), str(cell["cell_id"]))

    ranked = sorted((c for c in cells if oldest_key(c)[0] != float("inf")), key=oldest_key)
    if ranked:
        oldest: list[list[object]] = [
            [
                c["cell_id"],
                c["palm_count"],
                _num(_vintage_value(c.get("inventory_vintage")), 1),
                _num(_vintage_value(c.get("lidar_vintage")), 1),
                "yes" if c.get("stale") else "no",
            ]
            for c in ranked[:_OLDEST_CELLS]
        ]
        header = ["cell_id", "palms", "inventory_vintage", "lidar_vintage", "stale"]
        lines += ["", f"Oldest {min(_OLDEST_CELLS, len(ranked))} cells:", ""]
        lines += _table(header, oldest)
    return lines


def _unmatched(ctx: QaContext) -> list[str]:
    lines = ['## Unmatched names containing "palm"', ""]
    top = _by_count(ctx.unmatched_palm_names)[:_TOP_UNMATCHED]
    if not top:
        return [*lines, "None."]
    return [*lines, *_table(["name", "count"], [[k, n] for k, n in top])]


def _priors(ctx: QaContext) -> list[str]:
    keys = sorted(set(ctx.priors_computed) | set(ctx.priors_configured))
    lines = ["## Species priors", "", f"Used: {ctx.priors_used}"]
    if not keys:
        return lines
    rows = [
        [
            k,
            _num(ctx.priors_computed.get(k), 2) if k in ctx.priors_computed else "-",
            _num(ctx.priors_configured.get(k), 2) if k in ctx.priors_configured else "-",
        ]
        for k in keys
    ]
    return [*lines, "", *_table(["species", "computed", "configured"], rows)]


def _classifier(clf: ClassifierSummary) -> list[str]:
    lines = [
        "## Classifier",
        "",
        f"- Chosen model: {clf.chosen_model}",
        f"- Training samples: {clf.n_samples}",
        f"- CV accuracy, rules: {_num(clf.cv_acc_rules, 3)}",
        f"- CV accuracy, tree: {_num(clf.cv_acc_tree, 3)}",
    ]
    if clf.reason:
        lines.append(f"- Reason: {clf.reason}")
    if clf.confusion:
        labels = sorted({*clf.confusion, *(p for row in clf.confusion.values() for p in row)})
        rows = [
            [t, *(clf.confusion.get(t, {}).get(p, 0) for p in labels)]
            for t in sorted(clf.confusion)
        ]
        lines += ["", "Confusion matrix (rows: true, columns: predicted):", ""]
        lines += _table(["true \\ predicted", *labels], rows)
    return lines


def _warnings(ctx: QaContext) -> list[str]:
    lines = ["## Warnings", ""]
    return [*lines, *(f"- {w}" for w in ctx.warnings)] if ctx.warnings else [*lines, "None."]


def render_summary(ctx: QaContext) -> str:
    """The summary as Markdown with LF line ends and one trailing newline."""
    sections: list[list[str]] = [
        _header(ctx),
        _counts_by_source(ctx),
        _counts_by_species(ctx),
        _detection(ctx),
        _heights(ctx),
        _building_conflicts(ctx),
        _data_vintage(ctx),
        _unmatched(ctx),
        _priors(ctx),
    ]
    if ctx.classifier is not None:
        sections.append(_classifier(ctx.classifier))
    if ctx.accuracy_md:
        sections.append(["## Accuracy", "", ctx.accuracy_md.strip("\n")])
    sections.append(_warnings(ctx))
    return "\n\n".join("\n".join(s) for s in sections) + "\n"


def write_summary(ctx: QaContext, path: Path) -> None:
    """Write :func:`render_summary` as UTF-8 with LF line ends."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_summary(ctx))
