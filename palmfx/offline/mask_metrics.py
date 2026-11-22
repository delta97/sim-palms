"""Mask comparison metrics (plan 08, A9): pixel IoU and instance precision and recall.

``a`` is the method under test (the prediction) and ``b`` the reference (usually ``hand``).

Definitions, from ``plans/detailed/08-image-layer-experiment.md#a9-mask-comparison``:

- Pixel IoU per frame: ``|A & B| / |A | B|`` on the union masks, after a static occluder is removed
  from both. Empty union and empty reference count as 1.0 and are also counted in
  ``empty_empty_frames``. An empty prediction against a non-empty reference gives 0.0.
- Instance matching: label 0 is background. Instances are the non-zero label values. Candidate
  pairs are sorted by IoU, highest first, then by prediction label, then by reference label (so
  ties are deterministic). A pair is accepted when IoU >= ``iou_thr`` and IoU > 0, and both
  instances are still unmatched (one-to-one).
- ``precision = TP / (TP + FP)`` and ``recall = TP / (TP + FN)``. Both are ``None`` (null in JSON)
  when the denominator is 0. Summary values pool the counts over all compared frames.
- ``matched_iou_median`` is the median IoU over all matched pairs in all compared frames.

Frames present in only one method are skipped and counted, not compared.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from palmcore.errors import ConfigError
from palmfx.offline.session import read_mask

DEFAULT_IOU_THR = 0.3

_FRAME_FILE = re.compile(r"^(\d{6})\.png$")


@dataclass(frozen=True)
class MatchResult:
    """Outcome of one-to-one instance matching in one frame.

    ``pairs`` holds ``(pred_label, ref_label)`` in the order they were accepted (highest IoU
    first). ``matched_ious`` is parallel to ``pairs``.
    """

    tp: int
    fp: int
    fn: int
    pairs: tuple[tuple[int, int], ...]
    matched_ious: tuple[float, ...]


def iou(a: NDArray[Any], b: NDArray[Any]) -> float:
    """Pixel IoU of two masks (any non-zero value is foreground). Empty union gives 1.0."""
    if a.shape != b.shape:
        raise ConfigError(f"mask shapes differ: {a.shape} vs {b.shape}")
    fa = np.asarray(a) > 0
    fb = np.asarray(b) > 0
    union = int(np.count_nonzero(fa | fb))
    if union == 0:
        return 1.0
    return float(np.count_nonzero(fa & fb)) / float(union)


def _check_labels(pred: NDArray[Any], ref: NDArray[Any]) -> None:
    if pred.ndim != 2 or ref.ndim != 2:
        raise ConfigError("label images must be 2-D")
    if pred.shape != ref.shape:
        raise ConfigError(f"label image shapes differ: {pred.shape} vs {ref.shape}")


def _instance_index(
    pred: NDArray[Any], ref: NDArray[Any]
) -> tuple[NDArray[Any], NDArray[Any], NDArray[np.float64]]:
    """Sorted instance ids of each side and the (P, R) IoU matrix between them."""
    _check_labels(pred, ref)
    p_ids = np.unique(pred[pred > 0])
    r_ids = np.unique(ref[ref > 0])
    n_p, n_r = len(p_ids), len(r_ids)
    out = np.zeros((n_p, n_r), dtype=np.float64)
    if n_p == 0 or n_r == 0:
        return p_ids, r_ids, out
    pm = pred > 0
    rm = ref > 0
    p_area = np.bincount(np.searchsorted(p_ids, pred[pm]), minlength=n_p)
    r_area = np.bincount(np.searchsorted(r_ids, ref[rm]), minlength=n_r)
    both = pm & rm
    pi = np.searchsorted(p_ids, pred[both])
    ri = np.searchsorted(r_ids, ref[both])
    inter = np.bincount(pi * n_r + ri, minlength=n_p * n_r).reshape(n_p, n_r)
    union = p_area[:, None] + r_area[None, :] - inter
    out = inter / union
    return p_ids, r_ids, out


def instance_ious(pred: NDArray[Any], ref: NDArray[Any]) -> NDArray[np.float64]:
    """IoU of every predicted instance (rows, ascending label) with every reference instance
    (columns, ascending label). Label 0 is background and is never an instance."""
    return _instance_index(pred, ref)[2]


def match_instances(
    pred: NDArray[Any], ref: NDArray[Any], iou_thr: float = DEFAULT_IOU_THR
) -> MatchResult:
    """Greedy one-to-one matching of instances at IoU >= ``iou_thr`` (see module docstring)."""
    if not 0.0 < iou_thr <= 1.0:
        raise ConfigError(f"iou_thr must be in (0, 1], got {iou_thr}")
    p_ids, r_ids, mat = _instance_index(pred, ref)
    candidates = [
        (float(mat[i, j]), int(p_ids[i]), int(r_ids[j]), i, j)
        for i, j in np.argwhere((mat >= iou_thr) & (mat > 0)).tolist()
    ]
    # Highest IoU first; ties go to the lower prediction label, then the lower reference label.
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    used_p: set[int] = set()
    used_r: set[int] = set()
    pairs: list[tuple[int, int]] = []
    ious: list[float] = []
    for value, p_label, r_label, i, j in candidates:
        if i in used_p or j in used_r:
            continue
        used_p.add(i)
        used_r.add(j)
        pairs.append((p_label, r_label))
        ious.append(value)
    tp = len(pairs)
    return MatchResult(
        tp=tp,
        fp=len(p_ids) - tp,
        fn=len(r_ids) - tp,
        pairs=tuple(pairs),
        matched_ious=tuple(ious),
    )


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def _median(values: list[float]) -> float | None:
    return None if not values else float(np.median(np.asarray(values, dtype=np.float64)))


def list_frames(mask_dir: Path) -> dict[int, Path]:
    """Frame index to union-mask path for a method directory (``NNNNNN.png`` only)."""
    mask_dir = Path(mask_dir)
    if not mask_dir.is_dir():
        raise ConfigError(f"mask method directory not found: {mask_dir}")
    frames: dict[int, Path] = {}
    for path in sorted(mask_dir.iterdir()):
        match = _FRAME_FILE.match(path.name)
        if match and path.is_file():
            frames[int(match.group(1))] = path
    return frames


def _frame_result(
    idx: int,
    a_union: NDArray[np.uint8],
    b_union: NDArray[np.uint8],
    a_labels: NDArray[np.uint16],
    b_labels: NDArray[np.uint16],
    occluder: NDArray[np.bool_] | None,
    iou_thr: float,
) -> dict[str, Any]:
    keep = np.ones(a_union.shape, dtype=bool) if occluder is None else ~occluder
    a_fg = (a_union > 0) & keep
    b_fg = (b_union > 0) & keep
    # Instances are the labels restricted to the (occluder-free) union.
    a_lab = np.where(a_fg, a_labels, 0).astype(np.uint16)
    b_lab = np.where(b_fg, b_labels, 0).astype(np.uint16)
    match = match_instances(a_lab, b_lab, iou_thr)
    empty_empty = not bool(a_fg.any()) and not bool(b_fg.any())
    return {
        "idx": idx,
        "pixel_iou": iou(a_fg, b_fg),
        "empty_empty": empty_empty,
        "tp": match.tp,
        "fp": match.fp,
        "fn": match.fn,
        "precision": _ratio(match.tp, match.tp + match.fp),
        "recall": _ratio(match.tp, match.tp + match.fn),
        "matched_ious": list(match.matched_ious),
    }


def compare_dirs(
    dir_a: Path,
    dir_b: Path,
    occluder: NDArray[Any] | None = None,
    iou_thr: float = DEFAULT_IOU_THR,
) -> dict[str, Any]:
    """Compare two mask method directories frame by frame and summarise.

    ``dir_a`` is the prediction and ``dir_b`` the reference. ``occluder`` is an optional 2-D mask
    where non-zero means static occluder: those pixels are removed from both masks first.
    Returns ``{"iou_thr", "frames": [...], "skipped_frames": [...], "summary": {...}}``.
    """
    if not 0.0 < iou_thr <= 1.0:
        raise ConfigError(f"iou_thr must be in (0, 1], got {iou_thr}")
    frames_a = list_frames(Path(dir_a))
    frames_b = list_frames(Path(dir_b))
    common = sorted(set(frames_a) & set(frames_b))
    skipped = sorted(set(frames_a) ^ set(frames_b))
    occ_mask: NDArray[np.bool_] | None = None
    if occluder is not None:
        occ = np.asarray(occluder)
        if occ.ndim != 2:
            raise ConfigError("occluder must be a 2-D mask")
        occ_mask = occ > 0

    rows: list[dict[str, Any]] = []
    for idx in common:
        a = read_mask(Path(dir_a), idx)
        b = read_mask(Path(dir_b), idx)
        if a.union.shape != b.union.shape:
            raise ConfigError(
                f"frame {idx}: mask shapes differ: {a.union.shape} vs {b.union.shape}"
            )
        if occ_mask is not None and occ_mask.shape != a.union.shape:
            raise ConfigError(
                f"frame {idx}: occluder shape {occ_mask.shape} does not match {a.union.shape}"
            )
        rows.append(_frame_result(idx, a.union, b.union, a.labels, b.labels, occ_mask, iou_thr))

    return {
        "iou_thr": float(iou_thr),
        "frames": rows,
        "skipped_frames": skipped,
        "summary": _summary(rows, len(skipped), iou_thr),
    }


def _summary(rows: list[dict[str, Any]], skipped: int, iou_thr: float) -> dict[str, Any]:
    pixel = [float(r["pixel_iou"]) for r in rows]
    tp = sum(int(r["tp"]) for r in rows)
    fp = sum(int(r["fp"]) for r in rows)
    fn = sum(int(r["fn"]) for r in rows)
    matched: list[float] = [v for r in rows for v in r["matched_ious"]]
    return {
        "pixel_iou_mean": float(np.mean(pixel)) if pixel else None,
        "pixel_iou_median": _median(pixel),
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "matched_iou_median": _median(matched),
        "frames_compared": len(rows),
        "frames_skipped": skipped,
        "empty_empty_frames": sum(1 for r in rows if r["empty_empty"]),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "iou_thr": float(iou_thr),
    }


def summary_lines(summary: Mapping[str, Any]) -> list[str]:
    """Four summary lines for the console (the command adds a fifth line with the output path)."""

    def fmt(v: Any) -> str:
        return "n/a" if v is None else f"{float(v):.3f}"

    return [
        f"pixel IoU   mean {fmt(summary['pixel_iou_mean'])}  "
        f"median {fmt(summary['pixel_iou_median'])}  "
        f"empty-empty {summary['empty_empty_frames']}",
        f"instances   precision {fmt(summary['precision'])}  recall {fmt(summary['recall'])}  "
        f"(TP {summary['tp']}, FP {summary['fp']}, FN {summary['fn']})",
        f"matched IoU median {fmt(summary['matched_iou_median'])}  "
        f"(iou_thr {float(summary['iou_thr']):.2f})",
        f"frames      compared {summary['frames_compared']}  skipped {summary['frames_skipped']}",
    ]
