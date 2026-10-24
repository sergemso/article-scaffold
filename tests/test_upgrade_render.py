"""Rendering the old and new template and diffing them into a repo-relative patch."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import run


@pytest.fixture()
def project(upgrade_project: Path) -> Path:
    return upgrade_project


@pytest.fixture()
def template(upgrade_template: dict[str, str]) -> dict[str, str]:
    return upgrade_template


def _build(project: Path, workdir: Path, new_ref: str, python: str | None = None) -> dict:
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from scripts.article import upgrade\n"
        f"plan = upgrade.plan(Path('.'), {new_ref!r})\n"
        "try:\n"
        "    out = upgrade.build_patch(\n"
        f"        Path('.'), plan, Path({str(workdir)!r}), python={python or sys.executable!r}\n"
        "    )\n"
        "except upgrade.UpgradeError as exc:\n"
        "    out = {'error': exc.code, 'message': exc.message}\n"
        "print(json.dumps(out))\n"
    )
    result = run(project, "python3", "-c", code)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_patch_touches_exactly_the_files_that_differ(
    project: Path, template: dict[str, str], tmp_path: Path
) -> None:
    out = _build(project, tmp_path / "work", template["b"])

    assert "error" not in out, out
    changed = {(f["status"], f["path"]) for f in out["files"]}
    assert changed == {("M", "scripts/article/status.py"), ("A", "docs/NEW.md")}


def test_patch_paths_are_repo_relative_and_apply_to_the_old_render(
    project: Path, template: dict[str, str], tmp_path: Path
) -> None:
    out = _build(project, tmp_path / "work", template["b"])
    patch = Path(out["patch"]).read_text(encoding="utf-8")

    assert "a/scripts/article/status.py" in patch
    assert "b/docs/NEW.md" in patch
    assert "template.json" not in patch
    check = subprocess.run(
        ["git", "apply", "--check", out["patch"]],
        cwd=out["old_tree"],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr


def test_up_to_date_builds_no_patch(
    project: Path, template: dict[str, str], tmp_path: Path
) -> None:
    out = _build(project, tmp_path / "work", template["a"])

    assert out["patch"] is None and out["files"] == []
    assert not (tmp_path / "work").exists()


def test_building_never_touches_the_repository(
    project: Path, template: dict[str, str], tmp_path: Path
) -> None:
    _build(project, tmp_path / "work", template["b"])

    assert run(project, "git", "status", "--porcelain").stdout == ""


def test_missing_cookiecutter_gives_the_install_hint(
    project: Path, template: dict[str, str], tmp_path: Path
) -> None:
    out = _build(project, tmp_path / "work", template["b"], python="/bin/false")

    assert out["error"] == "U009"
    assert "pip install cookiecutter" in out["message"]


def test_unknown_commit_is_a_checkout_error(project: Path, tmp_path: Path) -> None:
    out = _build(project, tmp_path / "work", "deadbeefdeadbeef")

    assert out["error"] == "U010"


def test_refused_plan_cannot_be_built(project: Path, tmp_path: Path) -> None:
    (project / "notes.txt").write_text("dirty", encoding="utf-8")
    out = _build(project, tmp_path / "work", "HEAD")

    assert out["error"] == "U012"
