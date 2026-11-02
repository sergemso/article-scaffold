"""``index`` writes a compact label and summary index; ``--check`` spots staleness."""

from __future__ import annotations

import json
import os
from pathlib import Path

from conftest import render, run

INDEX = "paper/build/section-index.json"


def _cli(project: Path, *args: str):
    return run(project, "python3", "-m", "scripts.article", *args)


def _load(project: Path) -> dict:
    return json.loads((project / INDEX).read_text())


def test_index_lists_labels_with_ranges_and_summaries(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "paper" / "sections" / "02_methods.tex").write_text(
        "\\section{Methods}\n"
        "\\label{sec:methods}\n"
        "% a comment that must not become the summary.\n"
        "\n"
        "We study the \\emph{contract} first. Then we test it again.\n"
        "More text.\n"
        "\\subsection{Design}\n"
        "\\label{sec:design}\n"
        "Design text.\n"
        "\\begin{figure}\n"
        "\\caption{A figure.}\n"
        "\\label{fig:one}\n"
        "\\end{figure}\n"
        "\\subsection{Other}\n"
        "Other text.\n"
    )
    result = _cli(project, "index")
    assert result.returncode == 0, result.stderr
    index = _load(project)
    methods = next(s for s in index["sections"] if s["file"].endswith("02_methods.tex"))
    assert methods["title"] == "Methods"
    assert methods["summary"] == "We study the contract first."
    assert methods["lines"] == 15
    labels = index["labels"]
    assert labels["sec:methods"] == {"file": "paper/sections/02_methods.tex", "lines": [1, 15]}
    assert labels["sec:design"]["lines"] == [7, 13]
    assert labels["fig:one"]["lines"] == [10, 13]
    assert "sec:introduction" in labels


def test_output_is_stable(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _cli(project, "index")
    first = (project / INDEX).read_bytes()
    _cli(project, "index")
    assert (project / INDEX).read_bytes() == first


def test_check_missing_fresh_and_stale(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    assert _cli(project, "index", "--check").returncode == 1
    assert _cli(project, "index").returncode == 0
    assert _cli(project, "index", "--check").returncode == 0
    section = project / "paper" / "sections" / "01_introduction.tex"
    later = (project / INDEX).stat().st_mtime + 10
    section.write_text(section.read_text() + "\nMore.\n")
    os.utime(section, (later, later))
    stale = _cli(project, "index", "--check")
    assert stale.returncode == 1
    assert "01_introduction.tex" in stale.stderr
    assert _cli(project, "index").returncode == 0
    new = (project / INDEX).stat().st_mtime + 10
    os.utime(project / INDEX, (new + 10, new + 10))
    assert _cli(project, "index", "--check").returncode == 0


def test_large_section_set_stays_small(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    for number in range(1, 7):
        body = [f"\\section{{Part {number}}}", f"\\label{{sec:part{number}}}"]
        for item in range(3):
            body.append(f"\\subsection{{Sub {number}.{item}}}\\label{{sec:sub{number}-{item}}}")
        body += [f"Line {i} of running text for the paper." for i in range(494)]
        (project / "paper" / "sections" / f"0{number}_big.tex").write_text("\n".join(body) + "\n")
    total = sum(
        len(p.read_text().splitlines()) for p in (project / "paper" / "sections").glob("*.tex")
    )
    assert total > 3000
    assert _cli(project, "index").returncode == 0
    assert (project / INDEX).stat().st_size < 4096


def test_make_validate_runs_the_check_when_an_index_exists(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    assert run(project, "make", "validate").returncode == 0  # no index: nothing to check
    _cli(project, "index")
    assert run(project, "make", "validate").returncode == 0
    section = project / "paper" / "sections" / "01_introduction.tex"
    later = (project / INDEX).stat().st_mtime + 10
    os.utime(section, (later, later))
    result = run(project, "make", "validate")
    assert result.returncode != 0
    assert "01_introduction.tex" in result.stderr
