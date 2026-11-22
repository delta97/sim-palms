"""Blob masks from raw depth and colour alone (plan 08, A8; task FX-011).

No palm database and no calibration: gradients of ``ln d`` do not depend on the depth scale. A blob
is a narrow object nearer than what lies left and right of it, with an olive-green to brown colour,
a depth edge on its sides and a plausible size. Every threshold comes from ``HeuristicParams``
(``config/heuristic.yaml``); pixel sizes are scaled by ``H / reference_height_px``.

What it needs: colour (RGB uint8) and raw depth ``d`` (0 = sky) from ``frames/NNNNNN.depthraw.npy``.
Whether near is larger ``d`` (reversed-Z) is read from ``session.json`` key ``reversed`` by the
command. VERIFY: the real MSFS 2024 depth convention (FX-001); the default is reversed.

Known limit: a blob wider than the opening (61 px at 1440 p) is not a narrow peak, so it is
missed. The synthetic scenes in ``palmfx.offline.synth`` (flat olive boxes) are a synthetic
stand-in for the green blob look, not a claim about what MSFS renders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from numpy.typing import NDArray
from scipy import ndimage

from palmcore.errors import ConfigError
from palmfx.offline.depth import DMIN
from palmfx.offline.session import MaskSet

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "heuristic.yaml"

REJECT_HEIGHT = "height"
REJECT_ASPECT = "aspect"
REJECT_FILL = "fill"
REJECT_EDGE = "edge_support"

# BGR colours for the debug overlay.
_YELLOW = (0, 255, 255)
_GREEN = (0, 255, 0)
_RED = (0, 0, 255)

_INT_FIELDS = {"hue_min", "hue_max", "sat_min", "val_min", "val_max"}


@dataclass(frozen=True)
class HeuristicParams:
    """All thresholds of the heuristic; see ``config/heuristic.yaml`` for their meaning."""

    reference_height_px: float
    protrusion_min: float
    opening_width_px: float
    hue_min: int
    hue_max: int
    sat_min: int
    val_min: int
    val_max: int
    edge_min: float
    sobel_scale: float
    edge_tolerance_px: float
    close_px: float
    min_height_px: float
    min_aspect: float
    min_fill: float
    min_edge_support: float
    dilate_px: float
    regrow_depth_tol: float

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> HeuristicParams:
        """Load and validate a config file (default: the packaged ``heuristic.yaml``)."""
        src = Path(path) if path is not None else DEFAULT_CONFIG
        try:
            doc = yaml.safe_load(src.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigError(f"cannot read heuristic config {src}: {exc}") from exc
        if not isinstance(doc, dict):
            raise ConfigError(f"{src} must hold a mapping")
        names = [f.name for f in fields(cls)]
        missing = sorted(set(names) - doc.keys())
        extra = sorted(doc.keys() - set(names))
        if missing or extra:
            raise ConfigError(f"{src}: missing keys {missing}, unknown keys {extra}")
        try:
            values = {k: (int if k in _INT_FIELDS else float)(doc[k]) for k in names}
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{src}: non-numeric value ({exc})") from exc
        params = cls(**values)  # type: ignore[arg-type]
        params.validate(str(src))
        return params

    def validate(self, label: str = "params") -> None:
        if self.reference_height_px <= 0:
            raise ConfigError(f"{label}: reference_height_px must be positive")
        if not (0 <= self.hue_min <= self.hue_max <= 179):
            raise ConfigError(f"{label}: need 0 <= hue_min <= hue_max <= 179")
        if not (0 <= self.val_min <= self.val_max <= 255):
            raise ConfigError(f"{label}: need 0 <= val_min <= val_max <= 255")
        if not (0.0 <= self.min_fill <= 1.0 and 0.0 <= self.min_edge_support <= 1.0):
            raise ConfigError(f"{label}: min_fill and min_edge_support must be in [0, 1]")
        for name in ("opening_width_px", "sobel_scale", "protrusion_min", "edge_min"):
            if getattr(self, name) <= 0:
                raise ConfigError(f"{label}: {name} must be positive")


def _px(value: float, scale: float, minimum: int = 0) -> int:
    return max(minimum, round(value * scale))


def _odd(n: int) -> int:
    return n if n % 2 == 1 else n + 1


def _kernel(size: int) -> NDArray[np.uint8]:
    return np.asarray(cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)), dtype=np.uint8)


def _near_positive_log(depth_raw: NDArray[Any], reversed_z: bool) -> tuple[Any, Any]:
    """``(N, sky)``: ln depth oriented so that nearer is larger; sky is set to the minimum."""
    d = np.asarray(depth_raw, dtype=np.float64)
    sky = ~np.isfinite(d) | (d <= 0.0)
    log_d = np.log(np.maximum(np.where(sky, DMIN, d), DMIN))
    n = log_d if reversed_z else -log_d
    floor = float(n[~sky].min()) if (~sky).any() else 0.0
    return np.where(sky, floor, n), sky


def heuristic_masks(
    color_rgb: NDArray[np.uint8],
    depth_raw: NDArray[Any],
    params: HeuristicParams,
    reversed: bool = True,  # name fixed by the plan interface
    occluder: NDArray[Any] | None = None,
    debug: bool = False,
) -> MaskSet:
    """Detect blob instances; ``debug=True`` adds diagnostics to ``params["debug"]``."""
    if color_rgb.ndim != 3 or color_rgb.shape[2] != 3 or color_rgb.dtype != np.uint8:
        raise ConfigError("color_rgb must be an (H, W, 3) uint8 RGB array")
    h, w = color_rgb.shape[:2]
    if depth_raw.shape != (h, w):
        raise ConfigError(f"depth shape {depth_raw.shape} does not match colour {(h, w)}")
    occ = np.zeros((h, w), dtype=bool)
    if occluder is not None:
        if occluder.shape != (h, w):
            raise ConfigError(f"occluder shape {occluder.shape} does not match colour {(h, w)}")
        occ = np.asarray(occluder) > 0

    s = h / params.reference_height_px
    n, sky = _near_positive_log(depth_raw, reversed)

    # 2. protrusion over the horizontal opening.
    width = _odd(_px(params.opening_width_px, s, 3))
    background = ndimage.grey_opening(n, size=(1, width), mode="nearest")
    prot = (n - background) > params.protrusion_min

    # 3. colour.
    hsv = cv2.cvtColor(color_rgb, cv2.COLOR_RGB2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    colour = (
        (hue >= params.hue_min)
        & (hue <= params.hue_max)
        & (sat >= params.sat_min)
        & (val >= params.val_min)
        & (val <= params.val_max)
    )

    # 4. depth edges (support only).
    nf = n.astype(np.float32)
    gx = cv2.Sobel(nf, cv2.CV_32F, 1, 0, ksize=3, scale=params.sobel_scale)
    gy = cv2.Sobel(nf, cv2.CV_32F, 0, 1, ksize=3, scale=params.sobel_scale)
    edge = np.hypot(gx, gy) > params.edge_min
    tol = _px(params.edge_tolerance_px, s)
    if tol > 0:
        edge = cv2.dilate(edge.astype(np.uint8), _kernel(2 * tol + 1)) > 0

    # 5. candidates, closing, components.
    cand = prot & colour & ~sky & ~occ
    close = _px(params.close_px, s)
    cand_u8 = cand.astype(np.uint8)
    if close > 1:
        cand_u8 = cv2.morphologyEx(cand_u8, cv2.MORPH_CLOSE, _kernel(_odd(close)))
    cand_u8 &= (~occ).astype(np.uint8)
    count, comp, stats, _ = cv2.connectedComponentsWithStats(cand_u8, connectivity=8)

    # 6. component filters.
    min_h = _px(params.min_height_px, s, 1)
    kept: list[int] = []
    diag: list[dict[str, Any]] = []
    for k in range(1, count):
        x, y, bw, bh, area = (int(v) for v in stats[k])
        sel = comp[y : y + bh, x : x + bw] == k
        support = _edge_support(sel, edge[y : y + bh, x : x + bw])
        reasons: list[str] = []
        if bh < min_h:
            reasons.append(REJECT_HEIGHT)
        if bh / bw < params.min_aspect:
            reasons.append(REJECT_ASPECT)
        if area / (bw * bh) < params.min_fill:
            reasons.append(REJECT_FILL)
        if support < params.min_edge_support:
            reasons.append(REJECT_EDGE)
        if not reasons:
            kept.append(k)
        diag.append(
            {
                "component": k,
                "bbox": [x, y, x + bw - 1, y + bh - 1],
                "area_px": area,
                "height_px": bh,
                "aspect": round(bh / bw, 3),
                "fill": round(area / (bw * bh), 3),
                "edge_support": round(support, 3),
                "kept": not reasons,
                "reason": reasons[0] if reasons else None,
                "reasons": reasons,
            }
        )

    # 7. optional regrow, then dilate; labels follow the component order (raster scan of CCL).
    labels = np.zeros((h, w), dtype=np.uint16)
    for rank, k in enumerate(kept, start=1):
        region = comp == k
        if params.regrow_depth_tol > 0:
            region = _regrow(region, colour & ~sky & ~occ, n, params.regrow_depth_tol)
        labels[region & (labels == 0)] = rank
    dil = _px(params.dilate_px, s)
    if dil > 0 and kept:
        labels = np.asarray(cv2.dilate(labels, _kernel(2 * dil + 1)), dtype=np.uint16)
    labels[occ] = 0
    union = np.where(labels > 0, 255, 0).astype(np.uint8)

    out_params: dict[str, Any] = {
        **asdict(params),
        "reversed": bool(reversed),
        "scale": s,
        "opening_px": width,
    }
    if debug:
        out_params["debug"] = {"components": diag, "candidate_px": int(cand_u8.sum())}
    return MaskSet(
        union=union,
        labels=labels,
        instances=_instances(labels),
        method="heuristic",
        params=out_params,
    )


def _edge_support(sel: NDArray[np.bool_], edge: NDArray[np.bool_]) -> float:
    """Share of each row's leftmost and rightmost ``sel`` pixels that sit on a depth edge."""
    rows = np.nonzero(sel.any(axis=1))[0]
    if rows.size == 0:
        return 0.0
    left = sel.argmax(axis=1)[rows]
    right = sel.shape[1] - 1 - sel[:, ::-1].argmax(axis=1)[rows]
    hits = int(edge[rows, left].sum()) + int(edge[rows, right].sum())
    return hits / (2.0 * rows.size)


