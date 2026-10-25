"""CI hardening tests: all workflows use pinned actions and least-privilege permissions."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_WORKFLOWS = ROOT / ".github" / "workflows"
TEMPLATE_WORKFLOWS = ROOT / "{{cookiecutter.repo_name}}" / ".github" / "workflows"
ALL_WORKFLOWS = list(SCAFFOLD_WORKFLOWS.glob("*.yml")) + list(TEMPLATE_WORKFLOWS.glob("*.yml"))

# Known pinned action SHAs (subset; add more as needed)
PINNED_ACTIONS = {
    "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",  # v4.2.2
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",  # v5.3.0
    "actions/upload-artifact": "b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882",  # v4.6.1
    "actions/download-artifact": "95815c38cf2ff2164869cbab79da8d1f422bc89e",  # v4.2.1
    "xu-cheng/texlive-action": "f886de8159e5952a131848a5fa9c3196a2132b5d",  # v2
    "softprops/action-gh-release": "c95fe1489396fe8a9eb87c0abf8aa5b2ef267fda",  # v2.2.1
}

# Actions that are allowed to be unpinned (e.g., local reusable workflows)
UNPINNED_ALLOWLIST = {
    "./.github/workflows/reusable-build.yml",
    "actions/checkout",  # checked via PINNED_ACTIONS
    "actions/setup-python",
    "actions/upload-artifact",
    "actions/download-artifact",
    "actions/configure-pages",
    "actions/upload-pages-artifact",
    "xu-cheng/texlive-action",
    "softprops/action-gh-release",
}


# Workflows written by `go-getter apply` ("do not edit"). Permissions and concurrency are
# configured by decision 0058, so they are tested like any other workflow; only the action
# pins are go-getter's own and must merely be SHA-pinned.
GENERATED_WORKFLOWS = {"go-getter-checks.yml"}


def _is_sha(ref: str) -> bool:
    return len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower())


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _find_uses(obj: dict | list, path: str = "") -> list[tuple[str, str, str]]:
    """Recursively find all 'uses:' keys in a workflow dict."""
    results = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "uses" and isinstance(value, str):
                results.append((value, path))
            elif isinstance(value, (dict, list)):
                results.extend(_find_uses(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            results.extend(_find_uses(item, f"{path}[{idx}]"))
    return results


@pytest.mark.parametrize("workflow_path", ALL_WORKFLOWS)
def test_workflow_has_permissions(workflow_path: Path) -> None:
    """Every workflow must declare permissions (at top level or per job)."""
    doc = _load_workflow(workflow_path)
    # Top-level permissions
    top_perms = doc.get("permissions")
    # Job-level permissions
    jobs = doc.get("jobs", {})
    job_perms = all("permissions" in job for job in jobs.values() if isinstance(job, dict))
    assert top_perms or job_perms, (
        f"{workflow_path.name}: missing permissions (top-level or per-job)"
    )


@pytest.mark.parametrize("workflow_path", ALL_WORKFLOWS)
def test_workflow_has_concurrency(workflow_path: Path) -> None:
    """Every workflow should have a concurrency group to avoid duplicate runs."""
    doc = _load_workflow(workflow_path)
    assert "concurrency" in doc, f"{workflow_path.name}: missing concurrency group"


@pytest.mark.parametrize("workflow_path", ALL_WORKFLOWS)
def test_workflow_uses_pinned_actions(workflow_path: Path) -> None:
    """All 'uses:' actions must be pinned to a commit SHA (except local reusable)."""
    doc = _load_workflow(workflow_path)
    uses_list = _find_uses(doc)

    for uses_value, path in uses_list:
        # Skip local reusable workflows
        if uses_value.startswith("./"):
            continue
        # Skip docker:// and other non-action uses
        if "://" in uses_value:
            continue

        # Generated workflows keep their own pins; they must still be SHA-pinned.
        if workflow_path.name in GENERATED_WORKFLOWS:
            ref = uses_value.partition("@")[2].split()[0]
            assert _is_sha(ref), f"{workflow_path.name}: {uses_value!r} at {path} is not SHA-pinned"
            continue

        # Extract action name (before @)
        action_name = uses_value.split("@")[0]

        # Check if it's in our allowlist
        if action_name not in UNPINNED_ALLOWLIST:
            pytest.fail(
                f"{workflow_path.name}: unknown action {uses_value!r} at {path} "
                f"(not in UNPINNED_ALLOWLIST)"
            )

        # Check if it's pinned to a SHA
        if "@" not in uses_value:
            pytest.fail(
                f"{workflow_path.name}: action {uses_value!r} at {path} is not pinned "
                f"(missing @sha)"
            )

        # Verify the SHA matches our known pinned version
        _, sha = uses_value.split("@", 1)
        expected_sha = PINNED_ACTIONS.get(action_name)
        if expected_sha and sha != expected_sha:
            pytest.fail(
                f"{workflow_path.name}: action {action_name} pinned to {sha!r} "
                f"but expected {expected_sha!r}"
            )


def test_reusable_build_workflow_exists() -> None:
    """The reusable build workflow must exist and be valid."""
    path = Path(".github/workflows/reusable-build.yml")
    assert path.is_file(), "reusable-build.yml missing"
    doc = _load_workflow(path)
    assert doc.get("on", {}).get("workflow_call"), "reusable-build.yml must be a workflow_call"
    assert "build-docx" in doc.get("jobs", {}), "missing build-docx job"
    assert "build-pdf" in doc.get("jobs", {}), "missing build-pdf job"
    assert "workflow_call" in doc["on"], "must be callable"


def test_generated_repo_uses_reusable_workflow() -> None:
    """Generated repo workflows must reuse the shared build workflow."""
    build_artifacts = Path("{{cookiecutter.repo_name}}/.github/workflows/build-artifacts.yml")
    release = Path("{{cookiecutter.repo_name}}/.github/workflows/release.yml")

    for path in (build_artifacts, release):
        assert path.is_file(), f"{path} missing"
        doc = _load_workflow(path)
        jobs = doc.get("jobs", {})
        # Should call the reusable workflow
        for job_name, job in jobs.items():
            if "uses" in job:
                assert job["uses"] == "./.github/workflows/reusable-build.yml", (
                    f"{path.name} job {job_name} must use reusable-build.yml"
                )


def test_dependabot_config_exists() -> None:
    """Dependabot config must exist for GitHub Actions and pip."""
    path = Path(".github/dependabot.yml")
    assert path.is_file(), "dependabot.yml missing"
    doc = _load_workflow(path)
    updates = doc.get("updates", [])
    ecosystems = {u["package-ecosystem"] for u in updates}
    assert "github-actions" in ecosystems, "dependabot must monitor github-actions"
    assert "pip" in ecosystems, "dependabot must monitor pip"


def test_no_floating_action_versions() -> None:
    """No workflow should use unpinned action versions (e.g., v4, v5)."""
    for workflow_path in ALL_WORKFLOWS:
        doc = _load_workflow(workflow_path)
        uses_list = _find_uses(doc)

        for uses_value, path in uses_list:
            if uses_value.startswith("./"):
                continue
            if "://" in uses_value:
                continue

            if "@" in uses_value:
                _, version = uses_value.split("@", 1)
                # SHA should be 40 hex chars (git commit)
                if len(version) != 40 or not all(c in "0123456789abcdef" for c in version.lower()):
                    pytest.fail(
                        f"{workflow_path.name}: action {uses_value!r} at {path} "
                        f"pinned to non-SHA version {version!r}"
                    )
            else:
                # Unpinned action (e.g., "actions/checkout@v4")
                pytest.fail(
                    f"{workflow_path.name}: action {uses_value!r} at {path} is unpinned"
                )


def test_jobs_have_permissions() -> None:
    """Every job in every workflow should have explicit permissions."""
    for workflow_path in ALL_WORKFLOWS:
        doc = _load_workflow(workflow_path)
        jobs = doc.get("jobs", {})
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            if "permissions" not in job:
                # Allow jobs that only use local reusable workflows (they inherit perms)
                uses = job.get("uses", "")
                if not uses.startswith("./"):
                    pytest.fail(
                        f"{workflow_path.name}: job {job_name} missing permissions"
                    )

@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK") != "1" or shutil.which("gh") is None,
    reason="set RUN_NETWORK=1 and install gh to resolve pinned action SHAs",
)
def test_pinned_action_shas_resolve_upstream() -> None:
    """A SHA that was never published fails the workflow at action resolution."""
    pins = {
        (uses.split("@")[0], uses.split("@")[1].split()[0])
        for path in ALL_WORKFLOWS
        for uses, _ in _find_uses(_load_workflow(path))
        if "@" in uses and not uses.startswith("./") and _is_sha(uses.split("@")[1].split()[0])
    }
    assert pins, "no SHA-pinned actions found"
    missing = []
    for action, sha in sorted(pins):
        repo = "/".join(action.split("/")[:2])
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/{sha}", "--jq", ".sha"],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or result.stdout.strip() != sha:
            missing.append(f"{action}@{sha}")
    assert not missing, f"pinned SHAs not found upstream: {missing}"
