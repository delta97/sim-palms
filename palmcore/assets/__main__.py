"""CLI: python -m palmcore.assets (build-manifest, validate). Exit 0 ok, 1 failures, 2 usage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from palmcore.assets.manifest import build_manifest, dump_manifest, validate_manifest
from palmcore.errors import PalmfixError
from palmcore.log import setup_logging

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m palmcore.assets", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-manifest", help="generate manifest.json from the yaml specs")
    build.add_argument("--assets-dir", type=Path, default=Path("assets"))
    build.add_argument("--out", type=Path, default=None, help="default: <assets-dir>/manifest.json")
    build.add_argument("--check", action="store_true", help="exit 1 if --out is stale")
    build.add_argument(
        "--include-draft", action="store_true", help="keep draft species (preview manifests only)"
    )

    val = sub.add_parser("validate", help="check a manifest")
    val.add_argument("--manifest", type=Path, default=Path("assets/manifest.json"))
    return parser


def _build(args: argparse.Namespace) -> int:
    assets_dir: Path = args.assets_dir
    out: Path = args.out or assets_dir / "manifest.json"
    text = dump_manifest(build_manifest(assets_dir, include_draft=args.include_draft))
    if args.check:
        try:
            current = out.read_bytes().decode("utf-8")
        except OSError as exc:
            print(f"error: cannot read {out}: {exc}", file=sys.stderr)
            return EXIT_FAIL
        if current != text:
            print(f"stale: {out} differs from the generated manifest", file=sys.stderr)
            return EXIT_FAIL
        print(f"ok: {out} is up to date")
        return EXIT_OK
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {out}")
    return EXIT_OK


def _validate(args: argparse.Namespace) -> int:
    problems = validate_manifest(args.manifest)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        return EXIT_FAIL
    print(f"ok: {args.manifest}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    setup_logging(-1)
    try:
        if args.command == "build-manifest":
            return _build(args)
        return _validate(args)
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
