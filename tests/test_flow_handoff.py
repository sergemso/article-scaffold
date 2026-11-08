"""`flow handoff`: validated, host-neutral, and a resumed brief omits the done anchors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT
from flow_helpers import cli, jcli, write_map

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-handoff.schema.json").read_text())
ORDER_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-order.schema.json").read_text())
RESULT = jsonschema.Draft7Validator(
    {"$ref": "#/definitions/result"}, resolver=jsonschema.RefResolver.from_schema(SCHEMA)
)
KEY = "a" * 64
TEXT = "Claim about `paper/sections/a.tex:1-2` and `paper/sections/a.tex:3-4`."
MAP = (
    "version: 1\nnodes:\n  - id: t1\n    type: thesis\n"
    f"    text: {TEXT}\n    status: accepted\n    accepted-by: Ada\nedges: []\n"
)
A1 = {"name": "paper/sections/a.tex:1-2", "file": "paper/sections/a.tex"}
A2 = {"name": "paper/sections/a.tex:3-4", "file": "paper/sections/a.tex"}


@pytest.fixture
def issued(flow_project: Path) -> tuple[Path, dict]:
    (flow_project / "paper" / "sections").mkdir(parents=True, exist_ok=True)
    (flow_project / "paper" / "sections" / "a.tex").write_text("one\ntwo\nthree\nfour\n")
    write_map(flow_project, MAP)
    return flow_project, jcli(flow_project, "flow", "next", "--brief")["order"]


def _doc(order: str, **changes) -> dict:
    doc = {
        "version": "1.0", "order": order, "done": [A1], "remaining": [A2],
        "files": ["paper/sections/a.tex"], "ledger_keys": [KEY],
        "verify": {"check": "theses-lint", "outcome": "fail"},
    }
    return doc | changes


def _hand(project: Path, order: str, doc: dict):
    path = project / "handoff.json"
    path.write_text(json.dumps(doc))
    return cli(project, "flow", "handoff", order, "--file", str(path))


def test_handoff_is_recorded_and_validates(issued) -> None:
    project, order = issued
    result = _hand(project, order["id"], _doc(order["id"]))
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    RESULT.validate(payload)
    assert payload["remaining"] == 1
    stored = yaml.safe_load((project / "flow.yaml").read_text())["orders"][order["id"]]
    assert stored["handoff"] == payload["handoff"]


def test_resumed_brief_omits_done_anchors_and_is_byte_identical(issued) -> None:
    project, order = issued
    before = [a["name"] for a in order["anchors"]]
    assert A1["name"] in before and A2["name"] in before
    assert _hand(project, order["id"], _doc(order["id"])).returncode == 0
    first = cli(project, "flow", "next", "--brief")
    second = cli(project, "flow", "next", "--brief")
    assert first.stdout == second.stdout
    resumed = json.loads(first.stdout)["order"]
    jsonschema.validate(resumed, ORDER_SCHEMA)
    assert resumed["id"] == order["id"]
    assert [a["name"] for a in resumed["anchors"]] == [A2["name"]]
    assert [a["name"] for a in resumed["brief"]["anchors"]] == [A2["name"]]
    handoffs = resumed["brief"]["handoffs"]
    assert len(handoffs) == 1
    jsonschema.validate(handoffs[0], SCHEMA)
    assert handoffs[0]["remaining"] == [A2]
    plain = jcli(project, "flow", "next")["order"]
    assert [a["name"] for a in plain["anchors"]] == [A2["name"]]


def test_order_without_handoff_is_unchanged(issued) -> None:
    _, order = issued
    assert "handoffs" not in order["brief"]


def test_handoff_is_normalized(issued) -> None:
    project, order = issued
    doc = _doc(order["id"], done=[A2, A1, A1], files=["b", "a", "a"], ledger_keys=["b" * 64, KEY])
    stored = json.loads(_hand(project, order["id"], doc | {"remaining": []}).stdout)["handoff"]
    assert [a["name"] for a in stored["done"]] == [A1["name"], A2["name"]]
    assert stored["files"] == ["a", "b"]
    assert stored["ledger_keys"] == [KEY, "b" * 64]


BAD = {
    "model": lambda o: {"model": "x"},
    "host": lambda o: {"host": "x"},
    "order-mismatch": lambda o: {"order": "o-" + "0" * 12},
    "bad-order": lambda o: {"order": "x"},
    "overlap": lambda o: {"remaining": [A1]},
    "path-escape": lambda o: {"files": ["../x"]},
    "absolute": lambda o: {"files": ["/etc/passwd"]},
    "bad-key": lambda o: {"ledger_keys": ["abc"]},
    "bad-outcome": lambda o: {"verify": {"check": None, "outcome": "error"}},
    "unnamed-check": lambda o: {"verify": {"check": "rm-all", "outcome": "pass"}},
    "bad-anchor": lambda o: {"done": [{"name": "x"}]},
    "version": lambda o: {"version": "2.0"},
    "pasted-paragraph": lambda o: {
        "remaining": [{"name": "The claim says the method wins everywhere.", "file": A2["file"]}]
    },
    "long-name": lambda o: {"remaining": [{"name": "a" * 201, "file": A2["file"]}]},
    "anchor-file-escape": lambda o: {"remaining": [{"name": "x", "file": "../x"}]},
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_invalid_handoff_is_rejected_and_not_stored(issued, case: str) -> None:
    project, order = issued
    doc = _doc(order["id"]) | BAD[case](order)
    result = _hand(project, order["id"], doc)
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False and "invalid handoff" in payload["error"]
    stored = yaml.safe_load((project / "flow.yaml").read_text())["orders"][order["id"]]
    assert "handoff" not in stored


def test_python_validator_agrees_with_the_schema(issued) -> None:
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import handoff
    finally:
        sys.path.remove(str(TEMPLATE))
    _, order = issued
    good = _doc(order["id"])
    assert handoff.errors(good) == []
    jsonschema.validate(good, SCHEMA)
    for case in ("model", "host", "bad-order", "path-escape", "absolute", "bad-key",
                 "bad-outcome", "bad-anchor", "version", "pasted-paragraph",
                 "long-name", "anchor-file-escape"):
        doc = good | BAD[case](order)
        assert handoff.errors(doc), case
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, SCHEMA)


def test_unknown_done_and_unreadable_inputs(issued) -> None:
    project, order = issued
    unknown = _hand(project, "o-" + "0" * 12, _doc("o-" + "0" * 12))
    assert unknown.returncode == 1 and "unknown order" in unknown.stdout
    missing = cli(project, "flow", "handoff", order["id"], "--file", str(project / "nope.json"))
    assert missing.returncode == 1 and "cannot read" in missing.stdout
    (project / "bad.json").write_text("{")
    bad = cli(project, "flow", "handoff", order["id"], "--file", str(project / "bad.json"))
    assert bad.returncode == 1 and "not valid JSON" in bad.stdout


def test_handoff_survives_reissue_and_ends_with_done(issued) -> None:
    project, order = issued
    _hand(project, order["id"], _doc(order["id"]))
    jcli(project, "flow", "next")
    state = yaml.safe_load((project / "flow.yaml").read_text())["orders"][order["id"]]
    assert state["handoff"]["done"] == [A1]
    done = _hand(project, order["id"], _doc(order["id"]))
    assert done.returncode == 0


def test_done_ids_tolerates_a_hand_edited_handoff() -> None:
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import handoff
    finally:
        sys.path.remove(str(TEMPLATE))
    assert handoff.done_ids({"done": [{"name": "x"}, {"file": "f"}, "junk", None]}) == set()
    assert handoff.done_ids({"done": [{"name": "n", "file": "f"}, {"name": "m"}]}) == {("f", "n")}
    assert handoff.done_ids({"done": "oops"}) == set()
    assert handoff.done_ids({}) == set() and handoff.done_ids(None) == set()
