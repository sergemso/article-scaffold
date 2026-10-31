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
    for name in ("topic", "title", "version", "license", "owner", "skip_pre_push_hook"):
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


def test_no_pat_and_owner_defaults_to_the_org() -> None:
    text = WORKFLOW.read_text()
    assert "GH_PAT" not in text and "COMPANION" not in text.replace("companion", "")
    assert _doc()["on"]["workflow_dispatch"]["inputs"]["owner"]["default"] == "strebulaev-articles"


def test_tokens_come_from_the_app_token_action() -> None:
    steps = _doc()["jobs"]["bootstrap"]["steps"]
    minted = [s for s in steps if s.get("uses") == "./.github/actions/app-token"]
    assert [s["id"] for s in minted] == ["admin_token", "push_token"]
    assert "repositories" not in minted[0]["with"]
    assert minted[1]["with"]["repositories"] == "${{ steps.validate.outputs.repo_name }}"
    assert minted[1]["with"]["permission-contents"] == "write"
    for s in minted:
        assert s["with"]["owner"] == "${{ steps.validate.outputs.owner }}"


def test_repo_creation_passes_visibility_explicitly() -> None:
    text = WORKFLOW.read_text()
    assert 'orgs/${OWNER}/repos' in text and '-F private="$PRIVATE"' in text
