"""Automated asset checks: ``python -m palmcore.assets check``.

Rules, levels and the check table: ``plans/detailed/03-palm-assets.md`` (W3). Every threshold
comes from ``assets/budgets.yaml``; nothing numeric is hard-coded here. The GUID check (model
XML GUID equals the manifest GUID) is ASSET-007's.

Layout read: ``<assets>/PackageSources/modelLib/<species>/<model_name>/<model_name>_LOD<n>.gltf``
plus textures referenced by the glTF files (exporter output: ``.../<species>/texture/``).
Until ASSET-007 parses model XML, LOD files are found by name.
VERIFY (ASSET-004): the exporter's real LOD file names, texture folder and node names. Node
(Blender object) names are not checked: the exporter may rewrite them.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from palmcore.assets.gltf_stats import GltfError, GltfStats, read_gltf, read_png_size
from palmcore.assets.manifest import (
    MODEL_LIB_DIR,
    Measured,
    SpeciesSpec,
    VariantSpec,
    _mapping,
    _number,
    _read_yaml,
    load_species_specs,
    model_name,
)
from palmcore.errors import ConfigError
from palmcore.paths import Paths

Level = Literal["ERROR", "WARN"]

LOD_COUNT: Final = 4
BUDGETS_NAME: Final = "budgets.yaml"
TEXTURE_DIR: Final = "texture"
MATERIAL_PARTS: Final = ("trunk", "fronds", "skirt", "crownshaft", "cards")
TEXTURE_PARTS: Final = ("bark", "fronds", "skirt", "crownshaft", "cards")
TEXTURE_MAPS: Final = ("albedo", "normal", "orm")
MASKED_PARTS: Final = ("fronds", "skirt", "cards")  # alpha MASK and doubleSided
_AXES: Final = {"x": 0, "y": 1, "z": 2}
_LOD_FILE_RE: Final = re.compile(r"^(?P<stem>.+)_LOD(?P<n>\d+)\.(?P<ext>gltf|glb|bin)$")


@dataclass(frozen=True)
class CheckResult:
    level: Level
    check: str
    subject: str
    message: str


@dataclass(frozen=True)
class Budgets:
    """Thresholds from ``budgets.yaml``."""

    up_axis: int
    lod_triangles: tuple[tuple[int, int], ...]  # (min, max) for LOD0 to LOD3
    florida_lod0_max: int
    max_primitives: int
    max_primitives_lod3: int
    height_lod0_vs_spec: float
    height_lod_vs_lod0: float
    base_range: tuple[float, float]
    crown_tolerance: float
    textures: Mapping[str, tuple[int, int]]
    florida_texture_factor: float


# --- budgets ------------------------------------------------------------------------------


def _int(value: Any, where: str) -> int:
    number = _number(value, where, positive=False)
    if not number.is_integer() or number < 0:
        raise ConfigError(f"{where}: expected a non-negative integer, got {value!r}")
    return int(number)


def _pair(value: Any, where: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ConfigError(f"{where}: expected a list of two numbers")
    return (_number(value[0], where, positive=False), _number(value[1], where, positive=False))


def load_budgets(path: Path) -> Budgets:
    """Read and validate ``budgets.yaml``. Raises ``ConfigError``."""
    data = _mapping(_read_yaml(path), str(path))

    def section(key: str) -> dict[str, Any]:
        return _mapping(data.get(key), f"{path}: {key}")

    up = data.get("up_axis")
    if up not in _AXES:
        raise ConfigError(f"{path}: up_axis must be one of {sorted(_AXES)}, got {up!r}")
    lods = section("lod_triangles")
    by_lod = {str(k): v for k, v in lods.items()}
    tri: list[tuple[int, int]] = []
    for n in range(LOD_COUNT):
        entry = _mapping(by_lod.get(str(n)), f"{path}: lod_triangles[{n}]")
        lo = _int(entry.get("min"), f"{path}: lod_triangles[{n}].min")
        hi = _int(entry.get("max"), f"{path}: lod_triangles[{n}].max")
        if lo > hi:
            raise ConfigError(f"{path}: lod_triangles[{n}] min {lo} is above max {hi}")
        tri.append((lo, hi))
    prims = section("max_primitives")
    heights = section("height_tolerance")
    base_lo, base_hi = _pair(data.get("base_z_range"), f"{path}: base_z_range")
    if base_lo > base_hi:
        raise ConfigError(f"{path}: base_z_range is reversed")
    textures: dict[str, tuple[int, int]] = {}
    for role, size in section("textures").items():
        w, h = _pair(size, f"{path}: textures.{role}")
        textures[str(role)] = (int(w), int(h))
    return Budgets(
        up_axis=_AXES[up],
        lod_triangles=tuple(tri),
        florida_lod0_max=_int(data.get("florida_lod0_max"), f"{path}: florida_lod0_max"),
        max_primitives=_int(prims.get("default"), f"{path}: max_primitives.default"),
        max_primitives_lod3=_int(prims.get("lod3"), f"{path}: max_primitives.lod3"),
        height_lod0_vs_spec=_number(heights.get("lod0_vs_spec"), f"{path}: lod0_vs_spec"),
        height_lod_vs_lod0=_number(heights.get("lod_vs_lod0"), f"{path}: lod_vs_lod0"),
        base_range=(base_lo, base_hi),
        crown_tolerance=_number(data.get("crown_tolerance"), f"{path}: crown_tolerance"),
        textures=textures,
        florida_texture_factor=_number(
            data.get("florida_texture_factor"), f"{path}: florida_texture_factor"
        ),
    )


def find_budgets(assets_dir: Path) -> Path:
    """``<assets_dir>/budgets.yaml`` if present, else the repository's ``assets/budgets.yaml``."""
    local = assets_dir / BUDGETS_NAME
    if local.is_file():
        return local
    return Paths.resolve().repo_root / "assets" / BUDGETS_NAME


