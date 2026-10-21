"""The selected paper license and the MIT code license must be installed."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from conftest import render

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "{{cookiecutter.repo_name}}" / "licenses"


def _config() -> dict:
    return json.loads((ROOT / "cookiecutter.json").read_text())


def _metadata(project: Path) -> dict:
    return yaml.safe_load((project / "metadata.yaml").read_text())


def test_only_supported_licenses_are_offered() -> None:
    assert _config()["license"] == ["CC-BY-4.0", "MIT"]


def test_vendored_license_texts_are_complete() -> None:
    cc_by = (VENDORED / "CC-BY-4.0.txt").read_text()
    mit = (VENDORED / "MIT.txt").read_text()
    assert len(cc_by) > 10_000
    assert "Creative Commons Attribution 4.0 International" in cc_by
    assert len(mit) > 500
    assert "MIT License" in mit
    assert "THE SOFTWARE IS PROVIDED" in mit


def test_cc_by_paper_has_cc_by_license_and_mit_code_license(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, license="CC-BY-4.0")

    assert (project / "LICENSE").read_bytes() == (VENDORED / "CC-BY-4.0.txt").read_bytes()
    assert (project / "LICENSE-CODE").read_bytes() == (VENDORED / "MIT.txt").read_bytes()
    assert (project / "licenses" / "CC-BY-4.0.txt").is_file()
    assert (project / "licenses" / "MIT.txt").is_file()

    readme = (project / "README.md").read_text()
    assert "[CC-BY-4.0](LICENSE)" in readme
    assert "[MIT](LICENSE-CODE)" in readme

    metadata = _metadata(project)
    assert metadata["license"] == "CC-BY-4.0"
    assert metadata["license_code"] == "MIT"


def test_mit_paper_has_a_single_mit_license(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, license="MIT")

    assert (project / "LICENSE").read_bytes() == (VENDORED / "MIT.txt").read_bytes()
    assert not (project / "LICENSE-CODE").exists()

    readme = (project / "README.md").read_text()
    assert "[MIT](LICENSE)" in readme
    assert "[MIT](LICENSE-CODE)" not in readme
    assert "LICENSE-CODE" not in readme

    metadata = _metadata(project)
    assert metadata["license"] == "MIT"
    assert metadata["license_code"] == "MIT"
