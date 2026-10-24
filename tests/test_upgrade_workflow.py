"""The scheduled upgrade workflow: its shape, and its shell logic run for real.

The `run:` blocks are extracted from the YAML and executed against a generated repo with
a stub `gh` and a bare repo as `origin`, so the skip conditions, the branch push and the
draft decision are exercised without GitHub.
"""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import run

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "{{cookiecutter.repo_name}}"
    / ".github"
    / "workflows"
    / "upgrade.yml"
)
STATUS = "scripts/article/status.py"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps() -> dict[str, dict]:
    return {step["name"]: step for step in _doc()["jobs"]["upgrade"]["steps"]}


def test_triggers_are_a_weekly_schedule_and_a_manual_run() -> None:
    triggers = _doc()[True] if True in _doc() else _doc()["on"]

    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert len(triggers["schedule"]) == 1 and "cron" in triggers["schedule"][0]


def test_permissions_are_read_only_except_for_the_one_job() -> None:
    doc = _doc()

    assert doc["permissions"] == {"contents": "read"}
    assert doc["jobs"]["upgrade"]["permissions"] == {
        "contents": "write",
        "pull-requests": "write",
    }
    assert list(doc["jobs"]) == ["upgrade"]


def test_the_workflow_never_finishes_or_runs_untrusted_code() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "--finish" not in text.replace("`python3 -m scripts.article upgrade --finish`", "")
    assert "pull_request_target" not in text
    assert "upgrade --apply --commit" in text
    # Untrusted-looking values reach scripts through env, never by ${{ }} interpolation in run.
    for step in _steps().values():
        assert "${{" not in step.get("run", ""), step["name"]


def test_steps_after_the_plan_are_conditional_on_it() -> None:
    steps = _steps()

    for name in (
        "Stop if the upgrade branch already exists",
        "Apply the upgrade on a branch",
        "Push the branch and open the pull request",
    ):
        assert "steps.plan.outputs.action == 'apply'" in steps[name]["if"], name
    assert "exists == 'false'" in steps["Apply the upgrade on a branch"]["if"]


