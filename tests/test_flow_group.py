"""Orders whose write anchors share a file form one group; shared reads do not."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from conftest import ROOT
from flow_helpers import jcli, set_state, write_map

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
ORDER_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-order.schema.json").read_text())
FLOW_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow.schema.json").read_text())
GROUP_SCHEMA = {"definitions": ORDER_SCHEMA["definitions"], "$ref": "#/definitions/group"}


def _map(texts: dict[str, str]) -> str:
    lines = ["version: 1", "nodes:"]
    for node_id, text in texts.items():
        lines += [
            f"  - id: {node_id}",
            "    type: thesis",
            f"    text: {text}",
            "    status: accepted",
            "    accepted-by: Ada",
        ]
    return "\n".join(lines + ["edges: []", ""])


def _setup(project: Path, texts: dict[str, str]) -> None:
    (project / "paper" / "sections").mkdir(parents=True, exist_ok=True)
    (project / "paper" / "sections" / "a.tex").write_text("one\ntwo\nthree\nfour\n")
    write_map(project, _map(texts))


WRITE = "Claim about `theses.yaml:1-3`."
READ = "Claim about `paper/sections/a.tex:1-3`."
PLAIN = "Claim."


def test_two_orders_writing_the_same_file_are_one_group(flow_project: Path) -> None:
    _setup(flow_project, {"t1": WRITE, "t2": WRITE})
    payload = jcli(flow_project, "flow", "next", "--open", "--brief")
    assert len(payload["groups"]) == 1
    group = payload["groups"][0]
    jsonschema.validate(group, GROUP_SCHEMA)
    assert group["files"] == ["theses.yaml"]
    assert len(group["orders"]) == 2
    assert [o["id"] for o in payload["orders"]] == group["orders"]
    for order in payload["orders"]:
        jsonschema.validate(order, ORDER_SCHEMA)
        assert order["group"] == group["id"]
        assert order["parallel_safe"] is False
        assert "brief" not in order
        assert order["anchors"][0]["mode"] == "write"
    assert group["brief"]["order"] == group["id"]
    assert group["max_calls"] == sum(o["max_calls"] for o in payload["orders"])
    assert "deferred" not in payload


def test_next_returns_the_group_with_its_members(flow_project: Path) -> None:
    _setup(flow_project, {"t1": WRITE, "t2": WRITE, "t3": PLAIN})
    payload = jcli(flow_project, "flow", "next", "--brief")
    jsonschema.validate(payload["group"], GROUP_SCHEMA)
    assert payload["order"]["id"] == payload["group"]["orders"][0]
    assert [o["nodes"] for o in payload["orders"]] == [["t1"], ["t2"]]
    assert payload["order"]["group"] == payload["group"]["id"]


def test_disjoint_orders_stay_parallel(flow_project: Path) -> None:
    _setup(flow_project, {"t1": PLAIN, "t2": PLAIN})
    payload = jcli(flow_project, "flow", "next", "--open")
    assert "groups" not in payload
    assert [o["parallel_safe"] for o in payload["orders"]] == [True, True]
    assert all("group" not in o for o in payload["orders"])
    assert "group" not in jcli(flow_project, "flow", "next")


def test_shared_read_anchor_does_not_group(flow_project: Path) -> None:
    _setup(flow_project, {"t1": READ, "t2": READ})
    payload = jcli(flow_project, "flow", "next", "--open")
    assert "groups" not in payload
    for order in payload["orders"]:
        assert order["anchors"][0]["mode"] == "read"
        assert order["parallel_safe"] is True


def test_oversize_group_is_split_and_the_rest_offered_later(flow_project: Path) -> None:
    _setup(flow_project, {f"t{i}": WRITE for i in range(1, 6)})
    first = jcli(flow_project, "flow", "next", "--open")
    assert len(first["groups"][0]["orders"]) == 3  # default size
    assert len(first["orders"]) == 3
    assert len(first["deferred"]) == 2
    issued = (flow_project / "flow.yaml").read_text()
    for order_id in first["deferred"]:
        assert order_id not in issued  # a deferred order is not issued
    set_state(flow_project, group_size=2)
    smaller = jcli(flow_project, "flow", "next", "--open")
    assert len(smaller["groups"][0]["orders"]) == 2 and len(smaller["deferred"]) == 3
    # a closed first group leaves the remainder to be offered
    set_state(flow_project, group_size=1)
    off = jcli(flow_project, "flow", "next", "--open")
    assert "groups" not in off and "deferred" not in off and len(off["orders"]) == 5


def test_output_is_byte_identical_for_the_same_state(flow_project: Path) -> None:
    _setup(flow_project, {"t1": WRITE, "t2": WRITE})
    args = ("flow", "next", "--open", "--brief")
    a = jcli(flow_project, *args)
    b = jcli(flow_project, *args)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a == b


def test_group_size_is_validated(flow_project: Path) -> None:
    from flow_helpers import cli

    jsonschema.validate({"group_size": 2}, {**FLOW_SCHEMA, "required": []})
    set_state(flow_project, group_size=0)
    assert cli(flow_project, "flow", "status").returncode != 0
