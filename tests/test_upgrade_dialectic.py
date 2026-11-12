"""Dialectic stage: one-time upgrade notice, author files untouched, companion unchanged."""

# ruff: noqa: F811  (the module-scoped template fixture is imported under an alias)

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from conftest import ROOT, commit_all, render, run
from test_companion_build import _companion, _paths
from test_upgrade_theses import _apply, _old_repo
from test_upgrade_user_owned import template as base_template  # noqa: F401

TPL = ROOT / "{{cookiecutter.repo_name}}"
MAP = (
    "version: 1\nnodes:\n  - id: t1\n    type: thesis\n    text: Mine.\n"
    "    status: proposed\nedges: []\ncontradictions: []\nmoves: []\n"
)
FLOW = (
    "version: 1\nround: 3\nweights: {script: 0, small: 2, large: 9}\n"
    "budget: {limit: 40, used: 7}\nretry_cap: 1\nattestations: []\nwaivers: []\n"
    "orders: {}\nreviews: []\nrequired_stages: [dialectic]\n"
)


def _plan_json(project: Path) -> dict:
    """Unvalidated: an old repo still carries the old upgrade schema until applied."""
    result = run(project, "python3", "-m", "scripts.article", "upgrade", "--plan", "--json")
    return json.loads(result.stdout)


def _notice_codes(project: Path) -> list[str]:
    return [n["code"] for n in _plan_json(project)["notices"]]


def test_notice_is_shown_until_the_procedure_arrives(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    project = _old_repo(tmp_path, base_template)
    commit_all(project)
    notices = {n["code"]: n["message"] for n in _plan_json(project)["notices"]}
    assert "N004" in notices
    for word in ("required_stages", "untraced-reason", "flow attest dialectic", "theses add"):
        assert word in notices["N004"], word
    _apply(project, base_template["new"])
    assert "N004" not in _notice_codes(project)  # once per feature


def test_required_stage_notice_until_the_author_adds_the_line(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    project = _old_repo(tmp_path, base_template)
    (project / "flow.yaml").write_text(FLOW.replace("required_stages: [dialectic]\n", ""))
    commit_all(project)
    notices = {n["code"]: n["message"] for n in _plan_json(project)["notices"]}
    assert "N005" in notices and "required_stages: [dialectic]" in notices["N005"]
    before = yaml.safe_load((project / "flow.yaml").read_text())
    _apply(project, base_template["new"])
    # flow.yaml's values are the author's: the upgrade appends commented examples only.
    assert yaml.safe_load((project / "flow.yaml").read_text()) == before
    assert "N005" in _notice_codes(project)  # advice stays until the line is added
    (project / "flow.yaml").write_text(FLOW)
    assert "N005" not in _notice_codes(project)


def test_fresh_repo_requires_the_stage_and_opens_on_it(fresh_project: Path) -> None:
    flow = yaml.safe_load((fresh_project / "flow.yaml").read_text())
    assert flow["required_stages"] == ["dialectic"]
    assert "N005" not in _notice_codes(fresh_project)
    status = json.loads(
        run(fresh_project, "python3", "-m", "scripts.article", "flow", "status", "--json").stdout
    )
    assert [s["stage"] for s in status["stages"]][:2] == ["dialectic", "frame"]
    assert status["current_stage"] == "dialectic"
    order = json.loads(
        run(fresh_project, "python3", "-m", "scripts.article", "flow", "next").stdout
    )["order"]
    assert (order["stage"], order["kind"], order["needs_human"]) == (
        "dialectic", "ground-niche", True,
    )


def test_fresh_repo_has_no_dialectic_notice(tmp_path: Path) -> None:
    assert "N004" not in _notice_codes(render(tmp_path=tmp_path))


def test_upgrade_leaves_map_and_flow_with_dialectic_content_alone(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    project = _old_repo(tmp_path, base_template)
    (project / "theses.yaml").write_text(MAP)
    (project / "flow.yaml").write_text(FLOW)
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    assert (project / "theses.yaml").read_text() == MAP
    flow = (project / "flow.yaml").read_text()
    assert flow.startswith(FLOW)  # at most commented examples are appended
    assert all(not x.strip() or x.lstrip().startswith("#") for x in flow[len(FLOW):].splitlines())
    assert yaml.safe_load(flow)["required_stages"] == ["dialectic"]
    skipped = {item["path"] for item in out["skipped"]}
    assert {"theses.yaml", "flow.yaml"} <= skipped
    assert "docs/procedures/dialectic.md" in out["applied"]
    assert ".claude/skills/dialectic/SKILL.md" in out["applied"]


def test_companion_ships_no_dialectic_material(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "theses.yaml").write_text(
        MAP.replace("contradictions: []\nmoves: []\n", "")
        + "contradictions:\n  - id: c1\n    kind: soft\nmoves: []\n"
    )
    snap = tmp_path / "snap"
    result, payload = _companion(project, "--build", str(snap))
    assert result.returncode == 0, result.stderr
    paths = _paths(payload)
    assert "theses.yaml" not in paths
    assert not any(p.startswith(("docs/", ".claude/", ".theses/")) for p in paths), paths
    assert not (snap / "theses.yaml").exists()
    assert not (snap / "docs" / "procedures" / "dialectic.md").exists()
    # Schemas ship by design (generic structure, no map data); everything else is map-free.
    shipped = "".join(
        f.read_text(errors="ignore")
        for f in snap.rglob("*")
        if f.is_file() and f.relative_to(snap).parts[0] != "schemas"
    )
    assert "contradictions" not in shipped and "dialectic" not in shipped.lower()
    schemas = "".join(f.read_text() for f in (snap / "schemas").glob("*")).lower()
    assert "go-getter" not in schemas
    assert not re.search(r"\b(claude|gpt|opus|sonnet|haiku|gemini)\b", schemas)
    assert "contradiction-unmoved" not in schemas  # gap kinds are CLI output, not schema


def test_template_companion_config_needs_no_new_pattern() -> None:
    exclude = yaml.safe_load((TPL / "companion.yaml").read_text())["exclude"]
    assert {"theses.yaml", ".theses/**", "docs/**"} <= set(exclude)
    assert json.dumps(exclude).lower().count("dialectic") == 0