# --- geometry helpers ---------------------------------------------------------------------


def _top(stats: GltfStats, axis: int) -> float | None:
    return None if stats.bbox_max is None else stats.bbox_max[axis]


def _bottom(stats: GltfStats, axis: int) -> float | None:
    return None if stats.bbox_min is None else stats.bbox_min[axis]


def _crown(stats: GltfStats, axis: int) -> float | None:
    """Largest horizontal extent (the two axes that are not up)."""
    if stats.bbox_min is None or stats.bbox_max is None:
        return None
    return max(stats.bbox_max[i] - stats.bbox_min[i] for i in range(3) if i != axis)


def _lod_files(model_dir: Path, name: str) -> dict[int, Path]:
    """LOD glTF files by LOD number, found by name (``<name>_LOD<n>.gltf``)."""
    found: dict[int, Path] = {}
    for path in sorted(model_dir.glob(f"{name}_LOD*.gltf")):
        match = _LOD_FILE_RE.match(path.name)
        if match and match["stem"] == name:
            found[int(match["n"])] = path
    return found


def measure_models(budgets: Budgets) -> Callable[[Path], Measured]:
    """A ``build_manifest`` measure function reading LOD0 to LOD3 glTF files by name.

    Height is the LOD0 top along the up axis, crown the LOD0 horizontal extent. LODs whose
    file is absent stay ``None`` so yaml targets are used.
    """

    def measure(model_dir: Path) -> Measured:
        name = model_dir.name
        files = _lod_files(model_dir, name)
        stats = {n: read_gltf(path) for n, path in files.items() if n < LOD_COUNT}
        tris: tuple[int | None, ...] = tuple(
            stats[n].triangles if n in stats else None for n in range(LOD_COUNT)
        )
        lod0 = stats.get(0)
        height = None if lod0 is None else _top(lod0, budgets.up_axis)
        crown = None if lod0 is None else _crown(lod0, budgets.up_axis)
        return Measured(
            native_height_m=height,
            crown_diam_m=crown,
            triangles=tris if any(t is not None for t in tris) else None,
        )

    return measure


# --- checks -------------------------------------------------------------------------------


