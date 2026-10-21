"""Ensure no workflow assumes a hard-coded default branch."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "cookiecutter.repo_name" / ".github" / "workflows"
BOOTSTRAP = ROOT / ".github" / "workflows" / "bootstrap-article.yml"

# Regex to catch hard-coded branch filters like "branches: [master]" or
# "branches: ['main']" in YAML. The dynamic pattern
# "${{ github.event.repository.default_branch }}" is the only allowed form.
HARDCODED_BRANCH_RE = re.compile(
    r"branches:\s*\[\s*(?:'?\w+'?)\s*\]", re.IGNORECASE
)


def _yaml_branches(doc: dict) -> list[str]:
    """Extract literal branch lists from a parsed workflow."""
    on = doc.get("on")
    if not isinstance(on, dict):
        return []
    branches = on.get("push", {}).get("branches")
    if isinstance(branches, list):
        return [str(b) for b in branches]
    return []


def test_bootstrap_has_no_hardcoded_master() -> None:
    text = BOOTSTRAP.read_text()
    # The bootstrap workflow pushes to HEAD/default branch, not a literal name.
    assert "origin master" not in text
    assert "origin main" not in text
    # It should use the dynamic default branch from the rendered repo
    assert "rev-parse --abbrev-ref HEAD" in text


def test_template_workflows_use_dynamic_default_branch() -> None:
    for workflow in WORKFLOW_DIR.glob("*.yml"):
        text = workflow.read_text()
        doc = yaml.safe_load(text)
        for branch in _yaml_branches(doc):
            if branch not in ("${{ github.event.repository.default_branch }}",):
                raise AssertionError(
                    f"{workflow.name}: hard-coded branch filter {branch!r}; "
                    "use '${{ github.event.repository.default_branch }}' instead"
                )
        # Also grep the raw text for any literal master/main in branches context
        if HARDCODED_BRANCH_RE.search(text):
            # Allow the dynamic pattern; fail if anything else looks like a
            # static branch name in a branches list.
            for match in HARDCODED_BRANCH_RE.finditer(text):
                if "default_branch" not in match.group(0):
                    raise AssertionError(
                        f"{workflow.name}: possible hard-coded branch filter: {match.group(0)}"
                    )


def test_post_gen_uses_cookiecutter_default_branch() -> None:
    hook = ROOT / "hooks" / "post_gen_project.py"
    text = hook.read_text()
    assert '{{ cookiecutter.default_branch }}' in text
    assert "master" not in text or "default_branch" in text  # master only via default_branch


def test_cookiecutter_has_default_branch_choice() -> None:
    data = yaml.safe_load(ROOT.joinpath("cookiecutter.json").read_text())
    assert "default_branch" in data
    choices = data["default_branch"]
    assert isinstance(choices, list)
    assert "main" in choices
    assert "master" in choices


def test_cookiecutter_prompts_for_default_branch() -> None:
    data = yaml.safe_load(ROOT.joinpath("cookiecutter.json").read_text())
    prompts = data.get("__prompts__", {})
    assert "default_branch" in prompts
    assert "__prompt__" in prompts["default_branch"]