"""Render-matrix smoke tests and regressions for fixed Phase 1 defects."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from conftest import commit_all, run

EXPECTED_FILES = [
    "Makefile",
    "metadata.yaml",
    "CITATION.cff",
    ".zenodo.json",
    "paper/article.tex",
    "scripts/generate-metadata.py",
    "scripts/validate-paper.py",
]


def _assert_expected(project: Path) -> None:
    for rel in EXPECTED_FILES:
        assert (project / rel).is_file(), f"missing {rel} in {project}"


def test_default_render(default_project: Path) -> None:
    _assert_expected(default_project)
    assert (default_project / "paper" / "sections" / "01_introduction.tex").is_file()


def test_special_characters_render(special_project: Path) -> None:
    _assert_expected(special_project)


def test_doi_is_rendered(doi_project: Path) -> None:
    metadata = yaml.safe_load((doi_project / "metadata.yaml").read_text())
    assert metadata["doi"] == "10.5281/zenodo.1234567"


def test_empty_subtitle_is_allowed(tmp_path: Path) -> None:
    from conftest import render

    project = render(tmp_path=tmp_path, subtitle="")
    metadata = yaml.safe_load((project / "metadata.yaml").read_text())
    assert not metadata.get("subtitle")


def test_metadata_yaml_parses_with_quotes(special_project: Path) -> None:
    yaml.safe_load((special_project / "metadata.yaml").read_text())


def test_citation_cff_has_valid_type(default_project: Path) -> None:
    cff = yaml.safe_load((default_project / "CITATION.cff").read_text())
    assert cff["type"] in {"software", "article"}


def test_zenodo_json_parses_with_quotes(special_project: Path) -> None:
    json.loads((special_project / ".zenodo.json").read_text())


def test_latex_title_escapes_specials(special_project: Path) -> None:
    tex = (special_project / "paper" / "article.tex").read_text()
    assert r"\&" in tex
    assert r"\%" in tex


def test_validator_ignores_escaped_braces(default_project: Path) -> None:
    section = default_project / "paper" / "sections" / "01_introduction.tex"
    section.write_text(section.read_text() + "\nA literal \\{ brace.\n")
    result = run(default_project, "make", "validate")
    assert result.returncode == 0, result.stderr + result.stdout


def test_metadata_regeneration_is_idempotent(default_project: Path) -> None:
    commit_all(default_project)
    result = run(default_project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout
    diff = run(default_project, "git", "diff", "--exit-code")
    assert diff.returncode == 0, diff.stdout + diff.stderr
