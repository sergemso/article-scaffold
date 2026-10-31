"""The app-token composite action: allowlist check, pinned mint, no token echo."""

from pathlib import Path

import yaml

ACTION = Path(".github/actions/app-token/action.yml")


def _action() -> dict:
    return yaml.safe_load(ACTION.read_text())


def test_action_is_composite() -> None:
    doc = _action()
    assert doc["runs"]["using"] == "composite"
    assert doc["inputs"]["owner"]["required"] is True


def test_owner_checked_against_allowlist_before_minting() -> None:
    steps = _action()["runs"]["steps"]
    check = steps[0]
    assert "inputs.allowed-owners" in check["env"]["APP_OWNERS"]
    assert "vars." not in str(_action()["runs"])  # no vars context in a composite action
    assert "grep -Fxq" in check["run"] and "exit 1" in check["run"]
    mint = next(s for s in steps if s.get("id") == "mint")
    assert steps.index(check) < steps.index(mint)
    assert mint["uses"].startswith("actions/create-github-app-token@")
    assert mint["with"]["owner"] == "${{ inputs.owner }}"


def test_owner_is_not_interpolated_into_the_script() -> None:
    for step in _action()["runs"]["steps"]:
        assert "${{" not in step.get("run", ""), "use env, not expressions, inside run:"


def test_token_is_never_echoed() -> None:
    text = ACTION.read_text()
    for step in _action()["runs"]["steps"]:
        run = step.get("run", "")
        assert "steps.mint.outputs.token" not in run
        assert "echo" not in run.replace("echo \"::error::", "")
    assert text.count("steps.mint.outputs.token") == 1  # only the declared output


def test_repositories_has_no_widening_default() -> None:
    inputs = _action()["inputs"]
    assert inputs["repositories"]["default"] == ""
    for name, spec in inputs.items():
        if name.startswith("permission-"):
            assert spec["default"] == ""


def test_every_caller_passes_the_allowlist() -> None:
    from pathlib import Path

    for wf in Path(".github/workflows").glob("*.yml"):
        text = wf.read_text(encoding="utf-8")
        uses = text.count("uses: ./.github/actions/app-token")
        assert text.count("allowed-owners: ${{ vars.APP_OWNERS }}") == uses, wf
