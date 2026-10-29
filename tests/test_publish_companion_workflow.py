"""Static checks for the article-repo publish-companion workflow."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW = Path("{{cookiecutter.repo_name}}/.github/workflows/publish-companion.yml")


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps_text(job: dict) -> str:
    return yaml.safe_dump(job.get("steps", []))


def test_jobs_and_triggers() -> None:
    doc = _doc()
    assert list(doc["jobs"]) == ["gate", "build", "snapshot", "publish"]
    triggers = doc["on"]
    assert triggers["push"]["tags"] == ["v*"]
    assert "pull_request" not in triggers and "pull_request_target" not in triggers
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert inputs["tag"]["required"] is True
    assert inputs["dry_run"]["default"] is True


def test_no_expressions_in_on_block() -> None:
    assert "${{" not in yaml.safe_dump(_doc()["on"])


def test_permissions_and_concurrency() -> None:
    doc = _doc()
    assert doc["permissions"] == {}
    for name, job in doc["jobs"].items():
        assert job["permissions"] == {"contents": "read"}, name
    assert doc["concurrency"]["cancel-in-progress"] is False
    assert "publish-companion" in doc["concurrency"]["group"]


def test_secret_appears_only_in_the_publish_job() -> None:
    doc = _doc()
    for name, job in doc["jobs"].items():
        mentions = "COMPANION_TOKEN" in yaml.safe_dump(job)
        assert mentions == (name == "publish"), name
    assert WORKFLOW.read_text().count("secrets.COMPANION_TOKEN") == 1


def test_secret_is_passed_by_env_and_never_echoed_or_put_in_a_url() -> None:
    text = WORKFLOW.read_text()
    assert "secrets.COMPANION_TOKEN" in text
    run_lines = [ln for ln in text.splitlines() if "COMPANION_TOKEN" in ln]
    for line in run_lines:
        assert not re.search(r"echo[^\n]*\$\{?COMPANION_TOKEN", line), line
        assert "@github.com" not in line, line
    assert "https://x-access-token" not in text
    assert "add-mask" in text


def test_gate_calls_the_cli_and_publish_depends_on_it() -> None:
    doc = _doc()
    assert "companion --gate" in _steps_text(doc["jobs"]["gate"])
    publish = doc["jobs"]["publish"]
    assert set(publish["needs"]) == {"gate", "snapshot"}
    assert publish["if"] == "needs.gate.outputs.publish == 'true'"


def test_snapshot_validates_scans_and_uploads() -> None:
    steps = _steps_text(_doc()["jobs"]["snapshot"])
    assert "make validate" in steps
    assert "companion --build" in steps
    assert "companion-snapshot" in steps
    assert "retention-days: 7" in steps or "retention-days" in steps


def test_build_reuses_the_shared_workflow() -> None:
    assert _doc()["jobs"]["build"]["uses"] == "./.github/workflows/reusable-build.yml"


def test_existing_tag_is_compared_never_moved() -> None:
    text = WORKFLOW.read_text()
    assert "already published" in text
    assert "--force" not in text and "push -f" not in text
    assert "--atomic" in text
    assert "--verify-tag" in text


def test_release_notes_cannot_name_the_private_repo() -> None:
    text = WORKFLOW.read_text()
    release_cmd = text[text.index("gh release create") :]
    assert "GITHUB_REPOSITORY" not in release_cmd
    assert "github.repository" not in release_cmd
