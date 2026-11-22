"""Image-diff scores for two in-sim visual runs (TEST-008).

Plan: plans/detailed/06-testing.md#image-diff-scoring.

    python -m tests.visual.diff_score tests/visual/T1/2026-11-22_a tests/visual/T1/2026-11-22_b
    python -m tests.visual.diff_score RUN_A RUN_B --variant static --write
    python -m tests.visual.diff_score RUN_A RUN_B --variant nofix --variant-b static

For each viewpoint (VP1, VP2, VP3) the two JPEGs of the chosen variants are loaded, the larger
one is resized to the smaller size (Lanczos), both are converted to greyscale, and an optional
mask ``tests/visual/<site>/mask_<VP>.png`` limits the comparison (white = compare, black = ignore).
Scores:

  - ssim: mean of the full SSIM map (skimage ``structural_similarity``, ``data_range=255``)
    over the compared pixels;
  - mad: mean |a - b| / 255 over the compared pixels.

A viewpoint is flagged when ``ssim < ssim_min`` or ``mad > mad_max`` (``diff_thresholds.yaml``,
or ``--thresholds``). Flags are for a person to look at. They never pass or fail a phase.

With ``--write`` the run_b folder gets ``diff/<VP>_heatmap.png`` (absolute greyscale difference,
masked-out pixels 0) and ``diff/scores.json``.

Needs numpy and Pillow (the ``dev`` extra) and scikit-image (``dev``, also the ``lidar`` extra).
They are imported only when a comparison runs, so ``--help`` works without them.

Exit codes: 0 no flags, 1 at least one viewpoint flagged, 2 bad input (missing run, variant or
image, mismatched sites, bad thresholds, missing dependency).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from palmcore.errors import EXIT_OK, EXIT_UNEXPECTED, ConfigError, PalmfixError
from palmcore.log import get_logger
from tests.helpers.fixtures import REPO_ROOT
from tests.visual.new_run import VARIANTS, VIEWPOINT_FILES, VisualRunError, load_run

logger = get_logger(__name__)

THRESHOLDS_FILE: Final = REPO_ROOT / "tests" / "visual" / "diff_thresholds.yaml"
DIFF_DIR: Final = "diff"
SCORES_JSON: Final = "scores.json"
MASK_NAME: Final = "mask_{vp}.png"
# Greyscale mask pixels at or above this value count as "compare".
MASK_THRESHOLD: Final = 128
# structural_similarity uses a 7 x 7 window by default.
MIN_SSIM_SIDE: Final = 7
DEFAULT_VARIANT: Final = "static"
REQUIRED_THRESHOLD_KEYS: Final = ("ssim_min", "mad_max", "calibrated", "noise_floor")


@dataclass(frozen=True)
class Thresholds:
    ssim_min: float
    mad_max: float
    calibrated: bool
    noise_floor: Any
    source: Path


@dataclass(frozen=True)
class ViewpointScore:
    vp: str
    ssim: float
    mad: float
    flagged: bool
    compared_size: tuple[int, int]
    masked: bool
    heatmap: Any  # numpy uint8 array; written as PNG, not part of scores.json


# --- thresholds ------------------------------------------------------------------------------


def _number(value: Any, key: str, path: Path) -> float:
    # bool is an int subclass in Python; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path}: {key} must be a number, got {value!r}")
    return float(value)


def load_thresholds(path: Path) -> Thresholds:
    """Read and check a thresholds YAML. Raises ConfigError if missing or malformed."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path}: thresholds file not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path}: cannot read: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    missing = [key for key in REQUIRED_THRESHOLD_KEYS if key not in data]
    if missing:
        raise ConfigError(f"{path}: missing keys: {', '.join(missing)}")
    ssim_min = _number(data["ssim_min"], "ssim_min", path)
    mad_max = _number(data["mad_max"], "mad_max", path)
    if not 0.0 <= ssim_min <= 1.0:
        raise ConfigError(f"{path}: ssim_min must be between 0 and 1")
    if mad_max < 0.0:
        raise ConfigError(f"{path}: mad_max must be 0 or more")
    calibrated = data["calibrated"]
    if not isinstance(calibrated, bool):
        raise ConfigError(f"{path}: calibrated must be true or false")
    return Thresholds(ssim_min, mad_max, calibrated, data["noise_floor"], path)


# --- dependencies and images -----------------------------------------------------------------


