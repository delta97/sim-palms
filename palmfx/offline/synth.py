"""Synthetic test scene with exact ground truth (plan 08, A15).

A tiny analytic ray caster: ground plane ``u = 0``, axis-aligned "blob" boxes at palm positions and
one optional building box, rendered through ``palmfx.offline.camera`` so images and the camera
model agree exactly. Everything is deterministic (hash noise keyed by ``seed`` and world
position, no clocks, no global random state).

Conventions
-----------
- World is ENU metres. The ground is ``u = 0``. Palm positions are ``(e, n)`` or ``(e, n, u)``
  (``u`` ignored): a blob is the box ``[e +- w/2] x [n +- d/2] x [0, h]`` for
  ``box_size = (w, d, h)``.
- Pixel ``(i, j)`` (column, row) is sampled at its centre ``(i + 0.5, j + 0.5)`` in the continuous
  image coordinates used by ``camera.project`` (principal point at ``(W/2, H/2)``).
- ``depth_m`` is the camera-frame z of the hit (what ``camera.project`` returns as ``z``).
  ``depth_raw = 0.1 / z`` is a synthetic reversed-Z choice, not a claim about the sim.
  Sky is ``depth_raw == 0`` and ``depth_m == NaN``; hits beyond ``MAX_RANGE_M`` count as sky.
- ``hit_id`` per pixel: ``HIT_SKY`` 0, ``HIT_GROUND`` 1, ``HIT_BUILDING`` 2, ``HIT_PALM0 + i`` for
  palm ``i``. GT mask labels are ``i + 1`` (stable across frames) and instances carry ``palm_id``.
- Poses are canonical (true heading, pitch up positive, bank right-down positive). SimVar-style
  raw rows apply ``conventions`` (``pitch_sign`` etc.) via ``to_raw_row``.

Typical use::

    scene = SynthScene(palms_enu=[(6, 20), (-12, 55)])
    K = default_intrinsics()
    rows = trajectory(8, speed_mps=30.0, step_ms=1000 / 30)
    frames = render_sequence(scene, rows, K)
    write_fake_session(tmp / "s", scene, n_frames=8, offset_ms=40.0)

VERIFY: the on-disk naming of ReShade screenshot pairs is unconfirmed (FX-001). The fake session
uses ``shot_NNNNNN_before.png`` / ``shot_NNNNNN_after.png`` and records the suffixes in
``session.json``.
"""

from __future__ import annotations

import csv
import dataclasses
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from palmcore.errors import ConfigError
from palmfx.offline.camera import (
    CameraPose,
    Intrinsics,
    LocalFrame,
    backproject,
    pose_from_simvars,
    project,
)
from palmfx.offline.depth import DMIN, pack_log24
from palmfx.offline.session import (
    MaskSet,
    new_session,
    write_image,
    write_mask,
)

HIT_SKY = 0
HIT_GROUND = 1
HIT_BUILDING = 2
HIT_PALM0 = 3

MAX_RANGE_M = 50_000.0
RAW_DEPTH_NUM = 0.1  # depth_raw = RAW_DEPTH_NUM / z
SYNTH_VFOV_DEG = 50.0
SYNTH_SIZE = (320, 180)
SYNTH_FRAME = LocalFrame(32.7157, -117.161, 0.0)
T0_NS = 1_000_000_000_000  # arbitrary fixed host-clock origin for synthetic sessions
DEFAULT_BUILDING: tuple[tuple[float, float], tuple[float, float], float] = (
    (-4.0, -40.0),
    (12.0, -26.0),
    14.0,
)

BuildingSpec = tuple[tuple[float, float], tuple[float, float], float]
F64 = NDArray[np.float64]

_SKY_RGB = np.array([135.0, 190.0, 235.0])
_ASPHALT_RGB = np.array([88.0, 88.0, 94.0])
_GRASS_RGB = np.array([72.0, 112.0, 52.0])
_BLOB_RGB = np.array([85.0, 95.0, 45.0])
_BUILDING_RGB = np.array([150.0, 150.0, 156.0])
_FACE_SHADE = np.array([0.85, 0.75, 1.0])  # by hit-face axis: x, y, z(top)

