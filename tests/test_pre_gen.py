"""Pre-generation validation and human-readable prompt labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from conftest import DEFAULT_CONTEXT, ROOT
from cookiecutter.exceptions import FailedHookException
from cookiecutter.main import cookiecutter


def _generate(tmp_path: Path, **overrides: str) -> Path:
    context = dict(DEFAULT_CONTEXT)
    context.update(overrides)
    output_dir = Path(tmp_path) / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    return Path(
        cookiecutter(
            str(ROOT),
            no_input=True,
            output_dir=str(output_dir),
            extra_context=context,
        )
    )


def _rejected(tmp_path: Path, capfd, **overrides: str) -> str:
    with pytest.raises(FailedHookException):
        _generate(tmp_path, **overrides)
    captured = capfd.readouterr()
    assert "Traceback" not in captured.err
    return captured.err


def test_default_context_still_renders_without_prompts(tmp_path: Path) -> None:
    project = _generate(tmp_path)
    assert (project / "metadata.yaml").is_file()


def test_empty_orcid_is_accepted(tmp_path: Path) -> None:
    project = _generate(tmp_path, author_orcid="")
    data = yaml.safe_load((project / "metadata.yaml").read_text())
    assert data["authors"][0]["orcid"] == ""


def test_valid_doi_and_orcid_are_accepted(tmp_path: Path) -> None:
    project = _generate(
        tmp_path,
        author_orcid="0000-0002-1694-233X",
        doi="10.5281/zenodo.1234567",
    )
    data = yaml.safe_load((project / "metadata.yaml").read_text())
    assert data["authors"][0]["orcid"] == "0000-0002-1694-233X"
    assert data["doi"] == "10.5281/zenodo.1234567"


def test_invalid_topic_is_rejected(tmp_path: Path, capfd) -> None:
    err = _rejected(
        tmp_path,
        capfd,
        topic="Bad Topic",
        repo_name="articles.valid",
    )
    assert "ERROR: topic:" in err
    assert "lowercase" in err


def test_invalid_repo_name_is_rejected(tmp_path: Path, capfd) -> None:
    err = _rejected(tmp_path, capfd, repo_name="bad repo")
    assert "ERROR: repo_name:" in err


def test_empty_title_is_rejected(tmp_path: Path, capfd) -> None:
    err = _rejected(tmp_path, capfd, title="   ")
    assert "ERROR: title:" in err


def test_non_semver_is_rejected(tmp_path: Path, capfd) -> None:
    err = _rejected(tmp_path, capfd, version="1.0")
    assert "ERROR: version:" in err


def test_invalid_license_is_rejected_before_the_hook(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="choices are"):
        _generate(tmp_path, license="GPL-3.0")


def test_invalid_doi_is_rejected(tmp_path: Path, capfd) -> None:
    err = _rejected(tmp_path, capfd, doi="https://doi.org/10.1234/example")
    assert "ERROR: doi:" in err
    assert "bare DOI" in err


def test_invalid_orcid_checksum_is_rejected(tmp_path: Path, capfd) -> None:
    err = _rejected(tmp_path, capfd, author_orcid="0000-0002-1825-0098")
    assert "ERROR: author_orcid:" in err
    assert "ORCID" in err


def test_multiple_invalid_fields_are_reported_together(tmp_path: Path, capfd) -> None:
    err = _rejected(
        tmp_path,
        capfd,
        title="",
        version="1.0",
        author_orcid="0000-0002-1825-0098",
        doi="not-a-doi",
    )
    for field in ("title", "version", "author_orcid", "doi"):
        assert f"ERROR: {field}:" in err
    assert err.count("ERROR:") >= 4


def test_invalid_context_does_not_leave_a_project(tmp_path: Path, capfd) -> None:
    output = Path(tmp_path) / "out"
    output.mkdir(parents=True, exist_ok=True)
    with pytest.raises(FailedHookException):
        cookiecutter(
            str(ROOT),
            no_input=True,
            output_dir=str(output),
            extra_context={**DEFAULT_CONTEXT, "title": ""},
        )
    capfd.readouterr()
    assert not [child for child in output.iterdir() if child.is_dir()]


def test_prompts_are_plain_language_and_cover_choices() -> None:
    data = json.loads((ROOT / "cookiecutter.json").read_text())
    prompts = data["__prompts__"]

    assert prompts["title"] == "Manuscript title"
    assert prompts["author_orcid"] == "ORCID iD (optional; leave empty if none)"
    assert prompts["manuscript_kind"]["__prompt__"] == "Manuscript kind"
    assert prompts["manuscript_kind"]["empirical"].startswith("Empirical")
    assert prompts["citation_style"]["__prompt__"] == "Citation style"
    assert prompts["license"]["__prompt__"] == "Paper license"
