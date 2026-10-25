"""Read-only, offline repository status for ``article status --json``."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from . import core

STATUS_SCHEMA_VERSION = "1.0"
TEMPLATE_VERSION = "1.5.1"

_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)*)\b")


def _command_version(name: str, *args: str) -> str | None:
    executable = shutil.which(name)
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = _VERSION_RE.search(result.stdout + result.stderr)
    return match.group(1) if match else None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        return subprocess.run(
            [git, *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _git_state(root: Path) -> tuple[str | None, bool]:
    branch_result = _git(root, "symbolic-ref", "--short", "HEAD")
    branch: str | None = None
    if branch_result is not None and branch_result.returncode == 0:
        branch = branch_result.stdout.strip() or None
    else:
        detached = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
        if detached is not None and detached.returncode == 0:
            value = detached.stdout.strip()
            branch = value if value and value != "HEAD" else None

    status_result = _git(root, "status", "--porcelain")
    dirty = bool(status_result.stdout.strip()) if status_result is not None else False
    return branch, dirty


def _metadata_state(root: Path) -> tuple[bool, bool, str]:
    path = root / "metadata.yaml"
    try:
        metadata = core.load_metadata(path)
    except (OSError, ValueError, yaml.YAMLError):
        return False, True, TEMPLATE_VERSION

    valid = True
    try:
        expected = core.collect_expected(root, metadata)
        drift = bool(core.compare_outputs(root, expected))
    except (OSError, ValueError, yaml.YAMLError):
        drift = True
    template_version = str(metadata.get("template_version") or TEMPLATE_VERSION)
    return valid, drift, template_version


def _diagnostics_summary(root: Path) -> dict[str, int]:
    try:
        diagnostics = core.validate_paper(root)
    except (OSError, ValueError):
        return {"errors": 1, "warnings": 0}
    return {
        "errors": len(diagnostics.errors),
        "warnings": len(diagnostics.warnings),
    }


def build_status(root: Path) -> dict[str, Any]:
    """Return the stable status object without writing or using the network."""
    root = root.resolve()
    branch, dirty = _git_state(root)
    metadata_valid, metadata_drift, template_version = _metadata_state(root)
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "template_version": template_version,
        "repo": {
            "root": str(root),
            "branch": branch,
            "dirty": dirty,
        },
        "metadata": {
            "valid": metadata_valid,
            "drift": metadata_drift,
        },
        "diagnostics": _diagnostics_summary(root),
        "tools": {
            "python": platform.python_version(),
            "pandoc": _command_version("pandoc", "--version"),
            "latexmk": _command_version("latexmk", "-v"),
            "git": _command_version("git", "--version"),
            "pyyaml": getattr(yaml, "__version__", None),
        },
    }
