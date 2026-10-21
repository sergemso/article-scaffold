"""Zenodo deposit metadata: valid JSON, license vocabulary, no invented ids."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from conftest import render, run


def _load(project: Path) -> dict:
    return json.loads((project / ".zenodo.json").read_text())


def test_default_deposit_shape(tmp_path: Path) -> None:
    data = _load(render(tmp_path=tmp_path))
    assert data["title"] == "A Test Manuscript"
    assert data["description"] == "A short abstract used by the render tests."
    assert data["upload_type"] == "publication"
    assert data["publication_type"] == "preprint"
    assert data["access_right"] == "open"
    assert data["language"] == "en"
    assert data["license"] == "cc-by-4.0"
    assert data["communities"] == []
    assert isinstance(data["version"], str)
    assert data["creators"] == [
        {
            "name": "Ada Lovelace",
            "orcid": "0000-0002-1825-0097",
            "affiliation": "Analytical Engine Institute",
        }
    ]
    assert "doi" not in data
    assert "related_identifiers" not in data


def test_doi_is_optional_and_omitted_when_empty(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, doi="10.5281/zenodo.1234567")
    data = _load(project)
    assert data["doi"] == "10.5281/zenodo.1234567"
    assert "related_identifiers" not in data


def test_empty_orcid_and_affiliation_are_omitted(tmp_path: Path) -> None:
    data = _load(render(tmp_path=tmp_path, author_orcid="", author_affiliation=""))
    assert data["creators"] == [{"name": "Ada Lovelace"}]


def test_multiple_creators(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    metadata_path = project / "metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text())
    metadata["creators"] = [
        {
            "name": "Ada Lovelace",
            "orcid": "0000-0002-1825-0097",
            "affiliation": "Analytical Engine Institute",
        },
        {"name": "Charles Babbage"},
    ]
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True))

    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout
    data = _load(project)
    assert data["creators"] == [
        {
            "name": "Ada Lovelace",
            "orcid": "0000-0002-1825-0097",
            "affiliation": "Analytical Engine Institute",
        },
        {"name": "Charles Babbage"},
    ]


@pytest.mark.parametrize(
    ("spdx", "zenodo_id"),
    [
        ("CC-BY-4.0", "cc-by-4.0"),
        ("MIT", "mit"),
        ("CC0-1.0", "cc0-1.0"),
        ("Apache-2.0", "apache-2.0"),
        ("CC-BY-SA-4.0", "cc-by-sa-4.0"),
    ],
)
def test_license_mapping(tmp_path: Path, spdx: str, zenodo_id: str) -> None:
    data = _load(render(tmp_path=tmp_path, license=spdx))
    assert data["license"] == zenodo_id


def test_unknown_license_is_omitted(tmp_path: Path) -> None:
    data = _load(render(tmp_path=tmp_path, license="Proprietary"))
    assert "license" not in data


def test_publication_type_article(tmp_path: Path) -> None:
    data = _load(render(tmp_path=tmp_path, manuscript_type="Journal Article"))
    assert data["publication_type"] == "article"
