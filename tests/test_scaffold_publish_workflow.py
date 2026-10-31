"""Static checks for the scaffold's publish-companion workflow (decision 0063)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/publish-companion.yml")


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps_text(job: dict) -> str:
    return yaml.safe_dump(job.get("steps", []))


def _run_blocks(job: dict) -> list[str]:
    return [s["run"] for s in job["steps"] if "run" in s]


def test_jobs_and_triggers() -> None:
    doc = _doc()
    assert list(doc["jobs"]) == ["snapshot", "publish"]
    triggers = doc["on"]
    assert list(triggers) == ["workflow_dispatch"]
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert inputs["owner"]["default"] == "strebulaev-articles"
    assert inputs["repo"]["required"] is True
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


def test_publish_runs_only_when_not_dry_and_gate_allows() -> None:
    publish = _doc()["jobs"]["publish"]
    assert publish["needs"] == "snapshot"
    assert "!inputs.dry_run" in publish["if"]
    assert "needs.snapshot.outputs.allowed == 'true'" in publish["if"]


def test_gate_and_validation_run_in_the_snapshot_job() -> None:
    steps = _steps_text(_doc()["jobs"]["snapshot"])
    assert "companion --gate" in steps
    assert "make validate" in steps
    assert "companion --build" in steps
    assert "companion-snapshot" in steps


def test_snapshot_job_mints_only_a_read_token_for_one_repo() -> None:
    steps = _doc()["jobs"]["snapshot"]["steps"]
    mints = [s for s in steps if s.get("uses") == "./.github/actions/app-token"]
    assert len(mints) == 1
    with_ = mints[0]["with"]
    assert with_["permission-contents"] == "read"
    assert with_["repositories"] == "${{ inputs.repo }}"
    assert "permission-administration" not in with_ and "permission-workflows" not in with_
    checkout = next(s for s in steps if s.get("with", {}).get("path") == "article")
    assert checkout["with"]["persist-credentials"] is False


def test_publish_token_is_write_and_narrowed_to_the_companion() -> None:
    steps = _doc()["jobs"]["publish"]["steps"]
    mints = [s for s in steps if s.get("uses") == "./.github/actions/app-token"]
    assert len(mints) == 1
    with_ = mints[0]["with"]
    assert with_["permission-contents"] == "write"
    assert with_["repositories"] == "${{ steps.target.outputs.name }}"
    assert with_["owner"] == "${{ inputs.owner }}"


def test_publish_job_runs_no_article_code() -> None:
    text = "\n".join(_run_blocks(_doc()["jobs"]["publish"]))
    assert "scripts.article" not in text
    assert "make " not in text
    assert "/article" not in text


def test_companion_target_from_the_plan_is_validated() -> None:
    job = _doc()["jobs"]["publish"]
    target = next(s for s in job["steps"] if s.get("id") == "target")["run"]
    assert "fullmatch" in target
    assert "m.group(1) != owner" in target
    assert "m.group(2) == article" in target


def test_no_expressions_of_untrusted_values_inside_run() -> None:
    for name, job in _doc()["jobs"].items():
        for block in _run_blocks(job):
            assert "${{" not in block, f"{name}: expression inside run:\n{block}"


def test_inputs_are_validated_before_use() -> None:
    first = _doc()["jobs"]["snapshot"]["steps"][0]["run"]
    for var in ("OWNER", "REPO", "TAG"):
        assert f'"${var}" =~' in first


def test_token_is_never_echoed_or_put_in_a_url() -> None:
    text = WORKFLOW.read_text()
    for line in text.splitlines():
        assert not re.search(r"echo[^\n]*\$\{?GH_TOKEN", line), line
        assert "@github.com" not in line, line
    assert "https://x-access-token" not in text
    assert "add-mask" in text
    assert "COMPANION_TOKEN" not in text and "GH_PAT" not in text


def test_existing_tag_is_compared_never_moved() -> None:
    text = WORKFLOW.read_text()
    assert "already published" in text
    assert "--force" not in text and "push -f" not in text
    assert "--atomic" in text


def test_release_is_created_through_the_releases_api_with_generic_notes() -> None:
    text = WORKFLOW.read_text()
    release = text[text.index("POST") :]
    assert "repos/${REPO}/releases" in release
    assert "GITHUB_REPOSITORY" not in release
    assert "github.repository" not in release
    assert "inputs.repo" not in release


def test_snapshot_upload_keeps_dotfiles() -> None:
    # .zenodo.json is a dotfile; upload-artifact drops hidden files unless told otherwise.
    workflow = Path(__file__).resolve().parent.parent / ".github/workflows/publish-companion.yml"
    text = workflow.read_text(encoding="utf-8")
    block = text.split("name: companion-snapshot", 1)[1].split("retention-days", 1)[0]
    assert "include-hidden-files: true" in block
