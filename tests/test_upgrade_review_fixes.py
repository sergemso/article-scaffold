"""Regression tests for the upgrade command's review findings."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from conftest import run

STATUS = "scripts/article/status.py"


def _eval(project: Path, code: str) -> dict:
    result = run(project, sys.executable, "-c", code)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def _tpl(template: dict[str, str], *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@invalid", *args],
        cwd=template["path"], capture_output=True, text=True, check=True,
    ).stdout.strip()


def _edit_stamp(project: Path, **changes: object) -> None:
    path = project / "template.json"
    stamp = json.loads(path.read_text(encoding="utf-8"))
    stamp.update(changes)
    path.write_text(json.dumps(stamp), encoding="utf-8")
    run(project, "git", "commit", "-qam", "edit stamp", check=True)


def _plan_new(project: Path, ref: str) -> str:
    out = _eval(
        project,
        "import json\nfrom pathlib import Path\nfrom scripts.article import upgrade\n"
        f"print(json.dumps(upgrade.plan(Path('.'), {ref!r})['plan']))",
    )
    return out["new"]


def test_refs_resolve_by_exact_name_and_annotated_tags_to_their_commit(
    upgrade_project: Path, upgrade_template: dict[str, str]
) -> None:
    _tpl(upgrade_template, "tag", "-a", "rel", "-m", "release", upgrade_template["b"])
    _tpl(upgrade_template, "branch", "x/rel", upgrade_template["a"])

    assert _plan_new(upgrade_project, "rel") == upgrade_template["b"]


def test_a_relative_template_path_works_for_apply(
    upgrade_project: Path, upgrade_template: dict[str, str]
) -> None:
    relative = os.path.relpath(upgrade_template["path"], upgrade_project)
    _edit_stamp(upgrade_project, template=relative)
    code = (
        "import json\nfrom pathlib import Path\nfrom scripts.article import upgrade\n"
        f"print(json.dumps(upgrade.apply(Path('.'), {upgrade_template['b']!r}, "
        f"python={sys.executable!r})))"
    )

    out = _eval(upgrade_project, code)

    assert out["ok"] is True and STATUS in out["applied"], out


def test_a_failed_apply_is_rolled_back(
    upgrade_project: Path, upgrade_template: dict[str, str]
) -> None:
    before = run(upgrade_project, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    code = (
        "import json\nfrom pathlib import Path\nfrom scripts.article import upgrade\n"
        "def boom(root, chunk):\n    raise OSError('disk gone')\n"
        "upgrade._apply_chunk = boom\n"
        "try:\n"
        f"    upgrade.apply(Path('.'), {upgrade_template['b']!r}, python={sys.executable!r})\n"
        "    out = {}\n"
        "except upgrade.UpgradeError as exc:\n"
        "    out = {'error': exc.code}\n"
        "print(json.dumps(out))\n"
    )

    out = _eval(upgrade_project, code)

    assert "error" in out
    assert run(upgrade_project, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == before
    assert run(upgrade_project, "git", "branch", "--list", "upgrade/*").stdout.strip() == ""
    assert run(upgrade_project, "git", "status", "--porcelain").stdout == ""


def test_the_stamp_is_ignored_only_at_the_root(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "sub").mkdir(parents=True)
    (src / "template.json").write_text("root", encoding="utf-8")
    (src / "sub" / "template.json").write_text("nested", encoding="utf-8")
    pytest.importorskip("yaml")
    import shutil

    package = tmp_path / "pkg"
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "{{cookiecutter.repo_name}}" / "scripts" / "article",
        package / "article", ignore=shutil.ignore_patterns("__pycache__"),
    )
    code = (
        "import json, shutil, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(package)!r})\n"
        "from article import upgrade\n"
        f"src, dst = Path({str(src)!r}), Path({str(dst)!r})\n"
        "shutil.copytree(src, dst, ignore=upgrade._ignored(src))\n"
        "print(json.dumps(sorted(str(p.relative_to(dst)) for p in dst.rglob('*') if p.is_file())))"
    )
    import subprocess

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["sub/template.json"]


@pytest.mark.parametrize("context", [None, [], "x"])
def test_a_stamp_with_a_non_object_context_is_refused_not_a_crash(
    upgrade_project: Path, context: object
) -> None:
    _edit_stamp(upgrade_project, context=context)

    result = run(upgrade_project, sys.executable, "-m", "scripts.article", "upgrade", "--plan",
                 "--json")

    assert result.returncode == 1, result.stderr
    assert [r["code"] for r in json.loads(result.stdout)["refusals"]] == ["U002"]


def test_unusual_names_and_a_signing_config_do_not_change_the_diff(
    upgrade_project: Path, tmp_path: Path
) -> None:
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "é figure.tex").write_text("a\n", encoding="utf-8")
    (new / "é figure.tex").write_text("b\n", encoding="utf-8")
    (new / "added.log").write_text("x\n", encoding="utf-8")  # matches a global ignore below
    excludes = tmp_path / "ignore"
    excludes.write_text("*.log\n", encoding="utf-8")
    code = (
        "import json\nfrom pathlib import Path\nfrom scripts.article import upgrade\n"
        f"patch, files = upgrade._diff_trees(Path({str(old)!r}), Path({str(new)!r}), "
        f"Path({str(tmp_path / 'scratch')!r}))\n"
        "print(json.dumps(files))"
    )
    env = {
        **os.environ,
        "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "true",
        "GIT_CONFIG_KEY_1": "gpg.program", "GIT_CONFIG_VALUE_1": "false",
        "GIT_CONFIG_KEY_2": "core.excludesFile", "GIT_CONFIG_VALUE_2": str(excludes),
    }
    import subprocess

    result = subprocess.run([sys.executable, "-c", code], cwd=upgrade_project, env=env,
                            capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == [
        {"path": "added.log", "status": "A"},
        {"path": "é figure.tex", "status": "M"},
    ]


def test_apply_on_an_up_to_date_repo_says_so(
    upgrade_project: Path, upgrade_template: dict[str, str]
) -> None:
    result = run(upgrade_project, sys.executable, "-m", "scripts.article", "upgrade", "--apply",
                 "--to", upgrade_template["a"])

    assert result.returncode == 0, result.stderr
    assert "already up to date" in result.stdout
