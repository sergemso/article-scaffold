"""Contradictions and typed moves in the theses map (decision 0083): schema and structural lint."""

from __future__ import annotations

import copy
import json
import sys

import jsonschema
import pytest
import yaml
from conftest import ROOT, render, run

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SCHEMA = json.loads((TEMPLATE / "schemas" / "theses.schema.json").read_text())
PRINCIPLES = json.loads((TEMPLATE / "schemas" / "triz-principles.json").read_text())


def _modules():
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import dialectic, theses
    finally:
        sys.path.remove(str(TEMPLATE))
    return theses, dialectic


theses, dialectic = _modules()

PLAIN = {
    "version": 1,
    "nodes": [
        {"id": "t1", "type": "thesis", "text": "Main claim.", "status": "accepted",
         "accepted-by": "Ada Lovelace", "anchor": None},
        {"id": "o1", "type": "objection", "text": "An objection.", "status": "proposed"},
        {"id": "s1", "type": "source-claim", "text": "Smith says X.", "status": "proposed",
         "quote": "X holds", "locator": "p. 3", "bib_keys": ["smith2020"]},
        {"id": "s2", "type": "source-claim", "text": "Jones says not X.", "status": "proposed",
         "quote": "X fails", "locator": "p. 9"},
        {"id": "q1", "type": "hypothesis", "text": "Does X hold at scale?", "status": "proposed"},
    ],
    "edges": [{"from": "o1", "to": "t1", "type": "attacks"}],
}

VALID = copy.deepcopy(PLAIN)
VALID["contradictions"] = [
    {"id": "c1", "text": "X holds and X fails.", "kind": "dialectical", "status": "proposed",
     "author": "agent",
     "poles": [{"text": "X holds", "claim": "s1"}, {"text": "X fails", "claim": "s2"}]},
    {"id": "c2", "kind": "technical", "status": "accepted", "author": "human",
     "accepted-by": "Ada Lovelace",
     "poles": [{"text": "Strong evidence", "niche": "Studies are small and rigorous"},
               {"text": "Broad reach", "claim": "s2"}],
     "improving": "rigour", "worsening": "coverage", "principle": "segmentation",
     "ideal-result": "Rigour without losing coverage.", "resources": ["open datasets"]},
    {"id": "c3", "kind": "physical", "status": "proposed", "author": "agent",
     "poles": [{"text": "Be open", "niche": "Data should be shared"},
               {"text": "Be closed", "niche": "Data should be private"}],
     "principle": "dynamics"},
]
VALID["moves"] = [
    {"id": "m1", "type": "negation", "text": "Deny the shared premise.", "status": "proposed",
     "author": "agent", "cites": ["c1"]},
    {"id": "m2", "type": "negation-of-negation", "text": "Deny the denial.",
     "status": "proposed", "author": "agent", "cites": ["m1"]},
    {"id": "m3", "type": "synthesis", "text": "Scope X by scale.", "status": "proposed",
     "author": "agent", "cites": ["c1", "c2"]},
    {"id": "m4", "type": "aufhebung", "text": "Keep rigour, drop the universality.",
     "status": "proposed", "author": "agent", "cites": ["m2", "m3"],
     "preserved": "the evidence", "cancelled": "the universal claim", "lifted": "a scoped claim"},
    {"id": "m5", "type": "opening", "text": "Ask about scale.", "status": "proposed",
     "author": "agent", "cites": ["m4"], "opens": "q1"},
]


def _mutated(mutate, base=VALID) -> dict:
    data = copy.deepcopy(base)
    mutate(data)
    return data


def _diagnostics(data: dict):
    found = theses.Diagnostics()
    theses.validate_map(data, None, found)
    return found


def _codes(data: dict, severity: str = "error") -> set[str]:
    return {d.code for d in _diagnostics(data).items if d.severity == severity}


def _contradiction(d: dict, which: str = "c1") -> dict:
    return next(c for c in d["contradictions"] if c["id"] == which)


def _move(d: dict, which: str) -> dict:
    return next(m for m in d["moves"] if m["id"] == which)


# ---------------------------------------------------------------- compatibility


def test_valid_fixture_matches_schema_and_lints_clean() -> None:
    jsonschema.validate(VALID, SCHEMA)
    assert _diagnostics(VALID).items == []


def test_a_version_1_map_without_the_sections_validates_unchanged() -> None:
    jsonschema.validate(PLAIN, SCHEMA)
    assert _diagnostics(PLAIN).items == []
    assert not dialectic.uses_section(PLAIN)
    assert theses.development(PLAIN) == []


