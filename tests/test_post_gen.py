"""Post-generation git initialization and hook installation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import render, run

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "post_gen_project.py"


def _git_init(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "master"],
        cwd=path,
        check=True,
    )


def test_nested_render_creates_its_own_repo_and_hook(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    _git_init(parent)

    project = render(tmp_path=parent)

    assert (project / ".git").is_dir()
    assert (project / "scripts" / "githooks" / "pre-push").is_file()
    assert not (project / ".git" / "hooks" / "pre-push").exists()
    config = run(project, "git", "config", "--get", "core.hooksPath")
    assert config.returncode == 0
    assert config.stdout.strip() == "scripts/githooks"
    assert (project / "scripts" / "githooks" / "pre-push").read_bytes() == (
        project / "scripts" / "pre-push"
    ).read_bytes()

    # The parent repo must not be modified by a nested render.
    parent_config = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=parent,
        text=True,
        capture_output=True,
    )
    assert parent_config.returncode != 0


def test_make_hooks_is_idempotent(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)

    for _ in range(2):
        result = run(project, "make", "hooks")
        assert result.returncode == 0, result.stderr + result.stdout

    config = run(project, "git", "config", "--get", "core.hooksPath")
    assert config.stdout.strip() == "scripts/githooks"
    hooks = sorted(path.name for path in (project / "scripts" / "githooks").iterdir())
    assert hooks == ["pre-push"]


def test_missing_git_warns_but_does_not_fail_render(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    env = dict(os.environ)
    env["PATH"] = ""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "git not found" in result.stderr
    assert (project / "LICENSE").is_file()
