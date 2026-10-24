"""The `upgrade` subcommand: JSON contract, exit codes and the Make target."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
from conftest import run

STATUS = "scripts/article/status.py"


@pytest.fixture()
def project(upgrade_project: Path) -> Path:
    return upgrade_project


def _upgrade(project: Path, *args: str):
    # sys.executable has cookiecutter; the scrubbed PATH's python3 may not.
    return run(project, sys.executable, "-m", "scripts.article", "upgrade", *args)


def _payload(project: Path, result) -> dict:
    assert result.stdout.strip(), result.stderr
    payload = json.loads(result.stdout)
    schema = json.loads((project / "schemas" / "upgrade.schema.json").read_text())
    jsonschema.validate(payload, schema)
    return payload


def test_plan_is_the_default_and_matches_the_schema(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    result = _upgrade(project, "--json", "--to", upgrade_template["b"])
    payload = _payload(project, result)

    assert result.returncode == 0, result.stderr
    assert payload["mode"] == "plan" and payload["ok"] is True
    assert payload["plan"]["old"] == upgrade_template["a"]
    assert payload["plan"]["new"] == upgrade_template["b"]
    assert payload["refusals"] == []


def test_a_refusal_exits_1_and_still_matches_the_schema(project: Path) -> None:
    (project / "notes.txt").write_text("dirty", encoding="utf-8")
    result = _upgrade(project, "--plan", "--json")
    payload = _payload(project, result)

    assert result.returncode == 1
    assert [r["code"] for r in payload["refusals"]] == ["U005"]


def test_text_output_for_an_up_to_date_repository(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    result = _upgrade(project, "--to", upgrade_template["a"])

    assert result.returncode == 0, result.stderr
    assert "already up to date" in result.stdout


def test_apply_then_finish_through_the_cli(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    applied = _upgrade(project, "--apply", "--json", "--to", upgrade_template["b"])
    apply_payload = _payload(project, applied)

    assert applied.returncode == 0, applied.stderr
    assert apply_payload["mode"] == "apply"
    assert sorted(apply_payload["applied"]) == ["docs/NEW.md", STATUS]

    finished = _upgrade(project, "--finish", "--json")
    finish_payload = _payload(project, finished)

    assert finished.returncode == 0, finished.stderr
    assert finish_payload["finished"] is True
    stamp = json.loads((project / "template.json").read_text(encoding="utf-8"))
    assert stamp["template_commit"] == upgrade_template["b"]


def test_conflicts_exit_1_and_are_listed(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    path = project / STATUS
    path.write_text(path.read_text(encoding="utf-8") + "\n# my own ending\n", encoding="utf-8")
    run(project, "git", "commit", "-qam", "local edit", check=True)
    result = _upgrade(project, "--apply", "--json", "--to", upgrade_template["b"])
    payload = _payload(project, result)

    assert result.returncode == 1
    assert payload["ok"] is False and payload["conflicted"] == [STATUS]


def test_an_upgrade_error_is_reported_as_json(project: Path) -> None:
    result = _upgrade(project, "--finish", "--json")
    payload = _payload(project, result)

    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "U014"


def test_modes_are_mutually_exclusive(project: Path) -> None:
    result = _upgrade(project, "--plan", "--apply")

    assert result.returncode == 2
    assert "usage error" in result.stderr


def test_commit_needs_apply(project: Path) -> None:
    result = _upgrade(project, "--plan", "--commit")

    assert result.returncode == 2
    assert "--commit only goes with --apply" in result.stderr


def test_make_upgrade_runs_the_plan(project: Path) -> None:
    result = run(project, "make", "upgrade")

    assert result.returncode == 0, result.stderr
    assert "from " in result.stdout


def test_cli_doc_covers_every_upgrade_flag() -> None:
    doc = Path(__file__).resolve().parents[1] / "{{cookiecutter.repo_name}}" / "docs" / "cli.md"
    text = doc.read_text(encoding="utf-8")

    for flag in ("--plan", "--apply", "--finish", "--to", "upgrade.schema.json", "make upgrade"):
        assert flag in text, f"cli.md does not mention {flag}"


def test_upgrading_doc_describes_the_command_and_keeps_the_manual_fallback() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "upgrading.md").read_text(
        encoding="utf-8"
    )

    for needle in ("upgrade --plan", "upgrade --apply", "upgrade --finish", "make upgrade"):
        assert needle in text, f"upgrading.md does not mention {needle}"
    assert "Automatic upgrade pull requests" in text and "upgrade.yml" in text
    assert "Three-way merge by hand" in text
    assert "docs/migrating-to-v2.md" in text