class _Run:
    """Collects results for one ``run_checks`` call."""

    def __init__(self, assets_dir: Path, budgets: Budgets) -> None:
        self.assets_dir = assets_dir
        self.b = budgets
        self.results: list[CheckResult] = []

    def error(self, check: str, subject: str, message: str) -> None:
        self.results.append(CheckResult("ERROR", check, subject, message))

    def warn(self, check: str, subject: str, message: str) -> None:
        self.results.append(CheckResult("WARN", check, subject, message))

    # -- per model -----------------------------------------------------------------------

    def model(self, spec: SpeciesSpec, vs: VariantSpec, referenced: set[Path]) -> bool:
        """Check one model; return False when its folder does not exist."""
        name = model_name(spec.species, vs.variant)
        model_dir = self.assets_dir / MODEL_LIB_DIR / spec.species / name
        if not model_dir.is_dir():
            if spec.status != "draft":
                self.error("LOD count", name, f"model folder is missing: {model_dir}")
            return False
        files = self._naming_and_lods(model_dir, name)
        if sorted(files) != list(range(LOD_COUNT)):
            missing = [n for n in range(LOD_COUNT) if n not in files]
            extra = sorted(n for n in files if n >= LOD_COUNT)
            parts = [f"missing LOD{n}" for n in missing] + [f"extra LOD{n}" for n in extra]
            self.error("LOD count", name, f"need exactly {LOD_COUNT} LOD glTFs: {', '.join(parts)}")
        stats: dict[int, GltfStats] = {}
        for n in sorted(n for n in files if n < LOD_COUNT):
            try:
                stats[n] = read_gltf(files[n])
            except GltfError as exc:
                self.error("glTF", files[n].name, str(exc))
        for n, st in stats.items():
            subject = files[n].name
            self._triangles(spec, n, st, subject)
            self._primitives(n, st, subject)
            self._base(st, subject)
            self._crown(vs, st, subject)
            self._alpha_and_materials(spec, st, subject)
            self._textures(spec, files[n], st, referenced)
            for message in st.warnings:
                self.warn("glTF", subject, message)
        self._heights(vs, stats, files)
        if sorted(stats) == list(range(LOD_COUNT)):
            counts = [stats[n].triangles for n in range(LOD_COUNT)]
            if any(a <= b for a, b in itertools.pairwise(counts)):
                self.error("Monotonic", name, f"triangles must strictly decrease: {counts}")
        return True

    def _naming_and_lods(self, model_dir: Path, name: str) -> dict[int, Path]:
        lods: dict[int, Path] = {}
        for path in sorted(p for p in model_dir.iterdir() if p.is_file()):
            fname = path.name
            if not fname.isascii() or " " in fname:
                self.error("Naming", fname, "file names must be ASCII with no spaces")
            suffix = path.suffix.lower()
            match = _LOD_FILE_RE.match(fname)
            ok_lod = bool(match and match["stem"] == name)
            if suffix == ".glb":
                self.error("glTF", fname, "binary .glb is not supported yet (ASSET-007); use .gltf")
            elif suffix == ".gltf":
                if ok_lod and match:
                    lods[int(match["n"])] = path
                else:
                    self.error("Naming", fname, f"LOD files must be {name}_LOD<n>.gltf")
            elif suffix == ".bin" and not ok_lod:
                self.error("Naming", fname, f"buffers must be {name}_LOD<n>.bin")
            elif suffix == ".xml" and fname != f"{name}.xml":
                self.error("Naming", fname, f"model XML must be {name}.xml")
        return lods

    def _triangles(self, spec: SpeciesSpec, n: int, st: GltfStats, subject: str) -> None:
        lo, hi = self.b.lod_triangles[n]
        if n == 0 and spec.set == "florida":
            hi = self.b.florida_lod0_max
            lo = min(lo, hi)
        if st.triangles > hi:
            self.error("Triangle budget", subject, f"LOD{n} has {st.triangles} triangles, max {hi}")
        elif st.triangles < lo:
            self.warn("Triangle budget", subject, f"LOD{n} has {st.triangles} triangles, min {lo}")

    def _primitives(self, n: int, st: GltfStats, subject: str) -> None:
        limit = self.b.max_primitives_lod3 if n == LOD_COUNT - 1 else self.b.max_primitives
        if st.primitives > limit:
            self.warn("Primitives", subject, f"{st.primitives} primitives, max {limit}")

    def _base(self, st: GltfStats, subject: str) -> None:
        bottom = _bottom(st, self.b.up_axis)
        if bottom is None:
            self.error("Base", subject, "no geometry with POSITION min/max")
            return
        lo, hi = self.b.base_range
        if not lo <= bottom <= hi:
            self.error("Base", subject, f"bottom {bottom:.3f} m is outside [{lo}, {hi}]")

    def _crown(self, vs: VariantSpec, st: GltfStats, subject: str) -> None:
        crown = _crown(st, self.b.up_axis)
        if crown is None:
            return
        tol = self.b.crown_tolerance
        if abs(crown - vs.crown_diam_m) > tol * vs.crown_diam_m:
            self.warn(
                "Crown",
                subject,
                f"horizontal extent {crown:.3f} m vs spec {vs.crown_diam_m} m "
                f"(tolerance {tol:.0%})",
            )

    def _heights(
        self, vs: VariantSpec, stats: Mapping[int, GltfStats], files: Mapping[int, Path]
    ) -> None:
        axis = self.b.up_axis
        top0 = _top(stats[0], axis) if 0 in stats else None
        if top0 is not None:
            tol = self.b.height_lod0_vs_spec
            if abs(top0 - vs.native_height_m) > tol * vs.native_height_m:
                self.error(
                    "Height",
                    files[0].name,
                    f"LOD0 top {top0:.3f} m vs spec {vs.native_height_m} m (tolerance {tol:.0%})",
                )
        if top0 is None or top0 <= 0:
            return
        tol = self.b.height_lod_vs_lod0
        for n in sorted(stats):
            top = _top(stats[n], axis)
            if n == 0 or top is None:
                continue
            if abs(top - top0) > tol * top0:
                self.error(
                    "Height",
                    files[n].name,
                    f"LOD{n} top {top:.3f} m vs LOD0 {top0:.3f} m (tolerance {tol:.0%})",
                )

    def _alpha_and_materials(self, spec: SpeciesSpec, st: GltfStats, subject: str) -> None:
        pattern = re.compile(rf"^mat_{spec.species}_(?P<part>{'|'.join(MATERIAL_PARTS)})$")
        for mat in st.materials:
            if mat.alpha_mode == "BLEND":
                self.error("Alpha mode", subject, f"material {mat.name!r} uses BLEND")
            match = pattern.match(mat.name)
            if not match:
                self.error(
                    "Naming",
                    subject,
                    f"material {mat.name!r} must be "
                    f"mat_{spec.species}_<{'|'.join(MATERIAL_PARTS)}>",
                )
                continue
            if match["part"] in MASKED_PARTS:
                if mat.alpha_mode != "MASK":
                    self.error(
                        "Alpha mode",
                        subject,
                        f"material {mat.name!r} must be MASK, is {mat.alpha_mode}",
                    )
                if not mat.double_sided:
                    self.error("Alpha mode", subject, f"material {mat.name!r} must be doubleSided")

    # -- textures ------------------------------------------------------------------------

    def _textures(
        self, spec: SpeciesSpec, gltf: Path, st: GltfStats, referenced: set[Path]
    ) -> None:
        for uri in st.image_uris:
            if uri.startswith("data:"):
                self.warn("Textures", gltf.name, "embedded data-URI image is not checked")
                continue
            path = (gltf.parent / uri).resolve()
            if path in referenced:
                continue
            referenced.add(path)
            if not path.is_file():
                self.error("Textures", gltf.name, f"referenced image does not exist: {uri}")
                continue
            self.texture(spec, path)

    def texture(self, spec: SpeciesSpec, path: Path) -> None:
        """Naming, PNG, power-of-two and max-size checks for one texture file."""
        fname = path.name
        pattern = re.compile(
            rf"^tx_{spec.species}_(?P<part>{'|'.join(TEXTURE_PARTS)})_(?P<map>{'|'.join(TEXTURE_MAPS)})\.png$"
        )
        match = pattern.match(fname)
        if not match:
            self.error(
                "Naming",
                fname,
                f"texture must be tx_{spec.species}_<part>_<map>.png "
                f"(part {'|'.join(TEXTURE_PARTS)}, map {'|'.join(TEXTURE_MAPS)})",
            )
        try:
            width, height = read_png_size(path)
        except GltfError as exc:
            self.error("Textures", fname, str(exc))
            return
        if any(side & (side - 1) for side in (width, height)):
            self.error("Textures", fname, f"{width}x{height} is not power-of-two")
        if not match:
            return
        role = f"{match['part']}_{match['map']}"
        limit = self.b.textures.get(role) or self.b.textures.get(match["map"])
        if limit is None:
            self.warn("Textures", fname, f"no size budget for role {role!r} in budgets.yaml")
            return
        factor = self.b.florida_texture_factor if spec.set == "florida" else 1.0
        max_w, max_h = limit[0] * factor, limit[1] * factor
        if width > max_w or height > max_h:
            self.error(
                "Textures", fname, f"{width}x{height} exceeds max {max_w:g}x{max_h:g} for {role}"
            )

    def unreferenced(self, spec: SpeciesSpec, referenced: set[Path]) -> None:
        tex_dir = self.assets_dir / MODEL_LIB_DIR / spec.species / TEXTURE_DIR
        if not tex_dir.is_dir():
            return
        for path in sorted(tex_dir.glob("*.png")):
            if path.resolve() not in referenced:
                self.warn("Textures", path.name, "not referenced by any LOD glTF")
                self.texture(spec, path)

    def stray_model_dirs(self, spec: SpeciesSpec) -> None:
        species_dir = self.assets_dir / MODEL_LIB_DIR / spec.species
        if not species_dir.is_dir():
            return
        expected = {model_name(spec.species, v.variant) for v in spec.variants}
        for path in sorted(p for p in species_dir.iterdir() if p.is_dir()):
            if path.name != TEXTURE_DIR and path.name not in expected:
                self.warn(
                    "Naming", path.name, f"folder is not a variant of {spec.species} in its spec"
                )