_M1 = np.uint64(0x9E3779B97F4A7C15)
_M2 = np.uint64(0xBF58476D1CE4E5B9)
_M3 = np.uint64(0x94D049BB133111EB)


@dataclass(frozen=True)
class SynthScene:
    """Blobs at ``palms_enu`` plus an optional building. ``building=None`` disables it."""

    palms_enu: NDArray[np.float64]
    box_size: tuple[float, float, float] = (4.0, 4.0, 12.0)
    building: BuildingSpec | None = DEFAULT_BUILDING
    seed: int = 0

    def __post_init__(self) -> None:
        arr = np.asarray(self.palms_enu, dtype=np.float64)
        if arr.size == 0:
            arr = arr.reshape(0, 2)
        if arr.ndim != 2 or arr.shape[1] not in (2, 3):
            raise ConfigError("palms_enu must have shape (N, 2) or (N, 3)")
        object.__setattr__(self, "palms_enu", arr[:, :2].copy())
        if min(self.box_size) <= 0:
            raise ConfigError("box_size must be positive")

    @property
    def n_palms(self) -> int:
        return int(self.palms_enu.shape[0])

    def palm_id(self, i: int) -> str:
        """Stable id matching the palms.geojson pattern ``^[a-z]{2,6}-[0-9a-f]{16}$``."""
        return f"syn-{i:016x}"

    def blob_boxes(self) -> list[tuple[F64, F64]]:
        """(min, max) corners of every blob box."""
        w, d, h = self.box_size
        out: list[tuple[F64, F64]] = []
        for e, n in self.palms_enu:
            out.append((np.array([e - w / 2, n - d / 2, 0.0]), np.array([e + w / 2, n + d / 2, h])))
        return out

    def building_box(self) -> tuple[F64, F64] | None:
        if self.building is None:
            return None
        (x0, y0), (x1, y1), height = self.building
        lo = np.array([min(x0, x1), min(y0, y1), 0.0])
        hi = np.array([max(x0, x1), max(y0, y1), float(height)])
        return lo, hi


@dataclass(frozen=True)
class SynthFrame:
    """One rendered frame with ground truth. Arrays are read-only."""

    color: NDArray[np.uint8]  # (H, W, 3) RGB
    depth_raw: NDArray[np.float32]  # (H, W), 0 = sky
    depth_m: NDArray[np.float32]  # (H, W), NaN = sky
    gt: MaskSet  # blob masks; instances carry palm_id
    clean: NDArray[np.uint8]  # same frame rendered without blobs
    clean_depth_m: NDArray[np.float32]  # depth of the clean plate
    hit_id: NDArray[np.int16]  # see HIT_* constants
    pose: CameraPose
    K: Intrinsics
    idx: int | None = None
    t_ns: int | None = None
    pose_row: dict[str, float] | None = None  # canonical pose row this frame was rendered from
    extra: dict[str, Any] = field(default_factory=dict)


# --- noise -------------------------------------------------------------------------------------


def _hash01(seed: int, salt: int, *coords: NDArray[Any]) -> F64:
    """Deterministic per-cell noise in [0, 1) from integer cell coordinates."""
    shape = np.broadcast_shapes(*(c.shape for c in coords))
    with np.errstate(over="ignore"):
        h = np.full(shape, np.uint64((seed * 0x2545F491 + salt * 0x9E3779B1) & 0xFFFFFFFFFFFFFFFF))
        for c in coords:
            h = h ^ (np.asarray(c, dtype=np.int64).astype(np.uint64) + _M1)
            h = (h ^ (h >> np.uint64(30))) * _M2
            h = (h ^ (h >> np.uint64(27))) * _M3
            h = h ^ (h >> np.uint64(31))
    return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)


# --- ray casting -------------------------------------------------------------------------------


