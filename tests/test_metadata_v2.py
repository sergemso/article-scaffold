"""Tests for the v2 authors/affiliations loader and its v1 compatibility."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT, render

TEMPLATE_SCRIPTS = ROOT / "{{cookiecutter.repo_name}}" / "scripts"


@pytest.fixture(scope="session")
def metadata_core():
    sys.path.insert(0, str(TEMPLATE_SCRIPTS))
    try:
        importlib.invalidate_caches()
        yield importlib.import_module("article.metadata")
    finally:
        sys.path.remove(str(TEMPLATE_SCRIPTS))


def _codes(metadata: dict) -> list[str]:
    return [item["code"] for item in metadata["_metadata_diagnostics"]]


def _legacy_metadata() -> dict:
    return {
        "title": "A Legacy Paper",
        "author": {
            "name": "Ada Lovelace",
            "orcid": "0000-0002-1825-0097",
            "affiliation": "Analytical Engine Institute",
        },
        "github_user": "test-user",
        "repo_name": "articles.legacy",
    }


def _v2_metadata() -> dict:
    return {
        "metadata_schema": 2,
        "title": "A Multi-Author Paper",
        "authors": [
            {
                "name": "Ada Lovelace",
                "orcid": "0000-0002-1825-0097",
                "affiliations": ["afi"],
                "corresponding": True,
                "email": "ada@example.org",
            },
            {
                "name": "Plato",
            },
        ],
        "affiliations": {
            "afi": {
                "name": "Analytical Engine Institute",
                "ror": "https://ror.org/02mhbdp94",
            }
        },
        "github_user": "test-user",
        "repo_name": "articles.multi",
    }


def test_orcid_checksum_validation(metadata_core) -> None:
    assert metadata_core.valid_orcid("0000-0002-1825-0097")
    assert metadata_core.valid_orcid("0000-0002-1694-233X")
    assert not metadata_core.valid_orcid("0000-0002-1825-0098")
    assert not metadata_core.valid_orcid("0000-0002-1825")
    assert not metadata_core.valid_orcid("")
    assert metadata_core.is_valid_orcid("0000-0002-1825-0097")


def test_ror_shape_validation(metadata_core) -> None:
    assert metadata_core.valid_ror("https://ror.org/02mhbdp94")
    assert not metadata_core.valid_ror("http://ror.org/02mhbdp94")
    assert not metadata_core.valid_ror("https://ror.org/not-an-id")
    assert not metadata_core.valid_ror("")
    assert metadata_core.is_valid_ror("https://ror.org/02mhbdp94")


def test_legacy_author_is_normalized_with_deprecation_warning(metadata_core) -> None:
    normalized = metadata_core.normalize_metadata(_legacy_metadata())

    assert normalized["_metadata_schema"] == 1
    assert normalized["_metadata_ok"] is True
    author = normalized["_authors"][0]
    assert author["name"] == "Ada Lovelace"
    assert (author["given"], author["family"]) == ("Ada", "Lovelace")
    assert author["orcid"] == "0000-0002-1825-0097"
    assert author["corresponding"] is True
    assert author["affiliations"] == ["aff1"]
    assert normalized["_affiliations"]["aff1"]["name"] == "Analytical Engine Institute"
    assert normalized["_author_full"] == "Ada Lovelace"
    assert normalized["_author_family"] == "Lovelace"
    assert normalized["_author_given"] == "Ada"
    assert normalized["_author_affiliation"] == "Analytical Engine Institute"
    assert "W020" in _codes(normalized)
    assert normalized["_metadata_warnings"][0]["code"] == "W020"


def test_top_level_legacy_author_fields_are_accepted(metadata_core) -> None:
    normalized = metadata_core.normalize_metadata(
        {
            "title": "Top-level legacy",
            "author_name": "Ada Lovelace",
            "author_orcid": "0000-0002-1825-0097",
            "author_affiliation": "Analytical Engine Institute",
        }
    )

    assert normalized["_author_full"] == "Ada Lovelace"
    assert normalized["_authors"][0]["orcid"] == "0000-0002-1825-0097"
    assert "W020" in _codes(normalized)


def test_multi_author_and_affiliation_mapping(metadata_core) -> None:
    normalized = metadata_core.normalize_metadata(_v2_metadata())

    assert normalized["_metadata_schema"] == 2
    assert normalized["_metadata_ok"] is True
    assert normalized["_metadata_warnings"] == []
    assert [author["name"] for author in normalized["_authors"]] == [
        "Ada Lovelace",
        "Plato",
    ]
    assert normalized["_authors"][0]["affiliations"] == ["afi"]
    assert normalized["_authors"][0]["affiliation_names"] == [
        "Analytical Engine Institute"
    ]
    assert normalized["_authors"][0]["email"] == "ada@example.org"
    assert normalized["_affiliations"]["afi"]["ror"] == "https://ror.org/02mhbdp94"
    assert [creator["name"] for creator in normalized["_creators"]] == [
        "Ada Lovelace",
        "Plato",
    ]
    assert normalized["_creators"][0]["affiliation"] == "Analytical Engine Institute"


def test_mononym_is_normalized_without_a_given_name(metadata_core) -> None:
    data = {
        "metadata_schema": 2,
        "title": "Mononym",
        "authors": [{"name": "Plato", "corresponding": True}],
    }
    normalized = metadata_core.normalize_metadata(data)

    author = normalized["_authors"][0]
    assert author["name"] == "Plato"
    assert author["given"] == ""
    assert author["family"] == "Plato"
    assert normalized["_author_full"] == "Plato"
    assert normalized["_author_family"] == "Plato"
    assert normalized["_metadata_ok"] is True


def test_explicit_given_family_and_particles_are_preserved(metadata_core) -> None:
    data = {
        "metadata_schema": 2,
        "title": "Particles",
        "authors": [
            {
                "given": "Ludwig",
                "family": "van Beethoven",
                "corresponding": True,
            }
        ],
    }
    normalized = metadata_core.normalize_metadata(data)

    author = normalized["_authors"][0]
    assert author["name"] == "Ludwig van Beethoven"
    assert author["given"] == "Ludwig"
    assert author["family"] == "van Beethoven"


def test_invalid_orcid_is_an_actionable_error(metadata_core) -> None:
    data = _v2_metadata()
    data["authors"][1]["orcid"] = "0000-0002-1825-0098"
    normalized = metadata_core.normalize_metadata(data)

    assert normalized["_metadata_ok"] is False
    assert "E021" in _codes(normalized)
    message = next(
        item["message"] for item in normalized["_metadata_diagnostics"]
        if item["code"] == "E021"
    )
    assert "ORCID" in message
    assert metadata_core.validate_metadata(data).ok is False


def test_duplicate_affiliations_are_reported(metadata_core) -> None:
    duplicate_name = _v2_metadata()
    duplicate_name["affiliations"]["second"] = {"name": "Analytical Engine Institute"}
    normalized = metadata_core.normalize_metadata(duplicate_name)
    assert "E022" in _codes(normalized)

    duplicate_id = _v2_metadata()
    duplicate_id["affiliations"] = [
        {"id": "afi", "name": "One"},
        {"id": "afi", "name": "Two"},
    ]
    normalized = metadata_core.normalize_metadata(duplicate_id)
    assert "E022" in _codes(normalized)


def test_unknown_affiliation_reference_is_reported(metadata_core) -> None:
    data = _v2_metadata()
    data["authors"][0]["affiliations"] = ["missing"]

    normalized = metadata_core.normalize_metadata(data)

    assert normalized["_metadata_ok"] is False
    assert "E024" in _codes(normalized)


def test_missing_corresponding_author_is_reported(metadata_core) -> None:
    data = _v2_metadata()
    data["authors"] = [
        {"name": "Ada Lovelace", "affiliations": ["afi"]},
        {"name": "Plato"},
    ]
    normalized = metadata_core.normalize_metadata(data)

    assert normalized["_metadata_ok"] is False
    assert "E023" in _codes(normalized)
    assert any(
        "corresponding" in item["message"]
        for item in normalized["_metadata_diagnostics"]
        if item["code"] == "E023"
    )


def test_invalid_ror_is_an_actionable_error(metadata_core) -> None:
    data = _v2_metadata()
    data["affiliations"]["afi"]["ror"] = "https://ror.org/nope"
    normalized = metadata_core.normalize_metadata(data)

    assert normalized["_metadata_ok"] is False
    assert "E025" in _codes(normalized)


def test_v2_and_legacy_produce_the_same_author_derivations(metadata_core) -> None:
    legacy = metadata_core.normalize_metadata(_legacy_metadata())
    v2 = metadata_core.normalize_metadata(
        {
            "metadata_schema": 2,
            "title": "A Legacy Paper",
            "authors": [
                {
                    "name": "Ada Lovelace",
                    "orcid": "0000-0002-1825-0097",
                    "affiliations": ["aff1"],
                    "corresponding": True,
                }
            ],
            "affiliations": {
                "aff1": {"name": "Analytical Engine Institute"}
            },
            "github_user": "test-user",
            "repo_name": "articles.legacy",
        }
    )

    for key in (
        "_author_full",
        "_author_family",
        "_author_given",
        "_author_orcid",
        "_author_affiliation",
        "_creators",
    ):
        assert v2[key] == legacy[key]
    assert metadata_core.gen_citation_cff(v2) == metadata_core.gen_citation_cff(legacy)
    assert metadata_core.gen_zenodo_json(v2) == metadata_core.gen_zenodo_json(legacy)


def test_default_metadata_is_schema_v2_and_validates(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    data = yaml.safe_load((project / "metadata.yaml").read_text())
    schema = yaml.safe_load((project / "schemas" / "metadata.schema.json").read_text())

    assert data["metadata_schema"] == 2
    assert data["authors"]
    assert "author" not in data
    jsonschema.validate(data, schema)

    sys.path.insert(0, str(project))
    try:
        importlib.invalidate_caches()
        metadata = importlib.import_module("scripts.article.metadata")
        normalized = metadata.load_metadata(project / "metadata.yaml")
    finally:
        sys.path.remove(str(project))

    assert normalized["_metadata_schema"] == 2
    assert normalized["_metadata_ok"] is True
    assert "W020" not in _codes(normalized)
    assert normalized["_author_full"] == "Ada Lovelace"
    assert normalized["_author_affiliation"] == "Analytical Engine Institute"