def _load_deps() -> tuple[Any, Any, Any]:
    """Import numpy, Pillow and scikit-image lazily, with one clear message if one is missing."""
    try:
        import numpy as np
        from PIL import Image
        from skimage.metrics import structural_similarity
    except ImportError as exc:
        raise ConfigError(
            "image-diff needs numpy, Pillow and scikit-image; install the dev extra with "
            '`.venv/Scripts/python -m pip install -e ".[dev]"` '
            f"(missing: {exc.name})"
        ) from exc
    return np, Image, structural_similarity


def _open_grey(image_mod: Any, path: Path) -> Any:
    try:
        with image_mod.open(path) as img:
            return img.convert("L")
    except OSError as exc:
        raise VisualRunError(f"{path}: cannot read image: {exc}") from exc


def _score_viewpoint(
    deps: tuple[Any, Any, Any],
    vp: str,
    img_a: Any,
    img_b: Any,
    mask_img: Any | None,
    thresholds: Thresholds,
) -> ViewpointScore:
    np, image_mod, structural_similarity = deps
    resample = image_mod.Resampling.LANCZOS
    # Resize the larger image to the smaller size (compared by area).
    target = img_a.size
    if img_b.size[0] * img_b.size[1] < img_a.size[0] * img_a.size[1]:
        target = img_b.size
    if min(target) < MIN_SSIM_SIDE:
        raise VisualRunError(f"{vp}: image {target[0]}x{target[1]} is too small to score")
    if img_a.size != target:
        img_a = img_a.resize(target, resample)
    if img_b.size != target:
        img_b = img_b.resize(target, resample)
    a = np.asarray(img_a, dtype=np.float64)
    b = np.asarray(img_b, dtype=np.float64)

    if mask_img is None:
        compare = np.ones(a.shape, dtype=bool)
    else:
        resized = mask_img.resize(target, image_mod.Resampling.NEAREST)
        compare = np.asarray(resized) >= MASK_THRESHOLD
        if not compare.any():
            raise VisualRunError(f"{vp}: mask excludes every pixel")

    _, ssim_map = structural_similarity(a, b, data_range=255, full=True)
    diff = np.abs(a - b)
    ssim = float(ssim_map[compare].mean())
    mad = float(diff[compare].mean() / 255.0)
    flagged = ssim < thresholds.ssim_min or mad > thresholds.mad_max
    heatmap = np.where(compare, diff, 0.0).clip(0, 255).astype(np.uint8)
    return ViewpointScore(
        vp=vp,
        ssim=ssim,
        mad=mad,
        flagged=flagged,
        compared_size=(int(target[0]), int(target[1])),
        masked=mask_img is not None,
        heatmap=heatmap,
    )


# --- runs ------------------------------------------------------------------------------------


def _run_label(run_dir: Path) -> str:
    return f"{run_dir.parent.name}/{run_dir.name}"


def _check_variant(run_dir: Path, variant: str) -> None:
    if variant not in VARIANTS:
        raise ConfigError(f"variant must be one of {', '.join(VARIANTS)}, got {variant!r}")
    if not (run_dir / variant).is_dir():
        raise VisualRunError(f"{run_dir}: no {variant}/ folder")


def compare_runs(
    run_a: Path,
    run_b: Path,
    *,
    variant_a: str,
    variant_b: str,
    thresholds: Thresholds,
) -> tuple[str, list[ViewpointScore]]:
    """Score every viewpoint. Returns ``(site, scores)``. Raises VisualRunError on bad input."""
    for run_dir in (run_a, run_b):
        if not run_dir.is_dir():
            raise VisualRunError(f"{run_dir}: run folder not found")
    site_a = load_run(run_a).get("site")
    site_b = load_run(run_b).get("site")
    if site_a != site_b:
        raise VisualRunError(f"runs are from different sites: {site_a!r} and {site_b!r}")
    _check_variant(run_a, variant_a)
    _check_variant(run_b, variant_b)
    missing = [
        str(path) for path in (run_a / variant_a / n for n in VIEWPOINT_FILES) if not path.is_file()
    ] + [
        str(path) for path in (run_b / variant_b / n for n in VIEWPOINT_FILES) if not path.is_file()
    ]
    if missing:
        raise VisualRunError("missing image(s): " + ", ".join(missing))

    deps = _load_deps()
    image_mod = deps[1]
    site_dir = run_a.parent
    scores: list[ViewpointScore] = []
    for name in VIEWPOINT_FILES:
        vp = name.split("_", 1)[0]
        mask_path = site_dir / MASK_NAME.format(vp=vp)
        mask_img = _open_grey(image_mod, mask_path) if mask_path.is_file() else None
        scores.append(
            _score_viewpoint(
                deps,
                vp,
                _open_grey(image_mod, run_a / variant_a / name),
                _open_grey(image_mod, run_b / variant_b / name),
                mask_img,
                thresholds,
            )
        )
    return str(site_a), scores


