"""Applying an upgrade on a branch, leaving conflicts to the author, and finishing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import run

STATUS = "scripts/article/status.py"


@pytest.fixture()
def project(upgrade_project: Path) -> Path:
    return upgrade_project


def _call(project: Path, call: str) -> dict:
    code = (
        "import json\n"
        "from pathlib import Path\n"
        "from scripts.article import upgrade\n"
        "try:\n"
        f"    out = {call}\n"
        "except upgrade.UpgradeError as exc:\n"
        "    out = {'error': exc.code, 'message': exc.message}\n"
        "print(json.dumps(out))\n"
    )
    result = run(project, "python3", "-c", code)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _apply(project: Path, ref: str, commit: bool = False) -> dict:
    return _call(
        project,
        f"upgrade.apply(Path('.'), {ref!r}, python={sys.executable!r}, commit={commit})",
    )


def _finish(project: Path) -> dict:
    return _call(project, "upgrade.finish(Path('.'))")


def _commit(project: Path, message: str) -> None:
    run(project, "git", "add", "-A", check=True)
    run(project, "git", "commit", "-qm", message, check=True)


def _stamp(project: Path) -> dict:
    return json.loads((project / "template.json").read_text(encoding="utf-8"))


def test_clean_apply_updates_files_on_a_new_branch(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    head = run(project, "git", "rev-parse", "HEAD").stdout
    out = _apply(project, upgrade_template["b"])

    assert out["ok"] is True, out
    assert out["branch"] == f"upgrade/{upgrade_template['b'][:8]}"
    assert sorted(out["applied"]) == ["docs/NEW.md", STATUS]
    assert out["conflicted"] == [] and out["skipped"] == []
    assert (project / STATUS).read_text(encoding="utf-8").endswith("# template change B\n")
    assert (project / "docs" / "NEW.md").read_text(encoding="utf-8") == "added in B\n"
    assert run(project, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == out["branch"]
    assert run(project, "git", "rev-parse", "HEAD").stdout == head, "apply must not commit"
    assert _stamp(project)["template_commit"] == upgrade_template["a"], "stamp moves at finish"


def test_edits_in_other_places_merge_cleanly(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    """The base blob is imported, so a file the author edited still three-way merges."""
    path = project / STATUS
    path.write_text("# my header\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    _commit(project, "local edit at the top")
    out = _apply(project, upgrade_template["b"])

    assert out["conflicted"] == [] and out["skipped"] == [], out
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# my header\n") and text.endswith("# template change B\n")


def test_conflicts_are_left_for_the_author_and_finish_waits(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    path = project / STATUS
    path.write_text(path.read_text(encoding="utf-8") + "\n# my own ending\n", encoding="utf-8")
    _commit(project, "local edit at the end")
    out = _apply(project, upgrade_template["b"])

    assert out["ok"] is False
    assert out["conflicted"] == [STATUS]
    assert out["applied"] == ["docs/NEW.md"]
    assert "<<<<<<<" in path.read_text(encoding="utf-8")

    refused = _finish(project)
    assert refused["error"] == "U015" and STATUS in refused["message"]
    assert _stamp(project)["template_commit"] == upgrade_template["a"]

    path.write_text(
        path.read_text(encoding="utf-8").split("<<<<<<<")[0] + "# merged by hand\n",
        encoding="utf-8",
    )
    run(project, "git", "add", STATUS, check=True)
    done = _finish(project)
    assert done.get("finished") is True, done
    assert _stamp(project)["template_commit"] == upgrade_template["b"]


def test_finish_bumps_the_stamp_and_stages_the_result(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    _apply(project, upgrade_template["b"])
    done = _finish(project)

    assert done["finished"] is True, done
    stamp = _stamp(project)
    assert stamp["template_commit"] == upgrade_template["b"]
    assert "template.json" in run(project, "git", "diff", "--cached", "--name-only").stdout
    assert _finish(project)["error"] == "U014", "state is cleared after finishing"


def test_finish_without_an_upgrade_is_refused(project: Path) -> None:
    assert _finish(project)["error"] == "U014"


def test_an_existing_branch_blocks_the_apply(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    run(project, "git", "branch", f"upgrade/{upgrade_template['b'][:8]}", check=True)

    assert _apply(project, upgrade_template["b"])["error"] == "U013"


def test_locally_present_new_file_is_skipped_not_overwritten(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    (project / "docs" / "NEW.md").write_text("mine\n", encoding="utf-8")
    _commit(project, "local NEW.md")
    out = _apply(project, upgrade_template["b"])

    assert [s["path"] for s in out["skipped"]] == ["docs/NEW.md"]
    assert (project / "docs" / "NEW.md").read_text(encoding="utf-8") == "mine\n"


def test_up_to_date_does_nothing(project: Path, upgrade_template: dict[str, str]) -> None:
    out = _apply(project, upgrade_template["a"])

    assert out["up_to_date"] is True and out["branch"] is None
    assert run(project, "git", "branch", "--list", "upgrade/*").stdout.strip() == ""


def test_a_refused_plan_cannot_be_applied(project: Path, upgrade_template: dict[str, str]) -> None:
    (project / "notes.txt").write_text("dirty", encoding="utf-8")

    assert _apply(project, upgrade_template["b"])["error"] == "U012"


def test_conflict_is_found_when_the_pristine_file_was_never_committed(
    tmp_path: Path, upgrade_template: dict[str, str]
) -> None:
    """Only the imported base blob lets git three-way merge such a file into a conflict."""
    from conftest import commit_all, render

    project = render(tmp_path=tmp_path)
    stamp = _stamp(project)
    stamp.update(template=upgrade_template["path"], template_commit=upgrade_template["a"])
    (project / "template.json").write_text(json.dumps(stamp), encoding="utf-8")
    path = project / STATUS
    path.write_text(path.read_text(encoding="utf-8") + "\n# edited before any commit\n",
                    encoding="utf-8")
    commit_all(project)
    out = _apply(project, upgrade_template["b"])

    assert out["conflicted"] == [STATUS], out
    assert out["skipped"] == []
    assert "<<<<<<<" in path.read_text(encoding="utf-8")


def test_commit_mode_lets_a_fresh_checkout_finish_the_upgrade(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    """CI commits the result, markers included; the branch alone carries the state."""
    path = project / STATUS
    path.write_text(path.read_text(encoding="utf-8") + "\n# my own ending\n", encoding="utf-8")
    _commit(project, "local edit at the end")
    before = run(project, "git", "rev-parse", "HEAD").stdout.strip()
    out = _apply(project, upgrade_template["b"], commit=True)

    assert out["committed"] is True and out["conflicted"] == [STATUS]
    assert run(project, "git", "status", "--porcelain").stdout == ""
    assert run(project, "git", "rev-parse", "HEAD~1").stdout.strip() == before
    assert "<<<<<<<" in path.read_text(encoding="utf-8")
    assert (project / ".upgrade-state.json").is_file()

    # A new checkout of the branch has no state in .git.
    (project / ".git" / "upgrade-state.json").unlink()
    refused = _finish(project)
    assert refused["error"] == "U015", refused

    path.write_text(path.read_text(encoding="utf-8").split("<<<<<<<")[0] + "# merged\n",
                    encoding="utf-8")
    done = _finish(project)
    assert done.get("finished") is True, done
    assert not (project / ".upgrade-state.json").exists()
    assert _stamp(project)["template_commit"] == upgrade_template["b"]


def test_plain_apply_commits_nothing_and_leaves_no_tracked_state(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    out = _apply(project, upgrade_template["b"])

    assert out["committed"] is False
    assert not (project / ".upgrade-state.json").exists()


def _hand_edit_readme(project: Path) -> str:
    readme = project / "README.md"
    text = readme.read_text(encoding="utf-8")
    edited = text.replace("**Version:**", "**Version (hand edit):**", 1)
    assert edited != text
    readme.write_text(edited, encoding="utf-8")
    return edited


def test_finish_refuses_to_overwrite_hand_edited_derived_files(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    _apply(project, upgrade_template["b"])
    edited = _hand_edit_readme(project)

    refused = _finish(project)

    assert refused["error"] == "U019"
    assert "README.md" in refused["message"] and "--regenerate" in refused["message"]
    assert (project / "README.md").read_text(encoding="utf-8") == edited
    assert _stamp(project)["template_commit"] == upgrade_template["a"]


def test_finish_can_be_told_to_regenerate_over_the_drift(
    project: Path, upgrade_template: dict[str, str]
) -> None:
    _apply(project, upgrade_template["b"])
    edited = _hand_edit_readme(project)
    assert _finish(project)["error"] == "U019"

    done = _call(project, "upgrade.finish(Path('.'), regenerate=True)")

    assert done.get("finished") is True, done
    assert (project / "README.md").read_text(encoding="utf-8") != edited
    assert _stamp(project)["template_commit"] == upgrade_template["b"]


def test_regenerate_only_goes_with_finish(project: Path) -> None:
    result = run(project, sys.executable, "-m", "scripts.article", "upgrade", "--plan",
                 "--regenerate")

    assert result.returncode == 2
    assert "--regenerate only goes with --finish" in result.stderr


def _template_with_unrelated_commit(tmp_path: Path, template: dict[str, str]) -> tuple[Path, str]:
    """A private clone of the test template with one more commit that touches no payload file."""
    import subprocess

    clone = tmp_path / "tpl-c"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@invalid"]
    subprocess.run([*git, "clone", "--quiet", template["path"], str(clone)], check=True)
    (clone / "NOTES.md").write_text("release notes only\n", encoding="utf-8")
    subprocess.run([*git, "add", "NOTES.md"], cwd=clone, check=True)
    subprocess.run([*git, "commit", "--quiet", "-m", "C"], cwd=clone, check=True)
    head = subprocess.run(
        [*git, "rev-parse", "HEAD"], cwd=clone, capture_output=True, text=True, check=True
    ).stdout.strip()
    return clone, head


def test_a_template_commit_that_changes_nothing_here_makes_no_branch(
    project: Path, upgrade_template: dict[str, str], tmp_path: Path
) -> None:
    clone, head = _template_with_unrelated_commit(tmp_path, upgrade_template)
    stamp_path = project / "template.json"
    stamp = _stamp(project)
    stamp.update(template=str(clone), template_commit=upgrade_template["b"])
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    _commit(project, "stamp at B")
    before = run(project, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout

    out = _apply(project, head)

    assert out["ok"] is True and out["no_changes"] is True, out
    assert out["branch"] is None and out["applied"] == []
    assert run(project, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout == before
    assert run(project, "git", "branch", "--list", "upgrade/*").stdout.strip() == ""
    assert run(project, "git", "status", "--porcelain").stdout == ""
    assert _stamp(project)["template_commit"] == upgrade_template["b"]
