"""``palmfx mask-project``: blob masks by projecting palms.geojson into every frame (plan 08, A7).

Writes ``masks/project-raw/`` and, when metric depth is available and ``--no-depth-test`` is not
given, ``masks/project-depth/``, plus ``metrics/mask-project-summary.json``.

Camera setup, in order of precedence: ``--vfov-deg``; ``calib/intrinsics.json`` ``vfov_deg``
(written by ``palmfx calib``, FX-009); the synthetic session's ``vfov_deg``; 60 degrees (the plan's
starting value, with a warning). The pose bias comes from ``calib/pose_bias.json`` when present.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.camera import CameraPose, Intrinsics, LocalFrame, pose_from_simvars
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.mask_project import (
    SKIP_REASONS,
    ProjectParams,
    fill_ground_elev,
    load_palms,
    palms_to_enu,
    project_masks,
)
from palmfx.offline.session import FrameRecord, Session, read_image, write_mask

log = get_logger(__name__)

DEFAULT_VFOV_DEG = 60.0


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "mask-project",
        help="blob masks by projecting palms.geojson into each frame",
        description=(
            "Project palms into every posed frame. Writes masks/project-raw and, with metric "
            "depth (frames/NNNNNN.depth.npy), masks/project-depth."
        ),
    )
    add_standard_args(parser)
    parser.add_argument("--palms", required=True, type=Path, metavar="GEOJSON")
    parser.add_argument(
        "--no-depth-test", action="store_true", help="write project-raw only, ignore depth"
    )
    parser.add_argument(
        "--params",
        default=None,
        metavar="JSON",
        help="ProjectParams overrides as inline JSON or a path to a JSON file",
    )
    parser.add_argument("--vfov-deg", type=float, default=None, metavar="DEG")
    parser.add_argument(
        "--ground-elev-m",
        type=float,
        default=None,
        metavar="M",
        help="ground elevation for palms without ground_elev_m when none has one",
    )
    parser.add_argument(
        "--lenient-palms",
        action="store_true",
        help="read palms as plain JSON and default missing height/crown (skips validation)",
    )
    parser.set_defaults(func=run)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError(f"{path} must hold a JSON object")
    return doc


def _parse_inline(text: str) -> dict[str, Any]:
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"--params is neither a file nor JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError("--params must be a JSON object")
    return doc


def _params(arg: str | None) -> ProjectParams:
    if arg is None:
        return ProjectParams()
    candidate = Path(arg)
    try:
        is_file = candidate.is_file()
    except OSError:
        is_file = False
    doc = _read_json(candidate) if is_file else _parse_inline(arg)
    return ProjectParams.from_mapping(doc)


def _intrinsics(session: Session, frames: list[FrameRecord], vfov: float) -> Intrinsics:
    res = session.meta.get("resolution")
    if isinstance(res, list) and len(res) == 2:
        width, height = int(res[0]), int(res[1])
    else:
        img = read_image(frames[0].color)
        height, width = int(img.shape[0]), int(img.shape[1])
    return Intrinsics.from_vfov(width, height, vfov)


def _camera_setup(session: Session, vfov_arg: float | None) -> tuple[float, dict[str, Any]]:
    # File names and keys follow the plan's session layout and what `palmfx calib` (FX-009)
    # writes: calib/intrinsics.json {"vfov_deg", ...} and calib/pose_bias.json
    # {"d_heading_deg", "d_pitch_deg", "d_bank_deg", "d_body_m"}.
    intr_path = session.path("calib", "intrinsics.json")
    intr = _read_json(intr_path) if intr_path.is_file() else {}
    bias_path = session.path("calib", "pose_bias.json")
    bias_doc = _read_json(bias_path) if bias_path.is_file() else {}
    vfov = vfov_arg
    if vfov is None and intr.get("vfov_deg") is not None:
        vfov = float(intr["vfov_deg"])
    if vfov is None:
        synth = session.meta.get("synthetic")
        if isinstance(synth, dict) and synth.get("vfov_deg") is not None:
            vfov = float(synth["vfov_deg"])
    if vfov is None:
        log.warning("no vfov found, using the plan's starting value %.0f deg", DEFAULT_VFOV_DEG)
        vfov = DEFAULT_VFOV_DEG
    return vfov, dict(bias_doc) if isinstance(bias_doc, dict) else {}


def _ground_estimate(frames: list[FrameRecord]) -> float | None:
    """Median of altitude minus AGL over frames whose pose records both. VERIFY: FX-006 columns."""
    vals = [
        float(f.pose["alt_msl_m"]) - float(f.pose["alt_agl_m"])
        for f in frames
        if f.pose and f.pose.get("alt_msl_m") is not None and f.pose.get("alt_agl_m") is not None
    ]
    return float(np.median(vals)) if vals else None


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    params = _params(args.params)
    frames = session.frames()
    if not frames:
        raise ConfigError("session has no frames; run `palmfx ingest` first")
    posed = [f for f in frames if f.pose is not None]
    if not posed:
        raise ConfigError("no frame has a pose")
    first = posed[0].pose
    assert first is not None

    vfov, bias = _camera_setup(session, args.vfov_deg)
    K = _intrinsics(session, frames, vfov)
    cam_offset = session.meta.get("cam_offset_body_m") or (0.0, 0.0, 0.0)
    local = LocalFrame(first["lat_deg"], first["lon_deg"], 0.0)

    ground = args.ground_elev_m if args.ground_elev_m is not None else _ground_estimate(posed)
    palms = palms_to_enu(
        fill_ground_elev(load_palms(args.palms, strict=not args.lenient_palms), ground), local
    )
    n_defaulted = sum(1 for p in palms if p["defaulted"])
    n_elev = sum(1 for p in palms if p["elev_estimated"])

    occ_path = session.path("calib", "static_occluder.png")
    occluder = read_image(occ_path) if occ_path.is_file() else None
    if occluder is not None and occluder.ndim != 2:
        raise ConfigError(f"{occ_path} must be a single-channel PNG")

    depth_wanted = not args.no_depth_test
    out_raw = session.path("masks", "project-raw")
    out_depth = session.path("masks", "project-depth")
    per_frame: list[dict[str, Any]] = []
    totals = dict.fromkeys(SKIP_REASONS, 0)
    depth_frames = 0
    no_pose = 0
    for rec in frames:
        if rec.pose is None:
            no_pose += 1
            continue
        pose: CameraPose = pose_from_simvars(rec.pose, local, cam_offset, None, bias)
        depth = None
        if depth_wanted and rec.depth is not None and rec.depth.is_file():
            depth = np.load(rec.depth)
        res = project_masks(palms, K, pose, depth, params, occluder)
        write_mask(out_raw, rec.idx, res.raw)
        if res.depth is not None:
            write_mask(out_depth, rec.idx, res.depth)
            depth_frames += 1
        for k, v in res.skipped.items():
            totals[k] += v
        per_frame.append(
            {
                "idx": rec.idx,
                "palms_in_view": res.in_view,
                "palms_in_view_depth": res.in_view_depth if res.depth is not None else None,
                "skipped": res.skipped,
            }
        )

    summary = {
        "session_id": session.meta.get("session_id", session.root.name),
        "palms": len(palms),
        "palms_defaulted": n_defaulted,
        "palms_elev_estimated": n_elev,
        "frames_written": len(per_frame),
        "frames_without_pose": no_pose,
        "frames_with_depth_masks": depth_frames,
        "vfov_deg": vfov,
        "params": params.__dict__,
        "skipped_total": totals,
        "frames": per_frame,
    }
    out = session.path("metrics", "mask-project-summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    log.info("wrote %s", out)

    print(f"project-raw: {len(per_frame)} frames, {len(palms)} palms ({n_defaulted} defaulted)")
    if depth_frames:
        print(f"project-depth: {depth_frames} frames")
    elif args.no_depth_test:
        print("project-depth: skipped (--no-depth-test)")
    else:
        print("project-depth: not written, no metric depth (frames/NNNNNN.depth.npy; palmfx calib)")
    print(f"wrote {out}")
    return 0