def test_the_run_blocks_are_clean_shell() -> None:
    shellcheck = subprocess.run(["which", "shellcheck"], capture_output=True)
    if shellcheck.returncode != 0:
        pytest.skip("shellcheck is not installed")
    for step in _steps().values():
        if "run" not in step:
            continue
        result = subprocess.run(
            ["shellcheck", "-s", "bash", "-"],
            input="#!/usr/bin/env bash\n" + step["run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{step['name']}: {result.stdout}"


# ── running the shell logic ──────────────────────────────────────────────


@pytest.fixture()
def sandbox(tmp_path: Path, upgrade_project: Path, upgrade_template: dict[str, str]):
    """The generated repo wired to an HTTPS-looking template, a bare origin and a stub gh."""
    shim = tmp_path / "shim"
    shim.mkdir()
    # A symlink would lose the venv (pyvenv.cfg is looked up next to the link), so exec it.
    python = shim / "python3"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    gh_log = tmp_path / "gh.log"
    gh = shim / "gh"
    gh.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{gh_log}"\n', encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(origin)], check=True)
    run(upgrade_project, "git", "remote", "add", "origin", str(origin), check=True)

    stamp_path = upgrade_project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp["template"] = "https://example.test/tpl"
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    run(upgrade_project, "git", "commit", "-qam", "https template", check=True)

    temp = tmp_path / "runner-temp"
    temp.mkdir()
    env = {
        "PATH": f"{shim}:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "RUNNER_TEMP": str(temp),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@invalid",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@invalid",
        # Let the https URL resolve to the local throwaway template.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": f"url.file://{upgrade_template['path']}.insteadOf",
        "GIT_CONFIG_VALUE_0": "https://example.test/tpl",
    }
    return {"project": upgrade_project, "env": env, "origin": origin, "gh_log": gh_log,
            "temp": temp, "tmp": tmp_path, "tpl": upgrade_template}


def _step(sandbox: dict, name: str, **extra: str) -> dict[str, str]:
    """Run one step's script and return the lines it wrote to $GITHUB_OUTPUT."""
    output = Path(sandbox["env"]["GITHUB_OUTPUT"])
    output.write_text("", encoding="utf-8")
    env = {**sandbox["env"], **extra}
    result = subprocess.run(
        ["bash", "-c", _steps()[name]["run"]],
        cwd=sandbox["project"], env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"{name}: {result.stderr}{result.stdout}"
    pairs = [line.partition("=") for line in output.read_text(encoding="utf-8").splitlines()]
    return {key: value for key, _, value in pairs}


def _retarget(sandbox: dict, ref_commit: str) -> None:
    """Point the stamp at an older template commit so the sandbox repo is behind."""
    project = sandbox["project"]
    stamp = json.loads((project / "template.json").read_text(encoding="utf-8"))
    stamp["template_commit"] = ref_commit
    (project / "template.json").write_text(json.dumps(stamp), encoding="utf-8")
    run(project, "git", "commit", "-qam", "stamp", check=True)


def test_plan_step_skips_a_template_that_is_not_https(sandbox: dict) -> None:
    project = sandbox["project"]
    stamp = json.loads((project / "template.json").read_text(encoding="utf-8"))
    stamp["template"] = sandbox["tpl"]["path"]
    (project / "template.json").write_text(json.dumps(stamp), encoding="utf-8")
    run(project, "git", "commit", "-qam", "local template", check=True)
    out = _step(sandbox, "Plan the upgrade")

    assert out["action"] == "skip"
    assert "not an HTTPS URL" in out["reason"]


def test_plan_step_skips_when_there_is_nothing_to_do(sandbox: dict) -> None:
    out = _step(sandbox, "Plan the upgrade")

    assert out["action"] == "apply", out  # stamped at A, template is at B
    _retarget(sandbox, sandbox["tpl"]["b"])
    again = _step(sandbox, "Plan the upgrade")
    assert again["action"] == "skip" and again["reason"] == "already up to date"


def test_plan_step_skips_a_refused_upgrade_with_the_code(sandbox: dict) -> None:
    stamp_path = sandbox["project"] / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp["template_commit"] = None
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    run(sandbox["project"], "git", "commit", "-qam", "null commit", check=True)
    out = _step(sandbox, "Plan the upgrade")

    assert out["action"] == "skip" and "U003" in out["reason"]


def test_plan_step_leaves_the_working_tree_clean(sandbox: dict) -> None:
    _step(sandbox, "Plan the upgrade")

    assert run(sandbox["project"], "git", "status", "--porcelain").stdout == ""
    assert (sandbox["temp"] / "plan.json").is_file()


def _pipeline(sandbox: dict) -> dict[str, str]:
    plan = _step(sandbox, "Plan the upgrade")
    assert plan["action"] == "apply", plan
    branch = plan["branch"]
    existing = _step(sandbox, "Stop if the upgrade branch already exists", BRANCH=branch)
    assert existing["exists"] == "false"
    _step(sandbox, "Apply the upgrade on a branch")
    _step(sandbox, "Push the branch and open the pull request",
          BRANCH=branch, BASE="master", GH_TOKEN="x")
    return plan


def test_a_clean_upgrade_is_pushed_and_opened_as_a_normal_pull_request(sandbox: dict) -> None:
    plan = _pipeline(sandbox)
    gh = sandbox["gh_log"].read_text(encoding="utf-8")

    pushed = subprocess.run(
        ["git", "--git-dir", str(sandbox["origin"]), "branch", "--list", plan["branch"]],
        capture_output=True, text=True,
    ).stdout
    assert plan["branch"] in pushed
    assert gh.startswith("pr create --base master --head " + plan["branch"])
    assert "--draft" not in gh
    body = (sandbox["temp"] / "pr-body.md").read_text(encoding="utf-8")
    assert STATUS in body and "upgrade --finish" in body
    assert run(sandbox["project"], "git", "status", "--porcelain").stdout == ""


def test_conflicts_make_a_draft_pull_request_that_lists_them(sandbox: dict) -> None:
    project = sandbox["project"]
    path = project / STATUS
    path.write_text(path.read_text(encoding="utf-8") + "\n# my own ending\n", encoding="utf-8")
    run(project, "git", "commit", "-qam", "local edit", check=True)
    _pipeline(sandbox)
    gh = sandbox["gh_log"].read_text(encoding="utf-8")
    body = (sandbox["temp"] / "pr-body.md").read_text(encoding="utf-8")

    assert "--draft" in gh
    assert "Conflicts to resolve" in body and f"`{STATUS}`" in body
    assert "<<<<<<<" in path.read_text(encoding="utf-8")


def test_an_existing_remote_branch_stops_the_run(sandbox: dict) -> None:
    plan = _step(sandbox, "Plan the upgrade")
    run(sandbox["project"], "git", "push", "-q", "origin", f"HEAD:refs/heads/{plan['branch']}",
        check=True)
    existing = _step(sandbox, "Stop if the upgrade branch already exists", BRANCH=plan["branch"])

    assert existing["exists"] == "true"


def test_an_apply_error_fails_the_run(sandbox: dict) -> None:
    sandbox["env"]["PATH"] = "/usr/bin:/bin"  # no python3 shim: cookiecutter missing
    plan = subprocess.run(
        ["bash", "-c", _steps()["Apply the upgrade on a branch"]["run"]],
        cwd=sandbox["project"], env=sandbox["env"], capture_output=True, text=True,
    )

    assert plan.returncode != 0
