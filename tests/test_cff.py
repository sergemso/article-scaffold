"""CITATION.cff must be valid CFF 1.2.0 and keep version/date strings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import SPECIAL_ABSTRACT, SPECIAL_TITLE, render

CFFCONVERT = Path(sys.executable).with_name("cffconvert")


def _load(project: Path) -> dict:
    return yaml.safe_load((project / "CITATION.cff").read_text())


def _validate(project: Path) -> None:
    if not CFFCONVERT.is_file():
        pytest.skip("cffconvert is not installed")
    result = subprocess.run(
        [str(CFFCONVERT), "--validate", "-i", str(project / "CITATION.cff")],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_default_cff_has_valid_types_and_string_version(tmp_path: Path) -> None:
    cff = _load(render(tmp_path=tmp_path))
    assert cff["cff-version"] == "1.2.0"
    assert cff["type"] == "software"
    assert cff["preferred-citation"]["type"] == "unpublished"
    assert isinstance(cff["version"], str)
    assert isinstance(cff["date-released"], str)
    assert cff["authors"][0]["family-names"] == "Lovelace"
    assert cff["keywords"] == ["testing", "metadata"]
    _validate(render(tmp_path=tmp_path / "validate"))


def test_version_that_looks_like_a_float_stays_a_string(tmp_path: Path) -> None:
    cff = _load(render(tmp_path=tmp_path, version="1.0"))
    assert cff["version"] == "1.0"
    assert isinstance(cff["version"], str)


def test_doi_is_an_identifier(tmp_path: Path) -> None:
    cff = _load(render(tmp_path=tmp_path, doi="10.5281/zenodo.1234567"))
    identifiers = cff["identifiers"]
    assert identifiers[0]["type"] == "doi"
    assert identifiers[0]["value"] == "10.5281/zenodo.1234567"
    assert cff["preferred-citation"]["identifiers"][0]["value"] == "10.5281/zenodo.1234567"


def test_empty_optional_fields_are_omitted(tmp_path: Path) -> None:
    cff = _load(render(tmp_path=tmp_path, author_orcid="", author_affiliation=""))
    author = cff["authors"][0]
    assert "orcid" not in author
    assert "affiliation" not in author
    assert "identifiers" not in cff


def test_hostile_title_round_trips_and_validates(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, title=SPECIAL_TITLE, abstract=SPECIAL_ABSTRACT)
    cff = _load(project)
    assert cff["title"] == SPECIAL_TITLE
    assert cff["abstract"] == SPECIAL_ABSTRACT
    assert isinstance(cff["version"], str)
    _validate(project)