def test_the_shipped_template_map_still_validates() -> None:
    data = yaml.safe_load((TEMPLATE / "theses.yaml").read_text())
    jsonschema.validate(data, SCHEMA)
    assert _diagnostics(data).items == []


def test_empty_sections_are_fine() -> None:
    data = _mutated(lambda d: d.update(contradictions=[], moves=[]), PLAIN)
    jsonschema.validate(data, SCHEMA)
    assert _diagnostics(data).items == []
    assert not dialectic.uses_section(data)


def test_uses_section() -> None:
    assert dialectic.uses_section(VALID)
    assert dialectic.uses_section(_mutated(lambda d: d.pop("moves")))
    assert not dialectic.uses_section("nope")


# ---------------------------------------------------------------- principle list


def test_principle_list_is_the_closed_forty() -> None:
    items = PRINCIPLES["principles"]
    assert [p["number"] for p in items] == list(range(1, 41))
    tags = [p["id"] for p in items]
    assert len(set(tags)) == 40
    assert all(p["name"] and p["id"] == p["id"].lower() for p in items)


def test_schema_enum_matches_the_shipped_list() -> None:
    enum = SCHEMA["definitions"]["contradiction"]["properties"]["principle"]["enum"]
    assert enum == [p["id"] for p in PRINCIPLES["principles"]]
    assert list(dialectic.principles()) == enum


def test_every_principle_tag_is_accepted() -> None:
    for tag in dialectic.principles():
        data = _mutated(lambda d, tag=tag: _contradiction(d, "c3").update(principle=tag))
        assert _diagnostics(data).items == []


# ---------------------------------------------------------------- schema failures

SCHEMA_FAILURES = {
    "contradiction without poles": lambda d: _contradiction(d).pop("poles"),
    "one pole": lambda d: _contradiction(d)["poles"].pop(),
    "three poles": lambda d: _contradiction(d)["poles"].append({"text": "z", "niche": "z"}),
    "pole without text": lambda d: _contradiction(d)["poles"][0].pop("text"),
    "pole without anchor": lambda d: _contradiction(d)["poles"][0].pop("claim"),
    "pole with both anchors": lambda d: _contradiction(d)["poles"][0].update(niche="x"),
    "unknown pole field": lambda d: _contradiction(d)["poles"][0].update(weight=1),
    "bad kind": lambda d: _contradiction(d).update(kind="logical"),
    "contradiction without kind": lambda d: _contradiction(d).pop("kind"),
    "contradiction without author": lambda d: _contradiction(d).pop("author"),
    "bad status": lambda d: _contradiction(d).update(status="done"),
    "accepted without accepted-by": lambda d: _contradiction(d, "c2").pop("accepted-by"),
    "technical without improving": lambda d: _contradiction(d, "c2").pop("improving"),
    "technical without worsening": lambda d: _contradiction(d, "c2").pop("worsening"),
    "improving on a dialectical": lambda d: _contradiction(d).update(improving="x"),
    "worsening on a physical": lambda d: _contradiction(d, "c3").update(worsening="x"),
    "principle on a dialectical": lambda d: _contradiction(d).update(principle="dynamics"),
    "unknown principle": lambda d: _contradiction(d, "c2").update(principle="magic"),
    "unknown contradiction field": lambda d: _contradiction(d).update(extra=1),
    "multi-line improving": lambda d: _contradiction(d, "c2").update(improving="a\nb"),
    "bad move type": lambda d: _move(d, "m1").update(type="sublation"),
    "move without type": lambda d: _move(d, "m1").pop("type"),
    "move without author": lambda d: _move(d, "m1").pop("author"),
    "negation without cites": lambda d: _move(d, "m1").pop("cites"),
    "empty cites": lambda d: _move(d, "m1").update(cites=[]),
    "synthesis with one cite": lambda d: _move(d, "m3").update(cites=["c1"]),
    "aufhebung with one cite": lambda d: _move(d, "m4").update(cites=["m3"]),
    "aufhebung without preserved": lambda d: _move(d, "m4").pop("preserved"),
    "aufhebung without cancelled": lambda d: _move(d, "m4").pop("cancelled"),
    "aufhebung without lifted": lambda d: _move(d, "m4").pop("lifted"),
    "preserved on a synthesis": lambda d: _move(d, "m3").update(preserved="x"),
    "opening without opens": lambda d: _move(d, "m5").pop("opens"),
    "opens on a negation": lambda d: _move(d, "m1").update(opens="q1"),
    "unknown move field": lambda d: _move(d, "m1").update(extra=1),
    "accepted move without accepted-by": lambda d: _move(d, "m1").update(status="accepted"),
    "moves not a list": lambda d: d.update(moves={}),
    "contradictions not a list": lambda d: d.update(contradictions="x"),
}


