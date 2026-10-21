"""Regression tests for comment, citation, and input handling in the validator."""

from __future__ import annotations

from pathlib import Path

from conftest import render, run

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "validator"


def _article(project: Path, fixture: str) -> None:
    (project / "paper" / "article.tex").write_text((FIXTURES / fixture).read_text())


def _section(project: Path, fixture: str) -> None:
    target = project / "paper" / "sections" / "01_introduction.tex"
    target.write_text((FIXTURES / fixture).read_text())


def _validate(project: Path):
    return run(project, "python3", "scripts/validate-paper.py")


def test_clean_project_passes(tmp_path: Path) -> None:
    result = _validate(render(tmp_path=tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "All validation checks passed." in result.stdout


def test_commented_and_inline_commented_inputs_are_ignored(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _article(project, "commented_input.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "does-not-exist" not in result.stderr


def test_inline_input_and_include_resolve(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _article(project, "inline_input.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_all_citation_command_variants_resolve(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "cite_variants.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "All citation keys resolve." in result.stdout


def test_commented_citations_are_ignored(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "commented_cite.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_escaped_percent_is_not_a_comment(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "escaped_percent.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_escaped_braces_are_ignored(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "escaped_braces.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_missing_citation_has_a_structured_diagnostic(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "missing_cite.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "paper/sections/01_introduction.tex:2: E002:" in result.stderr
    assert "missing-key" in result.stderr


def test_unbalanced_braces_have_a_structured_diagnostic(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "unbalanced.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "paper/sections/01_introduction.tex:1: E003:" in result.stderr


def test_missing_input_has_a_structured_diagnostic(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _article(project, "missing_input.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "paper/article.tex:1: E001:" in result.stderr
    assert "does-not-exist" in result.stderr
