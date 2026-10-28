"""Reproducible build tests: two clean builds with fixed
SOURCE_DATE_EPOCH produce identical PDFs."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import render, run

# Skip if latexmk is not available
latexmk_available = shutil.which("latexmk") is not None


def _pdf_hash(pdf_path: Path) -> str:
    """Return SHA-256 hash of a PDF file."""
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def _build_with_epoch(project: Path, epoch: int) -> subprocess.CompletedProcess:
    """Build the PDF with a specific SOURCE_DATE_EPOCH."""
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = str(epoch)
    return subprocess.run(
        ["make", "pdf"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )


def _clean_build(project: Path) -> subprocess.CompletedProcess:
    """Clean the build directory."""
    return subprocess.run(
        ["make", "clean"],
        cwd=project,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_reproducible_build_pdf(tmp_path: Path) -> None:
    """Two clean builds with the same SOURCE_DATE_EPOCH produce identical PDFs."""
    project = render(tmp_path=tmp_path)
    
    # First build with fixed epoch
    _clean_build(project)
    result1 = _build_with_epoch(project, 1609459200)  # 2021-01-01 00:00:00 UTC
    assert result1.returncode == 0, result1.stderr
    pdf1 = project / "paper" / "article.pdf"
    assert pdf1.exists()
    hash1 = _pdf_hash(pdf1)
    
    # Clean and rebuild with same epoch
    _clean_build(project)
    result2 = _build_with_epoch(project, 1609459200)
    assert result2.returncode == 0, result2.stderr
    pdf2 = project / "paper" / "article.pdf"
    assert pdf2.exists()
    hash2 = _pdf_hash(pdf2)
    
    # Hashes must match exactly
    assert hash1 == hash2, f"Build not reproducible: {hash1} != {hash2}"


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_different_epochs_produce_different_pdfs(tmp_path: Path) -> None:
    """Builds with different SOURCE_DATE_EPOCH produce different PDFs."""
    project = render(tmp_path=tmp_path)
    
    _clean_build(project)
    result1 = _build_with_epoch(project, 1609459200)  # 2021-01-01
    assert result1.returncode == 0, result1.stderr
    pdf1 = project / "paper" / "article.pdf"
    hash1 = _pdf_hash(pdf1)
    
    _clean_build(project)
    result2 = _build_with_epoch(project, 1704067200)  # 2024-01-01
    assert result2.returncode == 0, result2.stderr
    pdf2 = project / "paper" / "article.pdf"
    hash2 = _pdf_hash(pdf2)
    
    assert hash1 != hash2, "Different epochs should produce different PDFs"


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_make_clean_removes_build_artifacts(tmp_path: Path) -> None:
    """make clean removes all build artifacts."""
    project = render(tmp_path=tmp_path)
    
    # Build
    result = run(project, "make", "pdf")
    assert result.returncode == 0, result.stderr
    
    # Check build artifacts exist
    assert (project / "paper" / "article.pdf").exists()
    assert (project / "paper" / "build" / "article.pdf").exists()
    
    # Clean
    clean_result = run(project, "make", "clean")
    assert clean_result.returncode == 0
    
    # Check artifacts removed
    assert not (project / "paper" / "article.pdf").exists()
    assert not (project / "paper" / "build").exists()


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_supplementary_pdf_build(tmp_path: Path) -> None:
    """Supplementary PDF builds when supplementary.tex exists."""
    project = render(tmp_path=tmp_path)
    
    # Create a minimal supplementary.tex
    supp_tex = project / "paper" / "supplementary.tex"
    supp_tex.write_text(r"""
\documentclass{article}
\begin{document}
Supplementary material.
\end{document}
""")
    
    result = run(project, "make", "supp-pdf")
    assert result.returncode == 0, result.stderr
    
    # Check supplementary PDF created
    assert (project / "paper" / "supplementary.pdf").exists()
    assert (project / "paper" / "build" / "supplementary.pdf").exists()


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_supplementary_pdf_absent_when_no_tex(tmp_path: Path) -> None:
    """supp-pdf succeeds even when supplementary.tex is absent."""
    project = render(tmp_path=tmp_path)
    
    # Remove supplementary.tex if it exists
    supp_tex = project / "paper" / "supplementary.tex"
    if supp_tex.exists():
        supp_tex.unlink()
    
    result = run(project, "make", "supp-pdf")
    assert result.returncode == 0, result.stderr
    
    # No PDF should be created
    assert not (project / "paper" / "supplementary.pdf").exists()


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_supplementary_included_in_release_artifacts(tmp_path: Path) -> None:
    """Supplementary PDF is uploaded as artifact in CI (simulated)."""
    project = render(tmp_path=tmp_path)
    
    # Create supplementary.tex
    supp_tex = project / "paper" / "supplementary.tex"
    supp_tex.write_text(r"""
\documentclass{article}
\begin{document}
Supplementary.
\end{document}
""")
    
    # Build supplementary
    result = run(project, "make", "supp-pdf")
    assert result.returncode == 0, result.stderr
    
    supp_pdf = project / "paper" / "supplementary.pdf"
    assert supp_pdf.exists()
    
    # Verify it's a valid PDF
    assert supp_pdf.read_bytes().startswith(b"%PDF-")


def test_pages_deployment_workflow_exists():
    """Verify the Pages deployment job exists in release.yml."""
    release_workflow = (
        Path(__file__).parent.parent
        / "{{cookiecutter.repo_name}}"
        / ".github"
        / "workflows"
        / "release.yml"
    )
    content = release_workflow.read_text()
    assert "deploy-pages:" in content
    assert "actions/configure-pages" in content
    assert "actions/upload-pages-artifact" in content
    assert "actions/download-artifact" in content
    assert "name: manuscript\n" in content
    assert "bundle/supp" in content


def test_reusable_build_workflow_has_supp_input():
    """Verify reusable-build.yml has upload-supp input and build-supp job."""
    reusable_workflow = (
    Path(__file__).parent.parent / ".github" / "workflows" / "reusable-build.yml"
)
    content = reusable_workflow.read_text()
    assert "upload-supp:" in content
    assert "build-supp:" in content
    assert "upload-supp" in content
    assert "manuscript-supp" in content


def test_makefile_has_supp_targets():
    """Verify Makefile has supp and supp-pdf targets."""
    makefile = Path(__file__).parent.parent / "{{cookiecutter.repo_name}}" / "Makefile"
    content = makefile.read_text()
    assert "supp-pdf:" in content
    assert "supp:" in content
    assert "supplementary.tex" in content
    assert "supplementary.pdf" in content


@pytest.mark.skipif(not latexmk_available, reason="latexmk not installed")
def test_supplementary_directory_builds_every_standalone_document(tmp_path: Path) -> None:
    """Each paper/supplementary/*.tex with a \\documentclass gets its own PDF."""
    project = render(tmp_path=tmp_path)
    supp = project / "paper" / "supplementary"
    for name in ("Supporting-Materials", "Extra"):
        (supp / f"{name}.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n" + name + "\n\\end{document}\n"
        )
    (supp / "fragment.tex").write_text("Not a document.\n")

    result = run(project, "make", "supp-pdf")
    assert result.returncode == 0, result.stderr

    for name in ("Supporting-Materials", "Extra"):
        assert (supp / f"{name}.pdf").read_bytes().startswith(b"%PDF-")
        assert (supp / "build" / f"{name}.pdf").exists()
    assert not (supp / "fragment.pdf").exists()

    clean = run(project, "make", "clean")
    assert clean.returncode == 0, clean.stderr
    assert not list(supp.glob("*.pdf"))
    assert not (supp / "build").exists()
