"""Structural validator checks: figures, references, includes, and BibTeX."""

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


def test_clean_project_passes_and_reports_warnings(tmp_path: Path) -> None:
    result = _validate(render(tmp_path=tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "W001" in result.stdout
    assert "W002" in result.stdout


def test_missing_figure_is_an_error(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "missing_figure.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "paper/sections/01_introduction.tex:2: E007:" in result.stderr


def test_figure_resolves_through_graphicspath(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "paper" / "figures" / "example.pdf").write_bytes(b"%PDF-1.4\n")
    _section(project, "valid_figure.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_commented_figure_is_ignored(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "commented_figure.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_custom_graphicspath_is_honored(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "paper" / "assets").mkdir()
    (project / "paper" / "assets" / "logo.pdf").write_bytes(b"%PDF-1.4\n")
    _article(project, "custom_graphicspath.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_duplicate_labels_are_errors(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "duplicate_label.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "E008" in result.stderr
    assert "sec:duplicate" in result.stderr


def test_missing_reference_is_an_error(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "missing_ref.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "paper/sections/01_introduction.tex:2: E009:" in result.stderr


def test_reference_command_variants_resolve(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "ref_variants.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "E009" not in result.stderr


def test_unused_label_is_a_warning(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _section(project, "unused_label.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "W001" in result.stdout
    assert "sec:unused" in result.stdout


def test_orphan_bib_entry_is_a_warning(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "W002" in result.stdout
    assert "example2026" in result.stdout


def test_duplicate_bib_key_is_an_error(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    refs = project / "paper" / "refs.bib"
    duplicate = (
        "\n@book{perez2002,\n"
        "  author = {Duplicate, Author},\n"
        "  title = {Duplicate},\n"
        "  year = {2026}\n"
        "}\n"
    )
    refs.write_text(refs.read_text() + duplicate)
    result = _validate(project)
    assert result.returncode == 1
    assert "E010" in result.stderr
    assert "perez2002" in result.stderr


def test_include_cannot_escape_paper_directory(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "outside.tex").write_text("Outside the paper directory.\n")
    _article(project, "escape_input.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "paper/article.tex:1: E011:" in result.stderr


def test_nested_includes_resolve(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    for fixture in ("nested_a.tex", "nested_b.tex", "nested_c.tex"):
        (project / "paper" / "sections" / fixture).write_text((FIXTURES / fixture).read_text())
    _article(project, "nested_input.tex")
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_include_depth_limit_is_enforced(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    sections = project / "paper" / "sections"
    for index in range(25):
        target = sections / f"depth_{index:02d}.tex"
        if index == 24:
            target.write_text("End of chain.\n")
        else:
            target.write_text(f"\\input{{sections/depth_{index + 1:02d}}}\n")
    _article(project, "depth_input.tex")
    result = _validate(project)
    assert result.returncode == 1
    assert "E012" in result.stderr


def test_standalone_supplementary_has_its_own_label_scope(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "paper" / "sections" / "extra.tex").write_text(
        "\\section{Extra}\\label{sec:shared}\nSee \\ref{sec:shared}.\n"
    )
    (project / "paper" / "supplementary" / "Supp.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{S}\\label{sec:shared}\nSee \\ref{sec:shared}.\n\\end{document}\n"
    )
    result = _validate(project)
    assert "E008" not in result.stderr, result.stderr
    assert "E009" not in result.stderr, result.stderr
