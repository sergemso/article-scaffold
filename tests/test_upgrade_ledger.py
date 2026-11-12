"""Upgrade delivers the ledger and the source store and leaves the author's files alone."""

# ruff: noqa: F811  (the module-scoped template fixture is imported under an alias)

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml
from conftest import commit_all, render, run
from test_upgrade_theses import _apply, _old_repo
from test_upgrade_user_owned import template as base_template  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"


def test_old_repo_gains_the_ledger_without_touching_author_files(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    project = _old_repo(tmp_path, base_template)
    (project / "paper" / "sources").mkdir(parents=True, exist_ok=True)
    (project / "paper" / "sources" / "MANIFEST.md").write_text("| key | file |\n")
    metadata = yaml.safe_load((project / "metadata.yaml").read_text())
    metadata.pop("abstract_note", None)  # the older 1.5.0 migration drops the placeholder
    flow_before = {"version": 1, "round": 3, "budget": {"limit": 20, "used": 7}}
    (project / "flow.yaml").write_text(yaml.safe_dump(flow_before))  # the author's file
    (project / ".gitattributes").write_text("*.pdf binary")
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    assert (project / "docs" / "ledger" / "README.md").is_file()
    assert yaml.safe_load((project / "metadata.yaml").read_text()) == metadata
    assert yaml.safe_load((project / "flow.yaml").read_text()) == flow_before
    assert "# max_calls:" in (project / "flow.yaml").read_text()
    attributes = (project / ".gitattributes").read_text().splitlines()
    assert attributes[0] == "*.pdf binary"
    assert "docs/ledger/** linguist-generated=true" in attributes
    assert "paper/sources/*.txt -text" in attributes
    assert "paper/sources/*/*/raw.* -text" in attributes
    manifest = json.loads((project / "paper/sources/manifest.json").read_text())
    assert manifest == {"schema_version": "1.0", "sources": []}
    assert (project / "paper/sources/MANIFEST.md").read_text() == "| key | file |\n"
    assert {"paper/sources/manifest.json", ".gitattributes"} <= set(out["applied"]) | {
        i["path"] for i in out["skipped"]
    }
    result = run(project, "python3", "-m", "scripts.article", "sources", "list", "--json")
    assert result.returncode == 0, result.stderr


def test_delivery_is_idempotent_and_adds_nothing_twice(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    from importlib import util

    spec = util.spec_from_file_location(
        "migrations_under_test", TEMPLATE / "scripts" / "article" / "migrations.py"
    )
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.deliveries(project) == {}  # a fresh repo already has everything
    (project / ".gitattributes").unlink()
    (project / "flow.yaml").write_text("version: 1\nround: 2\n")
    got = module.deliveries(project)
    assert ".gitattributes" not in got  # a missing file comes with the template diff
    assert got["flow.yaml"].startswith("version: 1\nround: 2\n")
    (project / "flow.yaml").write_text(got["flow.yaml"])
    assert module.deliveries(project) == {}


def _plan(project: Path) -> dict:
    result = run(project, "python3", "-m", "scripts.article", "upgrade", "--plan", "--json")
    payload = json.loads(result.stdout)
    jsonschema.validate(
        payload, json.loads((project / "schemas" / "upgrade.schema.json").read_text())
    )
    return payload


def test_plan_warns_about_sources_and_the_legacy_cache(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    assert _plan(project)["notices"] == []
    path = project / "companion.yaml"
    before = path.read_text()
    data = yaml.safe_load(before)
    dropped = ("paper/sources/**", "docs/**", "docs/ledger/**")
    data["exclude"] = [p for p in data["exclude"] if p not in dropped]
    path.write_text(yaml.safe_dump(data))
    (project / ".theses").mkdir(exist_ok=True)
    (project / ".theses" / "claims-cache.json").write_text("{}\n")
    edited = path.read_text()
    notices = {n["code"]: n["message"] for n in _plan(project)["notices"]}
    assert set(notices) == {"N002", "N003"}
    assert "paper/sources/**" in notices["N002"] and "docs/ledger/**" in notices["N002"]
    assert "claims-cache.json" in notices["N003"]
    assert path.read_text() == edited  # warned, never edited


def test_template_companion_default_excludes_ledger_and_sources() -> None:
    data = yaml.safe_load((TEMPLATE / "companion.yaml").read_text())
    assert {"docs/ledger/**", "paper/sources/**"} <= set(data["exclude"])


LEGACY_MAP = (
    "version: 1\nnodes:\n"
    "  - id: t1\n    type: thesis\n    text: Main claim.\n    status: accepted\n"
    "    accepted-by: Ada\n"
    "  - id: o1\n    type: objection\n    text: An objection.\n    status: accepted\n"
    "    accepted-by: Ada\n"
    "  - id: d1\n    type: defense\n    text: A defense.\n    status: proposed\n"
    "edges:\n  - {from: o1, to: t1, type: attacks}\n  - {from: d1, to: o1, type: rebuts}\n"
    "  - {from: d1, to: t1, type: supports}\n"
)


def test_upgrade_leaves_a_hand_accepted_map_and_the_ledger_alone(
    tmp_path: Path, base_template: dict[str, str]
) -> None:
    """Decision 0085: a map accepted before acceptance records existed lints with notes
    only, the stored ledger entries are untouched, and flow status is unchanged apart from
    the derived quality vector."""
    project = _old_repo(tmp_path, base_template)
    (project / "theses.yaml").write_text(LEGACY_MAP)
    flow_before = {
        "version": 1, "round": 2, "weights": {"script": 0, "small": 1, "large": 5},
        "budget": {"limit": 20, "used": 3}, "retry_cap": 3, "attestations": [],
        "waivers": [], "orders": {}, "reviews": [],
    }  # a complete pre-0084 flow.yaml: no required_stages line
    (project / "flow.yaml").write_text(yaml.safe_dump(flow_before))
    entry = project / "docs" / "ledger" / "check-outcome" / "ab" / ("ab" + "0" * 62 + ".json")
    entry.parent.mkdir(parents=True)
    entry.write_text("{\"kept\": \"as written\"}\n")  # whatever was there stays there
    commit_all(project)
    out = _apply(project, base_template["new"])
    assert not out.get("conflicted"), out
    assert (project / "theses.yaml").read_text() == LEGACY_MAP
    assert yaml.safe_load((project / "flow.yaml").read_text()) == flow_before
    assert entry.read_text() == "{\"kept\": \"as written\"}\n"
    lint = run(project, "python3", "-m", "scripts.article", "theses", "lint", "--json")
    assert lint.returncode == 0, lint.stderr + lint.stdout
    payload = json.loads(lint.stdout)
    assert payload["diagnostics"] == []
    assert [n["id"] for n in payload["notes"]] == ["t1", "o1"]  # file order
    status = run(project, "python3", "-m", "scripts.article", "flow", "status", "--json")
    stages = json.loads(status.stdout)
    assert [s["stage"] for s in stages["stages"]][0] == "frame"  # no required_stages line
    assert stages["quality"]["theses_accepted"] == 1
    assert stages["quality"]["objections_defended"] == 1
    accept = run(project, "python3", "-m", "scripts.article", "theses", "accept", "t1",
                 "--by", "Ada")
    assert accept.returncode == 0 and json.loads(accept.stdout)["recorded"] == "created"
    lint = run(project, "python3", "-m", "scripts.article", "theses", "lint", "--json")
    assert [n["id"] for n in json.loads(lint.stdout)["notes"]] == ["o1"]
