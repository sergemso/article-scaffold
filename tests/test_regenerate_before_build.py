"""Artifact builds refresh metadata-derived files; the scaffold ships no leftovers."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from conftest import render, run

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "{{cookiecutter.repo_name}}" / ".github" / "workflows"
LEFTOVER = re.compile(r"^\s*#\s*-\s|Replace this|Perez|independent evaluators", re.MULTILINE)


def _retitle(project: Path, title: str) -> None:
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data["title"] = title
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def test_rendered_metadata_has_no_leftovers(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    for rel in ("metadata.yaml", "paper/sections/00_abstract.tex", "CITATION.cff", ".zenodo.json"):
        text = (project / rel).read_text()
        assert not LEFTOVER.search(text), f"{rel} contains a leftover"
    data = yaml.safe_load((project / "metadata.yaml").read_text())
    assert "abstract_note" not in data
    assert "description" not in data
    assert "A note on evidence" not in (project / "paper/sections/00_abstract.tex").read_text()


def test_fresh_render_is_in_step_with_its_metadata(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(project, "python3", "-m", "scripts.article", "metadata", "--check")
    assert result.returncode == 0, result.stderr + result.stdout


def test_abstract_note_appears_only_when_given(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data["abstract_note"] = "Single-source data."
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    assert run(project, "make", "metadata").returncode == 0
    assert "Single-source data." in (project / "paper/sections/00_abstract.tex").read_text()
    del data["abstract_note"]
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    assert run(project, "make", "metadata").returncode == 0
    assert "A note on evidence" not in (project / "paper/sections/00_abstract.tex").read_text()


def test_build_regenerates_drifted_files(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _retitle(project, "A Retitled Manuscript")
    # The tool is absent or present; either way the files are refreshed first.
    run(project, "python3", "-m", "scripts.article", "build", "docx")
    assert "A Retitled Manuscript" in (project / "CITATION.cff").read_text()
    assert "A Retitled Manuscript" in (project / "paper/article.tex").read_text()


def test_build_pdf_regenerates_too(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _retitle(project, "Another Title")
    run(project, "python3", "-m", "scripts.article", "build", "pdf")
    assert "Another Title" in (project / ".zenodo.json").read_text()


def test_no_regenerate_and_dry_run_leave_files_alone(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _retitle(project, "Untouched")
    for flag in ("--no-regenerate", "--dry-run"):
        run(project, "python3", "-m", "scripts.article", "build", "pdf", flag)
        assert "Untouched" not in (project / "CITATION.cff").read_text()


def test_invalid_metadata_stops_the_build(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "metadata.yaml").write_text("title: [unterminated\n")
    result = run(project, "python3", "-m", "scripts.article", "build", "pdf", "--json")
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False and "plan" not in payload


def test_make_targets_regenerate_first() -> None:
    makefile = (ROOT / "{{cookiecutter.repo_name}}" / "Makefile").read_text()
    for target in ("docx", "html", "quick"):
        assert re.search(rf"^{target}: metadata$", makefile, re.MULTILINE), target


def test_reusable_build_regenerates_in_every_job() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "reusable-build.yml").read_text())
    for name, job in workflow["jobs"].items():
        runs = " ".join(step.get("run", "") for step in job["steps"])
        assert "scripts.article metadata" in runs, name


def test_metadata_sync_opens_a_pull_request_once() -> None:
    text = (WORKFLOWS / "metadata-sync.yml").read_text()
    workflow = yaml.safe_load(text)
    perms = workflow["jobs"]["sync"]["permissions"]
    assert perms == {"contents": "write", "pull-requests": "write"}
    assert "gh pr list --head" in text and "gh pr create" in text
