"""Theses map schema, template file and validate.py hook."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT, render, run

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SCHEMA = json.loads((TEMPLATE / "schemas" / "theses.schema.json").read_text())

VALID = {
    "version": 1,
    "nodes": [
        {"id": "t1", "type": "thesis", "text": "Main claim.", "status": "accepted",
         "accepted-by": "Ada Lovelace", "anchor": None},
        {"id": "o1", "type": "objection", "text": "An objection.", "status": "proposed"},
        {"id": "d1", "type": "defense", "text": "A defense.", "status": "proposed",
         "bib_keys": ["smith2020"]},
        {"id": "h1", "type": "hypothesis", "text": "A guess.", "status": "retired"},
        {"id": "s1", "type": "source-claim", "text": "Smith says X.",
         "status": "proposed", "quote": "X holds", "locator": "p. 3",
         "bib_keys": ["smith2020"]},
    ],
    "edges": [
        {"from": "o1", "to": "t1", "type": "attacks"},
        {"from": "d1", "to": "o1", "type": "rebuts"},
        {"from": "s1", "to": "t1", "type": "supports"},
    ],
}


def _mutated(mutate) -> dict:
    data = copy.deepcopy(VALID)
    mutate(data)
    return data


def _write(project: Path, data: dict) -> None:
    (project / "theses.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def _validate(project: Path):
    return run(project, "python3", "scripts/validate-paper.py")


def test_template_map_is_schema_valid() -> None:
    data = yaml.safe_load((TEMPLATE / "theses.yaml").read_text())
    jsonschema.validate(data, SCHEMA)
    assert data["nodes"] == [] and data["edges"] == []


def test_valid_fixture_matches_schema() -> None:
    jsonschema.validate(VALID, SCHEMA)


SCHEMA_FAILURES = {
    "unknown node field": lambda d: d["nodes"][0].update(extra=1),
    "unknown edge field": lambda d: d["edges"][0].update(weight=2),
    "bad node type": lambda d: d["nodes"][1].update(type="claim"),
    "bad edge type": lambda d: d["edges"][0].update(type="likes"),
    "bad status": lambda d: d["nodes"][1].update(status="done"),
    "accepted without accepted-by": lambda d: d["nodes"][0].pop("accepted-by"),
    "source-claim without quote": lambda d: d["nodes"][4].pop("quote"),
    "source-claim without locator": lambda d: d["nodes"][4].pop("locator"),
    "multi-line text": lambda d: d["nodes"][1].update(text="a\nb"),
    "missing version": lambda d: d.pop("version"),
}


@pytest.mark.parametrize("name", sorted(SCHEMA_FAILURES))
def test_schema_rejects(name: str) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_mutated(SCHEMA_FAILURES[name]), SCHEMA)


def test_rendered_repo_ships_empty_map_and_passes(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    assert (project / "theses.yaml").is_file()
    assert (project / "schemas" / "theses.schema.json").is_file()
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_valid_map_passes_validate(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _write(project, VALID)
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


def test_absent_map_is_not_an_error(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "theses.yaml").unlink()
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout


VALIDATE_FAILURES = {
    "T002": lambda d: d["nodes"][0].update(extra=1),
    "T005": lambda d: d["nodes"].append(dict(d["nodes"][1])),
    "T006": lambda d: d["nodes"][1].update(type="claim"),
    "T008": lambda d: d["nodes"][1].update(status="done"),
    "T012": lambda d: d["nodes"][0].pop("accepted-by"),
    "T013": lambda d: d["nodes"][0].update({"accepted-by": "red-team agent"}),
    "T014": lambda d: d["nodes"][4].pop("quote"),
    "T015": lambda d: d["edges"][0].update(type="likes"),
    "T016": lambda d: d["edges"][0].update({"to": "nope"}),
    "T010": lambda d: d["nodes"][1].update(anchor="sec:missing"),
}


@pytest.mark.parametrize("code", sorted(VALIDATE_FAILURES))
def test_validate_rejects(tmp_path: Path, code: str) -> None:
    project = render(tmp_path=tmp_path)
    _write(project, _mutated(VALIDATE_FAILURES[code]))
    result = _validate(project)
    assert result.returncode == 1
    assert f"theses.yaml:0: {code}:" in result.stderr


def test_existing_anchor_is_accepted(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    section = project / "paper" / "sections" / "01_introduction.tex"
    section.write_text(section.read_text() + "\n\\label{sec:anchor-test}\n")
    _write(project, _mutated(lambda d: d["nodes"][1].update(anchor="sec:anchor-test")))
    result = _validate(project)
    assert result.returncode == 0, result.stderr + result.stdout