@pytest.mark.parametrize("name", sorted(SCHEMA_FAILURES))
def test_schema_rejects(name: str) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_mutated(SCHEMA_FAILURES[name]), SCHEMA)


@pytest.mark.parametrize("name", sorted(SCHEMA_FAILURES))
def test_lint_also_rejects_what_the_schema_rejects(name: str) -> None:
    assert _codes(_mutated(SCHEMA_FAILURES[name]))


# ---------------------------------------------------------------- lint codes: contradictions

LINT_ERRORS = {
    "T070": lambda d: _contradiction(d).update(id=""),
    "T071": lambda d: _contradiction(d, "c3").update(id="c1"),
    "T072": lambda d: _contradiction(d).update(status="done"),
    "T073": lambda d: _contradiction(d).update(kind="logical"),
    "T074": lambda d: _contradiction(d, "c2").pop("improving"),
    "T075": lambda d: _contradiction(d).update(improving="x"),
    "T076": lambda d: _contradiction(d).update(principle="dynamics"),
    "T077": lambda d: _contradiction(d, "c2").update(principle="magic"),
    "T078": lambda d: _contradiction(d, "c2").update(resources="open data"),
    "T079": lambda d: _contradiction(d)["poles"].pop(),
    "T080": lambda d: _contradiction(d)["poles"][0].update(text=""),
    "T081": lambda d: _contradiction(d)["poles"][0].update(niche="x"),
    "T082": lambda d: _contradiction(d)["poles"][0].update(claim="o1"),
    "T083": lambda d: _move(d, "m1").update(type="sublation"),
    "T084": lambda d: _move(d, "m1").pop("cites"),
    "T085": lambda d: _move(d, "m3").update(cites=["c1"]),
    "T086": lambda d: _move(d, "m2").update(cites=["c1"]),
    "T087": lambda d: _move(d, "m4").pop("lifted"),
    "T088": lambda d: _move(d, "m1").update(cancelled="x"),
    "T089": lambda d: _move(d, "m5").pop("opens"),
    "T090": lambda d: _move(d, "m5").update(opens="o1"),
    "T091": lambda d: _move(d, "m1").update(opens="q1"),
    "T092": lambda d: _move(d, "m3").update(cites=["c1", "c1"]),
    "T093": lambda d: _move(d, "m1").update(cites=["nope"]),
    "T094": lambda d: _move(d, "m1").update(cites=["m5"]),
    "T095": lambda d: _move(d, "m4").update(lifted="The evidence"),
    "T002": lambda d: d.update(extra=[]),
    "T012": lambda d: _contradiction(d, "c2").pop("accepted-by"),
    "T013": lambda d: _contradiction(d, "c2").update({"accepted-by": "assistant"}),
}


@pytest.mark.parametrize("code", sorted(LINT_ERRORS))
def test_lint_reports(code: str) -> None:
    assert code in _codes(_mutated(LINT_ERRORS[code]))


def test_node_and_item_ids_share_one_namespace() -> None:
    data = _mutated(lambda d: _move(d, "m1").update(id="t1"))
    assert "T071" in _codes(data)


def test_a_contradiction_id_cannot_repeat_in_moves() -> None:
    data = _mutated(lambda d: _move(d, "m1").update(id="c1"))
    assert "T071" in _codes(data)


def test_pole_claim_must_exist() -> None:
    data = _mutated(lambda d: _contradiction(d)["poles"][0].update(claim="ghost"))
    assert "T082" in _codes(data)


def test_niche_pole_is_a_valid_anchor() -> None:
    assert _diagnostics(VALID).items == []
    assert _contradiction(VALID, "c3")["poles"][0].get("niche")


def test_a_physical_contradiction_may_carry_a_principle() -> None:
    assert _contradiction(VALID, "c3")["principle"] == "dynamics"
    assert _diagnostics(VALID).items == []


def test_a_retired_accepted_status_is_not_an_agent_error() -> None:
    data = _mutated(lambda d: _contradiction(d, "c1").update(status="retired"))
    assert _codes(data) == set()


