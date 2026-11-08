"""``flow next --brief``: anchors, compiled brief, guardrail rule table, call cap."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import jsonschema
import pytest
from conftest import ROOT
from flow_helpers import cli, jcli, set_state, write_map

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
ORDER_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-order.schema.json").read_text())
FLOW_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow.schema.json").read_text())

SUITE = '''\
"""Conformance suite."""


def unrelated():
    return "UNRELATED-MARKER"


class Suite:
    def run(self):
        return "RUN-BODY-MARKER"

    def other(self):
        return "OTHER-BODY-MARKER"
'''
MAP = """\
version: 1
nodes:
  - id: t1
    type: thesis
    text: The suite `Suite.run` checks the claim.
    status: accepted
    accepted-by: Ada Lovelace
    anchor: sec:intro
edges: []
"""
INTRO = "\\section{Intro}\n\\label{sec:intro}\nIntro opens here.\nSecond line.\n"


@pytest.fixture()
def project(flow_project: Path) -> Path:
    code = flow_project / "paper" / "supplementary"
    code.mkdir(parents=True, exist_ok=True)
    (code / "suite.py").write_text(SUITE)
    (flow_project / "paper" / "sections" / "01_introduction.tex").write_text(INTRO)
    write_map(flow_project, MAP)
    assert cli(flow_project, "index").returncode == 0
    return flow_project


def _flow(project: Path, *args: str) -> dict:
    payload = jcli(project, "flow", "next", *args)
    order = payload["order"]
    jsonschema.validate(order, ORDER_SCHEMA)
    return order


def test_brief_holds_the_anchor_slices_and_no_whole_file(project: Path) -> None:
    order = _flow(project, "--brief")
    assert (order["stage"], order["kind"]) == ("map", "fill-gap")
    brief = order["brief"]
    assert brief["order"] == order["id"]
    assert brief["row"]["source"] == "theses gaps"
    assert {g["kind"] for g in brief["row"]["gaps"]} == {"thesis-unsupported"}
    by_name = {a["name"]: a for a in brief["anchors"]}
    assert set(by_name) == {"Suite.run", "sec:intro"}
    assert "RUN-BODY-MARKER" in by_name["Suite.run"]["text"]
    assert "Intro opens here." in by_name["sec:intro"]["text"]
    text = json.dumps(brief)
    assert "OTHER-BODY-MARKER" not in text and "UNRELATED-MARKER" not in text
    assert brief["verify"] == {
        "check": "theses-lint", "command": "python3 -m scripts.article check record theses-lint",
    }
    assert brief["degraded"] == []


def test_same_repo_state_gives_byte_identical_briefs(project: Path) -> None:
    first = cli(project, "flow", "next", "--brief").stdout
    second = cli(project, "flow", "next", "--brief").stdout
    assert first == second
    brief = json.loads(first)["order"]["brief"]
    assert "T" not in "".join(ch for ch in json.dumps(brief) if ch.isdigit())  # no timestamps
    assert str(project) not in first  # paths are repo-relative


def test_plain_next_has_anchors_without_text_and_no_brief(project: Path) -> None:
    order = _flow(project)
    assert "brief" not in order
    assert {a["name"] for a in order["anchors"]} == {"Suite.run", "sec:intro"}
    assert all("text" not in a and "address" not in a for a in order["anchors"])
    assert "RUN-BODY-MARKER" not in json.dumps(order)
    assert len(json.dumps(order)) < 2000


def test_changed_slice_changes_the_anchor_hash(project: Path) -> None:
    before = {a["name"]: a["hash"] for a in _flow(project)["anchors"]}
    path = project / "paper" / "supplementary" / "suite.py"
    path.write_text(SUITE.replace("RUN-BODY-MARKER", "CHANGED"))
    assert cli(project, "index").returncode == 0
    after = {a["name"]: a["hash"] for a in _flow(project)["anchors"]}
    assert after["Suite.run"] != before["Suite.run"]
    assert after["sec:intro"] == before["sec:intro"]


def test_over_cap_brief_degrades_to_addresses(project: Path) -> None:
    body = "".join(f"        x{i} = {i}\n" for i in range(200))
    path = project / "paper" / "supplementary" / "suite.py"
    marker = '        return "RUN-BODY-MARKER"'
    path.write_text(SUITE.replace(marker, body + marker))
    assert cli(project, "index").returncode == 0
    set_state(project, brief_bytes=1500)
    brief = _flow(project, "--brief")["brief"]
    assert "slices" in brief["degraded"]
    assert all("text" not in a for a in brief["anchors"])
    run = next(a for a in brief["anchors"] if a["name"] == "Suite.run")
    assert run["address"] == f"{run['file']}:{run['lines'][0]}-{run['lines'][1]}@{run['hash']}"
    assert brief["bytes"] <= 1500
    set_state(project, brief_bytes=60000)
    assert _flow(project, "--brief")["brief"]["degraded"] == []


def test_max_calls_comes_from_the_tier_table_and_is_advisory(project: Path) -> None:
    order = _flow(project, "--brief")
    assert order["tier"] == "small" and order["max_calls"] == 40
    assert order["brief"]["max_calls"] == 40
    assert "advisory" in order["brief"]["max_calls_note"]
    set_state(project, max_calls={"small": 7})
    assert _flow(project)["max_calls"] == 7


def test_script_and_human_orders_carry_no_call_cap(flow_project: Path) -> None:
    order = _flow(flow_project)  # frame: a person states the thesis
    assert order["needs_human"] is True and "max_calls" not in order


def test_flow_yaml_fields_are_validated(project: Path) -> None:
    for change in ({"max_calls": {"huge": 3}}, {"max_calls": {"small": 0}}, {"brief_bytes": 10}):
        set_state(project, **change)
        result = cli(project, "flow", "next")
        assert json.loads(result.stdout)["ok"] is False
        set_state(project)  # keep the file; the next change overwrites the key
        for key in change:
            import yaml

            path = project / "flow.yaml"
            data = yaml.safe_load(path.read_text())
            data.pop(key)
            path.write_text(yaml.safe_dump(data, sort_keys=False))
    good = {"max_calls": {"small": 9, "large": 12}, "brief_bytes": 4000}
    set_state(project, **good)
    import yaml

    jsonschema.validate(yaml.safe_load((project / "flow.yaml").read_text()), FLOW_SCHEMA)


def test_old_flow_without_the_new_fields_works(project: Path) -> None:
    import yaml

    data = yaml.safe_load((project / "flow.yaml").read_text())
    assert "max_calls" not in data and "brief_bytes" not in data
    jsonschema.validate(data, FLOW_SCHEMA)
    assert _flow(project)["kind"] == "fill-gap"


def test_ledger_hits_for_the_orders_check_are_in_the_brief(project: Path) -> None:
    assert _flow(project, "--brief")["brief"]["ledger"] == []
    recorded = jcli(project, "check", "record", "theses-lint")
    assert recorded["stored"] is True
    brief = _flow(project, "--brief")["brief"]
    assert [(h["kind"], h["name"], h["status"]) for h in brief["ledger"]] == [
        ("check-outcome", "theses-lint", recorded["verdict"])
    ]


def test_open_orders_accept_brief(project: Path) -> None:
    payload = jcli(project, "flow", "next", "--open", "--brief")
    assert payload["orders"] and all("brief" in o for o in payload["orders"])
    for order in payload["orders"]:
        jsonschema.validate(order, ORDER_SCHEMA)


def test_validation_row_anchors_the_diagnostic_lines(flow_project: Path) -> None:
    clean = (
        "version: 1\nnodes:\n"
        "  - {id: t1, type: thesis, text: T., status: accepted, accepted-by: Ada}\n"
        "  - {id: o1, type: objection, text: O., status: accepted, accepted-by: Ada}\n"
        "  - {id: d1, type: defense, text: D., status: proposed}\n"
        "edges:\n  - {from: d1, to: t1, type: supports}\n"
        "  - {from: o1, to: t1, type: attacks}\n  - {from: d1, to: o1, type: rebuts}\n"
    )
    write_map(flow_project, clean)
    sections = flow_project / "paper" / "sections"
    (sections / "01_introduction.tex").write_text("\\section{Intro}\n\\cite{nobody1999}\n")
    assert cli(flow_project, "index").returncode == 0
    order = _flow(flow_project, "--brief")
    assert order["kind"] == "write-section"
    row = order["brief"]["row"]
    assert row["source"] == "validate" and row["count"] >= 1
    assert row["errors"] and all(not e["path"].startswith("/") for e in row["errors"])


# ------------------------------------------------------------ guardrail rules


def _brief_module():
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import brief
    finally:
        sys.path.remove(str(TEMPLATE))
    return brief


def _issued_kinds() -> set[str]:
    """Every order kind `flow.py` can issue: the second argument of each make_order call."""
    tree = ast.parse((TEMPLATE / "scripts" / "article" / "flow.py").read_text())
    kinds: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "make_order":
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                kinds.add(node.args[1].value)
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:  # ("write-section", "large")
            first, second = node.elts
            if (
                isinstance(first, ast.Constant) and isinstance(second, ast.Constant)
                and second.value == "large" and isinstance(first.value, str)
            ):
                kinds.add(first.value)
    return kinds


def test_rule_table_names_every_kind_flow_issues() -> None:
    brief = _brief_module()
    issued = _issued_kinds() | {"write-section", "fix-validation"}
    assert {"fill-gap", "claim-check", "run-cold", "red-team", "reindex"} <= issued
    assert issued <= set(brief.GUARDRAIL_RULES)
    assert set(brief.GUARDRAIL_RULES) - issued == set()


def test_rule_table_values() -> None:
    brief = _brief_module()
    rules = brief.GUARDRAIL_RULES
    assert set(rules["claim-check"]) == {"sources", "theses-map", "ledger", "retrieval"}
    assert set(rules["red-team"]) == {"theses-map", "agents"}
    assert set(rules["write-section"]) == {"verification"}
    assert set(rules["run-cold"]) == {"release", "orchestration", "ledger"}
    assert brief.DEFAULT_TAGS == ("orchestration",)


def _guardrail(root: Path, name: str, tags: str, line: str, status: str = "active") -> None:
    folder = root / "docs" / "guardrails"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(
        f"---\nid: {name}\ntitle: T {name}\nstatus: {status}\ntags: [{tags}]\n---\n\n"
        f"## Guardrail\n\n{line}\nSecond line.\n"
    )


def test_digest_is_the_first_line_of_each_matching_active_guardrail(tmp_path: Path) -> None:
    brief = _brief_module()
    _guardrail(tmp_path, "b-map", "theses-map, guardrail", "Map rule one.")
    _guardrail(tmp_path, "a-agents", "agents", "Agents rule one.")
    _guardrail(tmp_path, "c-release", "release", "Release rule.")
    _guardrail(tmp_path, "d-old", "theses-map", "Old rule.", status="retired")
    digest = brief.guardrail_digest(tmp_path, "red-team")
    assert digest == [
        {"id": "a-agents", "line": "Agents rule one."},
        {"id": "b-map", "line": "Map rule one."},
    ]
    assert [g["id"] for g in brief.guardrail_digest(tmp_path, "run-cold")] == ["c-release"]
    assert [g["id"] for g in brief.guardrail_digest(tmp_path, "unknown-kind")] == []
    assert brief.guardrail_digest(tmp_path / "none", "red-team") == []


def test_brief_digest_comes_from_the_repo_guardrails(project: Path) -> None:
    _guardrail(project, "map-rule", "theses-map", "Do the map thing.")
    _guardrail(project, "other-rule", "companion", "Not for this order.")
    brief = _flow(project, "--brief")["brief"]
    assert brief["guardrails"] == [{"id": "map-rule", "line": "Do the map thing."}]


def test_order_without_anchors_omits_the_field(flow_project: Path) -> None:
    """Contract in docs/cli.md: `anchors` is omitted when empty (state-thesis names no node)."""
    order = _flow(flow_project)
    assert order["kind"] == "state-thesis"
    assert "anchors" not in order
    assert _flow(flow_project, "--brief")["brief"]["anchors"] == []


def test_brief_bytes_counts_its_own_field_against_the_cap() -> None:
    brief = _brief_module()
    anchors = [{"name": "a", "file": "f.py", "lines": [1, 2], "hash": "h" * 12, "text": "x" * 300}]
    kwargs = dict(
        order={"id": "o1"}, row={"id": "r"}, anchors=anchors, guardrails=[], ledger_hits=[],
        verify=None, max_calls=None, notes=[],
    )  # fmt: skip
    for cap in range(300, 700):
        out = brief.compile_brief(cap=cap, **kwargs)
        printed = len(brief.dump(out).encode("utf-8"))
        assert out["bytes"] == printed  # the figure counts its own field
        if "over-cap" not in out["degraded"]:
            assert printed <= cap
