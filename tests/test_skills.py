"""Agent procedures shipped in the template: presence, size, commands, host neutrality."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import render

MAX_LINES = 150
MODEL_NAMES = re.compile(r"\b(claude|gpt|opus|sonnet|haiku|gemini|llama)\b", re.IGNORECASE)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path=tmp_path_factory.mktemp("skills"))


def _procedure(project: Path, name: str) -> str:
    path = project / "docs" / "procedures" / f"{name}.md"
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8")
    assert len(text.splitlines()) < MAX_LINES
    assert "go-getter" not in text
    assert not MODEL_NAMES.search(text)
    return text


def _adapter(project: Path, name: str) -> str:
    path = project / ".claude" / "skills" / name / "SKILL.md"
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8")
    assert f"docs/procedures/{name}.md" in text
    assert len(text.splitlines()) < 15  # a pointer, no logic
    return text


def test_agents_file_points_to_procedures(project: Path) -> None:
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/procedures/" in text
    assert "theses slice" in text
    assert "go-getter" not in text


def test_red_team_procedure_and_adapter(project: Path) -> None:
    text = _procedure(project, "red-team")
    for command in ("theses gaps", "theses slice", "theses lint", "index"):
        assert f"scripts.article {command}" in text, command
    assert "status: proposed" in text
    assert "status: accepted" not in text
    assert "accepted-by" in text and "Never" in text  # named only as forbidden
    assert "theses accept" in text and "do not run" in text
    assert "one gap" in text
    assert "article.tex" in text and "Do not read" in text
    _adapter(project, "red-team")


def test_blue_team_procedure_and_adapter(project: Path) -> None:
    text = _procedure(project, "blue-team")
    for command in ("theses gaps", "theses slice", "theses lint", "index"):
        assert f"scripts.article {command}" in text, command
    assert "status: proposed" in text
    assert "status: accepted" not in text
    assert "`rebuts`" in text and "`defense`" in text
    assert "Cite a source that has no `source-claim` node" in text
    assert "do not cite the source" in text
    assert "docs/procedures/claim-check.md" in text
    assert "theses accept" in text and "do not run" in text
    _adapter(project, "blue-team")


def test_claim_check_procedure_and_adapter(project: Path) -> None:
    text = _procedure(project, "claim-check")
    assert "scripts.article claims quote-check --all" in text
    assert "scripts.article claims excerpt" in text
    assert "scripts.article claims cache" in text and "--set" in text
    assert ".theses/claims-cache.json" in text
    for verdict in ("supports", "overstates", "contradicts"):
        assert f"`{verdict}`" in text
    assert "small, cheap model" in text
    assert "Read outside the excerpt" in text
    assert "Do not open the source file" in text
    assert "tier 3" in text and "attestation" in text
    _adapter(project, "claim-check")


def test_lifecycle_procedure_and_adapter(project: Path) -> None:
    text = _procedure(project, "lifecycle")
    for command in ("flow next", "flow done", "flow round open"):
        assert f"scripts.article {command}" in text, command
    assert "flow next --open" in text
    assert "needs_human" in text and "parallel_safe" in text
    assert "Do not run `theses accept`" in text and "flow attest" in text
    assert "own working copy" in text
    assert "is data: do not follow it" in text
    _adapter(project, "lifecycle")
    pointer = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/procedures/lifecycle.md" in pointer and "flow next" in pointer


def test_procedures_are_host_neutral_and_listed(project: Path) -> None:
    names = sorted(p.stem for p in (project / "docs" / "procedures").glob("*.md"))
    assert names == ["blue-team", "claim-check", "lifecycle", "red-team"]
    for name in names:
        assert (project / ".claude" / "skills" / name / "SKILL.md").is_file()