def run_checks(
    assets_dir: Path, species: str | None = None, budgets: Budgets | None = None
) -> list[CheckResult]:
    """Run every asset check except GUID (ASSET-007) and return the findings.

    Models are found from ``<assets_dir>/species/*.yaml``. Draft species with no model folder
    are skipped; other species must have all four LODs. ``budgets`` defaults to
    ``<assets_dir>/budgets.yaml``, falling back to the repository's ``assets/budgets.yaml``.
    """
    loaded = budgets or load_budgets(find_budgets(assets_dir))
    specs = load_species_specs(assets_dir)
    if species is not None:
        if species not in specs:
            raise ConfigError(f"unknown species {species!r}; known: {', '.join(sorted(specs))}")
        specs = {species: specs[species]}
    run = _Run(assets_dir, loaded)
    for spec in specs.values():
        referenced: set[Path] = set()
        found = [
            run.model(spec, vs, referenced) for vs in sorted(spec.variants, key=lambda v: v.variant)
        ]
        if any(found):  # nothing to say about textures of a species with no models yet
            run.unreferenced(spec, referenced)
            run.stray_model_dirs(spec)
    return run.results


def format_results(results: Sequence[CheckResult]) -> list[str]:
    """Aligned table rows (header first) plus a final ``N errors, M warnings`` line."""
    errors = sum(r.level == "ERROR" for r in results)
    warnings = len(results) - errors
    rows = [
        ("LEVEL", "CHECK", "SUBJECT", "MESSAGE"),
        *((r.level, r.check, r.subject, r.message) for r in results),
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    lines = ["  ".join(row[i].ljust(widths[i]) for i in range(3)) + "  " + row[3] for row in rows]
    if not results:
        lines = []
    lines.append(f"{errors} errors, {warnings} warnings")
    return lines
