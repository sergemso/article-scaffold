"""Parallel orders are marked only when disjoint; branches editing different nodes merge."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from conftest import ROOT, commit_all, run
from flow_helpers import cli, jcli, write_map

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
ORDER_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-order.schema.json").read_text())

MAP = """\
version: 1
nodes:
  - id: t1
    type: thesis
    text: First claim.
    status: proposed
  - id: t2
    type: thesis
    text: Second claim.
    status: proposed
  - id: t3
    type: thesis
    text: Third claim.
    status: proposed
edges: []
"""


def test_disjoint_orders_are_parallel_safe_and_overlapping_ones_are_not(
    flow_project: Path,
) -> None:
    write_map(flow_project, MAP.replace("proposed", "accepted\n    accepted-by: Ada"))
    payload = jcli(flow_project, "flow", "next", "--open")
    orders = payload["orders"]
    assert [o["nodes"] for o in orders] == [["t1"], ["t2"], ["t3"]]
    for order in orders:
        jsonschema.validate(order, ORDER_SCHEMA)
        assert order["parallel_safe"] is True
        assert order["outputs"] == [f"theses.yaml#{order['nodes'][0]}"]


def test_overlapping_outputs_or_nodes_are_not_safe() -> None:
    import sys

    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import flow
    finally:
        sys.path.remove(str(TEMPLATE))
    make = flow.make_order
    a = make("map", "fill-gap", nodes=["a"], outputs=["theses.yaml#a"], reason="x")
    b = make("map", "fill-gap", nodes=["b"], outputs=["theses.yaml#b"], reason="x")
    c = make("map", "fill-gap", nodes=["a", "c"], outputs=["theses.yaml#c"], reason="x")
    d = make("draft", "write-section", outputs=["paper/"], reason="x")
    e = make("draft", "fix-validation", outputs=["paper/sections/x.tex"], reason="x")
    h = make("frame", "state-thesis", needs_human=True, reason="x")
    flow.mark_parallel([a, b])
    assert a["parallel_safe"] and b["parallel_safe"]
    flow.mark_parallel([a, c])  # share node a
    assert not a["parallel_safe"] and not c["parallel_safe"]
    flow.mark_parallel([d, e])  # a directory output contains the other's file
    assert not d["parallel_safe"] and not e["parallel_safe"]
    flow.mark_parallel([a, h])
    assert a["parallel_safe"] and not h["parallel_safe"]


def test_branches_editing_different_nodes_merge_without_conflict(flow_project: Path) -> None:
    write_map(flow_project, MAP)
    commit_all(flow_project)
    base = run(flow_project, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    for branch, node in (("order-a", "t1"), ("order-b", "t3")):
        run(flow_project, "git", "checkout", "-q", "-b", branch, base, check=True)
        accepted = cli(flow_project, "theses", "accept", node, "--by", "Ada")
        assert accepted.returncode == 0, accepted.stdout
        run(flow_project, "git", "commit", "-qam", f"accept {node}", check=True)
    run(flow_project, "git", "checkout", "-q", "order-a", check=True)
    merged = run(flow_project, "git", "merge", "--no-edit", "order-b")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    text = (flow_project / "theses.yaml").read_text()
    assert text.count("accepted-by") == 2
    ids = [line.split("id:")[1].strip() for line in text.splitlines() if "- id:" in line]
    assert ids == ["t1", "t2", "t3"]  # order is stable
    assert cli(flow_project, "theses", "lint").returncode == 0
