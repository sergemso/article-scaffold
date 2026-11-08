"""Upgrade delivers flow to an old repo and leaves the author's flow.yaml alone."""

# ruff: noqa: F811  (the module-scoped template fixture is imported under an alias)

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from conftest import DEFAULT_CONTEXT, _tpl_git, commit_all, run
from cookiecutter.main import cookiecutter
from test_upgrade_theses import _apply, _old_repo
from test_upgrade_user_owned import _install_engine
from test_upgrade_user_owned import template as base_template  # noqa: F401

DELIVERED = [
    "scripts/article/flow.py",
    "schemas/flow.schema.json",
    "schemas/flow-order.schema.json",
    "schemas/flow-status.schema.json",
    "docs/procedures/lifecycle.md",
    ".claude/skills/lifecycle/SKILL.md",
    "flow.yaml",
]
STATE = (
    "version: 1\nround: 3\nweights: {script: 0, small: 2, large: 9}\n"
    "budget: {limit: 40, used: 7}\nretry_cap: 1\nattestations: []\nwaivers: []\n"
    "orders: {}\nreviews: []\n"
)


def test_old_repo_gains_flow(tmp_path: Path, base_template: dict[str, str]) -> None:
    project = _old_repo(tmp_path, base_template)
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    for path in DELIVERED:
        assert (project / path).is_file(), path
        if not path.startswith("scripts/article/"):
            assert path in out["applied"], (path, out)
    result = run(project, "python3", "-m", "scripts.article", "flow", "status", "--json")
    assert json.loads(result.stdout)["stages"][0]["stage"] == "frame", result.stderr


def _only_comments_added(text: str) -> bool:
    """The E.1 migration may append commented examples; no value may change."""
    if not text.startswith(STATE):
        return False
    extra = text[len(STATE) :].splitlines()
    return all(not line.strip() or line.lstrip().startswith("#") for line in extra)


def test_existing_flow_yaml_is_untouched(tmp_path: Path, base_template: dict[str, str]) -> None:
    project = _old_repo(tmp_path, base_template)
    (project / "flow.yaml").write_text(STATE)
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    assert _only_comments_added((project / "flow.yaml").read_text())
    assert "flow.yaml" in {item["path"] for item in out["skipped"]}
    assert "docs/procedures/lifecycle.md" in out["applied"]
    status = run(project, "python3", "-m", "scripts.article", "flow", "status", "--json")
    assert json.loads(status.stdout)["round"] == 3  # the author's state is what flow reads


def test_later_template_edits_to_flow_yaml_are_skipped(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    tpl = tmp_path / "tpl"
    shutil.copytree(base_template["path"], tpl)
    out = tmp_path / "out"
    out.mkdir()
    project = Path(
        cookiecutter(
            str(tpl), no_input=True, output_dir=str(out), extra_context=dict(DEFAULT_CONTEXT)
        )
    )
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=str(tpl), template_commit=_tpl_git(tpl, "rev-parse", "HEAD"))
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    _install_engine(project, stale=False)
    (project / "flow.yaml").write_text(STATE)
    commit_all(project)
    tpl_root = tpl / "{{cookiecutter.repo_name}}"
    (tpl_root / "flow.yaml").write_text((tpl_root / "flow.yaml").read_text() + "# newer\n")
    _tpl_git(tpl, "add", "-A")
    _tpl_git(tpl, "commit", "--quiet", "-m", "template edits")
    result = _apply(project, _tpl_git(tpl, "rev-parse", "HEAD"))
    assert not result.get("conflicted"), result
    assert _only_comments_added((project / "flow.yaml").read_text())
    reasons = {i["path"]: i["reason"] for i in result["skipped"]}
    assert "yours after first render" in reasons["flow.yaml"]
    assert yaml.safe_load((project / "flow.yaml").read_text())["round"] == 3
