"""Calibration from clicked correspondences (plan 08, A6).

Fits the vertical FOV, the trigger-to-frame time offset, a small attitude bias, a body-frame
camera offset bias and the depth model. Everything is deterministic: fixed start values,
bounded Huber least squares, a fixed offset grid.

Model. Frame ``i`` is shown at ``t_trigger_i + offset``. The pose there is interpolated from the
raw pose log (``timing.interpolate_poses``, canonical signs from ``session.json``), the bias is
applied through ``camera.pose_from_simvars`` and each clicked world point is projected with
``Intrinsics.from_vfov``. Residuals are projected minus clicked pixels.

Degeneracy. For a straight constant-velocity flight a time offset moves the camera exactly like a
forward ``d_body_m`` offset, so the two cannot be told apart from pixels alone. A weak prior pulls
``d_body_m`` to 0 (``BODY_PRIOR_PX_PER_M`` px per metre, Huber like the data) so the offset is
still picked; curved or accelerating flight (or an independent body offset) is what really
identifies both. VERIFY: with real captures (FX-013), check the fitted pair for this trade-off.

Heights are treated as MSL for poses and palms, as everywhere in ``palmfx``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.camera import Intrinsics, LocalFrame, pose_from_simvars, project
from palmfx.offline.clicks import palm_record, validate_click
from palmfx.offline.depth import DepthModel, fit_depth_model, to_metric
from palmfx.offline.ingest import read_pose_rows, read_triggers
from palmfx.offline.session import FRAMES_JSONL, Session
from palmfx.offline.timing import interpolate_poses

log = get_logger(__name__)

VFOV_START_DEG = 60.0
VFOV_BOUNDS_DEG = (20.0, 120.0)
ATT_BOUND_DEG = 5.0
BODY_BOUND_M = 5.0
HUBER_SCALE_PX = 3.0
OFFSET_GRID_MS = tuple(range(-150, 151, 5))
REFINE_HALF_WIDTH_MS = 5
BODY_PRIOR_PX_PER_M = 3.0
BEHIND_CAMERA_PX = 1e3
DEFAULT_HEIGHT_M = 12.0
TARGET_RMS_PX_1440P = 8.0
TARGET_DEPTH_REL = 0.05
MAX_POSE_GAP_MS = 50.0
DEPTH_OUTLIER_REL = 0.10

Array = NDArray[np.float64]


@dataclass(frozen=True)
class CalibResult:
    vfov_deg: float
    offset_ms: float
    bias: dict[str, Any]  # d_heading_deg, d_pitch_deg, d_bank_deg, d_body_m [f, r, d]
    depth_model: DepthModel | None
    rms_px: float
    width: int = 0
    height: int = 0
    n_points: int = 0

    @property
    def intrinsics(self) -> Intrinsics:
        return Intrinsics.from_vfov(self.width, self.height, self.vfov_deg)

    @property
    def rms_target_px(self) -> float:
        """Plan target (8 px at 1440 p) scaled by image height."""
        return TARGET_RMS_PX_1440P * self.height / 1440.0


@dataclass
class _Problem:
    width: int
    height: int
    frame_idx: list[int]
    trigger_ns: Array
    pose_rows: list[dict[str, Any]]
    cam_offset: Sequence[float]
    conventions: Mapping[str, float]
    frame: LocalFrame
    click_frame: NDArray[np.intp]  # per click: index into frame_idx
    world: Array  # (N, 3) ENU
    uv: Array  # (N, 2)


def _world_points(
    clicks: Sequence[Mapping[str, Any]], palms: Sequence[Mapping[str, Any]]
) -> list[tuple[float, float, float]]:
    """``(lat, lon, h)`` per click: palm base/top or the free world point."""
    by_id = {str(r["palm_id"]): r for r in (palm_record(p) for p in palms)}
    out: list[tuple[float, float, float]] = []
    for c in clicks:
        if "world" in c:
            lat, lon, h = c["world"]
            out.append((float(lat), float(lon), float(h)))
            continue
        rec = by_id.get(c["palm_id"])
        if rec is None:
            raise ConfigError(f"click names unknown palm_id {c['palm_id']!r}")
        ground = rec.get("ground_elev_m")
        if ground is None:
            raise ConfigError(f"palm {c['palm_id']} has no ground_elev_m")
        h = float(ground)
        if c["part"] == "top":
            height = rec.get("height_m")
            h += DEFAULT_HEIGHT_M if height is None else float(height)
        out.append((float(rec["lat"]), float(rec["lon"]), h))
    return out


def _build(
    session: Session, clicks: Sequence[Mapping[str, Any]], palms: Sequence[Mapping[str, Any]]
) -> _Problem:
    cl = [validate_click(c) for c in clicks]
    if not cl:
        raise ConfigError("no clicks to calibrate from")
    triggers = dict(read_triggers(session))
    unknown = sorted({c["frame"] for c in cl} - set(triggers))
    if unknown:
        raise ConfigError(f"clicks on frames without a trigger: {unknown}")
    frame_idx = sorted({c["frame"] for c in cl})
    pos = {f: i for i, f in enumerate(frame_idx)}
    geo = np.array(_world_points(cl, palms), dtype=np.float64)
    frame = LocalFrame(float(geo[0, 0]), float(geo[0, 1]), float(geo[0, 2]))
    world = frame.to_enu(geo[:, 0], geo[:, 1], geo[:, 2])
    res = session.meta.get("resolution")
    if not res or len(res) != 2:
        raise ConfigError("session.json has no resolution [w, h]")
    pose_rows, _, _ = read_pose_rows(session)
    n_params = 7
    if len(cl) * 2 + 3 < n_params:
        raise ConfigError(f"{len(cl)} clicks are too few to fit {n_params} parameters")
    return _Problem(
        width=int(res[0]),
        height=int(res[1]),
        frame_idx=frame_idx,
        trigger_ns=np.array([triggers[f] for f in frame_idx], dtype=np.float64),
        pose_rows=pose_rows,
        cam_offset=session.meta.get("cam_offset_body_m") or (0.0, 0.0, 0.0),
        conventions=session.meta.get("simvar_conventions") or {},
        frame=frame,
        click_frame=np.array([pos[c["frame"]] for c in cl], dtype=np.intp),
        world=world,
        uv=np.array([c["uv"] for c in cl], dtype=np.float64),
    )


def _poses_at(pb: _Problem, offset_ms: float) -> list[dict[str, float]] | None:
    t_ns = np.round(pb.trigger_ns + offset_ms * 1e6).astype(np.int64)
    poses = interpolate_poses(pb.pose_rows, t_ns, MAX_POSE_GAP_MS, pb.conventions)
    if any(p is None for p in poses):
        return None
    return [p for p in poses if p is not None]


def _bias_from_x(x: Array) -> dict[str, Any]:
    return {
        "d_heading_deg": float(x[1]),
        "d_pitch_deg": float(x[2]),
        "d_bank_deg": float(x[3]),
        "d_body_m": [float(x[4]), float(x[5]), float(x[6])],
    }


def _project_all(
    pb: _Problem, poses: Sequence[Mapping[str, float]], x: Array
) -> tuple[Array, Array]:
    """Projected pixels and camera z for every click."""
    K = Intrinsics.from_vfov(pb.width, pb.height, float(x[0]))
    bias = _bias_from_x(x)
    uv = np.empty_like(pb.uv)
    z = np.empty(len(pb.uv))
    for i, pose_row in enumerate(poses):
        sel = np.flatnonzero(pb.click_frame == i)
        if sel.size == 0:
            continue
        cam = pose_from_simvars(pose_row, pb.frame, pb.cam_offset, None, bias)
        uv[sel], z[sel] = project(pb.world[sel], cam, K)
    return uv, z


def _residuals(x: Array, pb: _Problem, poses: Sequence[Mapping[str, float]]) -> Array:
    uv, _ = _project_all(pb, poses, x)
    diff = uv - pb.uv
    diff = np.where(np.isfinite(diff), diff, BEHIND_CAMERA_PX)
    prior = np.asarray(x[4:7]) * BODY_PRIOR_PX_PER_M
    return np.concatenate([diff.ravel(), prior])


_LO = np.array([VFOV_BOUNDS_DEG[0]] + [-ATT_BOUND_DEG] * 3 + [-BODY_BOUND_M] * 3)
_HI = np.array([VFOV_BOUNDS_DEG[1]] + [ATT_BOUND_DEG] * 3 + [BODY_BOUND_M] * 3)
_SCALE = np.array([10.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])


def _fit_at(
    pb: _Problem, offset_ms: float, x0: Array | None = None
) -> tuple[float, Array, list[dict[str, float]]] | None:
    poses = _poses_at(pb, offset_ms)
    if poses is None:
        return None
    start = np.array([VFOV_START_DEG, 0, 0, 0, 0, 0, 0], dtype=np.float64) if x0 is None else x0
    sol = least_squares(
        _residuals,
        start,
        args=(pb, poses),
        bounds=(_LO, _HI),
        loss="huber",
        f_scale=HUBER_SCALE_PX,
        x_scale=_SCALE,
    )
    return float(sol.cost), np.asarray(sol.x, dtype=np.float64), poses


def _sample_depth(depth: NDArray[Any], uv: Sequence[float], half: int = 2) -> float:
    """Median of the (2*half+1)^2 window of raw depth around ``uv``, NaN outside the image."""
    h, w = depth.shape
    u, v = int(np.floor(uv[0])), int(np.floor(uv[1]))
    if not (0 <= u < w and 0 <= v < h):
        return float("nan")
    win = depth[max(v - half, 0) : v + half + 1, max(u - half, 0) : u + half + 1]
    win = win[np.isfinite(win) & (win > 0)]
    return float(np.median(win)) if win.size else float("nan")


def _depth_model(
    session: Session,
    pb: _Problem,
    clicks: Sequence[Mapping[str, Any]],
    z: Array,
) -> DepthModel | None:
    records = {r.idx: r for r in session.frames()}
    d_list: list[float] = []
    z_list: list[float] = []
    cache: dict[int, NDArray[Any]] = {}
    for k, c in enumerate(clicks):
        if c.get("part") != "base" or not np.isfinite(z[k]):
            continue
        rec = records.get(c["frame"])
        if rec is None or rec.depthraw is None:
            continue
        if c["frame"] not in cache:
            cache[c["frame"]] = np.load(rec.depthraw)
        d = _sample_depth(cache[c["frame"]], c["uv"])
        if np.isfinite(d):
            d_list.append(d)
            z_list.append(float(z[k]))
    if len(d_list) < 2:
        log.warning("depth model skipped: %d usable base clicks with depth", len(d_list))
        return None
    d_arr, z_arr = np.array(d_list), np.array(z_list)
    try:
        keep = np.ones(len(d_arr), dtype=bool)
        model = fit_depth_model(d_arr, z_arr)
        # Trim the single worst pair at a time (occluded or mis-clicked bases) while it is off
        # by more than DEPTH_OUTLIER_REL and at least 3 pairs remain.
        while keep.sum() > 2:
            rel = np.where(keep, np.abs(model.a / (d_arr + model.b) - z_arr) / z_arr, 0.0)
            worst = int(np.argmax(rel))
            if not rel[worst] > DEPTH_OUTLIER_REL:
                break
            keep[worst] = False
            model = fit_depth_model(d_arr[keep], z_arr[keep])
    except ConfigError as exc:
        log.warning("depth model skipped: %s", exc)
        return None
    return model


def calibrate(
    session: Session,
    clicks: Sequence[Mapping[str, Any]],
    palms: Sequence[Mapping[str, Any]],
    offsets_ms: Sequence[float] = OFFSET_GRID_MS,
) -> CalibResult:
    """Fit vfov, time offset, pose bias and depth model from clicks (module docstring)."""
    pb = _build(session, clicks, palms)
    cl = [validate_click(c) for c in clicks]

    best: tuple[float, float, Array, list[dict[str, float]]] | None = None
    for off in offsets_ms:
        fit = _fit_at(pb, float(off))
        if fit is not None and (best is None or fit[0] < best[0]):
            best = (fit[0], float(off), fit[1], fit[2])
    if best is None:
        raise ConfigError("no time offset in the grid leaves every clicked frame with a pose")
    coarse = best[1]
    for off in np.arange(coarse - REFINE_HALF_WIDTH_MS, coarse + REFINE_HALF_WIDTH_MS + 1.0):
        if off == coarse:
            continue
        fit = _fit_at(pb, float(off), best[2])
        if fit is not None and fit[0] < best[0]:
            best = (fit[0], float(off), fit[1], fit[2])
    _, offset, x, poses = best

    uv, z = _project_all(pb, poses, x)
    dist = np.hypot(*(uv - pb.uv).T)
    rms = float(np.sqrt(np.mean(np.where(np.isfinite(dist), dist, BEHIND_CAMERA_PX) ** 2)))
    model = _depth_model(session, pb, cl, z)
    result = CalibResult(
        vfov_deg=float(x[0]),
        offset_ms=offset,
        bias=_bias_from_x(x),
        depth_model=model,
        rms_px=rms,
        width=pb.width,
        height=pb.height,
        n_points=len(cl),
    )
    log.info(
        "calibrated: vfov %.3f deg, offset %.0f ms, rms %.2f px over %d clicks",
        result.vfov_deg,
        result.offset_ms,
        result.rms_px,
        result.n_points,
    )
    return result


def warnings_for(result: CalibResult) -> list[str]:
    """Messages for results above the plan targets (empty when within)."""
    out: list[str] = []
    if result.rms_px > result.rms_target_px:
        out.append(
            f"reprojection RMS {result.rms_px:.2f} px above target {result.rms_target_px:.2f} px"
        )
    if result.depth_model is None:
        out.append("no depth model fitted")
    elif not result.depth_model.rms_rel <= TARGET_DEPTH_REL:
        out.append(
            f"depth model RMS {100 * result.depth_model.rms_rel:.1f} % above target"
            f" {100 * TARGET_DEPTH_REL:.0f} %"
        )
    return out


# --- calib/ files -------------------------------------------------------------------------------


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def write_calib(session: Session, result: CalibResult) -> list[Path]:
    """Write ``calib/{intrinsics,time_offset,pose_bias,depth_model}.json``; returns the paths."""
    K = result.intrinsics
    docs: dict[str, dict[str, Any]] = {
        "intrinsics.json": {
            "width": K.width,
            "height": K.height,
            "fx": K.fx,
            "fy": K.fy,
            "cx": K.cx,
            "cy": K.cy,
            "vfov_deg": result.vfov_deg,
            "rms_px": result.rms_px,
        },
        "time_offset.json": {"offset_ms": result.offset_ms, "rms_px": result.rms_px},
        "pose_bias.json": dict(result.bias),
    }
    if result.depth_model is not None:
        m = result.depth_model
        docs["depth_model.json"] = {"kind": "inv", "a": m.a, "b": m.b, "rms_rel": m.rms_rel}
    paths: list[Path] = []
    for name, doc in docs.items():
        p = session.path("calib", name)
        _dump(p, doc)
        paths.append(p)
    return paths


def load_depth_model(session: Session) -> DepthModel:
    path = session.path("calib", "depth_model.json")
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return DepthModel(a=float(d["a"]), b=float(d["b"]), rms_rel=float(d.get("rms_rel", 0.0)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc


def write_metric_depth(session: Session, model: DepthModel) -> int:
    """Write ``frames/NNNNNN.depth.npy`` for every frame and set ``depth`` in frames.jsonl."""
    path = session.path(FRAMES_JSONL)
    if not path.is_file():
        raise ConfigError(f"missing {path}; run `palmfx ingest` first")
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        raw = session.path(str(obj["depthraw"]))
        rel = f"frames/{int(obj['idx']):06d}.depth.npy"
        np.save(session.path(rel), to_metric(np.load(raw), model).astype(np.float32))
        obj["depth"] = rel
        lines.append(json.dumps(obj, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(lines)
