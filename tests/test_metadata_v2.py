"""Tests for the v2 authors/affiliations loader and its v1 compatibility."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT, render, run

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


def _related(entries: list[dict], **extra: object) -> dict:
    return {**_v2_metadata(), "related_identifiers": entries, **extra}


def _entry(identifier: str, relation: str = "isPartOf", scheme: str = "doi") -> dict:
    return {"identifier": identifier, "relation": relation, "scheme": scheme}


def test_related_identifiers_absent_by_default(metadata_core) -> None:
    normalized = metadata_core.normalize_metadata(_v2_metadata())
    assert normalized["_metadata_ok"] is True
    assert "related_identifiers" not in normalized


def test_valid_series_is_normalised(metadata_core) -> None:
    data = _related(
        [
            _entry("https://doi.org/10.5281/zenodo.111", "isPartOf"),
            _entry("doi:10.5281/zenodo.222", "continues"),
            _entry("https://example.org/series", "isSupplementTo", "url"),
        ]
    )
    normalized = metadata_core.normalize_metadata(data)

    assert normalized["_metadata_ok"] is True
    assert [e["identifier"] for e in normalized["related_identifiers"]] == [
        "10.5281/zenodo.111",
        "10.5281/zenodo.222",
        "https://example.org/series",
    ]
    assert data["related_identifiers"][0]["identifier"].startswith("https://doi.org/")
    deposit = json.loads(metadata_core.gen_zenodo_json(normalized))
    assert deposit["related_identifiers"][1] == _entry(
        "10.5281/zenodo.222", "continues"
    )


@pytest.mark.parametrize(
    ("entry", "code"),
    [
        (_entry("10.5281/zenodo.1", "isFriendOf"), "E030"),
        (_entry("10.5281/zenodo.1", "isPartOf", "handle"), "E031"),
        (_entry("not-a-doi"), "E032"),
        (_entry("http://example.org/x", "isPartOf", "url"), "E033"),
        (_entry("https://github.com/test-user/articles.multi", "isPartOf", "url"), "E034"),
        (_entry("https://github.com/Test-User/other.public", "isPartOf", "url"), "E034"),
        ({"identifier": "10.5281/zenodo.1", "relation": "isPartOf"}, "E026"),
    ],
)
def test_invalid_related_identifier_is_reported(metadata_core, entry, code) -> None:
    normalized = metadata_core.normalize_metadata(_related([entry]))

    assert normalized["_metadata_ok"] is False
    assert code in _codes(normalized)
    message = next(
        i["message"] for i in normalized["_metadata_diagnostics"] if i["code"] == code
    )
    assert "related_identifiers entry 1" in message


def test_companion_url_is_allowed_other_owner_repos_are_not(metadata_core) -> None:
    companion_url = "https://github.com/test-user/articles.multi.public"
    data = _related([_entry(companion_url, "isSupplementedBy", "url")])

    assert metadata_core.validate_metadata(data).ok is False
    assert metadata_core.validate_metadata(
        data, companion_repo="test-user/articles.multi.public"
    ).ok
    other = _related([_entry("https://github.com/test-user/secret", "isPartOf", "url")])
    assert not metadata_core.validate_metadata(
        other, companion_repo="test-user/articles.multi.public"
    ).ok


def test_related_identifiers_schema(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    schema = yaml.safe_load((project / "schemas" / "metadata.schema.json").read_text())
    base = yaml.safe_load((project / "metadata.yaml").read_text())

    jsonschema.validate({**base, "related_identifiers": [_entry("10.1/x")]}, schema)
    for bad in (
        _entry("10.1/x", "isFriendOf"),
        _entry("10.1/x", "isPartOf", "handle"),
        {**_entry("10.1/x"), "extra": "key"},
        {"identifier": "10.1/x", "relation": "isPartOf"},
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**base, "related_identifiers": [bad]}, schema)


def _set_related(project: Path, entries: list[dict]) -> None:
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data["related_identifiers"] = entries
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def test_make_validate_rejects_private_repo_link(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    private = "https://github.com/test-user/articles.test"
    _set_related(project, [_entry(private, "isSupplementTo", "url")])

    result = run(project, "python3", "scripts/validate-paper.py")

    assert result.returncode == 1
    assert "E034" in result.stderr
    assert "related_identifiers entry 1" in result.stderr
    assert private in result.stderr


def test_valid_series_passes_validate_and_reaches_zenodo_json(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _set_related(
        project,
        [
            _entry("https://doi.org/10.5281/zenodo.111", "isPartOf"),
            _entry("10.5281/zenodo.222", "continues"),
        ],
    )

    assert run(project, "python3", "scripts/validate-paper.py").returncode == 0
    assert run(project, "make", "metadata").returncode == 0
    deposit = json.loads((project / ".zenodo.json").read_text())
    assert deposit["related_identifiers"] == [
        _entry("10.5281/zenodo.111", "isPartOf"),
        _entry("10.5281/zenodo.222", "continues"),
    ]
