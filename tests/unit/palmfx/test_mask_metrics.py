"""palmfx.offline.mask_metrics and the mask-compare command: hand-computed values on tiny masks.

Every expected number here is worked out by hand in the comment next to it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from palmcore.errors import ConfigError
from palmfx.offline import cli
from palmfx.offline.mask_metrics import (
    DEFAULT_IOU_THR,
    compare_dirs,
    instance_ious,
    iou,
    list_frames,
    match_instances,
)
from palmfx.offline.session import MaskSet, new_session, write_image, write_mask

Blob = tuple[int, int, int, int]  # (label, row, col_start, col_stop) with stop exclusive


def _img(shape: tuple[int, int], *blobs: Blob) -> np.ndarray:
    img = np.zeros(shape, dtype=np.uint16)
    for label, row, c0, c1 in blobs:
        img[row, c0:c1] = label
    return img


def _write(method_dir: Path, idx: int, labels: np.ndarray) -> None:
    union = np.where(labels > 0, 255, 0).astype(np.uint8)
    write_mask(method_dir, idx, MaskSet(union=union, labels=labels, method=method_dir.name))


def _method(root: Path, name: str, frames: dict[int, np.ndarray]) -> Path:
    method_dir = root / name
    for idx, labels in frames.items():
        _write(method_dir, idx, labels)
    return method_dir


# --- pixel IoU -------------------------------------------------------------------------------


def test_iou_identical_is_one() -> None:
    a = np.array([[255, 255, 0]], dtype=np.uint8)
    assert iou(a, a) == 1.0


def test_iou_disjoint_is_zero() -> None:
    a = np.array([[255, 0, 0]], dtype=np.uint8)
    b = np.array([[0, 0, 255]], dtype=np.uint8)
    assert iou(a, b) == 0.0


def test_iou_half_overlap_is_one_third() -> None:
    # A = {x1, x2}, B = {x2, x3}: intersection 1, union 3, so 1/3.
    a = np.array([[255, 255, 0, 0]], dtype=np.uint8)
    b = np.array([[0, 255, 255, 0]], dtype=np.uint8)
    assert iou(a, b) == pytest.approx(1.0 / 3.0, abs=0.0)


def test_iou_empty_empty_is_one_and_empty_vs_full_is_zero() -> None:
    empty = np.zeros((2, 2), dtype=np.uint8)
    full = np.full((2, 2), 255, dtype=np.uint8)
    assert iou(empty, empty) == 1.0
    assert iou(empty, full) == 0.0
    assert iou(full, empty) == 0.0


def test_iou_shape_mismatch_is_config_error() -> None:
    with pytest.raises(ConfigError, match="shapes differ"):
        iou(np.zeros((2, 2)), np.zeros((2, 3)))


# --- instance IoU matrix and label 0 as background --------------------------------------------


def test_instance_ious_rows_and_columns_in_ascending_label_order() -> None:
    # pred labels 3 (row 1, cols 0-1) and 9 (row 0, cols 0-1); ref label 5 (row 0, cols 0-3).
    pred = _img((2, 4), (9, 0, 0, 2), (3, 1, 0, 2))
    ref = _img((2, 4), (5, 0, 0, 4))
    mat = instance_ious(pred, ref)
    assert mat.shape == (2, 1)
    # label 3: no overlap -> 0. label 9: inter 2, union 2 + 4 - 2 = 4 -> 0.5.
    assert mat[0, 0] == 0.0
    assert mat[1, 0] == 0.5


def test_label_zero_is_background_not_an_instance() -> None:
    pred = np.zeros((2, 4), dtype=np.uint16)
    ref = _img((2, 4), (1, 0, 0, 2))
    assert instance_ious(pred, ref).shape == (0, 1)
    result = match_instances(pred, ref)
    assert (result.tp, result.fp, result.fn) == (0, 0, 1)
    assert result.pairs == ()


def test_background_pixels_never_match_a_reference_instance() -> None:
    # The prediction covers the reference only with label 0, so nothing is matched.
    pred = np.zeros((1, 4), dtype=np.uint16)
    ref = _img((1, 4), (1, 0, 0, 4))
    result = match_instances(pred, ref, iou_thr=0.01)
    assert (result.tp, result.fp, result.fn) == (0, 0, 1)


# --- instance matching -------------------------------------------------------------------------


def test_matching_is_one_to_one_two_preds_on_one_ref() -> None:
    # Ref 1 = row 0, cols 0-9 (10 px). Pred 1 = cols 5-9 and pred 2 = cols 0-4, disjoint.
    # Each has IoU 5/10 = 0.5 with the ref. Pred 1 takes the ref (tie, lower label);
    # pred 2 is a false positive. One TP, one FP, zero FN.
    ref = _img((1, 10), (1, 0, 0, 10))
    pred = _img((1, 10), (1, 0, 5, 10), (2, 0, 0, 5))
    result = match_instances(pred, ref)
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)
    assert result.pairs == ((1, 1),)
    assert result.matched_ious == (0.5,)


def test_threshold_is_inclusive_at_exactly_thr() -> None:
    # Ref = 10 px in row 0. Pred = 3 px inside it. Intersection 3, union 10: IoU 0.3 exactly.
    ref = _img((1, 10), (1, 0, 0, 10))
    pred = _img((1, 10), (1, 0, 0, 3))
    assert DEFAULT_IOU_THR == 0.3
    at = match_instances(pred, ref, iou_thr=0.3)
    assert (at.tp, at.fp, at.fn) == (1, 0, 0)
    assert at.matched_ious == (0.3,)
    above = match_instances(pred, ref, iou_thr=0.31)
    assert (above.tp, above.fp, above.fn) == (0, 1, 1)


def test_threshold_below_iou_does_not_match() -> None:
    # Pred 2 px inside a 10 px ref: IoU 0.2, below 0.3.
    ref = _img((1, 10), (1, 0, 0, 10))
    pred = _img((1, 10), (1, 0, 0, 2))
    result = match_instances(pred, ref)
    assert (result.tp, result.fp, result.fn) == (0, 1, 1)


def test_greedy_takes_highest_iou_before_lower_label() -> None:
    # Pred 1 = row 0, cols 0-5 (6 px). Ref 5 = cols 0-1 (IoU 2/6 = 1/3, above 0.3).
    # Ref 6 = cols 2-5 (IoU 4/6 = 2/3). The refs are disjoint. Greedy by IoU gives pred 1 -> ref 6,
    # even though ref 5 has the lower label. Ref 5 is left unmatched (FN).
    pred = _img((1, 6), (1, 0, 0, 6))
    ref = _img((1, 6), (5, 0, 0, 2), (6, 0, 2, 6))
    result = match_instances(pred, ref)
    assert result.pairs == ((1, 6),)
    assert result.matched_ious == pytest.approx((2.0 / 3.0,), abs=0.0)
    assert (result.tp, result.fp, result.fn) == (1, 0, 1)


def test_tie_on_iou_goes_to_lower_prediction_label() -> None:
    # Ref 1 = row 0, cols 0-3. Pred 7 = cols 0-1 and pred 3 = cols 2-3, both IoU 2/4 = 0.5.
    # The tie goes to the lower label (3), not to the leftmost blob.
    ref = _img((1, 4), (1, 0, 0, 4))
    pred = _img((1, 4), (7, 0, 0, 2), (3, 0, 2, 4))
    result = match_instances(pred, ref)
    assert result.pairs == ((3, 1),)
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)


def test_tie_on_iou_goes_to_lower_reference_label() -> None:
    # Pred 1 = cols 0-3. Refs 5 (cols 0-1) and 6 (cols 2-3): both IoU 0.5. Ref 5 wins.
    pred = _img((1, 4), (1, 0, 0, 4))
    ref = _img((1, 4), (6, 0, 2, 4), (5, 0, 0, 2))
    result = match_instances(pred, ref)
    assert result.pairs == ((1, 5),)
    assert (result.tp, result.fp, result.fn) == (1, 0, 1)


def test_match_result_counts_when_both_sides_empty() -> None:
    empty = np.zeros((2, 2), dtype=np.uint16)
    result = match_instances(empty, empty)
    assert (result.tp, result.fp, result.fn) == (0, 0, 0)
    assert result.pairs == ()
    assert result.matched_ious == ()


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.01])
def test_iou_threshold_must_be_in_unit_interval(bad: float) -> None:
    labels = _img((1, 2), (1, 0, 0, 2))
    with pytest.raises(ConfigError, match="iou_thr"):
        match_instances(labels, labels, iou_thr=bad)


def test_label_shape_mismatch_is_config_error() -> None:
    with pytest.raises(ConfigError, match="shapes differ"):
        instance_ious(np.zeros((2, 2), np.uint16), np.zeros((2, 3), np.uint16))


# --- compare_dirs: frames, edge cases and pooling --------------------------------------------


def test_identical_methods_score_one(tmp_path: Path) -> None:
    frame = _img((2, 4), (1, 0, 0, 2), (2, 1, 1, 4))
    a = _method(tmp_path, "a", {0: frame})
    b = _method(tmp_path, "b", {0: frame})
    summary = compare_dirs(a, b)["summary"]
    assert summary["pixel_iou_mean"] == 1.0
    assert summary["precision"] == 1.0
    assert summary["recall"] == 1.0
    assert summary["matched_iou_median"] == 1.0
    assert (summary["frames_compared"], summary["frames_skipped"]) == (1, 0)


def test_empty_prediction_and_empty_reference_frame(tmp_path: Path) -> None:
    empty = np.zeros((2, 2), dtype=np.uint16)
    a = _method(tmp_path, "a", {0: empty})
    b = _method(tmp_path, "b", {0: empty})
    result = compare_dirs(a, b)
    row = result["frames"][0]
    assert row["pixel_iou"] == 1.0
    assert row["empty_empty"] is True
    assert row["precision"] is None
    assert row["recall"] is None
    summary = result["summary"]
    assert summary["empty_empty_frames"] == 1
    assert summary["pixel_iou_mean"] == 1.0
    assert summary["precision"] is None
    assert summary["recall"] is None
    assert summary["matched_iou_median"] is None


def test_empty_prediction_against_reference_scores_zero_recall(tmp_path: Path) -> None:
    a = _method(tmp_path, "a", {0: np.zeros((2, 4), dtype=np.uint16)})
    b = _method(tmp_path, "b", {0: _img((2, 4), (1, 0, 0, 2), (2, 1, 0, 2))})
    row = compare_dirs(a, b)["frames"][0]
    assert row["pixel_iou"] == 0.0
    assert row["empty_empty"] is False
    assert row["precision"] is None  # TP + FP = 0
    assert row["recall"] == 0.0  # 0 / (0 + 2)
    assert (row["tp"], row["fp"], row["fn"]) == (0, 0, 2)


def test_empty_reference_against_prediction_scores_zero_precision(tmp_path: Path) -> None:
    a = _method(tmp_path, "a", {0: _img((2, 4), (1, 0, 0, 2))})
    b = _method(tmp_path, "b", {0: np.zeros((2, 4), dtype=np.uint16)})
    row = compare_dirs(a, b)["frames"][0]
    assert row["pixel_iou"] == 0.0
    assert row["precision"] == 0.0  # 0 / (0 + 1)
    assert row["recall"] is None  # TP + FN = 0


def test_static_occluder_removed_from_both_masks(tmp_path: Path) -> None:
    # Row 0 of width 6. A = cols 0-3, B = cols 2-5: IoU 2/6 = 1/3 without the occluder.
    # Occluder = cols 0-1: A becomes cols 2-3, B stays cols 2-5 (after removal, cols 2-5):
    # intersection 2, union 4, so 0.5.
    a = _method(tmp_path, "a", {0: _img((1, 6), (1, 0, 0, 4))})
    b = _method(tmp_path, "b", {0: _img((1, 6), (1, 0, 2, 6))})
    occluder = np.zeros((1, 6), dtype=np.uint8)
    occluder[0, 0:2] = 255
    assert compare_dirs(a, b)["frames"][0]["pixel_iou"] == pytest.approx(1.0 / 3.0)
    assert compare_dirs(a, b, occluder=occluder)["frames"][0]["pixel_iou"] == 0.5


def test_instance_entirely_under_occluder_is_not_counted(tmp_path: Path) -> None:
    # A has a blob (label 1) under the occluder and a blob (label 2) that matches B exactly.
    a = _method(tmp_path, "a", {0: _img((1, 6), (1, 0, 0, 2), (2, 0, 3, 5))})
    b = _method(tmp_path, "b", {0: _img((1, 6), (1, 0, 3, 5))})
    occluder = np.zeros((1, 6), dtype=np.uint8)
    occluder[0, 0:2] = 1
    row = compare_dirs(a, b, occluder=occluder)["frames"][0]
    assert (row["tp"], row["fp"], row["fn"]) == (1, 0, 0)


def test_occluder_shape_must_match(tmp_path: Path) -> None:
    a = _method(tmp_path, "a", {0: _img((1, 4), (1, 0, 0, 2))})
    b = _method(tmp_path, "b", {0: _img((1, 4), (1, 0, 0, 2))})
    with pytest.raises(ConfigError, match="occluder shape"):
        compare_dirs(a, b, occluder=np.zeros((2, 4), dtype=np.uint8))


def test_frames_in_only_one_method_are_skipped_and_counted(tmp_path: Path) -> None:
    frame = _img((1, 4), (1, 0, 0, 2))
    a = _method(tmp_path, "a", {0: frame, 1: frame, 2: frame})
    b = _method(tmp_path, "b", {1: frame, 2: frame, 3: frame})
    result = compare_dirs(a, b)
    assert [r["idx"] for r in result["frames"]] == [1, 2]
    assert result["skipped_frames"] == [0, 3]
    assert result["summary"]["frames_compared"] == 2
    assert result["summary"]["frames_skipped"] == 2


def test_summary_pools_counts_and_takes_median_of_matched_ious(tmp_path: Path) -> None:
    # Frame 0: pred {1: cols 0-1, 2: cols 2-3}, ref {1: cols 0-1}. TP 1 (IoU 1.0), FP 1.
    # Frame 1: pred {1: cols 0-1, 2: row 1}, ref {1: cols 0-3}. Pred 1 IoU 2/4 = 0.5 -> TP 1,
    #          pred 2 is FP. FN 0.
    # Pooled: TP 2, FP 2, FN 0. Precision 0.5, recall 1.0. Matched IoUs [1.0, 0.5] -> median 0.75.
    shape = (2, 4)
    a = _method(
        tmp_path,
        "a",
        {
            0: _img(shape, (1, 0, 0, 2), (2, 0, 2, 4)),
            1: _img(shape, (1, 0, 0, 2), (2, 1, 0, 2)),
        },
    )
    b = _method(
        tmp_path,
        "b",
        {
            0: _img(shape, (1, 0, 0, 2)),
            1: _img(shape, (1, 0, 0, 4)),
        },
    )
    summary = compare_dirs(a, b)["summary"]
    assert (summary["tp"], summary["fp"], summary["fn"]) == (2, 2, 0)
    assert summary["precision"] == 0.5
    assert summary["recall"] == 1.0
    assert summary["matched_iou_median"] == 0.75


def test_hand_mask_without_label_image_uses_eight_connected_instances(tmp_path: Path) -> None:
    # A hand mask has no .inst.png, so instances come from 8-connected components. The two
    # diagonal pixels in B form one instance (IoU with A's single pixel = 1/2 = 0.5).
    a_dir = tmp_path / "a"
    a_dir.mkdir()
    union_a = np.zeros((2, 2), dtype=np.uint8)
    union_a[0, 0] = 255
    write_image(a_dir / "000000.png", union_a)
    b_dir = tmp_path / "hand"
    b_dir.mkdir()
    union_b = np.zeros((2, 2), dtype=np.uint8)
    union_b[0, 0] = 255
    union_b[1, 1] = 255
    write_image(b_dir / "000000.png", union_b)
    row = compare_dirs(a_dir, b_dir)["frames"][0]
    assert (row["tp"], row["fp"], row["fn"]) == (1, 0, 0)
    assert row["pixel_iou"] == 0.5


def test_list_frames_ignores_label_images_and_sidecars(tmp_path: Path) -> None:
    frame = _img((1, 2), (1, 0, 0, 1))
    method = _method(tmp_path, "a", {4: frame})
    (method / "notes.txt").write_text("x", encoding="utf-8")
    assert sorted(list_frames(method)) == [4]


def test_missing_method_directory_is_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        compare_dirs(tmp_path / "nope", tmp_path)


def test_frame_shape_mismatch_is_config_error(tmp_path: Path) -> None:
    a = _method(tmp_path, "a", {0: _img((2, 2), (1, 0, 0, 1))})
    b = _method(tmp_path, "b", {0: _img((2, 3), (1, 0, 0, 1))})
    with pytest.raises(ConfigError, match="shapes differ"):
        compare_dirs(a, b)


# --- mask-compare command --------------------------------------------------------------------


def _session_with_methods(
    tmp_path: Path, pred: dict[int, np.ndarray], ref: dict[int, np.ndarray]
) -> Path:
    root = tmp_path / "20261205-T1-low-01"
    new_session(root, {"site": "T1"})
    _method(root / "masks", "pred", pred)
    _method(root / "masks", "hand", ref)
    return root


_SUMMARY_KEYS = {
    "pixel_iou_mean",
    "pixel_iou_median",
    "precision",
    "recall",
    "matched_iou_median",
    "frames_compared",
    "frames_skipped",
    "empty_empty_frames",
}


def test_mask_compare_writes_json_and_prints_five_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frame = _img((2, 4), (1, 0, 0, 2))
    root = _session_with_methods(tmp_path, {0: frame, 1: frame}, {0: frame})
    code = cli.main(
        ["mask-compare", "--session", str(root), "--a", "pred", "--b", "hand", "--no-log-file"]
    )
    assert code == 0
    out_path = root / "metrics" / "mask-pred-vs-hand.json"
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    assert set(doc["summary"]) >= _SUMMARY_KEYS
    assert doc["summary"]["frames_compared"] == 1
    assert doc["summary"]["frames_skipped"] == 1
    assert doc["iou_thr"] == DEFAULT_IOU_THR
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 5
    assert lines[-1].endswith("mask-pred-vs-hand.json")


def test_mask_compare_passes_iou_thr_and_occluder(tmp_path: Path) -> None:
    frame = _img((1, 4), (1, 0, 0, 3))
    root = _session_with_methods(tmp_path, {0: frame}, {0: frame})
    occ = np.zeros((1, 4), dtype=np.uint8)
    occ[0, 3] = 255
    occ_path = tmp_path / "occluder.png"
    write_image(occ_path, occ)
    code = cli.main(
        [
            "mask-compare",
            "--session",
            str(root),
            "--a",
            "pred",
            "--b",
            "hand",
            "--iou-thr",
            "0.5",
            "--occluder",
            str(occ_path),
            "--no-log-file",
        ]
    )
    assert code == 0
    doc = json.loads((root / "metrics" / "mask-pred-vs-hand.json").read_text(encoding="utf-8"))
    assert doc["iou_thr"] == 0.5
    assert doc["occluder"] == str(occ_path)


def test_mask_compare_with_no_common_frames_is_config_error(tmp_path: Path) -> None:
    frame = _img((1, 4), (1, 0, 0, 1))
    root = _session_with_methods(tmp_path, {0: frame}, {1: frame})
    code = cli.main(
        ["mask-compare", "--session", str(root), "--a", "pred", "--b", "hand", "--no-log-file"]
    )
    assert code == ConfigError.exit_code
    assert not (root / "metrics" / "mask-pred-vs-hand.json").exists()


def test_mask_compare_rejects_bad_method_name_and_threshold(tmp_path: Path) -> None:
    frame = _img((1, 4), (1, 0, 0, 1))
    root = _session_with_methods(tmp_path, {0: frame}, {0: frame})
    base = ["mask-compare", "--session", str(root), "--no-log-file"]
    assert cli.main([*base, "--a", "../pred", "--b", "hand"]) == 2
    assert cli.main([*base, "--a", "pred", "--b", "hand", "--iou-thr", "0"]) == 2
    assert cli.main([*base, "--a", "pred", "--b", "hand", "--iou-thr", "1.5"]) == 2
