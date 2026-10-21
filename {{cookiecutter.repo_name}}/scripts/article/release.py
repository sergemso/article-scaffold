"""Release planning and application for article repositories.

This module provides read-only release planning and gated release application.
It never calls external APIs; DOI handling is limited to updating metadata.yaml
and regenerating derived files.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build import docx_plan, pdf_plan

# Import from sibling modules (no circular imports - these are leaf functions)
from .metadata import (
    collect_expected,
    compare_outputs,
    load_metadata,
    normalize_metadata,
    write_expected,
)

# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReleasePlan:
    """A read-only plan for a release. Never mutates the repository."""

    version: str
    tag: str
    doi: str | None
    artifact_list: list[str]
    checks: dict[str, bool]
    dry_run_diff: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tag": self.tag,
            "doi": self.doi,
            "artifact_list": self.artifact_list,
            "checks": self.checks,
            "dry_run_diff": self.dry_run_diff,
        }


class ReleaseError(Exception):
    """A user-actionable release failure."""
    pass


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _git_root(root: Path) -> Path:
    """Return the git root, or raise if not a git repo."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReleaseError("not a git repository (git rev-parse failed)")
    return Path(result.stdout.strip()).resolve()


def _git_state(root: Path) -> tuple[str, bool]:
    """Return (branch, dirty)."""
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    branch_name = branch.stdout.strip() if branch.returncode == 0 else ""
    dirty = bool(status.stdout.strip()) if status.returncode == 0 else False
    return branch_name, dirty


