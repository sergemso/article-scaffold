"""Static tests for preamble package order and build directory structure."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
TEMPLATE_ARTICLE = TEMPLATE / "paper" / "article.tex"


def _read_rendered_article(kind: str, citation: str = "numeric") -> str:
    """Render the template and return the article.tex content."""
    import tempfile

    from tests.conftest import render

    with tempfile.TemporaryDirectory() as tmp:
        project = render(
            tmp_path=Path(tmp),
            manuscript_kind=kind,
            citation_style=citation,
        )
        return (project / "paper" / "article.tex").read_text()


def test_preamble_package_order() -> None:
    """Verify the LaTeX preamble has the correct package loading order."""
    # Check rendered output since template has conditionals
    text_numeric = _read_rendered_article("empirical", "numeric")
    text_ay = _read_rendered_article("empirical", "author-year")

    for text, style in [(text_numeric, "numeric"), (text_ay, "author-year")]:
        preamble_end = text.find(r"\begin{document}")
        assert preamble_end > 0, f"\\begin{{document}} not found in {style}"
        preamble = text[:preamble_end]

        pkg_lines = [
            line.strip()
            for line in preamble.splitlines()
            if line.strip().startswith(r"\usepackage")
        ]

        # Find indices
        hyperref_idx = next(i for i, line in enumerate(pkg_lines) if "hyperref" in line)
        cleveref_idx = next(i for i, line in enumerate(pkg_lines) if "cleveref" in line)
        titlesec_idx = next(i for i, line in enumerate(pkg_lines) if "titlesec" in line)
        float_idx = next(i for i, line in enumerate(pkg_lines) if "float" in line)
        xcolor_idx = next(i for i, line in enumerate(pkg_lines) if "xcolor" in line)
        enumitem_idx = next(i for i, line in enumerate(pkg_lines) if "enumitem" in line)

        # Bib package depends on style
        if style == "numeric":
            cite_idx = next(i for i, line in enumerate(pkg_lines) if "cite" in line)
            assert cite_idx < hyperref_idx, f"{style}: cite must be before hyperref"
        else:
            natbib_idx = next(i for i, line in enumerate(pkg_lines) if "natbib" in line)
            assert natbib_idx < hyperref_idx, f"{style}: natbib must be before hyperref"

        # titlesec before hyperref
        assert titlesec_idx < hyperref_idx, f"{style}: titlesec must be before hyperref"

        # cleveref after hyperref
        assert hyperref_idx < cleveref_idx, f"{style}: cleveref must be after hyperref"

        # hyperref late
        assert float_idx < hyperref_idx, f"{style}: float must be before hyperref"
        assert xcolor_idx < hyperref_idx, f"{style}: xcolor must be before hyperref"
        assert enumitem_idx < hyperref_idx, f"{style}: enumitem must be before hyperref"


def test_empirical_loads_threeparttable_and_caption() -> None:
    """Empirical kind should load threeparttable and caption."""
    text = _read_rendered_article("empirical")
    assert r"\usepackage{threeparttable}" in text
    assert r"\usepackage{caption}" in text


def test_perspective_does_not_load_threeparttable() -> None:
    """Perspective kind should not load threeparttable/caption."""
    text = _read_rendered_article("perspective")
    assert r"\usepackage{threeparttable}" not in text
    assert r"\usepackage{caption}" not in text


def test_numeric_uses_cite() -> None:
    """Numeric citation style should load cite package."""
    text = _read_rendered_article("empirical", "numeric")
    assert r"\usepackage{cite}" in text
    assert r"\usepackage[round]{natbib}" not in text


def test_author_year_uses_natbib() -> None:
    """Author-year citation style should load natbib with round option."""
    text = _read_rendered_article("empirical", "author-year")
    assert r"\usepackage[round]{natbib}" in text
    assert r"\usepackage{cite}" not in text


def test_latexmkrc_exists_and_has_outdir() -> None:
    """The paper/.latexmkrc must exist and configure outdir=build."""
    latexmkrc = TEMPLATE / "paper" / ".latexmkrc"
    assert latexmkrc.is_file(), "paper/.latexmkrc missing"
    content = latexmkrc.read_text()
    assert "$out_dir = 'build'" in content
    assert "SOURCE_DATE_EPOCH" in content
    assert "-halt-on-error" in content
    assert "-file-line-error" in content


def test_makefile_pdf_copies_from_build() -> None:
    """Makefile pdf target must copy from paper/build/article.pdf."""
    makefile = TEMPLATE / "Makefile"
    content = makefile.read_text()
    assert "$(PAPER_DIR)/build/article.pdf" in content
    assert "cp $(PAPER_DIR)/build/article.pdf" in content


def test_makefile_clean_removes_build_and_pdf() -> None:
    """Makefile clean must remove build/ and paper/article.pdf."""
    makefile = TEMPLATE / "Makefile"
    content = makefile.read_text()
    assert "rm -rf $(PAPER_DIR)/build" in content
    assert "rm -f $(PAPER_DIR)/article.pdf" in content


def test_build_plan_output_is_build_dir() -> None:
    """The build.py pdf_plan output should be paper/build/article.pdf."""
    build_py = TEMPLATE / "scripts" / "article" / "build.py"
    content = build_py.read_text()
    assert 'output="paper/build/article.pdf"' in content


def test_github_workflows_use_build_dir() -> None:
    """CI workflows must reference paper/build/article.pdf."""
    for wf in (TEMPLATE / ".github" / "workflows").glob("*.yml"):
        content = wf.read_text()
        if "article.pdf" in content and "manuscript.pdf" not in content:
            # The build step should reference build/article.pdf
            assert "build/article.pdf" in content, f"{wf.name} should use build/article.pdf"


def test_clean_build_from_fresh_clone() -> None:
    """A clean build from a fresh render should produce paper/article.pdf via build/."""
    import tempfile

    from tests.conftest import render, run

    with tempfile.TemporaryDirectory() as tmp:
        project = render(tmp_path=Path(tmp), manuscript_kind="empirical")

        # First build
        result = run(project, "make", "pdf")
        assert result.returncode == 0, result.stderr + result.stdout
        assert (project / "paper" / "article.pdf").is_file()
        assert (project / "paper" / "build" / "article.pdf").is_file()

        # Clean
        result = run(project, "make", "clean")
        assert result.returncode == 0
        assert not (project / "paper" / "build").exists()
        assert not (project / "paper" / "article.pdf").exists()

        # Second build (simulates fresh clone after clean)
        result = run(project, "make", "pdf")
        assert result.returncode == 0, result.stderr + result.stdout
        assert (project / "paper" / "article.pdf").is_file()
        assert (project / "paper" / "build" / "article.pdf").is_file()


def test_no_aux_files_in_paper_root_after_build() -> None:
    """After build, no .aux, .log, .bbl, etc. should remain in paper/ root."""
    import tempfile

    from tests.conftest import render, run

    with tempfile.TemporaryDirectory() as tmp:
        project = render(tmp_path=Path(tmp), manuscript_kind="empirical")
        result = run(project, "make", "pdf")
        assert result.returncode == 0, result.stderr + result.stdout

        # Check that no LaTeX auxiliary files are in paper/ root
        for ext in (".aux", ".log", ".bbl", ".blg", ".out", ".toc", ".lof", ".lot",
                    ".fls", ".fdb_latexmk", ".synctex.gz"):
            aux_files = list(project.glob(f"paper/*{ext}"))
            assert not aux_files, f"Found {ext} files in paper/ root: {aux_files}"