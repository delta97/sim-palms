"""Local CI: run the same checks the GitHub workflows ran, on this machine.

The GitHub Actions workflows (.github/workflows/python.yml and tracking.yml) are disabled
in the repository settings; this script replaces them. Run it from the repo root before
merging a task branch into main:

    python scripts/ci.py            # lint, types, tests with coverage gate, tracking checks
    python scripts/ci.py --quick    # skip tests marked slow
    python scripts/ci.py --install  # first create/refresh .venv with all extras

It uses the repo's .venv (created with --install). Exit code is 0 only if every step passes.
Standard library only, so it runs before the venv exists.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRAS = "dev,scan,lidar,gen,fx"
COVERAGE_MIN = 85


def venv_python() -> Path:
    win = ROOT / ".venv" / "Scripts" / "python.exe"
    return win if win.exists() else ROOT / ".venv" / "bin" / "python"


def run(name: str, cmd: list[str]) -> bool:
    print(f"\n=== {name}: {' '.join(cmd)}", flush=True)
    start = time.perf_counter()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    ok = subprocess.run(cmd, cwd=ROOT, env=env).returncode == 0
    print(f"=== {name}: {'PASS' if ok else 'FAIL'} ({time.perf_counter() - start:.0f}s)", flush=True)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install", action="store_true", help="create/refresh .venv with all extras first")
    ap.add_argument("--quick", action="store_true", help="skip tests marked slow")
    args = ap.parse_args()

    if args.install:
        if not venv_python().exists() and not run("venv", [sys.executable, "-m", "venv", ".venv"]):
            return 1
        if not run("install", [str(venv_python()), "-m", "pip", "install", "-q", "-e", f".[{EXTRAS}]"]):
            return 1

    py = str(venv_python())
    if not Path(py).exists():
        print("No .venv found. Run: python scripts/ci.py --install", file=sys.stderr)
        return 2

    marker = "not network and not sim" + (" and not slow" if args.quick else "")
    steps = [
        ("ruff check", [py, "-m", "ruff", "check", "."]),
        ("ruff format", [py, "-m", "ruff", "format", "--check", "."]),
        ("mypy", [py, "-m", "mypy"]),
        (
            "pytest",
            [py, "-m", "pytest", "-q", "-m", marker, "--cov=palmcore",
             "--cov-report=term-missing:skip-covered", f"--cov-fail-under={COVERAGE_MIN}"],
        ),
        ("tasks validate", [sys.executable, "scripts/tasks.py", "validate"]),
        ("tasks conflicts", [sys.executable, "scripts/tasks.py", "conflicts"]),
    ]
    results = [(name, run(name, cmd)) for name, cmd in steps]

    print("\n=== Summary")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
