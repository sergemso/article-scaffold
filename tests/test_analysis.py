"""The empirical data/analysis pipeline is reproducible and opt-in."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from conftest import render, run

TABLE = Path("paper/tables/analysis_summary.tex")
FIGURE = Path("paper/figures/analysis_plot.pdf")
FIGURE_FRAGMENT = Path("paper/figures/analysis_figure.tex")


def _empirical(tmp_path: Path) -> Path:
    return render(tmp_path=tmp_path, manuscript_kind="empirical")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _output(project: Path, *args: str) -> str:
    result = run(project, *args)
    return result.stdout + result.stderr


def test_analysis_layout_has_checksums_lockfile_and_opt_in_extras(tmp_path: Path) -> None:
    project = _empirical(tmp_path)

    assert (project / "data/raw/observations.csv").is_file()
    checksums = (project / "data/checksums.sha256").read_text()
    assert "data/raw/observations.csv" in checksums
    assert (project / "analysis/analyze.py").is_file()

    lockfiles = [
        path
        for path in (project / "analysis").iterdir()
        if path.name in {"uv.lock", "renv.lock"}
    ]
    assert lockfiles, "expected a uv.lock or renv.lock in analysis/"

    pyproject = (project / "analysis/pyproject.toml").read_text()
    assert "optional-dependencies" in pyproject
    assert "heavy" in pyproject
    assert "pandas" in pyproject
    # The default script must not import heavy packages at module import time.
    analyze = (project / "analysis/analyze.py").read_text()
    assert "import pandas" not in analyze
    assert "import matplotlib" not in analyze


def test_make_analysis_regenerates_reproducible_artifacts(tmp_path: Path) -> None:
    project = _empirical(tmp_path)

    first = run(project, "make", "analysis")
    assert first.returncode == 0, first.stdout + first.stderr
    table = project / TABLE
    figure = project / FIGURE
    fragment = project / FIGURE_FRAGMENT
    assert table.is_file()
    assert figure.is_file()
    assert fragment.is_file()
    assert figure.read_bytes().startswith(b"%PDF-")
    assert "analysis_plot.pdf" in fragment.read_text()
    assert "control" in table.read_text()
    assert "treatment" in table.read_text()

    first_hashes = (_digest(table), _digest(figure), _digest(fragment))
    second = run(project, "make", "analysis")
    assert second.returncode == 0, second.stdout + second.stderr
    assert (_digest(table), _digest(figure), _digest(fragment)) == first_hashes


def test_analysis_check_is_read_only(tmp_path: Path) -> None:
    project = _empirical(tmp_path)
    before = {
        path: _digest(project / path)
        for path in (TABLE, FIGURE, FIGURE_FRAGMENT)
        if (project / path).is_file()
    }

    result = run(project, "make", "analysis-check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "input checksum" in result.stdout
    assert {
        path: _digest(project / path)
        for path in before
    } == before


def test_empirical_manuscript_consumes_generated_artifacts(tmp_path: Path) -> None:
    if shutil.which("latexmk") is None:
        pytest.skip("latexmk is not installed")

    project = _empirical(tmp_path)
    analysis = run(project, "make", "analysis")
    assert analysis.returncode == 0, analysis.stdout + analysis.stderr

    result = run(project, "make", "pdf")
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    log = (project / "paper" / "build" / "article.log").read_text(errors="replace")
    assert "analysis_summary.tex" in log
    assert "analysis_figure.tex" in log
    assert "analysis_plot.pdf" in log


def test_make_pdf_does_not_invoke_analysis(tmp_path: Path) -> None:
    project = _empirical(tmp_path)

    result = run(project, "make", "-n", "pdf")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "analysis/analyze.py" not in result.stdout


def test_missing_input_fails_clearly_without_outputs(tmp_path: Path) -> None:
    project = _empirical(tmp_path)
    for path in (TABLE, FIGURE, FIGURE_FRAGMENT):
        (project / path).unlink(missing_ok=True)
    (project / "data/raw/observations.csv").unlink()

    result = run(project, "make", "analysis")
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "ERROR:" in output
    assert "missing input" in output
    assert "Traceback" not in output
    assert not (project / TABLE).exists()
    assert not (project / FIGURE).exists()
    assert not (project / FIGURE_FRAGMENT).exists()


def test_checksum_mismatch_fails_clearly(tmp_path: Path) -> None:
    project = _empirical(tmp_path)
    data = project / "data/raw/observations.csv"
    data.write_text(data.read_text().replace("treatment,18.0", "treatment,99.0"))

    result = run(project, "make", "analysis")
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "checksum mismatch" in output
    assert "observations.csv" in output
    assert "Traceback" not in output
