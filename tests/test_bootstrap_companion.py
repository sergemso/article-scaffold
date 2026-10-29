"""bootstrap-article.yml defaults to private and provisions the companion."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/bootstrap-article.yml"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def test_default_visibility_is_private() -> None:
    inputs = _doc()["on"]["workflow_dispatch"]["inputs"]
    assert inputs["repo_visibility"]["default"] == "private"
    assert set(inputs["repo_visibility"]["options"]) == {"public", "private"}
    assert inputs["create_companion"]["default"] is True


def test_existing_inputs_are_intact() -> None:
    inputs = _doc()["on"]["workflow_dispatch"]["inputs"]
    for name in ("topic", "title", "version", "license", "new_repo_owner", "skip_pre_push_hook"):
        assert name in inputs


def test_companion_job_calls_provisioning_for_the_new_repo() -> None:
    doc = _doc()
    job = doc["jobs"]["companion"]
    assert job["needs"] == "bootstrap"
    assert job["if"] == "inputs.create_companion"
    assert job["uses"] == "./.github/workflows/provision-companion.yml"
    assert job["with"]["repo"] == "${{ needs.bootstrap.outputs.repo_full }}"
    assert job["with"]["dry_run"] is False
    assert job["secrets"] == "inherit"
    assert job["permissions"] == {"contents": "read"}
    assert "repo_full" in doc["jobs"]["bootstrap"]["outputs"]


def test_summary_points_at_the_zenodo_skill() -> None:
    assert "enabling-zenodo-for-a-companion" in WORKFLOW.read_text()
