"""Template upgrade path: the version stamp and the documented procedure."""

from __future__ import annotations

import json
import re
from pathlib import Path

from conftest import render
from cookiecutter.main import cookiecutter

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "upgrading.md"


def _template_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match
    return match.group(1)


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not {".git", "__pycache__"} & set(p.relative_to(root).parts)
    }


def test_stamp_is_written(default_project: Path) -> None:
    stamp = json.loads((default_project / "template.json").read_text(encoding="utf-8"))

    assert stamp["template_version"] == _template_version()
    assert stamp["template"] == str(ROOT)
    assert "template_commit" in stamp
    ctx = stamp["context"]["cookiecutter"]
    assert ctx["title"] == "A Test Manuscript"
    assert ctx["repo_name"] == default_project.name
    assert ctx["manuscript_kind"] == "perspective"


def test_stamp_survives_special_characters(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path, title='He said "hi" & 100% \\ ok', abstract="x: y # z")
    ctx = json.loads((project / "template.json").read_text(encoding="utf-8"))
    assert ctx["context"]["cookiecutter"]["title"] == 'He said "hi" & 100% \\ ok'
    assert ctx["context"]["cookiecutter"]["abstract"] == "x: y # z"


def test_stored_context_reproduces_the_repo(tmp_path: Path) -> None:
    """The stamp holds enough to re-render the same repo (step 2 of the guide)."""
    original = render(tmp_path=tmp_path / "a")
    stored = json.loads((original / "template.json").read_text(encoding="utf-8"))
    out = tmp_path / "b"
    out.mkdir()
    again = Path(
        cookiecutter(
            stored["template"],
            no_input=True,
            output_dir=str(out),
            extra_context=stored["context"]["cookiecutter"],
        )
    )

    assert _files(again) == _files(original)


def test_upgrade_doc_matches_the_stamp() -> None:
    text = DOC.read_text(encoding="utf-8")
    template_file = ROOT / "{{cookiecutter.repo_name}}" / "template.json"
    assert template_file.is_file()

    for key in ("template", "template_version", "template_commit", "context.cookiecutter"):
        assert f"`{key}`" in text, f"upgrading.md does not document {key}"


def test_upgrade_doc_commands_match_real_files() -> None:
    text = DOC.read_text(encoding="utf-8")

    for command in ("make metadata", "make validate"):
        assert command in text
        target = command.split()[1]
        makefile = (ROOT / "{{cookiecutter.repo_name}}" / "Makefile").read_text(encoding="utf-8")
        assert re.search(rf"^{target}:", makefile, re.MULTILINE), f"Makefile has no {target}"
    assert (ROOT / "{{cookiecutter.repo_name}}" / "docs" / "migrating-to-v2.md").is_file()
    assert "never" in text.lower() and "merges" in text.lower()
    assert "cruft" in text and "Copier" in text
