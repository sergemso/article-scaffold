"""A fresh render must already be coherent and metadata regeneration a no-op."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import SPECIAL_ABSTRACT, SPECIAL_TITLE, commit_all, render, run

FIXTURES = [
    pytest.param({}, id="default"),
    pytest.param({"doi": "10.5281/zenodo.1234567"}, id="doi-set"),
    pytest.param(
        {
            "title": SPECIAL_TITLE,
            "abstract": SPECIAL_ABSTRACT,
            "keywords": 'quotes, "100%", #hashtag, ünïcode',
        },
        id="hostile-input",
    ),
]


@pytest.mark.parametrize("context", FIXTURES)
def test_render_then_metadata_is_clean(tmp_path: Path, context: dict[str, str]) -> None:
    project = render(tmp_path=tmp_path, **context)
    commit_all(project)

    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout

    diff = run(project, "git", "diff", "--exit-code")
    assert diff.returncode == 0, diff.stdout + diff.stderr
    status = run(project, "git", "status", "--porcelain")
    assert status.stdout.strip() == "", status.stdout
