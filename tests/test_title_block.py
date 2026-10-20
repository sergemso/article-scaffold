"""PDF metadata comes from the generated title block."""

from __future__ import annotations

import re
from pathlib import Path

from conftest import SPECIAL_TITLE, render, run


def _title_block(project: Path) -> str:
    tex = (project / "paper" / "article.tex").read_text()
    match = re.search(
        r"% METADATA:TITLE_BLOCK:START(.*?)% METADATA:TITLE_BLOCK:END",
        tex,
        re.DOTALL,
    )
    assert match, "title block sentinels are missing"
    return match.group(1)


def test_pdf_metadata_escapes_special_characters(tmp_path: Path) -> None:
    project = render(
        tmp_path=tmp_path,
        title=SPECIAL_TITLE,
        author_name='A & B "C" 100%',
        keywords='quotes, "100%", #hashtag, ünïcode',
    )
    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout

    block = _title_block(project)
    assert block.count(r"\hypersetup") == 1
    assert "pdftitle" in block
    assert "pdfauthor" in block
    assert "pdfsubject" in block
    assert "pdfkeywords" in block
    assert r"\&" in block
    assert r"\%" in block
    assert r"\_" in block
    assert r"100\%" in block
    assert r"\#hashtag" in block
    assert "pdfsubject={ Perspective / Review Essay }" in block


def test_empty_subtitle_keeps_pdf_metadata(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, subtitle="")
    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout

    block = _title_block(project)
    assert "pdftitle" in block
    assert r"\\[0.3em]" not in block
