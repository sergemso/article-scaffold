"""The bootstrap workflow must never interpolate inputs into shell code."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "bootstrap-article.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps() -> list[dict]:
    return _workflow()["jobs"]["bootstrap"]["steps"]


def _step_by_name(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"missing workflow step: {name}")


def test_no_input_expression_reaches_a_run_block() -> None:
    for step in _steps():
        run = step.get("run", "")
        assert "${{ inputs." not in run, step.get("name")
        assert "${{ github.event.inputs." not in run, step.get("name")
        assert "${{" not in run, step.get("name")


def test_validation_runs_before_cookiecutter_or_github_commands() -> None:
    names = [step.get("name", "") for step in _steps()]
    assert names.index("Validate inputs") < names.index("Render template via cookiecutter")
    assert names.index("Validate inputs") < names.index("Create and push new GitHub repo")

    validate = _step_by_name("Validate inputs")
    env = validate["env"]
    for key in ("TOPIC", "VERSION", "LICENSE", "REPO_VISIBILITY", "NEW_REPO_OWNER"):
        assert key in env
    run = validate["run"]
    assert "REPO_NAME=\"articles.${TOPIC}\"" in run
    assert "^[a-z0-9][a-z0-9_-]*$" in run
    assert "^articles\\." in run
    assert "^[0-9]+\\.[0-9]+\\.[0-9]+" in run
    assert "CC-BY-4.0|MIT" in run
    assert "public|private" in run


def test_cookiecutter_uses_explicit_context_and_no_prompts() -> None:
    render = _step_by_name("Render template via cookiecutter")
    run = render["run"]
    assert "cookiecutter --no-input --output-dir" in run
    for key in (
        "TOPIC",
        "TITLE",
        "SUBTITLE",
        "MANUSCRIPT_TYPE",
        "AUTHOR_NAME",
        "AUTHOR_ORCID",
        "AUTHOR_AFFILIATION",
        "VERSION",
        "VERSION_LABEL",
        "LICENSE",
        "TARGET_DEPOSIT",
        "DOI",
        "KEYWORDS",
        "ABSTRACT",
        "OWNER",
        "REPO_NAME",
    ):
        assert key in render["env"]
    assert 'topic="$TOPIC"' in run
    assert 'abstract="$ABSTRACT"' in run


def test_repository_creation_is_idempotent_and_sets_topics() -> None:
    create = _step_by_name("Create and push new GitHub repo")
    run = create["run"]
    assert 'if gh repo view "$REPO_FULL"' in run
    assert run.index("gh repo view") < run.index("gh repo create")
    assert "already exists; refusing to overwrite" in run
    for topic in ("article", "manuscript", "latex", "research"):
        assert f"--add-topic {topic}" in run
    assert "git remote set-url origin" in run
    assert "set +x" in run


def test_permissions_are_explicit() -> None:
    assert _workflow()["permissions"] == {"contents": "read"}
