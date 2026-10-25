"""DOCX builds must find figures through LaTeX's graphics paths."""

from __future__ import annotations

import base64
import hashlib
import shutil
import zipfile
from pathlib import Path

import pytest
from conftest import render, run

PANDOC = shutil.which("pandoc")
pytestmark = pytest.mark.skipif(PANDOC is None, reason="pandoc is not installed")

# A valid 1x1 PNG. Pandoc embeds the bytes in word/media/.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _build_with_figure(tmp_path: Path) -> Path:
    project = render(tmp_path=tmp_path)
    figure = project / "paper" / "figures" / "docx-figure.png"
    figure.write_bytes(PNG)
    article = project / "paper" / "article.tex"
    article.write_text(
        article.read_text().replace(
            "\\end{document}",
            "\\includegraphics[width=0.5\\textwidth]{docx-figure.png}\n\\end{document}",
        )
    )
    return project


def test_docx_embeds_figure_from_paper_figures(tmp_path: Path) -> None:
    project = _build_with_figure(tmp_path)
    figure = project / "paper" / "figures" / "docx-figure.png"
    before = hashlib.sha256(figure.read_bytes()).hexdigest()

    result = run(project, "make", "docx")
    assert result.returncode == 0, result.stderr + result.stdout

    docx = project / "manuscript.docx"
    assert docx.is_file()
    with zipfile.ZipFile(docx) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
        assert media, "DOCX contains no embedded media"
        assert any(archive.read(name) == PNG for name in media)

    # The PDF source image must be read in place, never rewritten for DOCX.
    after = hashlib.sha256(figure.read_bytes()).hexdigest()
    assert after == before


def test_docx_uses_shared_resource_path_and_reference_doc(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    makefile = (project / "Makefile").read_text()
    (project / ".github" / "workflows" / "build-artifacts.yml").read_text()
    reusable = (project / ".github" / "workflows" / "reusable-build.yml").read_text()

    assert "DOCX_RESOURCE_PATH = .:figures:.." in makefile
    assert "--resource-path=$(DOCX_RESOURCE_PATH)" in makefile
    assert "-w /workspace/paper" in reusable
    assert "--resource-path=.:figures:.." in reusable
    assert "REFERENCE_DOCX ?= reference.docx" in makefile
    assert "--reference-doc=../$(REFERENCE_DOCX)" in makefile
    assert "reference.docx" in reusable
    assert "pandoc/core:3.1" in reusable

    for shared in (
        "--from=latex",
        "--to=docx",
        "--bibliography=refs.bib",
        "article.tex",
    ):
        assert shared in makefile
        assert shared in reusable


def test_docx_contains_input_sections(tmp_path: Path) -> None:
    """\\input{sections/...} resolves against pandoc's cwd, so a wrong cwd gives an empty DOCX."""
    project = render(tmp_path=tmp_path)
    marker = "DocxSectionMarkerZq7"
    intro = project / "paper" / "sections" / "01_introduction.tex"
    intro.write_text(intro.read_text() + f"\n\n{marker} body text.\n")

    result = run(project, "make", "docx")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Could not load include file" not in result.stderr + result.stdout

    with zipfile.ZipFile(project / "manuscript.docx") as archive:
        assert marker in archive.read("word/document.xml").decode()