def _slab(
    origin: F64, dirs: F64, lo: F64, hi: F64
) -> tuple[NDArray[np.bool_], F64, NDArray[np.int64]]:
    """Slab test of rays against one box. Returns (hit, t_enter, entry axis)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / dirs
        t1 = (lo - origin) * inv
        t2 = (hi - origin) * inv
    tmin = np.minimum(t1, t2)
    tmax = np.maximum(t1, t2)
    # Rays parallel to a slab give NaN/inf: inside the slab means no constraint, outside a miss.
    inside = (origin >= lo) & (origin <= hi)
    par = dirs == 0.0
    tmin = np.where(par, np.where(inside, -np.inf, np.inf), tmin)
    tmax = np.where(par, np.where(inside, np.inf, -np.inf), tmax)
    axis = np.argmax(tmin, axis=1)
    t_enter = np.take_along_axis(tmin, axis[:, None], axis=1)[:, 0]
    t_exit = np.min(tmax, axis=1)
    hit = (t_enter <= t_exit) & (t_enter > 0.0)
    return hit, t_enter, axis.astype(np.int64)


@dataclass
class _Trace:
    t: F64
    hit_id: NDArray[np.int16]
    face: NDArray[np.int64]
    points: F64
    up: F64  # up component of the unit ray direction


def _trace(scene: SynthScene, pose: CameraPose, K: Intrinsics, blobs: bool) -> _Trace:
    h, w = K.height, K.width
    jj, ii = np.mgrid[0:h, 0:w]
    uv = np.stack([ii.ravel() + 0.5, jj.ravel() + 0.5], axis=1).astype(np.float64)
    origin = np.asarray(pose.position_enu, dtype=np.float64)
    # z = 1 in the camera frame, so the ray parameter t equals the camera-frame depth.
    dirs = backproject(uv, np.ones(len(uv)), pose, K) - origin
    n = len(uv)

    t = np.full(n, np.inf)
    hit_id = np.zeros(n, dtype=np.int16)
    face = np.full(n, 2, dtype=np.int64)

    down = dirs[:, 2] < 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        tg = np.where(down, -origin[2] / dirs[:, 2], np.inf)
    ground = down & (tg > 0.0) & (tg <= MAX_RANGE_M)
    t = np.where(ground, tg, t)
    hit_id[ground] = HIT_GROUND

    boxes: list[tuple[int, F64, F64]] = []
    b = scene.building_box()
    if b is not None:
        boxes.append((HIT_BUILDING, b[0], b[1]))
    if blobs:
        boxes.extend((HIT_PALM0 + i, lo, hi) for i, (lo, hi) in enumerate(scene.blob_boxes()))
    for ident, lo, hi in boxes:
        hit, te, axis = _slab(origin, dirs, lo, hi)
        closer = hit & (te < t) & (te <= MAX_RANGE_M)
        t = np.where(closer, te, t)
        hit_id[closer] = ident
        face[closer] = axis[closer]

    finite = np.isfinite(t)
    points = np.zeros((n, 3))
    points[finite] = origin + dirs[finite] * t[finite, None]
    up = dirs[:, 2] / np.linalg.norm(dirs, axis=1)
    return _Trace(t=t, hit_id=hit_id, face=face, points=points, up=up)


def _shade(scene: SynthScene, tr: _Trace) -> NDArray[np.uint8]:
    n = len(tr.t)
    rgb = np.zeros((n, 3))
    seed = scene.seed

    sky = tr.hit_id == HIT_SKY
    # Light-blue sky, a little lighter towards the horizon (dirs_u is the ray's up component).
    rgb[sky] = _SKY_RGB * (1.0 - 0.12 * np.clip(tr.up[sky], 0.0, 1.0))[:, None]

    g = tr.hit_id == HIT_GROUND
    if g.any():
        x, y = tr.points[g, 0], tr.points[g, 1]
        patch = _hash01(seed, 1, np.floor(x / 20.0), np.floor(y / 20.0))
        base = np.where((patch < 0.5)[:, None], _ASPHALT_RGB, _GRASS_RGB)
        fine = _hash01(seed, 2, np.floor(x / 0.5), np.floor(y / 0.5))
        rgb[g] = base * (0.85 + 0.3 * fine)[:, None]

    for ident, base_rgb, noise_amp in (
        (HIT_BUILDING, _BUILDING_RGB, 0.06),
        (None, _BLOB_RGB, 0.18),
    ):
        sel = tr.hit_id == HIT_BUILDING if ident is not None else tr.hit_id >= HIT_PALM0
        if not sel.any():
            continue
        p = tr.points[sel]
        cell = _hash01(
            seed,
            3,
            np.floor(p[:, 0] / 0.75),
            np.floor(p[:, 1] / 0.75),
            np.floor(p[:, 2] / 0.75),
        )
        shade = _FACE_SHADE[tr.face[sel]]
        rgb[sel] = base_rgb * (shade * (1.0 + noise_amp * (2.0 * cell - 1.0)))[:, None]

    return np.clip(np.floor(rgb + 0.5), 0, 255).astype(np.uint8)


def _readonly(a: NDArray[Any]) -> NDArray[Any]:
    a.setflags(write=False)
    return a


def render(scene: SynthScene, pose: CameraPose, K: Intrinsics) -> SynthFrame:
    """Render colour, depth, GT masks and the clean plate for one camera pose."""
    h, w = K.height, K.width
    full = _trace(scene, pose, K, blobs=True)
    clean_tr = _trace(scene, pose, K, blobs=False)

    color = _shade(scene, full).reshape(h, w, 3)
    clean = _shade(scene, clean_tr).reshape(h, w, 3)

    def depths(tr: _Trace) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        sky = tr.hit_id == HIT_SKY
        z = np.where(sky, np.nan, tr.t)
        raw = np.where(sky, 0.0, RAW_DEPTH_NUM / np.where(sky, 1.0, tr.t))
        return raw.reshape(h, w).astype(np.float32), z.reshape(h, w).astype(np.float32)

    raw, z_m = depths(full)
    _, clean_z = depths(clean_tr)
    hit_id = full.hit_id.reshape(h, w)

    gt = _gt_masks(scene, hit_id, z_m, pose, K)
    return SynthFrame(
        color=_readonly(color),
        depth_raw=_readonly(raw),
        depth_m=_readonly(z_m),
        gt=gt,
        clean=_readonly(clean),
        clean_depth_m=_readonly(clean_z),
        hit_id=_readonly(hit_id.astype(np.int16)),
        pose=pose,
        K=K,
    )


def _gt_masks(
    scene: SynthScene,
    hit_id: NDArray[np.int16],
    z_m: NDArray[np.float32],
    pose: CameraPose,
    K: Intrinsics,
) -> MaskSet:
    union = np.where(hit_id >= HIT_PALM0, 255, 0).astype(np.uint8)
    labels = np.where(hit_id >= HIT_PALM0, hit_id - HIT_PALM0 + 1, 0).astype(np.uint16)
    instances: list[dict[str, Any]] = []
    hgt = scene.box_size[2]
    for i, (e, n) in enumerate(scene.palms_enu):
        sel = labels == i + 1
        if not sel.any():
            continue
        ys, xs = np.nonzero(sel)
        uv, _z = project([[e, n, 0.0], [e, n, hgt]], pose, K)
        instances.append(
            {
                "k": i + 1,
                "palm_id": scene.palm_id(i),
                "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                "area_px": int(sel.sum()),
                "z_m": float(np.median(z_m[sel])),
                "base_uv": None if np.isnan(uv[0]).any() else [float(v) for v in uv[0]],
                "top_uv": None if np.isnan(uv[1]).any() else [float(v) for v in uv[1]],
            }
        )
    return MaskSet(
        union=_readonly(union),
        labels=_readonly(labels),
        instances=instances,
        method="synth-gt",
        params={"seed": scene.seed},
    )


# --- trajectory and poses ----------------------------------------------------------------------


def default_intrinsics(
    width: int = SYNTH_SIZE[0], height: int = SYNTH_SIZE[1], vfov_deg: float = SYNTH_VFOV_DEG
) -> Intrinsics:
    return Intrinsics.from_vfov(width, height, vfov_deg)


def trajectory(
    n_frames: int,
    speed_mps: float,
    step_ms: float,
    alt_m: float | None = 50.0,
    pitch_deg: float = -10.0,
    heading_deg: float = 0.0,
    start_enu: Sequence[float] = (0.0, -150.0, 50.0),
    *,
    bank_deg: float = 0.0,
    frame: LocalFrame = SYNTH_FRAME,
    t0_ns: int = T0_NS,
    i0: int = 0,
) -> list[dict[str, float]]:
    """Canonical pose rows of a straight, level flight at constant attitude.

    Sample ``k`` (``k = i0 .. i0 + n_frames - 1``) is at time ``t0 + k * step_ms`` and position
    ``start + v * k * step``, flying along ``heading_deg`` (clockwise from north). ``alt_m``
    overrides the up component of ``start_enu`` (pass ``None`` to use it). Rows hold
    ``t_host_ns, sim_time_s, lat_deg, lon_deg, alt_msl_m, heading_true_deg, pitch_deg, bank_deg``.
    """
    if n_frames < 0 or step_ms <= 0:
        raise ConfigError("n_frames must be >= 0 and step_ms > 0")
    start = np.asarray(start_enu, dtype=np.float64)
    if start.shape not in ((2,), (3,)):
        raise ConfigError("start_enu must have 2 or 3 elements")
    up = float(alt_m) if alt_m is not None else (float(start[2]) if start.size == 3 else 50.0)
    h = np.radians(heading_deg)
    vel = np.array([np.sin(h), np.cos(h)]) * speed_mps
    ks = np.arange(i0, i0 + n_frames, dtype=np.float64)
    secs = ks * step_ms / 1000.0
    enu = np.zeros((n_frames, 3))
    enu[:, :2] = start[:2] + secs[:, None] * vel
    enu[:, 2] = up
    if n_frames == 0:
        return []
    lat, lon, alt = frame.from_enu(enu)
    rows: list[dict[str, float]] = []
    for k in range(n_frames):
        rows.append(
            {
                "t_host_ns": int(t0_ns + round(float(ks[k]) * step_ms * 1e6)),
                "sim_time_s": float(secs[k]),
                "lat_deg": float(lat[k]),
                "lon_deg": float(lon[k]),
                "alt_msl_m": float(alt[k]),
                "heading_true_deg": float(heading_deg),
                "pitch_deg": float(pitch_deg),
                "bank_deg": float(bank_deg),
            }
        )
    return rows


def to_raw_row(
    row: Mapping[str, float], conventions: Mapping[str, float] | None = None
) -> dict[str, float]:
    """SimVar-style row: canonical attitude with ``conventions`` signs applied (they are +-1)."""
    conv = conventions or {}
    out = dict(row)
    out["heading_true_deg"] = conv.get("heading_sign", 1) * row["heading_true_deg"]
    out["pitch_deg"] = conv.get("pitch_sign", 1) * row["pitch_deg"]
    out["bank_deg"] = conv.get("bank_sign", 1) * row["bank_deg"]
    return out


def camera_pose(
    row: Mapping[str, float],
    frame: LocalFrame = SYNTH_FRAME,
    cam_offset_body_m: Sequence[float] = (0.0, 0.0, 0.0),
) -> CameraPose:
    """Camera pose of a canonical row (the pose ``render`` should use)."""
    return pose_from_simvars(row, frame, cam_offset_body_m)


def render_sequence(
    scene: SynthScene,
    rows: Sequence[Mapping[str, float]],
    K: Intrinsics,
    frame: LocalFrame = SYNTH_FRAME,
) -> list[SynthFrame]:
    """Render one frame per canonical pose row; fills ``idx``, ``t_ns`` and ``pose_row``."""
    out: list[SynthFrame] = []
    for i, row in enumerate(rows):
        f = render(scene, camera_pose(row, frame), K)
        out.append(dataclasses.replace(f, idx=i, t_ns=int(row["t_host_ns"]), pose_row=dict(row)))
    return out


# --- palms.geojson -----------------------------------------------------------------------------


def make_palms_geojson(scene: SynthScene, frame: LocalFrame = SYNTH_FRAME) -> dict[str, Any]:
    """A palms.geojson FeatureCollection (schema 1.x) matching the scene's blob boxes."""
    from palmcore.contract import PALMS_SCHEMA_VERSION
    from palmcore.palms import Palm

    w, _, hgt = scene.box_size
    features: list[dict[str, Any]] = []
    if scene.n_palms:
        enu = np.column_stack([scene.palms_enu, np.zeros(scene.n_palms)])
        lat, lon, alt = frame.from_enu(enu)
        for i in range(scene.n_palms):
            palm = Palm(
                palm_id=scene.palm_id(i),
                lon=round(float(lon[i]), 7),
                lat=round(float(lat[i]), 7),
                species="synthetic_blob",
                species_confidence=1.0,
                species_source="inventory",
                height_m=float(hgt),
                height_source="inventory",
                crown_diam_m=float(w),
                ground_elev_m=round(float(alt[i]), 3),
                detected_by="inventory",
                source_ids=(f"synth:{i}",),
                exclusion_radius_m=float(w) / 2 + 1.0,
                building_conflict=False,
                data_vintage={"inventory": "2026"},
                region="synthetic",
            )
            features.append(palm.to_feature())
    return {
        "type": "FeatureCollection",
        "schema_version": PALMS_SCHEMA_VERSION,
        "region": "synthetic",
        "generated_at": "2026-01-01T00:00:00Z",
        "data_version": "2026-01",
        "generator": {"name": "palmfx.synth", "version": "0"},
        "config_sha256": None,
        "features": features,
    }


