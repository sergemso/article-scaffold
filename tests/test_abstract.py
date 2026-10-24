"""The abstract, keywords, masthead and version blocks are generated."""

from __future__ import annotations

from pathlib import Path

import yaml
from conftest import render, run


def _rewrite_metadata(project: Path) -> None:
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(
        {
            "title": "New title with 100% & quotes",
            "abstract": "New abstract with 100% & # and — unicode.",
            "abstract_note": "New note with 50% & more.",
            "keywords": ["alpha", "beta & gamma"],
            "version": "2.0.0",
            "version_label": "v2 preprint",
            "date": "2026-02-03",
            "target_deposit": "arXiv",
        }
    )
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _assert_single_block(text: str, start: str, end: str) -> None:
    assert text.count(start) == 1, f"{start} appears {text.count(start)} times"
    assert text.count(end) == 1, f"{end} appears {text.count(end)} times"


def test_metadata_blocks_update_without_duplication(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _rewrite_metadata(project)

    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout

    abstract = (project / "paper" / "sections" / "00_abstract.tex").read_text()
    _assert_single_block(abstract, "% ABSTRACT:START", "% ABSTRACT:END")
    assert abstract.count("New abstract with 100\\% \\& \\# and — unicode.") == 1
    assert abstract.count("Keywords:} alpha, beta \\& gamma.") == 1
    assert "New note with 50\\% \\& more." in abstract

    readme = (project / "README.md").read_text()
    _assert_single_block(readme, "<!-- README:META:START -->", "<!-- README:META:END -->")
    assert "# New title with 100% & quotes" in readme
    assert "**Version:** v2 preprint (2026-02-03)" in readme
    assert "New abstract with 100% & # and — unicode." in readme

    changes = (project / "CHANGES.md").read_text()
    _assert_single_block(
        changes, "<!-- CHANGES:CURRENT:START -->", "<!-- CHANGES:CURRENT:END -->"
    )
    assert "## v2 preprint - 2026-02-03 (current)" in changes
    assert "Initial scaffolded version." in changes

    backmatter = (project / "paper" / "sections" / "08_backmatter.tex").read_text()
    _assert_single_block(
        backmatter,
        "% BACKMATTER:VERSION:START",
        "% BACKMATTER:VERSION:END",
    )
    assert "version~2.0.0" in backmatter
    assert "2026-02-03, prepared for arXiv" in backmatter


def test_regeneration_is_idempotent(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _rewrite_metadata(project)

    first = run(project, "make", "metadata")
    assert first.returncode == 0, first.stderr + first.stdout

    paths = [
        project / "paper" / "sections" / "00_abstract.tex",
        project / "README.md",
        project / "CHANGES.md",
        project / "paper" / "sections" / "08_backmatter.tex",
    ]
    before = {path: path.read_text() for path in paths}

    second = run(project, "make", "metadata")
    assert second.returncode == 0, second.stderr + second.stdout
    after = {path: path.read_text() for path in paths}
    assert before == after


def test_renumbered_sections_are_still_found(tmp_path: Path) -> None:
    """Authors renumber sections; the generator finds abstract and backmatter by name."""
    project = render(tmp_path=tmp_path)
    sections = project / "paper" / "sections"
    (sections / "08_backmatter.tex").rename(sections / "15_backmatter.tex")
    (sections / "00_abstract.tex").rename(sections / "01_abstract.tex")

    result = run(project, "make", "metadata")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "version~" in (sections / "15_backmatter.tex").read_text(encoding="utf-8")
    assert not (sections / "08_backmatter.tex").exists()
    assert not (sections / "00_abstract.tex").exists()
    assert run(project, "make", "metadata-check").returncode == 0


def test_release_notes_are_written_under_the_version_heading(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    changes = project / "CHANGES.md"
    heading_only = changes.read_text(encoding="utf-8")
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data["release_notes"] = "First public version.\n\n### Contents\n- One thing\n- Another\n"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    assert run(project, "make", "metadata").returncode == 0

    text = changes.read_text(encoding="utf-8")
    block = text.split("<!-- CHANGES:CURRENT:START -->")[1].split("<!-- CHANGES:CURRENT:END -->")[0]
    assert block.splitlines()[1:] == [
        "## v1 preprint - 2026-01-02 (current)",
        "",
        "First public version.",
        "",
        "### Contents",
        "- One thing",
        "- Another",
    ]
    assert run(project, "make", "metadata-check").returncode == 0

    del data["release_notes"]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    assert run(project, "make", "metadata").returncode == 0
    assert changes.read_text(encoding="utf-8") == heading_only
