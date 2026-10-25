"""Render matrix for manuscript kind and citation style."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from conftest import ROOT, render

KINDS = ("perspective", "empirical", "review")
STYLES = ("numeric", "author-year")
STRUCTURAL_SECTIONS = ("02_methods", "03_results", "04_discussion")


def _environments(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\\(begin|end)\{([^}]+)\}", text)


def _assert_balanced_environments(text: str) -> None:
    stack: list[str] = []
    for kind, name in _environments(text):
        if kind == "begin":
            stack.append(name)
        else:
            assert stack and stack[-1] == name, f"unbalanced \\end{{{name}}}"
            stack.pop()
    assert not stack, f"unclosed environments: {stack}"


def _assert_active_inputs(project: Path, text: str) -> None:
    for section in re.findall(r"^\\input\{([^}]+)\}", text, re.MULTILINE):
        assert (project / "paper" / f"{section}.tex").is_file(), section


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("style", STYLES)
def test_kind_style_matrix(tmp_path: Path, kind: str, style: str) -> None:
    project = render(
        tmp_path=tmp_path,
        manuscript_kind=kind,
        citation_style=style,
    )
    article = (project / "paper" / "article.tex").read_text()
    references = (project / "paper" / "sections" / "09_references.tex").read_text()
    metadata = yaml.safe_load((project / "metadata.yaml").read_text())

    assert metadata["manuscript_kind"] == kind
    assert metadata["citation_style"] == style

    _assert_balanced_environments(article)
    _assert_active_inputs(project, article)

    if kind == "empirical":
        for section in STRUCTURAL_SECTIONS:
            assert re.search(
                rf"^\\input\{{sections/{section}\}}$", article, re.MULTILINE
            ), section
        assert r"\usepackage{threeparttable}" in article
        assert r"\usepackage{caption}" in article
        assert r"\graphicspath{ {figures/}{tables/} }" in article
    else:
        for section in STRUCTURAL_SECTIONS:
            assert f"% \\input{{sections/{section}}}" in article
            assert not re.search(
                rf"^\\input\{{sections/{section}\}}$", article, re.MULTILINE
            ), section
        assert r"\usepackage{threeparttable}" not in article
        assert r"\graphicspath{ {figures/} }" in article

    if style == "numeric":
        assert r"\usepackage{cite}" in article
        assert r"\usepackage[round]{natbib}" not in article
        assert r"\bibliographystyle{plain}" in references
        assert "apalike" not in references
    else:
        assert r"\usepackage[round]{natbib}" in article
        assert r"\usepackage{cite}" not in article
        assert r"\bibliographystyle{apalike}" in references
        assert r"\bibliographystyle{plain}" not in references

    makefile = (project / "Makefile").read_text()
    assert "CITATION_STYLE" in makefile
    assert "--citation-style=$(CITATION_STYLE)" in makefile
    # pandoc 3 reads citation-style as a CSL file name, which "numeric" is not
    assert "--metadata=citation-style" not in makefile
    assert "paper/tables" in makefile
    assert (project / "paper" / "tables" / "README.md").is_file()


def test_defaults_are_perspective_numeric() -> None:
    data = json.loads((ROOT / "cookiecutter.json").read_text())
    assert data["manuscript_kind"][0] == "perspective"
    assert data["citation_style"][0] == "numeric"
    assert set(data["manuscript_kind"]) == set(KINDS)
    assert set(data["citation_style"]) == set(STYLES)