def test_non_mapping_entries_are_reported_not_raised() -> None:
    data = _mutated(lambda d: (d["contradictions"].append("x"), d["moves"].append(3)))
    assert "T001" in _codes(data)


def test_sections_that_are_not_lists_are_reported() -> None:
    assert "T001" in _codes(_mutated(lambda d: d.update(moves={})))
    assert "T001" in _codes(_mutated(lambda d: d.update(contradictions="x")))


# --------------------------------------------- a valid and an invalid fixture per move type

MOVE_VALID = {
    "negation": {"id": "mv", "type": "negation", "text": "Deny it.", "status": "proposed",
                 "author": "agent", "cites": ["c1"]},
    "negation-of-negation": {"id": "mv", "type": "negation-of-negation", "text": "Deny the denial.",
                             "status": "proposed", "author": "agent", "cites": ["m1"]},
    "synthesis": {"id": "mv", "type": "synthesis", "text": "Join them.", "status": "proposed",
                  "author": "agent", "cites": ["c1", "c2"]},
    "aufhebung": {"id": "mv", "type": "aufhebung", "text": "Lift them.", "status": "proposed",
                  "author": "agent", "cites": ["c1", "m1"], "preserved": "p",
                  "cancelled": "c", "lifted": "l"},
    "opening": {"id": "mv", "type": "opening", "text": "Begin again.",
                      "status": "proposed", "author": "agent", "opens": "t1"},
}
MOVE_INVALID = {
    "negation": ({"cites": ["ghost"]}, "T093"),
    "negation-of-negation": ({"cites": ["c1"]}, "T086"),
    "synthesis": ({"cites": ["c1"]}, "T085"),
    "aufhebung": ({"lifted": ""}, "T087"),
    "opening": ({"opens": "o1"}, "T090"),
}


def _with_move(move: dict) -> dict:
    return _mutated(lambda d: d["moves"].append(move))


def test_every_move_type_is_covered() -> None:
    assert set(MOVE_VALID) == set(MOVE_INVALID) == set(dialectic.MOVE_TYPES)
    assert set(SCHEMA["definitions"]["move"]["properties"]["type"]["enum"]) == set(MOVE_VALID)


@pytest.mark.parametrize("kind", sorted(MOVE_VALID))
def test_valid_move_fixture(kind: str) -> None:
    data = _with_move(MOVE_VALID[kind])
    jsonschema.validate(data, SCHEMA)
    assert _diagnostics(data).items == []


@pytest.mark.parametrize("kind", sorted(MOVE_INVALID))
def test_invalid_move_fixture(kind: str) -> None:
    patch, code = MOVE_INVALID[kind]
    data = _with_move({**MOVE_VALID[kind], **patch})
    assert code in _codes(data)


def test_negation_of_negation_may_cite_a_negation_among_others() -> None:
    data = _with_move({**MOVE_VALID["negation-of-negation"], "cites": ["c2", "m1"]})
    assert _diagnostics(data).items == []


def test_synthesis_may_cite_moves() -> None:
    data = _with_move({**MOVE_VALID["synthesis"], "cites": ["m1", "m3"]})
    assert _diagnostics(data).items == []


def test_opening_may_open_a_thesis_or_a_hypothesis() -> None:
    for target in ("t1", "q1"):
        data = _with_move({**MOVE_VALID["opening"], "opens": target})
        assert _diagnostics(data).items == []


def test_opening_cannot_open_a_missing_node() -> None:
    data = _with_move({**MOVE_VALID["opening"], "opens": "ghost"})
    assert "T090" in _codes(data)


@pytest.mark.parametrize("field", ["preserved", "cancelled", "lifted"])
def test_aufhebung_needs_each_of_its_three_fields(field: str) -> None:
    move = {k: v for k, v in MOVE_VALID["aufhebung"].items() if k != field}
    assert "T087" in _codes(_with_move(move))


# ---------------------------------------------------------------- T095 trivial aufhebung


def test_lifted_may_not_repeat_cancelled() -> None:
    data = _mutated(lambda d: _move(d, "m4").update(lifted="the universal claim!"))
    assert "T095" in _codes(data)


def test_lifted_may_not_repeat_a_pole_of_a_cited_contradiction() -> None:
    aufhebung = {**MOVE_VALID["aufhebung"], "cites": ["c1", "c2"], "lifted": "X holds."}
    assert "T095" in _codes(_with_move(aufhebung))


def test_lifted_may_repeat_a_pole_of_a_contradiction_it_does_not_cite() -> None:
    aufhebung = {**MOVE_VALID["aufhebung"], "cites": ["c2", "m1"], "lifted": "Be open"}
    assert "T095" not in _codes(_with_move(aufhebung))


