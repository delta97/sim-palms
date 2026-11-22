"""Ingest a raw capture into ``frames/`` and ``frames.jsonl`` (plan 08, A4).

Inputs under ``raw/``: ``triggers.csv`` (``frame_idx,t_trigger_ns``), ``poses.csv`` and
``reshade/`` screenshot pairs. The "before" image is clean colour, the "after" image is the
packed depth (log24). Frame ``idx`` is the trigger's ``frame_idx``, so frames dropped with
``drop`` leave holes in the numbering.

VERIFY (FX-001/FX-007): ReShade's real file names for "save before and after". The suffix
defaults below are placeholders; override with ``--before-suffix/--after-suffix`` or the
``reshade_suffixes`` object in ``session.json`` (``{"before": ..., "after": ...}``). Pairs are
matched by the file name stem with the suffix removed and ordered by (stem, mtime), so the stems
must sort in capture order. The pose log column names are likewise unconfirmed: ``columns``
maps canonical names to CSV headers (``session.json`` key ``pose_columns``).
"""

from __future__ import annotations

import contextlib
import csv
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.depth import read_depth_png
from palmfx.offline.session import FRAMES_JSONL, Session, read_image, write_image
from palmfx.offline.timing import interpolate_poses_with_gap

log = get_logger(__name__)

DEFAULT_BEFORE = "_before"  # VERIFY: FX-001
DEFAULT_AFTER = "_after"  # VERIFY: FX-001
DEFAULT_MAX_GAP_MS = 50.0
POSE_COLUMNS: dict[str, str] = {
    "t_host_ns": "t_host_ns",
    "lat_deg": "lat_deg",
    "lon_deg": "lon_deg",
    "alt_msl_m": "alt_msl_m",
    "heading_true_deg": "heading_true_deg",
    "pitch_deg": "pitch_deg",
    "bank_deg": "bank_deg",
}
_SCREENSHOT_EXT = ".png"


@dataclass(frozen=True)
class ShotPair:
    """One screenshot pair: clean colour and packed depth."""

    stem: str
    before: Path
    after: Path


def suffixes(session: Session, before: str | None, after: str | None) -> tuple[str, str]:
    """Resolve suffixes: explicit argument, then ``session.json``, then the defaults."""
    meta = session.meta.get("reshade_suffixes") or {}
    b = before or meta.get("before") or DEFAULT_BEFORE
    a = after or meta.get("after") or DEFAULT_AFTER
    if b == a:
        raise ConfigError("before and after suffixes must differ")
    return str(b), str(a)


