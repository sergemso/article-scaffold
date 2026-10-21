"""Offline schema/type checks plus opt-in network checks for Zenodo and CFF."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

import pytest
import yaml
from conftest import render, run

CFFCONVERT = Path(sys.executable).with_name("cffconvert")
ZENODO_LICENSES = {
    "cc-by-4.0",
    "cc-by-sa-4.0",
    "cc-by-nc-4.0",
    "cc-by-nd-4.0",
    "cc-by-nc-sa-4.0",
    "cc-by-nc-nd-4.0",
    "cc0-1.0",
    "mit",
    "apache-2.0",
    "gpl-3.0",
    "lgpl-3.0",
    "bsd-3-clause",
    "bsd-2-clause",
}
NETWORK = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK") != "1",
    reason="set RUN_NETWORK=1 to run network checks",
)


def _cff(project: Path) -> dict:
    return yaml.safe_load((project / "CITATION.cff").read_text())


def _zenodo(project: Path) -> dict:
    return json.loads((project / ".zenodo.json").read_text())


def _rewrite_license(project: Path, value: str) -> Path:
    """Bypass the cookiecutter choice to exercise the generator's SPDX map."""
    path = project / "metadata.yaml"
    metadata = yaml.safe_load(path.read_text())
    metadata["license"] = value
    path.write_text(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True))
    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout
    return project


def _assert_cff_types(cff: dict) -> None:
    for key in ("cff-version", "message", "title", "type", "authors"):
        assert key in cff, key
    assert cff["cff-version"] == "1.2.0"
    assert cff["type"] == "software"
    assert isinstance(cff["version"], str)
    assert isinstance(cff["date-released"], str)
    assert isinstance(cff["authors"], list) and cff["authors"]
    assert cff["preferred-citation"]["type"] == "unpublished"
    assert all(isinstance(kw, str) for kw in cff.get("keywords", []))


def _assert_zenodo_types(data: dict) -> None:
    for key in (
        "title",
        "description",
        "creators",
        "keywords",
        "upload_type",
        "publication_type",
        "access_right",
        "version",
        "language",
        "communities",
    ):
        assert key in data, key
    assert data["upload_type"] == "publication"
    assert data["publication_type"] in {"preprint", "article"}
    assert data["access_right"] == "open"
    assert isinstance(data["version"], str)
    assert isinstance(data["creators"], list) and data["creators"]
    for creator in data["creators"]:
        assert isinstance(creator.get("name"), str) and creator["name"]
        for optional in ("orcid", "affiliation"):
            if optional in creator:
                assert creator[optional]
    assert isinstance(data["keywords"], list)
    assert all(isinstance(kw, str) for kw in data["keywords"])
    assert isinstance(data["communities"], list)
    for community in data["communities"]:
        assert isinstance(community, dict) and community.get("identifier")
    if "license" in data:
        assert data["license"] in ZENODO_LICENSES
    if "doi" in data:
        assert isinstance(data["doi"], str) and data["doi"]
    assert "related_identifiers" not in data


def test_cff_offline_schema(tmp_path: Path) -> None:
    _assert_cff_types(_cff(render(tmp_path=tmp_path)))


def test_cffconvert_offline_validation(tmp_path: Path) -> None:
    if not CFFCONVERT.is_file():
        pytest.skip("cffconvert is not installed")
    project = render(tmp_path=tmp_path)
    result = subprocess.run(
        [str(CFFCONVERT), "--validate", "-i", str(project / "CITATION.cff")],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_zenodo_offline_schema(tmp_path: Path) -> None:
    _assert_zenodo_types(_zenodo(render(tmp_path=tmp_path)))


def test_doi_shapes_offline(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, doi="10.5281/zenodo.1234567")
    cff = _cff(project)
    zenodo = _zenodo(project)
    _assert_cff_types(cff)
    _assert_zenodo_types(zenodo)
    assert cff["identifiers"][0]["type"] == "doi"
    assert zenodo["doi"] == "10.5281/zenodo.1234567"


def test_multi_creator_shapes_offline(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    metadata_path = project / "metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text())
    metadata["creators"] = [
        {"name": "Ada Lovelace", "orcid": "0000-0002-1825-0097"},
        {"name": "Charles Babbage"},
    ]
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True))
    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout
    _assert_zenodo_types(_zenodo(project))


@pytest.mark.network
@NETWORK
def test_zenodo_license_ids_resolve(tmp_path: Path) -> None:
    projects = [
        render(tmp_path=tmp_path / "cc-by", license="CC-BY-4.0"),
        render(tmp_path=tmp_path / "mit", license="MIT"),
        _rewrite_license(render(tmp_path=tmp_path / "cc0"), "CC0-1.0"),
    ]
    for project in projects:
        data = _zenodo(project)
        with urlopen(
            f"https://zenodo.org/api/vocabularies/licenses/{data['license']}",
            timeout=20,
        ) as response:
            assert response.status == 200


@pytest.mark.network
@NETWORK
def test_zenodo_community_resolves() -> None:
    with urlopen("https://zenodo.org/api/communities/zenodo", timeout=20) as response:
        assert response.status == 200
        payload = json.loads(response.read())
        assert payload.get("id")


@pytest.mark.network
@NETWORK
def test_cffconvert_validates_network(tmp_path: Path) -> None:
    if not CFFCONVERT.is_file():
        pytest.skip("cffconvert is not installed")
    project = render(tmp_path=tmp_path)
    result = subprocess.run(
        [str(CFFCONVERT), "--validate", "-i", str(project / "CITATION.cff")],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
