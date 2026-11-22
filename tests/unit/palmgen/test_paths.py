from pathlib import Path

from palmgen import paths


def test_defaults() -> None:
    assert paths.default_config("san-diego") == Path("regions/san-diego.yaml")
    assert paths.default_palms("san-diego") == Path("build/scan/san-diego/palms.geojson")
    assert paths.default_buildings("san-diego") == Path("build/scan/san-diego/buildings.geojson")
    assert paths.default_airports("san-diego") == Path("data/san-diego/masks/airports.geojson")
    assert paths.default_manifest() == Path("assets/manifest.json")


def test_package_and_project_dir() -> None:
    assert paths.package_name("san-diego") == "palmfix-san-diego"
    assert paths.project_dir("build", "san-diego") == Path("build/palmfix-san-diego")
    assert paths.project_dir(Path("out"), "x") == Path("out/palmfix-x")