def write_outputs(
    run_b: Path,
    *,
    site: str,
    run_a: Path,
    variant_a: str,
    variant_b: str,
    thresholds: Thresholds,
    scores: Sequence[ViewpointScore],
) -> Path:
    """Write heatmaps and scores.json under run_b/diff/. Returns the diff folder."""
    image_mod = _load_deps()[1]
    diff_dir = run_b / DIFF_DIR
    diff_dir.mkdir(exist_ok=True)
    for score in scores:
        image_mod.fromarray(score.heatmap, mode="L").save(diff_dir / f"{score.vp}_heatmap.png")
    document = {
        "site": site,
        "run_a": _run_label(run_a),
        "run_b": _run_label(run_b),
        "variant_a": variant_a,
        "variant_b": variant_b,
        "thresholds": {
            "ssim_min": thresholds.ssim_min,
            "mad_max": thresholds.mad_max,
            "calibrated": thresholds.calibrated,
            "source": thresholds.source.name,
        },
        "viewpoints": {
            s.vp: {
                "ssim": round(s.ssim, 6),
                "mad": round(s.mad, 6),
                "flagged": s.flagged,
                "compared_size": list(s.compared_size),
                "masked": s.masked,
            }
            for s in scores
        },
        "flagged": any(s.flagged for s in scores),
    }
    (diff_dir / SCORES_JSON).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return diff_dir


def format_table(scores: Sequence[ViewpointScore], thresholds: Thresholds) -> str:
    provisional = "" if thresholds.calibrated else " (provisional: not calibrated)"
    lines = [
        f"thresholds: ssim_min={thresholds.ssim_min:.3f} mad_max={thresholds.mad_max:.3f}"
        f"{provisional}",
        f"{'VP':<5}{'ssim':>9}{'mad':>9}  {'size':<11}{'mask':<6}flag",
    ]
    for s in scores:
        size = f"{s.compared_size[0]}x{s.compared_size[1]}"
        flag = "FLAGGED" if s.flagged else "-"
        lines.append(
            f"{s.vp:<5}{s.ssim:>9.4f}{s.mad:>9.4f}  {size:<11}"
            f"{'yes' if s.masked else 'no':<6}{flag}"
        )
    return "\n".join(lines)


# --- CLI -------------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.visual.diff_score",
        description=(
            "Score each viewpoint (VP1, VP2, VP3) of two visual runs with SSIM and mean absolute "
            "difference, and flag changes for a person to look at. Never a pass or fail."
        ),
    )
    parser.add_argument("run_a", type=Path, metavar="RUN_A", help="first run folder")
    parser.add_argument("run_b", type=Path, metavar="RUN_B", help="second run folder")
    parser.add_argument(
        "--variant",
        default=DEFAULT_VARIANT,
        metavar="V",
        help=f"variant folder of RUN_A, and of RUN_B unless --variant-b is given "
        f"(one of {', '.join(VARIANTS)}; default {DEFAULT_VARIANT})",
    )
    parser.add_argument(
        "--variant-b",
        default=None,
        metavar="V",
        help="variant folder of RUN_B (default: same as --variant)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write RUN_B/diff/<VP>_heatmap.png and RUN_B/diff/scores.json",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=THRESHOLDS_FILE,
        metavar="PATH",
        help="thresholds YAML (default: tests/visual/diff_thresholds.yaml)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    run_a: Path = args.run_a
    run_b: Path = args.run_b
    variant_a: str = args.variant
    variant_b: str = args.variant_b or variant_a
    try:
        thresholds = load_thresholds(args.thresholds)
        site, scores = compare_runs(
            run_a, run_b, variant_a=variant_a, variant_b=variant_b, thresholds=thresholds
        )
        print(
            f"site {site}: {_run_label(run_a)} [{variant_a}] vs {_run_label(run_b)} [{variant_b}]"
        )
        print(format_table(scores, thresholds))
        if args.write:
            diff_dir = write_outputs(
                run_b,
                site=site,
                run_a=run_a,
                variant_a=variant_a,
                variant_b=variant_b,
                thresholds=thresholds,
                scores=scores,
            )
            print(f"wrote {_run_label(diff_dir.parent)}/{DIFF_DIR}/")
        flagged = [s.vp for s in scores if s.flagged]
        if flagged:
            print(f"flagged for review: {', '.join(flagged)}")
            return EXIT_UNEXPECTED
        return EXIT_OK
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
