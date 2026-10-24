"""Rendering the old and new template and diffing them into a repo-relative patch."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT, commit_all, render, run

REPO_PATH = "{{cookiecutter.repo_name}}"


def _git(path: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@invalid",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@invalid",
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(path),
    }
    return subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """A throwaway clone of the template with two commits: A, then B (one edit, one new file)."""
    tpl = tmp_path_factory.mktemp("tpl") / "template"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    if head.returncode != 0:
        pytest.skip("the template is not a git checkout")
    _git(ROOT, "clone", "--quiet", str(ROOT), str(tpl))
    a = _git(tpl, "rev-parse", "HEAD")
    status = tpl / REPO_PATH / "scripts" / "article" / "status.py"
    status.write_text(
        status.read_text(encoding="utf-8") + "\n# template change B\n", encoding="utf-8"
    )
    (tpl / REPO_PATH / "docs" / "NEW.md").write_text("added in B\n", encoding="utf-8")
    _git(tpl, "add", "-A")
    _git(tpl, "commit", "--quiet", "-m", "B")
    return {"path": str(tpl), "a": a, "b": _git(tpl, "rev-parse", "HEAD")}


@pytest.fixture()
def project(tmp_path: Path, template: dict[str, str]) -> Path:
    """A repo stamped as generated from template commit A."""
    project = render(tmp_path=tmp_path)
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=template["path"], template_commit=template["a"])
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    commit_all(project)
    return project


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