def _tag_exists(tag: str, root: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", tag],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _semver_compare(a: str, b: str) -> int:
    """Compare two semantic versions. Returns -1 if a < b, 0 if equal, 1 if a > b."""
    def parse(v: str) -> tuple:
        v = v.lstrip('v')
        main = v.split('-')[0].split('+')[0]
        parts = tuple(int(x) for x in main.split('.'))
        return parts
    a_parts = parse(a)
    b_parts = parse(b)
    if a_parts < b_parts:
        return -1
    elif a_parts > b_parts:
        return 1
    return 0


def _is_valid_semver(version: str) -> bool:
    """Check if version string is valid semver (MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD])."""
    import re
    # Basic semver regex: MAJOR.MINOR.PATCH with optional prerelease and build metadata
    pattern = re.compile(
        r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
        r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
    )
    return bool(pattern.fullmatch(version))


def _load_repo_metadata(root: Path) -> dict[str, Any]:
    """Load and normalize metadata.yaml."""
    metadata_path = root / "metadata.yaml"
    if not metadata_path.is_file():
        raise ReleaseError("metadata.yaml not found")
    return load_metadata(metadata_path)


def _check_git_clean(root: Path) -> tuple[bool, str]:
    """Return (clean, message)."""
    try:
        _git_root(root)
    except ReleaseError as e:
        return False, str(e)
    _, dirty = _git_state(root)
    if dirty:
        return False, "working tree has uncommitted changes"
    return True, "working tree is clean"


def _check_tag_absent(root: Path, tag: str) -> tuple[bool, str]:
    if _tag_exists(tag, root):
        return False, f"tag {tag} already exists"
    return True, f"tag {tag} does not exist"


def _collect_artifacts(root: Path) -> list[str]:
    """Return list of expected artifact paths."""
    artifacts = []
    pdf = Path(root) / "paper" / "article.pdf"
    if pdf.is_file():
        artifacts.append(str(pdf.relative_to(root)))
    docx = Path(root) / "manuscript.docx"
    if docx.is_file():
        artifacts.append(str(docx.relative_to(root)))
    return artifacts


def _compute_dry_run_diff(root: Path) -> list[str]:
    """Generate a dry-run diff of what would change on metadata regeneration."""
    try:
        metadata = load_metadata(root / "metadata.yaml")
        expected = collect_expected(root, normalize_metadata(metadata))
        drift = compare_outputs(root, expected)
        return [f"would update {item.path}" for item in drift]
    except Exception:
        return ["(could not compute diff)"]


# ──────────────────────────────────────────────────────────────────────
# Release plan generation (read-only)
# ──────────────────────────────────────────────────────────────────────

def plan_release(root: Path) -> dict[str, Any]:
    """Generate a read-only release plan. Never mutates the repository."""
    root = Path(root).resolve()

    try:
        metadata = _load_repo_metadata(root)
    except ReleaseError as e:
        return {"ok": False, "error": str(e)}

    version = str(metadata.get("version", "")).strip()
    if not version:
        return {"ok": False, "error": "metadata.yaml missing version"}

    # Validate semver format
    if not _is_valid_semver(version):
        return {
            "ok": False,
            "error": f"invalid version format: {version!r}; expected semver like 1.0.0",
        }

    tag = f"v{version}"
    doi = metadata.get("doi", "") or None

    artifacts = _collect_artifacts(root)

    checks = {}
    checks["git_clean"], _ = _check_git_clean(root)
    checks["tag_absent"], _ = _check_tag_absent(root, tag)
    checks["has_version"] = bool(version)
    checks["has_artifacts"] = len(artifacts) > 0

    dry_run_diff = _compute_dry_run_diff(root)

    return {
        "ok": True,
        "plan": {
            "version": version,
            "tag": tag,
            "doi": doi,
            "artifact_list": artifacts,
            "checks": checks,
            "dry_run_diff": dry_run_diff,
        }
    }


# ──────────────────────────────────────────────────────────────────────
# Release application (gated, requires explicit confirmation)
# ──────────────────────────────────────────────────────────────────────

def apply_release(root: Path, yes: bool = False) -> dict[str, Any]:
    """Apply the release. Requires explicit confirmation (yes=True)."""
    if not yes:
        return {"ok": False, "error": "release apply requires explicit confirmation"}

    root = Path(root).resolve()

    try:
        metadata = _load_repo_metadata(root)
    except ReleaseError as e:
        return {"ok": False, "error": str(e)}

    version = str(metadata.get("version", "")).strip()
    if not version:
        return {"ok": False, "error": "metadata.yaml missing version"}

    tag = f"v{version}"

    # Run all checks
    clean, msg = _check_git_clean(root)
    if not clean:
        return {"ok": False, "error": msg}
    tag_absent, msg = _check_tag_absent(root, tag)
    if not tag_absent:
        return {"ok": False, "error": msg}

    # Regenerate derived metadata (in case DOI was added to metadata.yaml)
    try:
        metadata = load_metadata(root / "metadata.yaml")
        # metadata is already normalized by load_metadata; do not re-normalize
        expected = collect_expected(root, metadata)
        write_expected(expected)
    except Exception as e:
        return {"ok": False, "error": f"failed to regenerate derived files: {e}"}

    # Create git tag
    tag_name = f"v{version}"
    result = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"ok": False, "error": f"git tag failed: {result.stderr}"}

    # Build artifacts (PDF required, DOCX optional)
    artifacts_built = []
    try:
        plan_obj = pdf_plan(root)
        subprocess.run(
            list(plan_obj.command),
            cwd=Path(root) / plan_obj.cwd,
            check=True,
            capture_output=True,
        )
        artifacts_built.append("paper/article.pdf")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return {"ok": False, "error": f"PDF build failed: {stderr}"}

    # DOCX is optional - try to build but don't fail the release if pandoc is too old
    try:
        plan_obj = docx_plan(root)
        subprocess.run(
            list(plan_obj.command),
            cwd=Path(root) / plan_obj.cwd,
            check=True,
            capture_output=True,
        )
        artifacts_built.append("manuscript.docx")
    except subprocess.CalledProcessError as e:
        # Log warning but don't fail the release
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        print(f"WARNING: DOCX build failed (optional): {stderr}", file=sys.stderr)

    return {
        "ok": True,
        "version": version,
        "tag": tag_name,
        "artifacts": artifacts_built,
        "message": f"Release {version} applied successfully",
    }