def test_a_lifted_that_says_something_new_passes() -> None:
    assert "T095" not in _codes(VALID)


# ---------------------------------------------------------------- cycles


def test_self_citation_is_a_cycle() -> None:
    data = _mutated(lambda d: _move(d, "m1").update(cites=["m1"]))
    assert "T094" in _codes(data)


def test_two_move_cycle_is_reported_once() -> None:
    def mutate(d: dict) -> None:
        d["moves"] = [
            {"id": "a", "type": "negation", "text": "a", "status": "proposed", "author": "agent",
             "cites": ["b"]},
            {"id": "b", "type": "negation", "text": "b", "status": "proposed", "author": "agent",
             "cites": ["a"]},
        ]

    found = [d for d in _diagnostics(_mutated(mutate)).items if d.code == "T094"]
    assert len(found) == 1
    assert "a -> b -> a" in found[0].message


def test_long_cycle_is_reported() -> None:
    data = _mutated(lambda d: _move(d, "m1").update(cites=["m5"]))
    assert "T094" in _codes(data)


def test_a_dag_with_a_shared_cite_is_not_a_cycle() -> None:
    assert "T094" not in _codes(VALID)


def test_citing_a_contradiction_is_not_a_cycle() -> None:
    assert "T094" not in _codes(_mutated(lambda d: _move(d, "m1").update(cites=["c1", "c2"])))


# ---------------------------------------------------------------- development chain


def test_development_is_the_chain_in_order() -> None:
    chain = theses.development(VALID)
    assert [m["id"] for m in chain] == ["m1", "m2", "m3", "m4", "m5"]
    assert chain[4]["opens"] == "q1" and chain[0]["opens"] is None
    assert chain[3]["type"] == "aufhebung" and chain[3]["cites"] == ["m2", "m3"]


def test_development_orders_cited_moves_first_and_keeps_file_order_on_ties() -> None:
    data = _mutated(lambda d: d["moves"].reverse())
    chain = [m["id"] for m in theses.development(data)]
    for later, earlier in (("m2", "m1"), ("m4", "m2"), ("m4", "m3"), ("m5", "m4")):
        assert chain.index(earlier) < chain.index(later)
    assert chain == ["m3", "m1", "m2", "m4", "m5"]


def test_development_is_deterministic_and_not_stored() -> None:
    assert theses.development(VALID) == theses.development(copy.deepcopy(VALID))
    assert "development" not in SCHEMA["properties"]
    assert "development" in _codes_for_extra()


def _codes_for_extra() -> set[str]:
    data = _mutated(lambda d: d.update(development=[]))
    return {d.message.split("'")[1] for d in _diagnostics(data).items if d.code == "T002"}


def test_development_leaves_out_moves_in_a_cycle() -> None:
    data = _mutated(lambda d: _move(d, "m1").update(cites=["m2"]))
    ids = [m["id"] for m in theses.development(data)]
    assert "m1" not in ids and "m2" not in ids


def test_development_ignores_dangling_and_malformed_entries() -> None:
    entry = {"id": "x", "type": "negation", "cites": ["ghost"]}
    data = {"moves": [entry, "junk", {"type": "negation"}]}
    assert [m["id"] for m in theses.development(data)] == ["x"]


# ---------------------------------------------------------------- shipped files

def test_new_code_is_host_neutral_and_offline() -> None:
    text = (TEMPLATE / "scripts" / "article" / "dialectic.py").read_text().lower()
    for word in ("go-getter", "claude", "anthropic", "openai", "http", "urllib", "socket"):
        assert word not in text
    assert "go-getter" not in (TEMPLATE / "schemas" / "triz-principles.json").read_text().lower()


def test_rendered_project_validates_a_dialectic_map(tmp_path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "theses.yaml").write_text(yaml.safe_dump(VALID, sort_keys=False))
    result = run(project, "python3", "scripts/validate-paper.py")
    assert "T0" not in result.stdout + result.stderr


def test_rendered_project_rejects_a_broken_dialectic_map(tmp_path) -> None:
    project = render(tmp_path=tmp_path)
    broken = _mutated(lambda d: _move(d, "m1").update(cites=["m1"]))
    (project / "theses.yaml").write_text(yaml.safe_dump(broken, sort_keys=False))
    result = run(project, "python3", "scripts/validate-paper.py")
    assert "T094" in result.stdout + result.stderr


