"""Objection and defense fields in the theses map (decision 0074): schema, lint and gaps."""

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
        {"id": "t1", "type": "thesis", "text": "Main claim.", "status": "accepted",
         "accepted-by": "Ada Lovelace", "needs-rival-objection": True},
        {"id": "s1", "type": "source-claim", "text": "Rival says X.", "status": "proposed",
         "quote": "X holds", "locator": "p. 3"},
        {"id": "o1", "type": "objection", "text": "A rival counterexample.",
         "status": "proposed", "author": "agent", "target": "t1", "form": "strongest",
         "strongest-form": {"source": "s1", "restated": "X holds in every case."},
         "tradition": "rival", "kind": "counterexample", "severity": "serious",
         "counterexample": {"case": "A case with X but not the claim.",
                            "why-it-bites": "It breaks the first premise."}},
        {"id": "d1", "type": "defense", "text": "Cite the evidence.", "status": "proposed",
         "answers": "o1", "move": "cite-evidence", "anchor": "sec:limits"},
    ],
    "edges": [
        {"from": "o1", "to": "t1", "type": "attacks"},
        {"from": "s1", "to": "d1", "type": "supports"},
    ],
}


def _mutated(mutate) -> dict:
    data = copy.deepcopy(VALID)
    mutate(data)
    return data


def _node(data: dict, node_id: str) -> dict:
    return next(n for n in data["nodes"] if n["id"] == node_id)


def _diagnostics(data: dict, bib: set[str] | None = None):
    found = theses.Diagnostics()
    theses.validate_map(data, None, found, bib)
    return found


def _codes(data: dict, severity: str = "error", bib: set[str] | None = None) -> set[str]:
    return {d.code for d in _diagnostics(data, bib).items if d.severity == severity}


def _gaps(data: dict, kinds=theses.GAP_KINDS) -> list[tuple[str, str]]:
    return [(g["kind"], g["id"]) for g in theses.gaps(data, None, kinds)]


def test_valid_fixture_matches_schema_and_lints_clean() -> None:
    jsonschema.validate(VALID, SCHEMA)
    assert _diagnostics(VALID).items == []
    new = {"defense-no-answers", "defense-no-anchor", "thesis-no-rival", "objection-undefended"}
    assert not new & {kind for kind, _ in _gaps(VALID)}


def test_a_legacy_map_is_unchanged() -> None:
    legacy = {
        "version": 1,
        "nodes": [
            {"id": "t1", "type": "thesis", "text": "Claim.", "status": "proposed"},
            {"id": "o1", "type": "objection", "text": "Objection.", "status": "proposed"},
            {"id": "d1", "type": "defense", "text": "Defense.", "status": "proposed"},
        ],
        "edges": [
            {"from": "o1", "to": "t1", "type": "attacks"},
            {"from": "d1", "to": "o1", "type": "rebuts"},
        ],
    }
    jsonschema.validate(legacy, SCHEMA)
    assert _diagnostics(legacy).items == []
    kinds = {k for k, _ in _gaps(legacy)}
    assert not kinds & {"defense-no-answers", "defense-no-anchor", "thesis-no-rival"}


SCHEMA_FAILURES = {
    "weak form": lambda d: _node(d, "o1").update(form="weak"),
    "bad tradition": lambda d: _node(d, "o1").update(tradition="friendly"),
    "bad kind": lambda d: _node(d, "o1").update(kind="complaint"),
    "bad severity": lambda d: _node(d, "o1").update(severity="catastrophic"),
    "bad author": lambda d: _node(d, "o1").update(author="model"),
    "bad move": lambda d: _node(d, "d1").update(move="ignore"),
    "strongest without strongest-form": lambda d: _node(d, "o1").pop("strongest-form"),
    "strongest-form without restated": lambda d: _node(d, "o1")["strongest-form"].pop("restated"),
    "counterexample kind without counterexample": lambda d: _node(d, "o1").pop("counterexample"),
    "counterexample without why-it-bites": lambda d: _node(d, "o1")["counterexample"].pop(
        "why-it-bites"),
    "accept-cost without cost": lambda d: _node(d, "d1").update(move="accept-cost"),
    "concede-scope without cost": lambda d: _node(d, "d1").update(move="concede-scope"),
    "multi-line cost": lambda d: _node(d, "d1").update(cost="a\nb"),
    "target on a defense": lambda d: _node(d, "d1").update(target="t1"),
    "answers on an objection": lambda d: _node(d, "o1").update(answers="o1"),
    "severity on a thesis": lambda d: _node(d, "t1").update(severity="fatal"),
    "needs-rival-objection on an objection": lambda d: _node(d, "o1").update(
        {"needs-rival-objection": True}),
    "needs-rival-objection not boolean": lambda d: _node(d, "t1").update(
        {"needs-rival-objection": "yes"}),
}


