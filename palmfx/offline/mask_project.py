"""Blob masks by projecting known palm positions into each frame (plan 08, A7).

Every palm in ``palms.geojson`` becomes a camera-facing billboard (a quadrilateral from the palm
base to its top) that is projected with :mod:`palmfx.offline.camera` and filled. Two mask sets
come out per frame:

- ``project-raw``: geometry only.
- ``project-depth``: geometry intersected with the pixels whose metric depth agrees with the palm
  base depth, ``|z_pix - z_base| <= max(depth_tol_m, depth_tol_rel * z_base)``. That removes nearer
  occluders (a building in front of the palm) and background seen beside a thin blob.

Both sets are dilated, lose static-occluder pixels, and where billboards overlap the nearer palm
keeps the pixel. Labels are ``1..N`` in palm order and ``0`` is background (the
:mod:`palmfx.offline.session` mask format).

Palm heights and ground elevations are used as given, in the same vertical datum as the pose
altitude. VERIFY: ``ground_elev_m`` is orthometric (ARCH-002) while the sim pose altitude is MSL
of some datum; a datum mismatch shifts palms vertically (FX-009's pose fit absorbs a constant
part of it).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from palmcore.errors import ConfigError
from palmcore.palms import read_palms
from palmfx.offline.camera import CameraPose, Intrinsics, LocalFrame, project
from palmfx.offline.session import MaskSet

DEFAULT_HEIGHT_M = 12.0
DEFAULT_CROWN_M = 4.0

SKIP_BEHIND = "behind_camera"
SKIP_RANGE = "out_of_range"
SKIP_SMALL = "too_small"
SKIP_OFFSCREEN = "off_screen"
SKIP_OCCLUDED = "fully_occluded"
SKIP_REASONS = (SKIP_BEHIND, SKIP_RANGE, SKIP_SMALL, SKIP_OFFSCREEN, SKIP_OCCLUDED)

_UV_LIMIT = 1.0e6

Palm = dict[str, Any]
Array = NDArray[np.float64]


@dataclass(frozen=True)
class ProjectParams:
    """Starting parameters from plan 08 A7 (tuned for 1440 p real footage)."""

    min_width_m: float = 4.0
    width_scale: float = 1.3
    top_extra_m: float = 1.0
    depth_tol_m: float = 3.0
    depth_tol_rel: float = 0.05
    dilate_px: int = 3
    max_range_m: float = 1500.0
    min_height_px: float = 6.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> ProjectParams:
        """Defaults overridden by ``values``; unknown keys are an error."""
        base = asdict(cls())
        extra = dict(values or {})
        unknown = sorted(set(extra) - set(base))
        if unknown:
            raise ConfigError(f"unknown projection parameters: {unknown}")
        base.update(extra)
        p = cls(**{k: type(v)(base[k]) for k, v in asdict(cls()).items()})
        if p.dilate_px < 0 or p.min_width_m <= 0 or p.max_range_m <= 0:
            raise ConfigError("projection parameters out of range")
        return p


@dataclass
class ProjectResult:
    """Masks and bookkeeping for one frame."""

    raw: MaskSet
    depth: MaskSet | None
    skipped: dict[str, int]
    in_view: int  # palms with a non-empty raw instance
    in_view_depth: int  # palms with a non-empty depth-tested instance


# --- palms -------------------------------------------------------------------------------------


def _positive(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def palm_record(
    palm_id: str, lon: float, lat: float, props: Mapping[str, Any] | None = None
) -> Palm:
    """A palm dict with defaults filled: ``height_m`` 12, ``crown_diam_m`` 4.

    Missing, null or non-positive values are replaced and named in ``defaulted``.
    ``ground_elev_m`` stays ``None`` when unknown (see :func:`fill_ground_elev`).
    """
    props = props or {}
    defaulted: list[str] = []
    height = _positive(props.get("height_m"))
    if height is None:
        height = DEFAULT_HEIGHT_M
        defaulted.append("height_m")
    crown = _positive(props.get("crown_diam_m"))
    if crown is None:
        crown = DEFAULT_CROWN_M
        defaulted.append("crown_diam_m")
    elev_raw = props.get("ground_elev_m")
    try:
        elev = None if elev_raw is None else float(elev_raw)
    except (TypeError, ValueError):
        elev = None
    if elev is not None and not math.isfinite(elev):
        elev = None
    return {
        "palm_id": str(palm_id),
        "lon": float(lon),
        "lat": float(lat),
        "height_m": height,
        "crown_diam_m": crown,
        "ground_elev_m": elev,
        "defaulted": defaulted,
        "elev_estimated": False,
    }


def load_palms(path: Path, *, strict: bool = True) -> list[Palm]:
    """Palms from a ``palms.geojson``, sorted by ``palm_id``.

    ``strict`` validates through ``palmcore.palms.read_palms`` (the contract requires
    ``height_m`` and ``crown_diam_m``, so nothing is defaulted in practice). ``strict=False`` reads
    the features as plain JSON and fills defaults for missing fields, for hand-made inputs.
    """
    path = Path(path)
    if strict:
        return [
            palm_record(
                p.palm_id,
                p.lon,
                p.lat,
                {
                    "height_m": p.height_m,
                    "crown_diam_m": p.crown_diam_m,
                    "ground_elev_m": p.ground_elev_m,
                },
            )
            for p in read_palms(path).palms
        ]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        feats = doc["features"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"cannot read palms from {path}: {exc!r}") from exc
    out: list[Palm] = []
    for n, f in enumerate(feats):
        try:
            lon, lat = f["geometry"]["coordinates"][:2]
            props = f.get("properties") or {}
            pid = props.get("palm_id") or f.get("id") or f"palm-{n}"
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"{path}: feature {n} has no point geometry") from exc
        out.append(palm_record(str(pid), lon, lat, props))
    return sorted(out, key=lambda p: p["palm_id"])


def fill_ground_elev(palms: Sequence[Palm], fallback_m: float | None = None) -> list[Palm]:
    """Copies of ``palms`` with every null ``ground_elev_m`` filled.

    Fill value: the median of the palms that have one; if none do, ``fallback_m`` (the pose-log
    estimate, altitude minus AGL). Filled palms get ``elev_estimated = True``.
    """
    known = [p["ground_elev_m"] for p in palms if p["ground_elev_m"] is not None]
    if known:
        fill: float | None = float(np.median(known))
    else:
        fill = fallback_m
    out: list[Palm] = []
    for p in palms:
        q = dict(p)
        q["defaulted"] = list(p.get("defaulted", []))
        if q["ground_elev_m"] is None:
            if fill is None:
                raise ConfigError(
                    "no palm has ground_elev_m and the pose log has no ground estimate; "
                    "pass --ground-elev-m"
                )
            q["ground_elev_m"] = fill
            q["elev_estimated"] = True
        out.append(q)
    return out


def palms_to_enu(palms: Sequence[Palm], frame: LocalFrame) -> list[Palm]:
    """Copies of ``palms`` with ``enu_base`` = ``[e, n, u]`` at ``ground_elev_m`` (must be set)."""
    if not palms:
        return []
    enu = frame.to_enu(
        [p["lat"] for p in palms], [p["lon"] for p in palms], [p["ground_elev_m"] for p in palms]
    )
    out: list[Palm] = []
    for p, e in zip(palms, enu, strict=True):
        q = dict(p)
        q["enu_base"] = [float(v) for v in e]
        out.append(q)
    return out


# --- geometry ----------------------------------------------------------------------------------


def palm_billboard(palm: Palm, pose: CameraPose, params: ProjectParams | None = None) -> Array:
    """Billboard corners (4, 3) in ENU: ``B-r, B+r, T+r, T-r`` with ``r`` = half width * facing.

    ``palm`` needs ``enu_base``, ``height_m`` and ``crown_diam_m``. ``r`` is the horizontal unit
    vector perpendicular to the camera-to-base direction, so the quad faces the camera. Looking
    straight down it falls back to the camera's right axis.
    """
    p = params or ProjectParams()
    base = np.asarray(palm["enu_base"], dtype=np.float64)
    top = base + np.array([0.0, 0.0, float(palm["height_m"]) + p.top_extra_m])
    d = base[:2] - pose.position_enu[:2]
    norm = float(np.hypot(d[0], d[1]))
    if norm > 1e-6:
        r2 = np.array([-d[1], d[0]]) / norm
    else:
        right = pose.R_cam_from_enu[0, :2]
        rn = float(np.hypot(right[0], right[1]))
        r2 = right / rn if rn > 1e-9 else np.array([1.0, 0.0])
    half = max(p.min_width_m, p.width_scale * float(palm["crown_diam_m"])) / 2.0
    r = np.array([r2[0], r2[1], 0.0]) * half
    return np.array([base - r, base + r, top + r, top - r])


@dataclass
class _Candidate:
    index: int
    palm: Palm
    z_base: float
    base_uv: Array
    top_uv: Array
    mask: NDArray[np.bool_]  # crop-sized
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 (exclusive) of the crop in the image


def _static_ok(occluder: NDArray[Any] | None, shape: tuple[int, int]) -> NDArray[np.bool_] | None:
    if occluder is None:
        return None
    if occluder.shape != shape:
        raise ConfigError(f"static occluder is {occluder.shape}, frame is {shape}")
    return np.asarray(occluder > 0)


def _crop_box(uv: Array, pad: int, h: int, w: int) -> tuple[int, int, int, int] | None:
    x0 = math.floor(float(np.min(uv[:, 0]))) - pad
    x1 = math.ceil(float(np.max(uv[:, 0]))) + 1 + pad
    y0 = math.floor(float(np.min(uv[:, 1]))) - pad
    y1 = math.ceil(float(np.max(uv[:, 1]))) + 1 + pad
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _fill_quad(uv: Array, x0: int, y0: int, x1: int, y1: int) -> NDArray[np.bool_]:
    """Pixels of the crop ``[x0:x1, y0:y1]`` whose centre lies inside the convex quad ``uv``.

    Pixel (i, j) is centred at (i + 0.5, j + 0.5) in camera coordinates. ``cv2.fillPoly`` also
    paints the outline pixels, which fattens a thin blob by about a pixel on each side, so the
    quad is rasterised by centre sampling instead. The quad is convex (a perspective image of a
    rectangle); a degenerate (zero-area) quad gives an empty mask.
    """
    xs = np.arange(x0, x1, dtype=np.float64) + 0.5
    ys = np.arange(y0, y1, dtype=np.float64) + 0.5
    gx, gy = np.meshgrid(xs, ys)
    pos = np.ones(gx.shape, dtype=bool)
    neg = np.ones(gx.shape, dtype=bool)
    for i in range(4):
        ax, ay = uv[i]
        bx, by = uv[(i + 1) % 4]
        cross = (bx - ax) * (gy - ay) - (by - ay) * (gx - ax)
        pos &= cross >= 0.0
        neg &= cross <= 0.0
    return pos | neg


def _dilate(mask: NDArray[np.bool_], px: int) -> NDArray[np.bool_]:
    if px <= 0:
        return mask
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return np.asarray(cv2.dilate(mask.astype(np.uint8), k) > 0)


def _compose(
    cands: Sequence[_Candidate],
    shape: tuple[int, int],
    occluder: NDArray[np.bool_] | None,
    method: str,
    params: ProjectParams,
    masks: Sequence[NDArray[np.bool_]],
) -> MaskSet:
    """Paint far to near so the nearer palm wins; instances describe what remains."""
    labels = np.zeros(shape, dtype=np.uint16)
    order = sorted(range(len(cands)), key=lambda i: (-cands[i].z_base, cands[i].index))
    for i in order:
        c, m = cands[i], masks[i]
        x0, y0, x1, y1 = c.box
        if occluder is not None:
            m = m & ~occluder[y0:y1, x0:x1]
        view = labels[y0:y1, x0:x1]
        view[m] = np.uint16(c.index + 1)
    instances: list[dict[str, Any]] = []
    for c in sorted(cands, key=lambda c: c.index):
        ys, xs = np.nonzero(labels == c.index + 1)
        if ys.size == 0:
            continue
        instances.append(
            {
                "k": c.index + 1,
                "palm_id": c.palm["palm_id"],
                "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                "area_px": int(ys.size),
                "z_m": float(c.z_base),
                "base_uv": [float(v) for v in c.base_uv],
                "top_uv": [float(v) for v in c.top_uv],
                "defaulted": list(c.palm.get("defaulted", [])),
                "elev_estimated": bool(c.palm.get("elev_estimated", False)),
            }
        )
    union = np.where(labels > 0, 255, 0).astype(np.uint8)
    return MaskSet(
        union=union, labels=labels, instances=instances, method=method, params=asdict(params)
    )


def project_masks(
    palms: Iterable[Palm],
    K: Intrinsics,
    pose: CameraPose,
    depth_m: NDArray[Any] | None,
    params: ProjectParams | None = None,
    occluder: NDArray[Any] | None = None,
) -> ProjectResult:
    """Project ``palms`` (with ``enu_base``) into one frame.

    ``depth_m`` is the metric depth map (camera-frame z, NaN or non-positive = no surface); with
    ``None`` only the raw masks are produced and ``ProjectResult.depth`` is ``None``.
    ``occluder`` is the static occluder (non-zero = remove). Palms are labelled by their position
    in ``palms``, so a palm keeps its label across frames.
    """
    p = params or ProjectParams()
    h, w = K.height, K.width
    shape = (h, w)
    if depth_m is not None and depth_m.shape != shape:
        raise ConfigError(f"depth is {depth_m.shape}, intrinsics say {shape}")
    occ = _static_ok(occluder, shape)
    skipped = dict.fromkeys(SKIP_REASONS, 0)
    palm_list = list(palms)

    cands: list[_Candidate] = []
    raw_masks: list[NDArray[np.bool_]] = []
    depth_masks: list[NDArray[np.bool_]] = []
    for index, palm in enumerate(palm_list):
        corners = palm_billboard(palm, pose, p)
        uv, z = project(corners, pose, K)
        base = np.asarray(palm["enu_base"], dtype=np.float64)
        z_base = float(project(base[None, :], pose, K)[1][0])
        if z_base <= 0.0 or bool(np.any(z <= 0.0)):
            skipped[SKIP_BEHIND] += 1
            continue
        if float(np.linalg.norm(base - pose.position_enu)) > p.max_range_m:
            skipped[SKIP_RANGE] += 1
            continue
        uv = np.clip(uv, -_UV_LIMIT, _UV_LIMIT)
        base_uv = (uv[0] + uv[1]) / 2.0
        top_uv = (uv[2] + uv[3]) / 2.0
        if float(np.hypot(*(top_uv - base_uv))) < p.min_height_px:
            skipped[SKIP_SMALL] += 1
            continue
        box = _crop_box(uv, p.dilate_px + 1, h, w)
        if box is None:
            skipped[SKIP_OFFSCREEN] += 1
            continue
        x0, y0, x1, y1 = box
        geom = _fill_quad(uv, x0, y0, x1, y1)
        if not geom.any():
            skipped[SKIP_OFFSCREEN] += 1
            continue
        raw_masks.append(_dilate(geom, p.dilate_px))
        if depth_m is not None:
            d = np.asarray(depth_m[y0:y1, x0:x1], dtype=np.float64)
            tol = max(p.depth_tol_m, p.depth_tol_rel * z_base)
            with np.errstate(invalid="ignore"):
                ok = np.isfinite(d) & (d > 0) & (np.abs(d - z_base) <= tol)
            depth_masks.append(_dilate(geom & ok, p.dilate_px))
        cands.append(_Candidate(index, palm, z_base, base_uv, top_uv, geom, box))

    raw = _compose(cands, shape, occ, "project-raw", p, raw_masks)
    depth = None
    if depth_m is not None:
        depth = _compose(cands, shape, occ, "project-depth", p, depth_masks)
    n_raw = len(raw.instances)
    skipped[SKIP_OCCLUDED] = len(cands) - n_raw
    return ProjectResult(
        raw=raw,
        depth=depth,
        skipped=skipped,
        in_view=n_raw,
        in_view_depth=0 if depth is None else len(depth.instances),
    )


def param_fields() -> list[str]:
    """Names accepted by ``--params``."""
    return [f.name for f in fields(ProjectParams)]
