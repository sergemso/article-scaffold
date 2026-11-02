"""Guardrail article-tooling-is-host-neutral: nothing shipped names go-getter or a model,
and host-specific paths exist only as thin adapters."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import render

MODEL_NAMES = re.compile(r"\b(claude|anthropic|gpt|openai|opus|sonnet|haiku|gemini|llama)\b", re.I)
# Directories and files that belong to one agent host.
HOST_PATHS = (".claude", ".cursor", ".codex", ".gemini", ".windsurf", "CLAUDE.md", "GEMINI.md")
# Words the template needs for a reason other than depending on that host: the detector of
# agent names, a bibliography placeholder, and a deny pattern keeping host files private.
ALLOWED = {
    ("scripts/article/theses.py", "claude"),
    ("scripts/article/theses.py", "gpt"),
    ("scripts/article/migrations.py", "anthropic"),
    ("companion.yaml", "claude"),
}
ADAPTER_ROOT = Path(".claude") / "skills"
MAX_ADAPTER_LINES = 15


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path=tmp_path_factory.mktemp("neutral"))


def _files(project: Path) -> list[Path]:
    return [
        p
        for p in sorted(project.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(project).parts
    ]


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def violations(project: Path) -> list[str]:
    found: list[str] = []
    for path in _files(project):
        rel = path.relative_to(project)
        if any(part in HOST_PATHS for part in rel.parts) and not rel.is_relative_to(ADAPTER_ROOT):
            found.append(f"{rel}: host-specific path outside the adapter location")
        text = _text(path)
        if text is None:
            continue
        if "go-getter" in text.lower():
            found.append(f"{rel}: names go-getter")
        names = {m.group(1).lower() for m in MODEL_NAMES.finditer(text)}
        if any((rel.as_posix(), name) not in ALLOWED for name in names):
            found.append(f"{rel}: names a model or vendor")
        if rel.is_relative_to(ADAPTER_ROOT) and len(text.splitlines()) >= MAX_ADAPTER_LINES:
            found.append(f"{rel}: adapter is not thin")
    return found


def test_rendered_template_is_host_neutral(project: Path) -> None:
    assert violations(project) == []


def test_the_scan_catches_what_it_should(project: Path, tmp_path: Path) -> None:
    probe = tmp_path / "probe"
    (probe / ".claude" / "skills" / "x").mkdir(parents=True)
    (probe / ".claude" / "settings.json").write_text("{}\n")
    (probe / "notes.md").write_text("Run go-getter apply with Claude.\n")
    (probe / ".claude" / "skills" / "x" / "SKILL.md").write_text("pointer\n" * 20)
    found = violations(probe)
    assert any("settings.json" in v and "outside the adapter" in v for v in found)
    assert any("notes.md" in v and "go-getter" in v for v in found)
    assert any("notes.md" in v and "model" in v for v in found)
    assert any("SKILL.md" in v and "not thin" in v for v in found)


def test_every_adapter_points_at_a_neutral_procedure(project: Path) -> None:
    adapters = sorted((project / ADAPTER_ROOT).glob("*/SKILL.md"))
    assert adapters
    for adapter in adapters:
        name = adapter.parent.name
        assert f"docs/procedures/{name}.md" in adapter.read_text(encoding="utf-8")
        assert (project / "docs" / "procedures" / f"{name}.md").is_file()
