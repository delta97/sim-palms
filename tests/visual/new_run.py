"""Scaffold one in-sim visual run, or finalize its screenshots (TEST-102).

Plan: plans/detailed/06-testing.md#visual-run-format and #visual-protocol (steps 1 and 5).

    python -m tests.visual.new_run --site T1 --label phase2 --sim-version 1.9.24 --region-pkg 0.3.0
    python -m tests.visual.new_run finalize tests/visual/T1/2026-11-22_phase2

The create form (the default subcommand) makes ``tests/visual/<site>/<date>[_<label>]/`` with
``run.yaml``, ``checklist.md`` and ``raw/<variant>/``, and appends a ``pending`` row to
``tests/visual/test_log.md``. It refuses a placeholder site unless ``--allow-placeholder`` is
given, and refuses a run folder that already exists.

The finalize form takes the three raw screenshots of each variant, in capture order, and writes
``<variant>/VP1_street.jpg``, ``VP2_oblique.jpg`` and ``VP3_approach.jpg`` (JPEG q90, at most
2560 px wide). It needs Pillow (the ``dev`` extra).

Exit codes follow palmcore: 0 ok, 2 bad input or refusal (also argparse errors).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, cast

import yaml

from palmcore.errors import EXIT_OK, ConfigError, PalmfixError
from palmcore.log import get_logger
from tests.helpers.fixtures import REPO_ROOT
from tests.helpers.sites import SITES_FILE, Site, get_site

logger = get_logger(__name__)

VARIANTS: Final = ("nofix", "static", "live")
DEFAULT_VARIANTS: Final = ("nofix", "static")
# Viewpoint order is fixed by the protocol: visit VP1, VP2, VP3 in that order.
VIEWPOINT_FILES: Final = ("VP1_street.jpg", "VP2_oblique.jpg", "VP3_approach.jpg")
RAW_EXTENSIONS: Final = (".png", ".jpg", ".jpeg", ".bmp")
JPEG_QUALITY: Final = 90
MAX_WIDTH_PX: Final = 2560
DEFAULT_GRAPHICS_PROFILE: Final = "ref-v1"
# Written for values nobody has filled in yet. check_run refuses to pass while any remain.
UNSET: Final = "VERIFY"
REQUIRED_RUN_KEYS: Final = (
    "site",
    "date",
    "label",
    "tester",
    "sim_version",
    "sdk_version",
    "packages",
    "graphics_profile",
    "deviations",
    "time_local",
    "weather",
    "variants",
)

RUN_YAML: Final = "run.yaml"
CHECKLIST: Final = "checklist.md"
TEMPLATE: Final = "checklist_template.md"
PROFILES: Final = "graphics_profile.yaml"
TEST_LOG: Final = "test_log.md"
LOG_COLUMNS: Final = (
    "Date",
    "Site",
    "Label",
    "Variants",
    "Sim version",
    "Region pkg",
    "Result",
    "Run folder",
)
RESULT_COLUMN: Final = LOG_COLUMNS.index("Result")
FOLDER_COLUMN: Final = LOG_COLUMNS.index("Run folder")
RESULT_VALUES: Final = ("pending", "pass", "fail")
LABEL_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


class VisualRunError(ConfigError):
    """A run cannot be created or finalized: bad input, a refusal, or a missing file."""


# --- paths -------------------------------------------------------------------------------------


def visual_dir(root: Path = REPO_ROOT) -> Path:
    return root / "tests" / "visual"


def log_path(root: Path = REPO_ROOT) -> Path:
    return visual_dir(root) / TEST_LOG


def run_folder_name(day: dt.date, label: str | None) -> str:
    return day.isoformat() if label is None else f"{day.isoformat()}_{label}"


# --- argument checks ---------------------------------------------------------------------------


def _date_arg(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD, got {text!r}") from None


def _plain_arg(name: str, text: str) -> str:
    value = text.strip()
    if not value:
        raise VisualRunError(f"{name} must not be empty")
    if "|" in value or "\n" in value or "\r" in value:
        raise VisualRunError(f"{name} must not contain '|' or line breaks: {text!r}")
    return value


def _label_arg(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    value = text.strip()
    if not LABEL_RE.match(value):
        raise VisualRunError(
            f"--label must be letters, digits, '-' or '_' (max 40, starting with a letter "
            f"or digit), got {text!r}"
        )
    return value


def parse_variants(text: str) -> tuple[str, ...]:
    """Split a comma list such as ``nofix,static``; reject unknown and repeated names."""
    items = [item.strip() for item in text.split(",") if item.strip()]
    if not items:
        raise VisualRunError("--variants must name at least one variant")
    unknown = [item for item in items if item not in VARIANTS]
    if unknown:
        raise VisualRunError(
            f"variants must be from {', '.join(VARIANTS)}, got {', '.join(unknown)}"
        )
    if len(set(items)) != len(items):
        raise VisualRunError(f"--variants repeats a name: {text!r}")
    return tuple(items)


# --- YAML and text files -----------------------------------------------------------------------


def _load_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise VisualRunError(f"{path}: file not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise VisualRunError(f"{path}: cannot read: {exc}") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise VisualRunError(f"{path}: invalid YAML: {exc}") from exc


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise VisualRunError(f"{path}: file not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise VisualRunError(f"{path}: cannot read: {exc}") from exc


def load_run(run_dir: Path) -> dict[str, Any]:
    """Read ``run.yaml`` in a run folder. Raises VisualRunError if missing or not a mapping."""
    data = _load_yaml(run_dir / RUN_YAML)
    if not isinstance(data, dict):
        raise VisualRunError(f"{run_dir / RUN_YAML}: top level must be a mapping")
    return cast("dict[str, Any]", data)


def profile_names(root: Path = REPO_ROOT) -> list[str]:
    data = _load_yaml(visual_dir(root) / PROFILES)
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict) or not profiles:
        raise VisualRunError(f"{visual_dir(root) / PROFILES}: no profiles defined")
    return [str(name) for name in cast("dict[str, Any]", profiles)]


# --- test log ----------------------------------------------------------------------------------


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _format_row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _read_log_lines(root: Path) -> list[str]:
    path = log_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise VisualRunError(f"{path}: visual test log not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise VisualRunError(f"{path}: cannot read visual test log: {exc}") from exc
    return text.split("\n")


def _log_header_index(lines: list[str], path: Path) -> int:
    for index, line in enumerate(lines):
        if line.lstrip().startswith("|") and split_row(line) == list(LOG_COLUMNS):
            if index + 1 >= len(lines) or not lines[index + 1].lstrip().startswith("|---"):
                raise VisualRunError(f"{path}: table separator missing under the header")
            return index
    raise VisualRunError(f"{path}: table header does not match the plan's visual log format")


def _log_row_indexes(lines: list[str], header: int) -> list[int]:
    rows = []
    for index in range(header + 2, len(lines)):
        if not lines[index].lstrip().startswith("|"):
            break
        rows.append(index)
    return rows


def append_log_row(root: Path, cells: Sequence[str]) -> None:
    """Append one row after the last table row. Refuses a second row for the same run folder."""
    path = log_path(root)
    lines = _read_log_lines(root)
    header = _log_header_index(lines, path)
    rows = _log_row_indexes(lines, header)
    folder = cells[FOLDER_COLUMN]
    if any(split_row(lines[i])[FOLDER_COLUMN] == folder for i in rows):
        raise VisualRunError(f"{path}: a row for run folder {folder} already exists")
    insert_at = (rows[-1] if rows else header + 1) + 1
    lines.insert(insert_at, _format_row(cells))
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    logger.info("added visual log row %s to %s", folder, path)


def set_log_result(root: Path, folder: str, value: str) -> None:
    """Set the Result cell of the row whose Run folder cell is ``folder``."""
    if value not in RESULT_VALUES:
        raise VisualRunError(f"result must be one of {', '.join(RESULT_VALUES)}, got {value!r}")
    path = log_path(root)
    lines = _read_log_lines(root)
    header = _log_header_index(lines, path)
    matches = [
        i for i in _log_row_indexes(lines, header) if split_row(lines[i])[FOLDER_COLUMN] == folder
    ]
    if not matches:
        raise VisualRunError(
            f"{path}: no row for run folder {folder}; create the run with new_run first"
        )
    index = matches[0]
    cells = split_row(lines[index])
    cells[RESULT_COLUMN] = value
    lines[index] = _format_row(cells)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    logger.info("set %s result = %s in %s", folder, value, path)


# --- create ------------------------------------------------------------------------------------


def resolve_site(site_id: str, *, sites_file: Path, allow_placeholder: bool) -> Site:
    """Return the registry entry, refusing a placeholder unless explicitly allowed."""
    try:
        site = get_site(site_id, sites_file)
    except KeyError as exc:
        raise VisualRunError(str(exc.args[0])) from None
    if site.status == "placeholder" and not allow_placeholder:
        raise VisualRunError(
            f"site {site.id} is a placeholder: its bbox, viewpoints and flight are not defined "
            "yet. TEST-100 (on the sim PC) defines the test sites, and no visual run can be "
            "scaffolded for a placeholder until then. --allow-placeholder only rehearses the "
            "tooling; it never produces a result."
        )
    return site


def _fill_checklist(
    template: str, *, site: str, day: dt.date, label: str | None, tester: str
) -> str:
    fills = {
        "- Site:": site,
        "- Date:": day.isoformat(),
        "- Label:": label or "-",
        "- Tester:": tester,
    }
    out: list[str] = []
    seen: set[str] = set()
    for line in template.split("\n"):
        for prefix, value in fills.items():
            if line.startswith(prefix) and prefix not in seen:
                line = f"{prefix} {value}"
                seen.add(prefix)
        out.append(line)
    if seen != set(fills):
        missing = ", ".join(sorted(set(fills) - seen))
        raise VisualRunError(f"{TEMPLATE}: header lines missing: {missing}")
    return "\n".join(out)


def _run_yaml_text(data: dict[str, Any]) -> str:
    header = (
        "# Visual run (TEST-102). Filled in by tests/visual/new_run.py; edit tester, versions and\n"
        "# deviations by hand. Plan: plans/detailed/06-testing.md#visual-run-format.\n"
    )
    return header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def create_run(
    site_id: str,
    *,
    day: dt.date,
    label: str | None,
    sim_version: str,
    region_pkg: str,
    sdk_version: str = UNSET,
    assets_pkg: str = "none",
    tester: str = UNSET,
    variants: Sequence[str] = DEFAULT_VARIANTS,
    graphics_profile: str = DEFAULT_GRAPHICS_PROFILE,
    allow_placeholder: bool = False,
    root: Path = REPO_ROOT,
    sites_file: Path = SITES_FILE,
) -> Path:
    """Create the run folder, its files and a pending log row. Returns the run folder.

    Every check runs before anything is written, so a refusal leaves no partial folder.
    """
    site = resolve_site(site_id, sites_file=sites_file, allow_placeholder=allow_placeholder)
    label_value = _label_arg(label)
    sim = _plain_arg("--sim-version", sim_version)
    region = _plain_arg("--region-pkg", region_pkg)
    sdk = _plain_arg("--sdk-version", sdk_version)
    assets = _plain_arg("--assets-pkg", assets_pkg)
    who = _plain_arg("--tester", tester)
    chosen = parse_variants(",".join(variants))
    if graphics_profile not in profile_names(root):
        raise VisualRunError(
            f"graphics profile {graphics_profile!r} is not in {visual_dir(root) / PROFILES}; "
            f"known: {', '.join(profile_names(root))}"
        )
    template = _read_text(visual_dir(root) / TEMPLATE)
    checklist = _fill_checklist(template, site=site.id, day=day, label=label_value, tester=who)

    folder_name = run_folder_name(day, label_value)
    folder_cell = f"{site.id}/{folder_name}"
    run = visual_dir(root) / site.id / folder_name
    if run.exists():
        raise VisualRunError(f"{run} already exists; pick another --label or date")
    lines = _read_log_lines(root)
    header = _log_header_index(lines, log_path(root))
    if any(
        split_row(lines[i])[FOLDER_COLUMN] == folder_cell for i in _log_row_indexes(lines, header)
    ):
        raise VisualRunError(f"{log_path(root)}: a row for {folder_cell} already exists")

    run_data: dict[str, Any] = {
        "site": site.id,
        "site_status": site.status,
        "date": day.isoformat(),
        "label": label_value,
        "tester": who,
        "sim_version": sim,
        "sdk_version": sdk,
        "packages": {"region": region, "assets": assets},
        "graphics_profile": graphics_profile,
        "deviations": [],
        "flight": site.flight,
        "time_local": site.time_local,
        "weather": site.weather,
        "variants": list(chosen),
    }
    run.mkdir(parents=True)
    (run / RUN_YAML).write_text(_run_yaml_text(run_data), encoding="utf-8", newline="\n")
    (run / CHECKLIST).write_text(checklist, encoding="utf-8", newline="\n")
    for variant in chosen:
        (run / "raw" / variant).mkdir(parents=True)
    append_log_row(
        root,
        [
            day.isoformat(),
            site.id,
            label_value or "-",
            ",".join(chosen),
            sim,
            region,
            "pending",
            folder_cell,
        ],
    )
    logger.info("created visual run %s", run)
    return run


# --- finalize ----------------------------------------------------------------------------------


def _write_jpeg(image_mod: Any, src: Path, dst: Path) -> None:
    try:
        with image_mod.open(src) as img:
            rgb = img.convert("RGB")
        if rgb.width > MAX_WIDTH_PX:
            height = round(rgb.height * MAX_WIDTH_PX / rgb.width)
            rgb = rgb.resize((MAX_WIDTH_PX, height), image_mod.Resampling.LANCZOS)
        rgb.save(dst, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    except (OSError, ValueError) as exc:
        raise VisualRunError(f"{src}: cannot convert to {dst.name}: {exc}") from exc


def finalize_run(run_dir: Path, *, order: str = "mtime") -> dict[str, list[tuple[Path, Path]]]:
    """Write the named JPEGs for every variant. Returns ``{variant: [(raw, output), ...]}``.

    ``order`` is ``mtime`` (capture order by modification time) or ``name`` (by file name).
    Nothing is written unless every variant has exactly three screenshots.
    """
    if order not in ("mtime", "name"):
        raise VisualRunError(f"--order must be mtime or name, got {order!r}")
    try:
        from PIL import Image
    except ImportError:
        raise VisualRunError(
            "finalize needs Pillow: pip install pillow (or pip install -e '.[dev]')"
        ) from None

    run = load_run(run_dir)
    raw_variants = run.get("variants")
    if not isinstance(raw_variants, list):
        raise VisualRunError(f"{run_dir / RUN_YAML}: variants must be a list")
    variants = parse_variants(",".join(str(v) for v in raw_variants))

    plans: dict[str, list[tuple[Path, Path]]] = {}
    for variant in variants:
        raw_dir = run_dir / "raw" / variant
        if not raw_dir.is_dir():
            raise VisualRunError(f"{raw_dir}: missing; copy the {variant} screenshots there")
        sources = [
            p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() in RAW_EXTENSIONS
        ]
        if len(sources) != 3:
            raise VisualRunError(
                f"{raw_dir}: expected exactly 3 screenshots (VP1, VP2, VP3) with extensions "
                f"{', '.join(RAW_EXTENSIONS)}, found {len(sources)}"
            )
        if order == "mtime":
            mtimes = [p.stat().st_mtime_ns for p in sources]
            if len(set(mtimes)) != len(mtimes):
                raise VisualRunError(
                    f"{raw_dir}: two screenshots share a modification time, so capture order "
                    "is unknown; rerun with --order name after renaming them in capture order"
                )
            sources.sort(key=lambda p: p.stat().st_mtime_ns)
        else:
            sources.sort(key=lambda p: p.name)
        plans[variant] = [
            (src, run_dir / variant / name)
            for src, name in zip(sources, VIEWPOINT_FILES, strict=True)
        ]

    for variant, pairs in plans.items():
        (run_dir / variant).mkdir(exist_ok=True)
        for src, dst in pairs:
            _write_jpeg(Image, src, dst)
    logger.info("finalized visual run %s", run_dir)
    return plans


# --- CLI ---------------------------------------------------------------------------------------

SUBCOMMANDS: Final = ("create", "finalize")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.visual.new_run",
        description=(
            "Scaffold a dated in-sim visual run (default: create), or finalize its screenshots."
        ),
        epilog=(
            "examples:\n"
            "  python -m tests.visual.new_run --site T1 --label phase2 "
            "--sim-version 1.9.24.0 --region-pkg 0.3.0\n"
            "  python -m tests.visual.new_run finalize tests/visual/T1/2026-11-22_phase2"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="{create,finalize}")

    create = sub.add_parser("create", help="make a run folder and a pending log row (default)")
    create.add_argument("--site", required=True, metavar="ID", help="site id, e.g. T1")
    create.add_argument("--date", type=_date_arg, default=None, metavar="YYYY-MM-DD")
    create.add_argument("--label", default=None, help="optional short label, e.g. phase2")
    create.add_argument(
        "--variants",
        default=",".join(DEFAULT_VARIANTS),
        metavar="LIST",
        help="comma list from nofix,static,live (default nofix,static)",
    )
    create.add_argument("--sim-version", required=True, metavar="V")
    create.add_argument("--sdk-version", default=UNSET, metavar="V", help="default: VERIFY")
    create.add_argument("--region-pkg", required=True, metavar="VER")
    create.add_argument("--assets-pkg", default="none", metavar="VER", help="default: none")
    create.add_argument("--tester", default=UNSET, metavar="NAME", help="default: VERIFY")
    create.add_argument(
        "--graphics-profile",
        default=DEFAULT_GRAPHICS_PROFILE,
        metavar="NAME",
        help="profile in tests/visual/graphics_profile.yaml (default ref-v1)",
    )
    create.add_argument(
        "--allow-placeholder",
        action="store_true",
        help="rehearse the tooling on a placeholder site; never for a real result",
    )
    create.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        metavar="DIR",
        help="repo root holding tests/visual (default: this repo; tests use a temp dir)",
    )

    fin = sub.add_parser("finalize", help="turn raw screenshots into named JPEGs")
    fin.add_argument("run_dir", type=Path, metavar="RUN_DIR")
    fin.add_argument(
        "--order",
        choices=("mtime", "name"),
        default="mtime",
        help="capture order: modification time (default) or file name",
    )
    return parser


def _create_next_steps(run: Path, unset: list[str]) -> list[str]:
    lines = [f"created {run}"]
    if unset:
        lines.append(f"still VERIFY in run.yaml (fill in by hand): {', '.join(unset)}")
    lines += [
        "next, as in tests/visual/PROTOCOL.md:",
        "  1. sim: graphics profile per run.yaml, 12:00 local, clear weather; note deviations",
        f"  2. nofix: deactivate the fix package, visit VP1, VP2, VP3;"
        f" copy shots to {run}/raw/nofix/",
        f"  3. static: activate the fix package, same viewpoints; copy shots to {run}/raw/static/",
        f"  4. python -m tests.visual.new_run finalize {run}",
        f"  5. fill {run / CHECKLIST}",
        f"  6. python -m tests.visual.check_run {run} --update-log",
    ]
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] not in (*SUBCOMMANDS, "-h", "--help"):
        args_list = ["create", *args_list]
    parser = _build_parser()
    args = parser.parse_args(args_list)
    try:
        if args.command == "finalize":
            plans = finalize_run(args.run_dir, order=args.order)
            for variant, pairs in plans.items():
                for src, dst in pairs:
                    print(
                        f"{variant}: {src.as_posix()} -> {dst.relative_to(args.run_dir).as_posix()}"
                    )
            print("check the mapping above against capture order before filling the checklist")
            return EXIT_OK

        day = args.date or dt.date.today()
        root: Path = args.root
        run = create_run(
            args.site,
            day=day,
            label=args.label,
            sim_version=args.sim_version,
            region_pkg=args.region_pkg,
            sdk_version=args.sdk_version,
            assets_pkg=args.assets_pkg,
            tester=args.tester,
            variants=parse_variants(args.variants),
            graphics_profile=args.graphics_profile,
            allow_placeholder=args.allow_placeholder,
            root=root,
            sites_file=SITES_FILE,
        )
        unset = [
            name
            for name, value in (("tester", args.tester), ("sdk_version", args.sdk_version))
            if value == UNSET
        ]
        print("\n".join(_create_next_steps(run, unset)))
        return EXIT_OK
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
