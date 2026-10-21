"""CI and `make validate` must call the same single validator implementation."""

from __future__ import annotations

from pathlib import Path

import yaml
from conftest import render, run

VALIDATOR_COMMAND = "python3 scripts/validate-paper.py"


def _workflow(project: Path) -> dict:
    return yaml.safe_load(
        (project / ".github" / "workflows" / "validate-latex.yml").read_text()
    )


def _make_validate_recipe(makefile: str) -> list[str]:
    lines = makefile.splitlines()
    in_target = False
    recipe: list[str] = []
    for line in lines:
        if line.startswith("validate:"):
            in_target = True
            continue
        if not in_target:
            continue
        if line.startswith("\t"):
            recipe.append(line.strip().lstrip("@"))
        elif line.strip() == "" or line.lstrip().startswith("#"):
            continue
        else:
            break
    return recipe


def _run_steps(workflow: dict) -> list[str]:
    return [
        step["run"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "run" in step
    ]


def _on_block(workflow: dict) -> dict:
    # PyYAML follows YAML 1.1 and parses the key `on` as boolean True.
    return workflow.get("on", workflow.get(True))


def test_make_and_ci_use_the_same_entrypoint(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    recipe = _make_validate_recipe((project / "Makefile").read_text())
    assert recipe[0] == VALIDATOR_COMMAND

    workflow = _workflow(project)
    assert _run_steps(workflow) == [VALIDATOR_COMMAND]

    result = run(project, "make", "validate")
    assert result.returncode == 0, result.stderr + result.stdout


def test_workflow_has_no_duplicated_validator_logic(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    text = (project / ".github" / "workflows" / "validate-latex.yml").read_text()
    assert "python3 - <<" not in text
    assert "re.findall" not in text
    assert "sys.exit" not in text
    assert text.count("python3 scripts/validate-paper.py") == 1


def test_workflow_permissions_concurrency_and_paths(tmp_path: Path) -> None:
    workflow = _workflow(render(tmp_path=tmp_path))
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert "github.ref" in workflow["concurrency"]["group"]

    on_block = _on_block(workflow)
    for event in ("push", "pull_request"):
        paths = on_block[event]["paths"]
        assert "paper/**" in paths
        assert "scripts/**" in paths
        assert "Makefile" in paths
        assert ".github/workflows/validate-latex.yml" in paths