def read_triggers(session: Session) -> list[tuple[int, int]]:
    """``(frame_idx, t_trigger_ns)`` rows of ``raw/triggers.csv``, sorted by frame_idx."""
    path = session.path("raw", "triggers.csv")
    if not path.is_file():
        raise ConfigError(f"missing {path}")
    rows: list[tuple[int, int]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            try:
                rows.append((int(row["frame_idx"]), int(row["t_trigger_ns"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise ConfigError(f"{path}:{lineno}: bad trigger row ({exc!r})") from exc
    rows.sort()
    idxs = [i for i, _ in rows]
    if len(set(idxs)) != len(idxs):
        raise ConfigError(f"{path}: duplicate frame_idx values")
    return rows


def _pose_columns(session: Session, override: Mapping[str, str] | None) -> dict[str, str]:
    cols = dict(POSE_COLUMNS)
    cols.update(session.meta.get("pose_columns") or {})
    cols.update(override or {})
    unknown = set(cols) - set(POSE_COLUMNS)
    if unknown:
        raise ConfigError(f"unknown pose column keys: {sorted(unknown)}")
    return cols


def read_pose_rows(
    session: Session, columns: Mapping[str, str] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    """Read ``raw/poses.csv``.

    Returns ``(rows, raw_rows, header)``: rows with canonical numeric keys (plus ``cam_*``),
    the untouched CSV rows and the CSV header. Rows that cannot be parsed are skipped.
    """
    cols = _pose_columns(session, columns)
    path = session.path("raw", "poses.csv")
    if not path.is_file():
        raise ConfigError(f"missing {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        missing = [c for c in cols.values() if c not in header]
        if missing:
            raise ConfigError(f"{path}: missing columns {missing} (header: {header})")
        raw_rows = list(reader)
    rows: list[dict[str, Any]] = []
    kept_raw: list[dict[str, str]] = []
    for raw in raw_rows:
        try:
            row: dict[str, Any] = {k: float(raw[c]) for k, c in cols.items()}
        except (TypeError, ValueError):
            continue
        row["t_host_ns"] = round(row["t_host_ns"])
        for name in header:
            if name.startswith("cam_"):
                with contextlib.suppress(TypeError, ValueError):
                    row[name] = float(raw[name])
        rows.append(row)
        kept_raw.append(raw)
    return rows, kept_raw, header


def pair_screenshots(
    session: Session, before_suffix: str, after_suffix: str
) -> tuple[list[ShotPair], list[str]]:
    """Pair ``raw/reshade`` PNGs by stem; returns ``(pairs, unpaired file names)``."""
    folder = session.path("raw", "reshade")
    if not folder.is_dir():
        raise ConfigError(f"missing {folder}")
    before: dict[str, Path] = {}
    after: dict[str, Path] = {}
    other: list[str] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() != _SCREENSHOT_EXT:
            continue
        stem = path.stem
        if stem.endswith(before_suffix):
            before[stem[: -len(before_suffix)]] = path
        elif stem.endswith(after_suffix):
            after[stem[: -len(after_suffix)]] = path
        else:
            other.append(path.name)
    unpaired = other + [p.name for k, p in before.items() if k not in after]
    unpaired += [p.name for k, p in after.items() if k not in before]
    pairs = [ShotPair(k, before[k], after[k]) for k in before if k in after]
    pairs.sort(key=lambda p: (p.stem, p.before.stat().st_mtime_ns))
    return pairs, sorted(unpaired)


def _gap_report(pairs: Sequence[ShotPair]) -> list[str]:
    """Positions where the screenshot mtime step is over 1.5x the median step."""
    if len(pairs) < 3:
        return []
    m = np.array([p.before.stat().st_mtime_ns for p in pairs], dtype=np.float64)
    steps = np.diff(m)
    med = float(np.median(steps))
    if med <= 0:
        return []
    return [
        f"pair {i} -> {i + 1} ({pairs[i].stem} -> {pairs[i + 1].stem}): step {s / med:.1f}x median"
        for i, s in enumerate(steps)
        if s > 1.5 * med
    ]


def match_frames(
    triggers: Sequence[tuple[int, int]], pairs: Sequence[ShotPair], drop: Iterable[int] = ()
) -> list[tuple[int, int, ShotPair]]:
    """Match screenshot pairs to triggers in order after removing ``drop`` trigger indices.

    Raises ``ConfigError`` listing the counts, unmatched indices and mtime gaps on mismatch.
    """
    dropped = set(drop)
    unknown = dropped - {i for i, _ in triggers}
    if unknown:
        raise ConfigError(f"--drop names frame indices not in triggers.csv: {sorted(unknown)}")
    kept = [(i, t) for i, t in triggers if i not in dropped]
    if len(kept) != len(pairs):
        lines = [
            f"{len(pairs)} screenshot pairs but {len(kept)} triggers"
            f" ({len(triggers)} in triggers.csv, {len(dropped)} dropped)."
        ]
        gaps = _gap_report(pairs)
        if gaps:
            lines.append("possible gaps in the screenshot sequence: " + "; ".join(gaps))
        if len(pairs) < len(kept):
            lines.append(
                f"{len(kept) - len(pairs)} trigger(s) have no screenshot; pass --drop with their"
                f" frame indices (trigger indices run {kept[0][0]}..{kept[-1][0]})."
            )
        else:
            lines.append("more screenshots than triggers; remove the extra files from raw/reshade.")
        raise ConfigError(" ".join(lines))
    return [(i, t, p) for (i, t), p in zip(kept, pairs, strict=True)]


def time_offset_ms(session: Session) -> float:
    """``calib/time_offset.json`` ``offset_ms`` or 0."""
    path = session.path("calib", "time_offset.json")
    if not path.is_file():
        return 0.0
    try:
        return float(json.loads(path.read_text(encoding="utf-8"))["offset_ms"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc


def parse_drop(text: str) -> tuple[int, ...]:
    """``"3,7"`` to ``(3, 7)``."""
    if not re.fullmatch(r"\s*\d+(\s*,\s*\d+)*\s*", text):
        raise ConfigError(f"--drop expects comma-separated frame indices, got {text!r}")
    return tuple(int(p) for p in text.split(","))


def ingest(
    session: Session,
    max_gap_ms: float = DEFAULT_MAX_GAP_MS,
    drop: Iterable[int] = (),
    before_suffix: str | None = None,
    after_suffix: str | None = None,
    offset_ms: float | None = None,
    columns: Mapping[str, str] | None = None,
) -> int:
    """Write ``frames/`` and ``frames.jsonl`` from ``raw/``; returns the frame count.

    ``offset_ms`` defaults to ``calib/time_offset.json`` (else 0); frame time is
    ``t_trigger + offset``. Poses are canonical (conventions from ``session.json``
    ``simvar_conventions`` applied) and ``null`` when no sample lies within ``max_gap_ms``.
    """
    b_suf, a_suf = suffixes(session, before_suffix, after_suffix)
    triggers = read_triggers(session)
    pairs, unpaired = pair_screenshots(session, b_suf, a_suf)
    if unpaired:
        log.warning("unpaired files in raw/reshade: %s", unpaired)
    matched = match_frames(triggers, pairs, drop)
    offset = time_offset_ms(session) if offset_ms is None else float(offset_ms)

    pose_rows, _, _ = read_pose_rows(session, columns)
    t_ns = np.array([round(t + offset * 1e6) for _, t, _ in matched], dtype=np.int64)
    conventions = session.meta.get("simvar_conventions") or {}
    posed = interpolate_poses_with_gap(pose_rows, t_ns, max_gap_ms, conventions)

    frames_dir = session.path("frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    missing_pose = 0
    for (idx, _, pair), t, (pose, gap) in zip(matched, t_ns, posed, strict=True):
        color = read_image(pair.before)
        if color.ndim != 3 or color.dtype != np.uint8:
            raise ConfigError(f"{pair.before}: expected an 8-bit colour PNG")
        depth = read_depth_png(pair.after)
        if depth.shape != color.shape[:2]:
            raise ConfigError(
                f"{pair.after}: depth is {depth.shape[1]}x{depth.shape[0]} but colour is"
                f" {color.shape[1]}x{color.shape[0]} (VERIFY: depth vs back-buffer size)"
            )
        stem = f"{idx:06d}"
        write_image(frames_dir / f"{stem}.color.png", color[..., :3])
        np.save(frames_dir / f"{stem}.depthraw.npy", depth.astype(np.float32))
        if pose is None:
            missing_pose += 1
        lines.append(
            json.dumps(
                {
                    "idx": idx,
                    "t_ns": int(t),
                    "color": f"frames/{stem}.color.png",
                    "depthraw": f"frames/{stem}.depthraw.npy",
                    "depth": None,
                    "pose": pose,
                    "pose_gap_ms": None if gap is None else round(gap, 3),
                },
                sort_keys=True,
            )
        )
    session.path(FRAMES_JSONL).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    log.info(
        "ingested %d frames (%d without pose), offset %.3f ms", len(lines), missing_pose, offset
    )
    return len(lines)
