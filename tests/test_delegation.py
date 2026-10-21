"""Every entry point must delegate to the vendored core implementation."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml
from conftest import render, run

DIAGNOSTIC_RE = re.compile(
    r"(?P<path>paper/[^:\n]+):(?P<line>\d+): (?P<code>[EW]\d{3}):"
)
GENERATED = (
    "CITATION.cff",
    ".zenodo.json",
    "README.md",
    "CHANGES.md",
    "paper/article.tex",
    "paper/sections/00_abstract.tex",
    "paper/sections/08_backmatter.tex",
)


def _diagnostics_from_text(text: str) -> set[tuple[str, int, str]]:
    return {
        (match.group("path"), int(match.group("line")), match.group("code"))
        for match in DIAGNOSTIC_RE.finditer(text)
    }


def _diagnostics_from_cli(project: Path) -> set[tuple[str, int, str]]:
    result = run(project, "python3", "-m", "scripts.article", "validate", "--json")
    payload = json.loads(result.stdout)
    return {
        (item["path"], item["line"], item["code"])
        for item in payload["diagnostics"]
    }


def _change_title(project: Path) -> None:
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data["title"] = "A Delegated Title"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def test_make_hooks_ci_and_shims_delegate(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    makefile = (project / "Makefile").read_text()
    pre_push = (project / "scripts" / "pre-push").read_text()
    validate_shim = (project / "scripts" / "validate-paper.py").read_text()
    metadata_shim = (project / "scripts" / "generate-metadata.py").read_text()
    workflow = (
        project / ".github" / "workflows" / "validate-latex.yml"
    ).read_text()

    assert "python3 -m scripts.article build pdf" in makefile
    assert "python3 -m scripts.article metadata" in makefile
    assert "python3 -m scripts.article metadata --check" in makefile
    assert "scripts.article build docx" in makefile

    assert "python3 -m scripts.article validate" in pre_push
    assert "make validate" not in pre_push

    assert "validate_paper" in validate_shim
    assert "INPUT_RE" not in validate_shim
    assert "collect_expected" in metadata_shim
    assert "def gen_citation_cff" not in metadata_shim
    assert "python3 scripts/validate-paper.py" in workflow


def test_validate_entrypoints_produce_identical_diagnostics(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)

    legacy = run(project, "python3", "scripts/validate-paper.py")
    make = run(project, "make", "validate")
    cli = _diagnostics_from_cli(project)

    assert legacy.returncode == 0
    assert make.returncode == 0
    assert _diagnostics_from_text(legacy.stdout + legacy.stderr) == cli
    assert _diagnostics_from_text(make.stdout + make.stderr) == cli

    section = project / "paper" / "sections" / "01_introduction.tex"
    section.write_text(section.read_text() + "\n\\citep{missing-key}\n")

    legacy_broken = run(project, "python3", "scripts/validate-paper.py")
    make_broken = run(project, "make", "validate")
    cli_broken = _diagnostics_from_cli(project)

    assert legacy_broken.returncode == 1
    assert make_broken.returncode != 0
    assert _diagnostics_from_text(
        legacy_broken.stdout + legacy_broken.stderr
    ) == cli_broken
    assert _diagnostics_from_text(
        make_broken.stdout + make_broken.stderr
    ) == cli_broken
    assert any(code == "E002" for _, _, code in cli_broken)


def test_legacy_generator_and_cli_write_identical_files(tmp_path: Path) -> None:
    legacy_project = render(tmp_path=tmp_path / "legacy")
    cli_project = render(tmp_path=tmp_path / "cli")
    _change_title(legacy_project)
    _change_title(cli_project)

    legacy = run(legacy_project, "python3", "scripts/generate-metadata.py")
    cli = run(cli_project, "python3", "-m", "scripts.article", "metadata")
    assert legacy.returncode == 0, legacy.stderr + legacy.stdout
    assert cli.returncode == 0, cli.stderr + cli.stdout

    for relative in GENERATED:
        assert (legacy_project / relative).read_bytes() == (
            cli_project / relative
        ).read_bytes(), relative


def test_pre_push_skips_cleanly_when_cli_is_missing(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    shutil.rmtree(project / "scripts" / "article")

    result = run(project, "bash", "scripts/pre-push")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "CLI not found" in result.stdout


def test_pre_push_runs_the_cli_when_present(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(project, "bash", "scripts/pre-push")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "scripts.article validate" in result.stdout
    assert "[pre-push] OK." in result.stdout
