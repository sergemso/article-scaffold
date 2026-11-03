"""Argument nodes in the theses map (decision 0073): schema and structural lint."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT, render, run

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SCHEMA = json.loads((TEMPLATE / "schemas" / "theses.schema.json").read_text())


def _theses():
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import theses
    finally:
        sys.path.remove(str(TEMPLATE))
    return theses


theses = _theses()

VALID = {
    "version": 1,
    "nodes": [
        {"id": "t1", "type": "thesis", "text": "Exhaustion is not rule Q.",
         "status": "accepted", "accepted-by": "Ada Lovelace"},
        {"id": "s1", "type": "source-claim", "text": "Rule Q covers corruption.",
         "status": "proposed", "quote": "Q applies to corruption", "locator": "p. 3"},
        {"id": "a1", "type": "argument", "text": "Exhaustion is deliberate, so not Q.",
         "status": "proposed", "conclusion": "t1", "inference": "modus-tollens",
         "premises": [
             {"n": 1, "text": "Rule Q is for corruption.", "ref": "s1"},
             {"n": 2, "text": "Exhaustion is a deliberate act."},
             {"n": 3, "text": "A deliberate act is not corruption.", "kind": "implicit",
              "status": "accepted"},
             {"n": 4, "text": "Exhaustion has a recovery path.", "role": "supports-conclusion"},
         ],
         "steps": [{"from": [1, 2, 3], "to": "c1", "rule": "modus-tollens"}]},
        {"id": "o1", "type": "objection", "text": "Premise 3 begs the question.",
         "status": "proposed", "premise-ref": {"argument": "a1", "n": 3}},
    ],
    "edges": [
        {"from": "a1", "to": "t1", "type": "supports"},
        {"from": "o1", "to": "a1", "type": "attacks"},
    ],
}


def _mutated(mutate) -> dict:
    data = copy.deepcopy(VALID)
    mutate(data)
    return data


def _argument(data: dict) -> dict:
    return data["nodes"][2]


def _diagnostics(data: dict):
    found = theses.Diagnostics()
    theses.validate_map(data, None, found)
    return found


def _codes(data: dict, severity: str = "error") -> set[str]:
    return {d.code for d in _diagnostics(data).items if d.severity == severity}


def test_valid_fixture_matches_schema_and_lints_clean() -> None:
    jsonschema.validate(VALID, SCHEMA)
    assert _diagnostics(VALID).items == []


def test_a_map_without_arguments_is_unchanged() -> None:
    plain = {"version": 1, "nodes": [VALID["nodes"][0], VALID["nodes"][1]], "edges": []}
    jsonschema.validate(plain, SCHEMA)
    assert _diagnostics(plain).items == []


SCHEMA_FAILURES = {
    "argument without conclusion": lambda d: _argument(d).pop("conclusion"),
    "argument without inference": lambda d: _argument(d).pop("inference"),
    "argument without premises": lambda d: _argument(d).pop("premises"),
    "empty premises": lambda d: _argument(d).update(premises=[]),
    "unknown inference": lambda d: _argument(d).update(inference="vibes"),
    "premise without text": lambda d: _argument(d)["premises"][0].pop("text"),
    "premise number zero": lambda d: _argument(d)["premises"][0].update(n=0),
    "unknown premise field": lambda d: _argument(d)["premises"][0].update(weight=1),
    "bad premise kind": lambda d: _argument(d)["premises"][0].update(kind="hidden"),
    "bad premise role": lambda d: _argument(d)["premises"][0].update(role="optional"),
    "step without rule": lambda d: _argument(d)["steps"][0].pop("rule"),
    "premises on a thesis": lambda d: d["nodes"][0].update(premises=[{"n": 1, "text": "x"}]),
    "inference on an objection": lambda d: d["nodes"][3].update(inference="deduction"),
    "premise-ref on a thesis": lambda d: d["nodes"][0].update(
        {"premise-ref": {"argument": "a1", "n": 1}}),
    "premise-ref without n": lambda d: d["nodes"][3]["premise-ref"].pop("n"),
}


@pytest.mark.parametrize("name", sorted(SCHEMA_FAILURES))
def test_schema_rejects(name: str) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_mutated(SCHEMA_FAILURES[name]), SCHEMA)


LINT_ERRORS = {
    "T017": lambda d: d["nodes"][0].update(premises=[{"n": 1, "text": "x"}]),
    "T018": lambda d: _argument(d).pop("inference"),
    "T019": lambda d: _argument(d).update(conclusion="nope"),
    "T020": lambda d: _argument(d).update(inference="vibes"),
    "T021": lambda d: _argument(d).update(premises=[]),
    "T022": lambda d: _argument(d)["premises"][1].update(n=5),
    "T023": lambda d: _argument(d)["steps"][0].update({"from": [1, 9]}),
    "T024": lambda d: _argument(d)["premises"][0].update(ref="t1"),
    "T025": lambda d: (
        _argument(d).update(status="accepted", **{"accepted-by": "Ada Lovelace"}),
        _argument(d)["premises"][2].pop("status"),
    ),
    "T028": lambda d: d["nodes"][3]["premise-ref"].update(n=9),
}


@pytest.mark.parametrize("code", sorted(LINT_ERRORS))
def test_lint_reports(code: str) -> None:
    assert code in _codes(_mutated(LINT_ERRORS[code]))


def test_conclusion_must_be_a_thesis_or_hypothesis() -> None:
    data = _mutated(lambda d: _argument(d).update(conclusion="o1"))
    assert "T019" in _codes(data)


def test_duplicate_premise_numbers_are_reported() -> None:
    data = _mutated(lambda d: _argument(d)["premises"][1].update(n=1))
    assert "T022" in _codes(data)


def test_premise_ref_must_name_an_argument() -> None:
    data = _mutated(lambda d: d["nodes"][3].update({"premise-ref": {"argument": "s1", "n": 1}}))
    assert "T028" in _codes(data)


def test_implicit_premise_without_status_blocks_acceptance() -> None:
    def mutate(d: dict) -> None:
        _argument(d).update(status="accepted", **{"accepted-by": "Ada Lovelace"})
        _argument(d)["premises"][2]["status"] = "proposed"

    assert "T025" in _codes(_mutated(mutate))


def test_proposed_implicit_premise_is_fine_while_the_argument_is_proposed() -> None:
    data = _mutated(lambda d: _argument(d)["premises"][2].update(status="proposed"))
    assert _diagnostics(data).items == []


def test_single_premise_deduction_is_a_warning_not_an_error() -> None:
    def mutate(d: dict) -> None:
        _argument(d).update(inference="deduction", premises=[{"n": 1, "text": "Only one."}])
        _argument(d).pop("steps")
        d["nodes"][3].pop("premise-ref")

    data = _mutated(mutate)
    assert _codes(data) == set()
    assert _codes(data, "warning") == {"T026"}


def test_single_premise_induction_is_not_flagged() -> None:
    def mutate(d: dict) -> None:
        _argument(d).update(inference="induction", premises=[{"n": 1, "text": "Only one."}])
        _argument(d).pop("steps")
        d["nodes"][3].pop("premise-ref")

    assert _diagnostics(_mutated(mutate)).items == []


@pytest.mark.parametrize("which", ["conclusion", "required premise", "ref"])
def test_accepted_argument_over_retired_input_is_flagged(which: str) -> None:
    def mutate(d: dict) -> None:
        _argument(d).update(status="accepted", **{"accepted-by": "Ada Lovelace"})
        if which == "conclusion":
            d["nodes"][0]["status"] = "retired"
        elif which == "required premise":
            _argument(d)["premises"][1]["status"] = "retired"
        else:
            d["nodes"][1]["status"] = "retired"

    data = _mutated(mutate)
    assert _codes(data) == set()
    assert _codes(data, "warning") == {"T027"}


def test_retired_supporting_premise_does_not_flag() -> None:
    def mutate(d: dict) -> None:
        _argument(d).update(status="accepted", **{"accepted-by": "Ada Lovelace"})
        _argument(d)["premises"][3]["status"] = "retired"

    assert _diagnostics(_mutated(mutate)).items == []


def test_malformed_argument_does_not_crash_the_linter() -> None:
    for premises in (None, "text", [None], [{"n": "one", "text": 3}], [[]]):
        data = _mutated(lambda d, bad=premises: _argument(d).update(premises=bad))
        assert _codes(data), premises
    data = _mutated(lambda d: _argument(d).update(steps="soon"))
    assert "T023" in _codes(data)
    data = _mutated(lambda d: d["nodes"][3].update({"premise-ref": "a1#3"}))
    assert "T028" in _codes(data)


def test_rendered_repo_lints_and_accepts_an_argument(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    text = yaml.safe_dump(VALID, sort_keys=False)
    (project / "theses.yaml").write_text(text)
    lint = run(project, "python3", "-m", "scripts.article", "theses", "lint")
    assert lint.returncode == 0, lint.stdout + lint.stderr
    accept = run(project, "python3", "-m", "scripts.article", "theses", "accept", "a1",
                 "--by", "Ada Lovelace")
    assert accept.returncode == 0, accept.stdout + accept.stderr
    saved = yaml.safe_load((project / "theses.yaml").read_text())
    node = next(n for n in saved["nodes"] if n["id"] == "a1")
    assert node["status"] == "accepted" and node["accepted-by"] == "Ada Lovelace"
    assert node["premises"] == VALID["nodes"][2]["premises"]


def test_accept_refuses_while_an_implicit_premise_is_proposed(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    data = _mutated(lambda d: _argument(d)["premises"][2].update(status="proposed"))
    (project / "theses.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    before = (project / "theses.yaml").read_text()
    accept = run(project, "python3", "-m", "scripts.article", "theses", "accept", "a1",
                 "--by", "Ada Lovelace")
    assert accept.returncode != 0
    assert (project / "theses.yaml").read_text() == before
