"""Ensure no workflow assumes a hard-coded default branch."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import render

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / ".github" / "workflows" / "bootstrap-article.yml"

# Actions does not evaluate expressions in `on:` (docs/facts/0001), so a branch
# filter must be the literal branch chosen at generation time (decision 0056).


def _push_branches(workflow: Path) -> list[str] | None:
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on` as the boolean True.
    on = doc.get("on", doc.get(True))
    if not isinstance(on, dict):
        return None
    push = on.get("push")
    if not isinstance(push, dict):
        return None
    branches = push.get("branches")
    return [str(b) for b in branches] if isinstance(branches, list) else None


def test_bootstrap_has_no_hardcoded_master() -> None:
    text = BOOTSTRAP.read_text()
    # The bootstrap workflow pushes to HEAD/default branch, not a literal name.
    assert "origin master" not in text
    assert "origin main" not in text
    # It should use the dynamic default branch from the rendered repo
    assert "rev-parse --abbrev-ref HEAD" in text


@pytest.mark.parametrize("branch", ["main", "master"])
def test_rendered_workflows_filter_on_the_chosen_branch(tmp_path: Path, branch: str) -> None:
    project = render(tmp_path=tmp_path, default_branch=branch)
    filtered = 0
    for workflow in sorted((project / ".github" / "workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        assert "__DEFAULT_BRANCH__" not in text, f"{workflow.name}: placeholder left behind"
        branches = _push_branches(workflow)
        if branches is None:
            continue
        filtered += 1
        assert branches == [branch], f"{workflow.name}: on.push.branches is {branches!r}"
    assert filtered, "no rendered workflow has an on.push.branches filter to check"


def _on_block(workflow: Path) -> object:
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return doc.get("on", doc.get(True))


def test_template_workflows_keep_the_placeholder_and_no_expression_in_on() -> None:
    """The unrendered template keeps the placeholder the post-gen hook substitutes.

    An expression is fine in a step (the upgrade workflow reads the default branch
    there); it is only dead inside `on:`.
    """
    workflows = ROOT / "{{cookiecutter.repo_name}}" / ".github" / "workflows"
    paths = sorted(workflows.glob("*.yml"))
    assert any("__DEFAULT_BRANCH__" in p.read_text(encoding="utf-8") for p in paths)
    for path in paths:
        assert "${{" not in str(_on_block(path)), f"{path.name}: expression inside on:"
