"""CI hardening tests: workflows use versioned actions and least-privilege permissions."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_WORKFLOWS = ROOT / ".github" / "workflows"
TEMPLATE_WORKFLOWS = ROOT / "{{cookiecutter.repo_name}}" / ".github" / "workflows"
ALL_WORKFLOWS = list(SCAFFOLD_WORKFLOWS.glob("*.yml")) + list(TEMPLATE_WORKFLOWS.glob("*.yml"))

# Actions are referenced by major version tag (e.g. actions/checkout@v7); dependabot
# moves the tag when a new major is released.
MAJOR_TAGS = {
    "actions/checkout": "v7",
    "actions/setup-python": "v7",
    "actions/upload-artifact": "v7",
    "actions/download-artifact": "v8",
    "actions/configure-pages": "v6",
    "actions/upload-pages-artifact": "v5",
    "xu-cheng/texlive-action": "v3",
    "softprops/action-gh-release": "v3",
    "actions/create-github-app-token": "v3",
}


# Workflows written by `go-getter apply` ("do not edit"). Permissions and concurrency are
# configured by decision 0058, so they are tested like any other workflow; only the action
# pins are go-getter's own and must stay SHA-pinned.
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


def _action_refs(workflow_path: Path) -> list[tuple[str, str, str]]:
    """(action, ref, location) for every remote action a workflow uses."""
    refs = []
    for uses_value, path in _find_uses(_load_workflow(workflow_path)):
        if uses_value.startswith("./") or "://" in uses_value:
            continue
        action, sep, rest = uses_value.partition("@")
        assert sep and rest.split(), f"{workflow_path.name}: {uses_value!r} at {path} has no ref"
        refs.append((action, rest.split()[0], path))
    return refs


@pytest.mark.parametrize("workflow_path", ALL_WORKFLOWS)
def test_workflow_uses_major_version_tags(workflow_path: Path) -> None:
    """Remote actions use a major version tag; go-getter's generated file keeps SHAs."""
    for action, ref, path in _action_refs(workflow_path):
        if workflow_path.name in GENERATED_WORKFLOWS:
            assert _is_sha(ref), f"{workflow_path.name}: {action}@{ref} at {path} is not SHA-pinned"
            continue
        assert re.fullmatch(r"v\d+", ref), (
            f"{workflow_path.name}: {action}@{ref} at {path} is not a major version tag"
        )
        expected = MAJOR_TAGS.get(action)
        assert expected, f"{workflow_path.name}: unknown action {action!r} at {path}"
        assert ref == expected, f"{workflow_path.name}: {action} is @{ref}, expected @{expected}"


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


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK") != "1" or shutil.which("gh") is None,
    reason="set RUN_NETWORK=1 and install gh to resolve action refs",
)
def test_action_refs_resolve_upstream() -> None:
    """A tag or SHA that was never published fails the workflow at action resolution."""
    refs = {
        (action, ref)
        for path in ALL_WORKFLOWS
        for action, ref, _ in _action_refs(path)
    }
    assert refs, "no remote actions found"
    missing = []
    for action, ref in sorted(refs):
        repo = "/".join(action.split("/")[:2])
        endpoint = (
            f"repos/{repo}/commits/{ref}" if _is_sha(ref) else f"repos/{repo}/git/ref/tags/{ref}"
        )
        result = subprocess.run(
            ["gh", "api", endpoint, "--jq", ".sha // .object.sha"], capture_output=True, text=True
        )
        if result.returncode != 0 or not result.stdout.strip():
            missing.append(f"{action}@{ref}")
    assert not missing, f"action refs not found upstream: {missing}"
