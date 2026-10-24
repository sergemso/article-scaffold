"""Read-only upgrade planner: refusals, the happy path and the no-write guarantee."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT, commit_all, render, run


def _plan(project: Path, new_ref: str | None = None) -> dict:
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from scripts.article import upgrade\n"
        f"result = upgrade.plan(Path('.'), {new_ref!r})\n"
        "result['cookiecutter_imported'] = 'cookiecutter' in sys.modules\n"
        "print(json.dumps(result))\n"
    )
    result = run(project, "python3", "-c", code)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _codes(result: dict) -> list[str]:
    return [r["code"] for r in result["refusals"]]


def _head(path: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev], cwd=path, capture_output=True, text=True, check=True
    ).stdout.strip()


def _clean_project(tmp_path: Path) -> Path:
    project = render(tmp_path=tmp_path)
    stamp = json.loads((project / "template.json").read_text(encoding="utf-8"))
    if not stamp["template_commit"]:
        pytest.skip("the template is not a git checkout, so the stamp has no commit")
    commit_all(project)
    return project


def _edit_stamp(project: Path, **changes: object) -> None:
    path = project / "template.json"
    stamp = json.loads(path.read_text(encoding="utf-8"))
    stamp.update(changes)
    path.write_text(json.dumps(stamp), encoding="utf-8")
    run(project, "git", "commit", "-qam", "edit stamp", check=True)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    return _clean_project(tmp_path)


def test_plan_for_an_older_template_commit_is_ok(project: Path) -> None:
    try:
        older = _head(ROOT, "HEAD~1")
    except subprocess.CalledProcessError:
        pytest.skip("the template checkout is shallow (no parent commit)")
    result = _plan(project, older)

    assert result["ok"] is True, result["refusals"]
    assert result["refusals"] == []
    assert result["plan"]["old"] == _head(ROOT)
    assert result["plan"]["new"] == older
    assert result["plan"]["up_to_date"] is False
    assert result["plan"]["template"] == str(ROOT)


def test_default_target_is_the_template_head(project: Path) -> None:
    result = _plan(project)

    assert result["plan"]["new"] == _head(ROOT)
    assert result["plan"]["up_to_date"] is True
    assert result["ok"] is True


def test_branch_names_resolve_through_the_template(project: Path) -> None:
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    if branch == "HEAD":
        pytest.skip("template checkout is on a detached HEAD")

    assert _plan(project, branch)["plan"]["new"] == _head(ROOT)


def test_planning_writes_nothing_and_never_imports_cookiecutter(project: Path) -> None:
    before = run(project, "git", "status", "--porcelain").stdout
    result = _plan(project)
    after = run(project, "git", "status", "--porcelain").stdout

    assert before == after == ""
    assert result["cookiecutter_imported"] is False


def test_missing_stamp_is_refused(project: Path) -> None:
    (project / "template.json").unlink()
    run(project, "git", "commit", "-qam", "drop stamp", check=True)

    assert "U001" in _codes(_plan(project))


def test_malformed_stamp_is_refused(project: Path) -> None:
    (project / "template.json").write_text("{", encoding="utf-8")
    run(project, "git", "commit", "-qam", "break stamp", check=True)

    assert "U002" in _codes(_plan(project))


def test_null_template_commit_is_refused(project: Path) -> None:
    _edit_stamp(project, template_commit=None)
    result = _plan(project)

    assert result["ok"] is False
    assert "U003" in _codes(result)


def test_dirty_tree_is_refused(project: Path) -> None:
    (project / "notes.txt").write_text("uncommitted", encoding="utf-8")
    result = _plan(project)

    assert _codes(result) == ["U005"]


def test_non_git_directory_is_refused(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    shutil.rmtree(project / ".git")

    assert "U004" in _codes(_plan(project))


def test_v1_metadata_is_refused_with_the_migration_pointer(project: Path) -> None:
    (project / "metadata.yaml").write_text("title: x\nauthor:\n  name: A\n", encoding="utf-8")
    run(project, "git", "commit", "-qam", "v1 metadata", check=True)
    result = _plan(project)

    assert _codes(result) == ["U006"]
    assert "migrating-to-v2.md" in result["refusals"][0]["message"]


def test_unreachable_template_is_refused(project: Path, tmp_path: Path) -> None:
    _edit_stamp(project, template=str(tmp_path / "no-such-template"))
    result = _plan(project)

    assert "U007" in _codes(result)
    assert result["plan"]["new"] is None


def test_unknown_ref_is_refused(project: Path) -> None:
    assert _codes(_plan(project, "no-such-branch")) == ["U008"]


def test_every_refusal_is_reported_together(project: Path) -> None:
    _edit_stamp(project, template_commit=None)
    (project / "notes.txt").write_text("uncommitted", encoding="utf-8")

    assert set(_codes(_plan(project))) == {"U003", "U005"}