@pytest.mark.parametrize("name", sorted(SCHEMA_FAILURES))
def test_schema_rejects(name: str) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_mutated(SCHEMA_FAILURES[name]), SCHEMA)


def test_author_is_allowed_on_every_node_type() -> None:
    data = _mutated(lambda d: [n.update(author="human") for n in d["nodes"]])
    jsonschema.validate(data, SCHEMA)
    assert _diagnostics(data).items == []


LINT_ERRORS = {
    "T017": lambda d: _node(d, "d1").update(target="t1"),
    "T029": lambda d: _node(d, "o1").update(severity="catastrophic"),
    "T030": lambda d: _node(d, "o1").update(target="nope"),
    "T031": lambda d: _node(d, "o1").pop("strongest-form"),
    "T032": lambda d: _node(d, "o1")["strongest-form"].update(source="t1"),
    "T033": lambda d: _node(d, "o1").pop("counterexample"),
    "T034": lambda d: _node(d, "d1").update(answers="t1"),
    "T035": lambda d: _node(d, "d1").update(move="accept-cost"),
    "T036": lambda d: d["edges"].pop(),
}


@pytest.mark.parametrize("code", sorted(LINT_ERRORS))
def test_lint_reports(code: str) -> None:
    assert code in _codes(_mutated(LINT_ERRORS[code]))


def test_an_objection_with_adversarial_fields_needs_a_target() -> None:
    data = _mutated(lambda d: _node(d, "o1").pop("target"))
    assert "T030" in _codes(data)


def test_a_bare_legacy_objection_needs_no_target() -> None:
    def mutate(d: dict) -> None:
        for field in ("target", "form", "strongest-form", "tradition", "kind",
                      "counterexample", "severity"):
            _node(d, "o1").pop(field)

    assert _diagnostics(_mutated(mutate)).items == []


def test_unknown_answers_target_is_an_error() -> None:
    assert "T034" in _codes(_mutated(lambda d: _node(d, "d1").update(answers="nope")))


def test_cite_evidence_needs_a_source_claim_not_just_any_supporter() -> None:
    def mutate(d: dict) -> None:
        d["edges"][1] = {"from": "t1", "to": "d1", "type": "supports"}

    assert "T036" in _codes(_mutated(mutate))


def test_strongest_form_source_may_be_a_bib_key() -> None:
    def mutate(d: dict) -> None:
        _node(d, "o1")["strongest-form"]["source"] = "smith1999"

    data = _mutated(mutate)
    assert "T032" not in _codes(data)  # no bibliography given: nothing to check against
    assert "T032" not in _codes(data, bib={"smith1999"})
    assert "T032" in _codes(data, bib={"jones2001"})


def test_strongest_form_source_node_id_beats_bib_keys() -> None:
    assert _diagnostics(VALID, bib={"jones2001"}).items == []


def test_premise_ref_must_agree_with_target() -> None:
    def mutate(d: dict) -> None:
        d["nodes"].append({
            "id": "a1", "type": "argument", "text": "An argument.", "status": "proposed",
            "conclusion": "t1", "inference": "induction",
            "premises": [{"n": 1, "text": "A premise."}]})
        _node(d, "o1")["premise-ref"] = {"argument": "a1", "n": 1}

    assert "T038" in _codes(_mutated(mutate))


def test_duplicate_objections_warn_and_retired_ones_do_not() -> None:
    def twin(d: dict, status: str = "proposed") -> None:
        copy_of = copy.deepcopy(_node(d, "o1"))
        copy_of.update(id="o2", status=status)
        d["nodes"].append(copy_of)

    data = _mutated(twin)
    assert _codes(data) == set() and _codes(data, "warning") == {"T037"}
    assert _diagnostics(_mutated(lambda d: twin(d, "retired"))).items == []


def test_different_kinds_on_one_target_are_not_duplicates() -> None:
    def mutate(d: dict) -> None:
        other = copy.deepcopy(_node(d, "o1"))
        other.update(id="o2", kind="scope")
        other.pop("counterexample")
        d["nodes"].append(other)

    assert _diagnostics(_mutated(mutate)).items == []


def test_malformed_values_do_not_crash_the_linter() -> None:
    bad = [{"strongest-form": "s1"}, {"counterexample": ["x"]}, {"strongest-form": {"source": 3}},
           {"target": ["t1"]}, {"premise-ref": {"argument": "o1", "n": 1}}]
    for patch in bad:
        data = _mutated(lambda d, p=patch: _node(d, "o1").update(p))
        assert _codes(data), patch
    assert "T034" in _codes(_mutated(lambda d: _node(d, "d1").update(answers=["o1"])))


