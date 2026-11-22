"""Default path rules for palmgen. Paths are relative to the current working directory."""

from __future__ import annotations

from pathlib import Path


def default_config(region: str) -> Path:
    return Path("regions") / f"{region}.yaml"


def default_palms(region: str) -> Path:
    """Canonical palmscan output."""
    return Path("build") / "scan" / region / "palms.geojson"


def default_buildings(region: str) -> Path:
    """Canonical palmscan output."""
    return Path("build") / "scan" / region / "buildings.geojson"


def default_airports(region: str) -> Path:
    """Default ``--out`` of ``palmgen masks airports``.

    A build reads the airport mask from ``masks.airports.path`` in the region config.
    """
    return Path("data") / region / "masks" / "airports.geojson"


def default_manifest() -> Path:
    return Path("assets") / "manifest.json"


def package_name(region: str) -> str:
    return f"palmfix-{region}"


def project_dir(out: Path | str, region: str) -> Path:
    return Path(out) / package_name(region)