def _regrow(
    region: NDArray[np.bool_],
    colour_ok: NDArray[np.bool_],
    n: NDArray[np.float64],
    tol: float,
) -> NDArray[np.bool_]:
    """Add colour-matching pixels in the component's column span at the same depth (+-``tol``)."""
    cols = region.any(axis=0)
    centre = float(np.median(n[region]))
    near = np.abs(n - centre) <= np.log1p(tol)
    allowed = near & colour_ok & cols[None, :]
    grown, _ = ndimage.label(allowed | region, structure=np.ones((3, 3), dtype=bool))
    ids = np.unique(grown[region])
    return np.asarray(np.isin(grown, ids[ids > 0]))


def _instances(labels: NDArray[np.uint16]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for k, sl in enumerate(ndimage.find_objects(labels.astype(np.int32)), start=1):
        if sl is None:
            continue
        ys, xs = sl
        out.append(
            {
                "k": k,
                "palm_id": None,
                "bbox": [int(xs.start), int(ys.start), int(xs.stop - 1), int(ys.stop - 1)],
                "area_px": int(np.count_nonzero(labels[sl] == k)),
                "z_m": None,
                "base_uv": None,
                "top_uv": None,
            }
        )
    return out


def debug_overlay(color_rgb: NDArray[np.uint8], ms: MaskSet) -> NDArray[np.uint8]:
    """RGB image: components in yellow, kept in green, rejected in red with reason initials."""
    img = cv2.cvtColor(color_rgb, cv2.COLOR_RGB2BGR)
    comps = ms.params.get("debug", {}).get("components", [])
    thick = max(1, img.shape[0] // 360)
    for c in comps:
        x0, y0, x1, y1 = c["bbox"]
        cv2.rectangle(img, (x0 - 1, y0 - 1), (x1 + 1, y1 + 1), _YELLOW, thick)
    keep_mask = ms.union > 0
    img[keep_mask] = (0.5 * img[keep_mask] + 0.5 * np.array(_GREEN)).astype(np.uint8)
    for c in comps:
        x0, y0, x1, y1 = c["bbox"]
        colour = _GREEN if c["kept"] else _RED
        cv2.rectangle(img, (x0 - 2, y0 - 2), (x1 + 2, y1 + 2), colour, thick)
        if not c["kept"]:
            text = ",".join(r[:1].upper() for r in c["reasons"])
            cv2.putText(img, text, (x0, max(10, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, _RED, 1)
    return np.asarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
