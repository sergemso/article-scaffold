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
    assert "scripts.article claims record" in text and "--set" in text
    assert "docs/ledger/claim-verdict" in text
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


def test_reading_a_source_procedure_and_adapter(project: Path) -> None:
    text = _procedure(project, "reading-a-source")
    for command in ("sources list", "sources slice", "sources find", "sources read"):
        assert f"scripts.article {command}" in text, command
    assert "--pages" in text and "--section" in text and "--by" in text
    assert "Never fetch" in text and "OCR" in text
    assert "paper/sources/` is private" in text
    _adapter(project, "reading-a-source")
    pointer = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/procedures/reading-a-source.md" in pointer


def test_procedures_are_host_neutral_and_listed(project: Path) -> None:
    names = sorted(p.stem for p in (project / "docs" / "procedures").glob("*.md"))
    assert names == [
        "blue-team",
        "claim-check",
        "dialectic",
        "lifecycle",
        "reading-a-source",
        "red-team",
    ]
    for name in names:
        assert (project / ".claude" / "skills" / name / "SKILL.md").is_file()


def test_procedures_name_the_cost_tooling(project: Path) -> None:
    claim = _procedure(project, "claim-check")
    for command in ("sources slice", "sources find", "ledger get"):
        assert f"scripts.article {command}" in claim, command
    life = _procedure(project, "lifecycle")
    for command in ("flow next --brief", "flow handoff", "check NAME", "index slice"):
        assert command in life, command
    assert "max_calls" in life and "Never edit `docs/ledger/`" in life
    for name in ("red-team", "blue-team"):
        text = _procedure(project, name)
        for command in ("sources slice", "index slice", "flow handoff"):
            assert command in text, (name, command)
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert len(agents.splitlines()) <= MAX_LINES
    for command in ("check", "sources slice", "index slice", "flow next --brief", "flow handoff"):
        assert command in agents, command
    assert not MODEL_NAMES.search(agents) and "go-getter" not in agents
    cli = (project / "docs" / "cli.md").read_text(encoding="utf-8")
    for command in ("check record NAME", "check --cold", "flow handoff", "N002", "N003"):
        assert command in cli, command


def test_dialectic_procedure_and_adapter(project: Path) -> None:
    text = _procedure(project, "dialectic")
    for command in (
        "theses lint",
        "theses gaps",
        "theses dialectic",
        "flow attest dialectic",
        "sources find",
        "sources slice",
    ):
        assert f"scripts.article {command}" in text, command
    for move in ("negation", "negation-of-negation", "synthesis", "aufhebung", "opening"):
        assert f"`{move}`" in text, move
    for field in ("preserved", "cancelled", "lifted", "untraced-reason", "proposed"):
        assert field in text, field
    assert "reading-a-source" in text and "theses add --section" in text
    assert "must cite the move it follows" in text
    for kind in ("map-contradictions", "move-contradiction", "develop-move", "trace-thesis"):
        assert f"`{kind}`" in text, kind
    for check in ("opening-undeveloped", "thesis-restates-pole", "T095"):
        assert text.count(check) >= 1, check
    assert "flow done" in text and "flow handoff" in text
    assert "lifecycle" not in text or "docs/procedures/lifecycle.md" not in text
    life = _procedure(project, "lifecycle")
    assert "docs/procedures/dialectic.md" in life
    _adapter(project, "dialectic")


def test_dialectic_vocabulary_matches_the_cli(project: Path) -> None:
    import sys

    sys.path.insert(0, str(project))
    from scripts.article import dialectic

    text = _procedure(project, "dialectic")
    for move in dialectic.MOVE_TYPES:
        assert f"`{move}`" in text
    for kind in dialectic.CONTRADICTION_KINDS:
        assert f"`{kind}`" in text
    for kind in ("contradiction-unmoved", "move-without-opening", "thesis-untraced"):
        assert kind in dialectic.GAP_KINDS and kind in text
    cli = (project / "scripts" / "article" / "cli.py").read_text(encoding="utf-8")
    assert '"dialectic"' in cli
