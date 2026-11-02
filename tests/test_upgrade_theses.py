"""Upgrade delivers the theses tooling to an old repo and leaves the author's map alone."""

# ruff: noqa: F811  (the module-scoped template fixture is imported under an alias)

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import jsonschema
import yaml
from conftest import DEFAULT_CONTEXT, ROOT, _tpl_git, commit_all, render, run
from cookiecutter.main import cookiecutter
from test_upgrade_user_owned import _call, _install_engine
from test_upgrade_user_owned import template as base_template  # noqa: F401

DELIVERED = [
    "scripts/article/theses.py",
    "scripts/article/claims.py",
    "scripts/article/index.py",
    "schemas/theses.schema.json",
    "docs/procedures/red-team.md",
    "docs/procedures/blue-team.md",
    "docs/procedures/claim-check.md",
    ".claude/skills/red-team/SKILL.md",
    "theses.yaml",
    "AGENTS.md",
]
MAP = (
    "version: 1\nnodes:\n  - id: t1\n    type: thesis\n    text: Mine.\n"
    "    status: proposed\nedges: []\n"
)
AGENTS = "# My own instructions\n\nBe terse.\n"


def _old_repo(tmp_path: Path, base_template: dict[str, str]) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    project = Path(
        cookiecutter(
            base_template["old_source"],
            no_input=True,
            output_dir=str(out),
            extra_context=dict(DEFAULT_CONTEXT),
        )
    )
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=base_template["path"], template_commit=base_template["old"],
                 template_version="1.4.1")
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    _install_engine(project, stale=False)
    return project


def _apply(project: Path, new: str) -> dict:
    return _call(project, f"upgrade.apply(Path('.'), {new!r}, python={sys.executable!r})")


def test_old_repo_gains_the_tooling(tmp_path: Path, base_template: dict[str, str]) -> None:
    project = _old_repo(tmp_path, base_template)
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    for path in DELIVERED:
        assert (project / path).is_file(), path
        if not path.startswith("scripts/article/"):  # the engine copied in is already current
            assert path in out["applied"], (path, out)
    result = run(project, "python3", "-m", "scripts.article", "index")
    assert result.returncode == 0, result.stderr
    assert run(project, "python3", "-m", "scripts.article", "theses", "lint").returncode == 0


def test_existing_map_and_agents_file_are_not_touched(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    project = _old_repo(tmp_path, base_template)
    (project / "theses.yaml").write_text(MAP)
    (project / "AGENTS.md").write_text(AGENTS)
    (project / ".theses").mkdir()
    (project / ".theses" / "claims-cache.json").write_text("{}\n")
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    assert (project / "theses.yaml").read_text() == MAP
    assert (project / "AGENTS.md").read_text() == AGENTS
    assert (project / ".theses" / "claims-cache.json").read_text() == "{}\n"
    skipped = {item["path"] for item in out["skipped"]}
    assert {"theses.yaml", "AGENTS.md"} <= skipped
    assert "docs/procedures/red-team.md" in out["applied"]


def test_later_template_edits_to_owned_files_are_skipped(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    """The template changes theses.yaml and AGENTS.md after the repo was rendered."""
    tpl = tmp_path / "tpl"
    shutil.copytree(base_template["path"], tpl)
    out = tmp_path / "out"
    out.mkdir()
    project = Path(
        cookiecutter(
            str(tpl), no_input=True, output_dir=str(out), extra_context=dict(DEFAULT_CONTEXT)
        )
    )
    base = _tpl_git(tpl, "rev-parse", "HEAD")
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=str(tpl), template_commit=base)
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    _install_engine(project, stale=False)
    (project / "theses.yaml").write_text(MAP)
    (project / "AGENTS.md").write_text(AGENTS)
    commit_all(project)

    tpl_root = tpl / "{{cookiecutter.repo_name}}"
    (tpl_root / "theses.yaml").write_text(
        (tpl_root / "theses.yaml").read_text() + "# a newer template comment\n"
    )
    (tpl_root / "AGENTS.md").write_text((tpl_root / "AGENTS.md").read_text() + "\nNew line.\n")
    (tpl_root / "docs" / "procedures" / "red-team.md").write_text(
        (tpl_root / "docs" / "procedures" / "red-team.md").read_text() + "\nExtra rule.\n"
    )
    _tpl_git(tpl, "add", "-A")
    _tpl_git(tpl, "commit", "--quiet", "-m", "template edits")
    new = _tpl_git(tpl, "rev-parse", "HEAD")

    result = _apply(project, new)
    assert not result.get("conflicted"), result
    assert (project / "theses.yaml").read_text() == MAP
    assert (project / "AGENTS.md").read_text() == AGENTS
    reasons = {i["path"]: i["reason"] for i in result["skipped"]}
    assert "yours after first render" in reasons["theses.yaml"]
    assert "docs/procedures/red-team.md" in result["applied"]
    assert "Extra rule." in (project / "docs/procedures/red-team.md").read_text()


def _plan(project: Path) -> dict:
    result = run(project, "python3", "-m", "scripts.article", "upgrade", "--plan", "--json")
    payload = json.loads(result.stdout)
    jsonschema.validate(
        payload, json.loads((project / "schemas" / "upgrade.schema.json").read_text())
    )
    return payload


def test_plan_notices_a_companion_config_without_the_deny_patterns(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    assert _plan(project)["notices"] == []
    path = project / "companion.yaml"
    data = yaml.safe_load(path.read_text())
    data["exclude"] = [p for p in data["exclude"] if p not in ("theses.yaml", ".theses/**")]
    path.write_text(yaml.safe_dump(data))
    notices = _plan(project)["notices"]
    assert [n["code"] for n in notices] == ["N001"]
    assert "theses.yaml" in notices[0]["message"] and ".theses/**" in notices[0]["message"]
    text = run(project, "python3", "-m", "scripts.article", "upgrade", "--plan")
    assert "NOTICE [N001]" in text.stderr


def test_plan_without_companion_config_has_no_notice(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "companion.yaml").unlink()
    assert _plan(project)["notices"] == []


def test_owned_lists_name_the_author_files() -> None:
    text = (ROOT / "{{cookiecutter.repo_name}}/scripts/article/upgrade.py").read_text()
    assert '"theses.yaml"' in text and '"AGENTS.md"' in text