# --- fake session ------------------------------------------------------------------------------

POSE_COLUMNS = (
    "t_host_ns",
    "sim_time_s",
    "lat_deg",
    "lon_deg",
    "alt_msl_m",
    "heading_true_deg",
    "pitch_deg",
    "bank_deg",
)
RESHADE_SUFFIXES = ("_before", "_after")
POSE_RATE_FACTOR = 3  # pose samples per frame


def _write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)


def write_fake_session(
    root: Path,
    scene: SynthScene,
    n_frames: int = 8,
    offset_ms: float = 0.0,
    conventions: Mapping[str, float] | None = None,
    *,
    fps: float = 30.0,
    speed_mps: float = 30.0,
    K: Intrinsics | None = None,
    pitch_deg: float = -10.0,
    heading_deg: float = 0.0,
    bank_deg: float = 0.0,
    start_enu: Sequence[float] = (0.0, -150.0, 50.0),
    gt_masks: bool = True,
    frame: LocalFrame = SYNTH_FRAME,
) -> Path:
    """Write a raw (pre-ingest) session directory and return ``root``.

    Layout: ``session.json``, ``raw/triggers.csv``, ``raw/poses.csv`` (SimVar-style signs from
    ``conventions``, ``POSE_RATE_FACTOR`` samples per frame, padded past both ends),
    ``raw/reshade/shot_NNNNNN_{before,after}.png`` (colour, packed log24 depth), ``palms.geojson``
    and, with ``gt_masks``, exact masks in ``masks/gt/``.

    Frame ``i`` shows the scene at true time ``t_i = T0 + i / fps``. The trigger was fired at
    ``t_trigger_i = t_i - offset_ms``, so ingest computing ``t_i = t_trigger_i + offset`` recovers
    the content time with ``offset == offset_ms`` (the truth is stored in ``session.json`` under
    ``synthetic``). Poses are not interpolated to frame times: ingest must do that.
    """
    if n_frames < 1 or fps <= 0:
        raise ConfigError("n_frames must be >= 1 and fps > 0")
    k = K or default_intrinsics()
    step_ms = 1000.0 / fps
    conv = dict(conventions or {})
    root = Path(root)

    rows = trajectory(
        n_frames,
        speed_mps,
        step_ms,
        None,
        pitch_deg,
        heading_deg,
        start_enu,
        bank_deg=bank_deg,
        frame=frame,
    )
    frames = render_sequence(scene, rows, k, frame)

    pad = 2 * POSE_RATE_FACTOR
    samples = trajectory(
        POSE_RATE_FACTOR * (n_frames - 1) + 1 + 2 * pad,
        speed_mps,
        step_ms / POSE_RATE_FACTOR,
        None,
        pitch_deg,
        heading_deg,
        start_enu,
        bank_deg=bank_deg,
        frame=frame,
        i0=-pad,
    )

    new_session(
        root,
        {
            "site": "SYN",
            "created": "2026-01-01T00:00:00Z",
            "sim_build": "synthetic",
            "reshade_version": "synthetic",
            "reshade_build": "standard",
            "resolution": [k.width, k.height],
            "graphics": "synthetic",
            "upscaler": "none",
            "render_scale_pct": 100,
            "frame_generation": False,
            "sim_rate": 1.0,
            "trigger_interval_ms": step_ms,
            "sim_step_ms": step_ms,
            "view": "low",
            "zoom": "",
            "depth_encoding": {"kind": "log24", "dmin": DMIN},
            "reshade_depth_flags": {},
            "simvar_conventions": conv,
            "cam_offset_body_m": [0.0, 0.0, 0.0],
            "reshade_suffixes": {"before": RESHADE_SUFFIXES[0], "after": RESHADE_SUFFIXES[1]},
            "notes": "synthetic session from palmfx.offline.synth; VERIFY: real ReShade names",
            "synthetic": {
                "seed": scene.seed,
                "time_offset_ms": float(offset_ms),
                "t0_ns": T0_NS,
                "vfov_deg": float(np.degrees(2.0 * np.arctan(k.height / 2.0 / k.fy))),
                "origin": {"lat0": frame.lat0, "lon0": frame.lon0, "h0": frame.h0},
                "n_frames": n_frames,
                "fps": fps,
                "pose_rate_factor": POSE_RATE_FACTOR,
            },
        },
    )

    offset_ns = round(offset_ms * 1e6)
    _write_csv(
        root / "raw" / "triggers.csv",
        ("frame_idx", "t_trigger_ns"),
        [(f.idx, f.t_ns - offset_ns) for f in frames if f.idx is not None and f.t_ns is not None],
    )
    _write_csv(
        root / "raw" / "poses.csv",
        POSE_COLUMNS,
        [
            [
                int(raw["t_host_ns"]),
                f"{raw['sim_time_s']:.6f}",
                f"{raw['lat_deg']:.9f}",
                f"{raw['lon_deg']:.9f}",
                f"{raw['alt_msl_m']:.4f}",
                f"{raw['heading_true_deg']:.6f}",
                f"{raw['pitch_deg']:.6f}",
                f"{raw['bank_deg']:.6f}",
            ]
            for raw in (to_raw_row(r, conv) for r in samples)
        ],
    )
    shots = root / "raw" / "reshade"
    for f in frames:
        stem = f"shot_{f.idx:06d}"
        write_image(shots / f"{stem}{RESHADE_SUFFIXES[0]}.png", np.asarray(f.color))
        write_image(shots / f"{stem}{RESHADE_SUFFIXES[1]}.png", pack_log24(f.depth_raw))
        if gt_masks:
            write_mask(root / "masks" / "gt", int(f.idx or 0), f.gt)

    (root / "palms.geojson").write_text(
        json.dumps(make_palms_geojson(scene, frame), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


def box_corners(lo: ArrayLike, hi: ArrayLike) -> F64:
    """The 8 corners of an axis-aligned box (for tests and projection checks)."""
    lo_a = np.asarray(lo, dtype=np.float64)
    hi_a = np.asarray(hi, dtype=np.float64)
    return np.array([[(hi_a if (m >> a) & 1 else lo_a)[a] for a in range(3)] for m in range(8)])