# ------------------------------------------------------------------ edge cases

EDGE_CODES = {
    "multi-line contradiction text": ("T007", lambda d: _contradiction(d).update(text="a\nb")),
    "multi-line move text": ("T007", lambda d: _move(d, "m1").update(text="a\nb")),
    "blank ideal-result": ("T007", lambda d: _contradiction(d, "c2").update({"ideal-result": " "})),
    "agent named on an accepted move": (
        "T013", lambda d: _move(d, "m1").update(status="accepted", **{"accepted-by": "claude"})
    ),
    "accepted move without accepted-by": (
        "T012", lambda d: _move(d, "m1").update(status="accepted")
    ),
    "cites not a list": ("T092", lambda d: _move(d, "m1").update(cites="c1")),
    "cites holds a non-string": ("T092", lambda d: _move(d, "m1").update(cites=[1])),
    "resources with a multi-line item": (
        "T078", lambda d: _contradiction(d, "c2").update(resources=["ok", "a\nb"])
    ),
    "blank niche anchor": (
        "T081", lambda d: _contradiction(d)["poles"][1].update(niche=" ")
    ),
    "pole not a mapping": ("T079", lambda d: _contradiction(d)["poles"].__setitem__(0, "x")),
    "unknown pole field": ("T002", lambda d: _contradiction(d)["poles"][0].update(weight=1)),
    "opening of a source-claim": ("T090", lambda d: _move(d, "m5").update(opens="o1")),
    "move without id": ("T070", lambda d: _move(d, "m1").pop("id")),
}


@pytest.mark.parametrize("name", sorted(EDGE_CODES))
def test_edge_case_is_reported_with_its_code(name: str) -> None:
    code, mutate = EDGE_CODES[name]
    assert code in _codes(_mutated(mutate))


def test_a_move_cannot_reuse_a_contradiction_id() -> None:
    assert "T071" in _codes(_mutated(lambda d: _move(d, "m1").update(id="c1")))


def test_a_human_acceptance_is_not_an_agent_error() -> None:
    data = _mutated(
        lambda d: _move(d, "m1").update(status="accepted", **{"accepted-by": "Sergei Strebulaev"})
    )
    assert _codes(data) == set()


def test_a_bad_move_type_does_not_cascade_into_field_errors() -> None:
    codes = _codes(_mutated(lambda d: _move(d, "m1").update(type="sublation", opens="q1")))
    assert "T083" in codes
    assert not codes & {"T084", "T091"}


def test_principles_are_keyed_by_tag_and_complete() -> None:
    known = dialectic.principles()
    assert len(known) == 40
    assert set(known) == {p["id"] for p in PRINCIPLES["principles"]}


def test_development_of_a_map_without_moves_is_empty() -> None:
    assert dialectic.development(PLAIN) == []
    assert dialectic.development({"moves": None}) == []


def test_every_declared_gap_kind_is_documented_in_the_procedure() -> None:
    text = (TEMPLATE / "docs" / "procedures" / "dialectic.md").read_text()
    for kind in dialectic.GAP_KINDS:
        assert kind in text.replace("`", "")


def test_every_move_type_is_documented_in_the_procedure_and_decision() -> None:
    procedure = (TEMPLATE / "docs" / "procedures" / "dialectic.md").read_text()
    decision = next((ROOT / "docs" / "decisions").glob("0083-*.md")).read_text()
    for kind in dialectic.MOVE_TYPES:
        assert f"`{kind}`" in procedure
        assert f"`{kind}`" in decision


# ------------------------------------------- wrong types are reported, never raised

WRONG_TYPES = {
    "opens as a list": ("T090", lambda d: _move(d, "m5").update(opens=["t1"])),
    "opens as a mapping": ("T090", lambda d: _move(d, "m5").update(opens={"id": "t1"})),
    "claim as a list": ("T082", lambda d: _contradiction(d)["poles"][0].update(claim=["o1"])),
    "claim as a mapping": ("T082", lambda d: _contradiction(d)["poles"][0].update(claim={"a": 1})),
    "principle as a list": ("T077", lambda d: _contradiction(d, "c2").update(principle=["x"])),
    "principle as a mapping": ("T077", lambda d: _contradiction(d, "c2").update(principle={})),
}


@pytest.mark.parametrize("name", sorted(WRONG_TYPES))
def test_a_wrong_typed_field_gets_its_code_and_no_crash(name: str) -> None:
    code, mutate = WRONG_TYPES[name]
    assert code in _codes(_mutated(mutate))