# ---------------------------------------------------------------------- gaps


def test_an_unanswered_fatal_objection_is_listed_first() -> None:
    def mutate(d: dict) -> None:
        _node(d, "o1")["severity"] = "fatal"
        d["nodes"].remove(_node(d, "d1"))
        d["edges"].pop()
        d["nodes"].append({"id": "o0", "type": "objection", "text": "A minor one.",
                           "status": "proposed"})

    found = _gaps(_mutated(mutate))
    assert found[0] == ("objection-fatal-undefended", "o1")
    assert ("objection-undefended", "o0") in found
    assert ("objection-undefended", "o1") not in found


def test_a_defense_with_answers_closes_the_objection_gap_without_an_edge() -> None:
    assert ("objection-undefended", "o1") not in _gaps(VALID)
    assert ("objection-fatal-undefended", "o1") not in _gaps(
        _mutated(lambda d: _node(d, "o1").update(severity="fatal")))


def test_a_retired_defense_does_not_answer() -> None:
    data = _mutated(lambda d: _node(d, "d1").update(status="retired"))
    assert ("objection-undefended", "o1") in _gaps(data)


def test_defense_gaps_only_fire_for_defenses_that_use_the_new_fields() -> None:
    def mutate(d: dict) -> None:
        _node(d, "d1").pop("answers")
        _node(d, "d1").pop("anchor")

    found = _gaps(_mutated(mutate))
    assert ("defense-no-answers", "d1") in found
    assert ("defense-no-anchor", "d1") in found


def test_a_defense_with_an_anchor_has_no_anchor_gap() -> None:
    assert ("defense-no-anchor", "d1") not in _gaps(VALID)


def test_rival_gap_is_opt_in_per_thesis() -> None:
    def no_rival(d: dict) -> None:
        _node(d, "o1")["tradition"] = "internal"

    assert ("thesis-no-rival", "t1") in _gaps(_mutated(no_rival))
    assert ("thesis-no-rival", "t1") not in _gaps(VALID)
    opted_out = _mutated(lambda d: [no_rival(d), _node(d, "t1").pop("needs-rival-objection")])
    assert ("thesis-no-rival", "t1") not in _gaps(opted_out)


def test_rival_gap_ignores_retired_objections_and_unaccepted_theses() -> None:
    retired = _mutated(lambda d: _node(d, "o1").update(status="retired"))
    assert ("thesis-no-rival", "t1") in _gaps(retired)

    def proposed(d: dict) -> None:
        _node(d, "t1").update(status="proposed")
        _node(d, "t1").pop("accepted-by")
        _node(d, "o1")["tradition"] = "internal"

    assert ("thesis-no-rival", "t1") not in _gaps(_mutated(proposed))


def test_rival_objection_linked_by_an_attacks_edge_counts() -> None:
    def mutate(d: dict) -> None:
        _node(d, "o1").pop("target")
        _node(d, "o1")["tradition"] = "rival"

    assert ("thesis-no-rival", "t1") not in _gaps(_mutated(mutate))


# ----------------------------------------------------------- rendered project


def test_lint_resolves_bib_keys_against_the_papers_refs(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    keys = [k for k in (project / "paper" / "refs.bib").read_text().split("@")[1:]]
    first = keys[0].split("{", 1)[1].split(",", 1)[0].strip()

    def with_source(source: str) -> dict:
        def mutate(d: dict) -> None:
            _node(d, "o1")["strongest-form"]["source"] = source
            _node(d, "d1").pop("anchor")  # the rendered paper has no such label

        return _mutated(mutate)

    def lint(source: str):
        (project / "theses.yaml").write_text(yaml.safe_dump(with_source(source), sort_keys=False))
        result = run(project, "python3", "-m", "scripts.article", "theses", "lint", "--json")
        return result, json.loads(result.stdout)["diagnostics"]

    result, found = lint(first)
    assert result.returncode == 0, found
    result, found = lint("no-such-key-2099")
    assert result.returncode == 1
    assert any(i["code"] == "T032" for i in found)


def test_gaps_cli_lists_the_fatal_objection_first(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)

    def mutate(d: dict) -> None:
        _node(d, "o1")["severity"] = "fatal"
        d["nodes"].remove(_node(d, "d1"))
        d["edges"].pop()
        _node(d, "t1").pop("needs-rival-objection")

    (project / "theses.yaml").write_text(yaml.safe_dump(_mutated(mutate), sort_keys=False))
    result = run(project, "python3", "-m", "scripts.article", "theses", "gaps")
    gaps = json.loads(result.stdout)["gaps"]
    assert result.returncode == 1
    assert gaps[0] == {"kind": "objection-fatal-undefended", "id": "o1",
                       "text": "A rival counterexample."}
