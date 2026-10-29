"""Derived citation URLs follow companion.yaml."""

from __future__ import annotations

import re
from pathlib import Path

from conftest import render, run

PRIVATE = "github.com/test-user/articles.test_topic"
COMPANION = PRIVATE + ".public"
# The private name is a prefix of the companion name, so look for it followed
# by anything other than ".public".
PRIVATE_ONLY = re.compile(re.escape(PRIVATE) + r"(?!\.public)")


def _generate(project: Path) -> None:
    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stdout + result.stderr


def test_default_companion_points_citations_at_companion(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _generate(project)

    for name in ("CITATION.cff", "README.md"):
        text = (project / name).read_text()
        assert COMPANION in text, name
        assert not PRIVATE_ONLY.search(text), name


def test_metadata_is_idempotent(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _generate(project)
    first = {n: (project / n).read_text() for n in ("CITATION.cff", "README.md")}
    _generate(project)
    assert first == {n: (project / n).read_text() for n in first}
    assert run(project, "make", "metadata-check").returncode == 0


def test_without_companion_yaml_urls_are_unchanged(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "companion.yaml").unlink()
    _generate(project)

    cff = (project / "CITATION.cff").read_text()
    assert f"https://{PRIVATE}\n" in cff
    assert COMPANION not in cff
    assert COMPANION not in (project / "README.md").read_text()


def test_invalid_companion_yaml_is_a_clean_error(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "companion.yaml").write_text("version: 1\nrepo: nope\n")

    result = run(project, "python3", "-m", "scripts.article", "metadata", "--json")
    assert "Traceback" not in result.stderr
    assert result.returncode != 0
    assert "companion.yaml" in result.stdout
