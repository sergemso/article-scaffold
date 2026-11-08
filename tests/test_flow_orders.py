"""``flow next``: one order per stage kind, idempotent re-issue, small ids-only JSON."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from conftest import ROOT
from flow_helpers import THESIS_MAP, cli, jcli, record_cold_run, set_state, write_map

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
ORDER_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-order.schema.json").read_text())
MAX_ORDER_BYTES = 2000

CLEAN = (
    "version: 1\nnodes:\n"
    "  - {id: t1, type: thesis, text: Main claim., status: accepted, accepted-by: Ada}\n"
    "  - {id: o1, type: objection, text: An objection., status: accepted, accepted-by: Ada}\n"
    "  - {id: d1, type: defense, text: A defense., status: proposed}\n"
    "edges:\n"
    "  - {from: d1, to: t1, type: supports}\n"
    "  - {from: o1, to: t1, type: attacks}\n"
    "  - {from: d1, to: o1, type: rebuts}\n"
)
SOURCED = (
    "version: 1\nnodes:\n"
    "  - {id: t1, type: thesis, text: Main claim., status: accepted, accepted-by: Ada}\n"
    "  - {id: s1, type: source-claim, text: Smith says X., status: proposed,\n"
    "     quote: X holds, locator: p. 3, bib_keys: [smith2020]}\n"
    "edges:\n  - {from: s1, to: t1, type: supports}\n"
)


TWO_SOURCES = SOURCED.replace(
    "edges:",
    "  - {id: s2, type: source-claim, text: Jones says Y., status: proposed,\n"
    "     quote: Y holds, locator: p. 4, bib_keys: [jones2021]}\nedges:",
    1,
) + "  - {from: s2, to: t1, type: supports}\n"


def _order(project: Path) -> dict:
    payload = jcli(project, "flow", "next")
    order = payload["order"]
    assert order is not None, payload
    jsonschema.validate(order, ORDER_SCHEMA)
    assert len(json.dumps(payload)) < MAX_ORDER_BYTES
    return order


def _reach_verify(project: Path, text: str = SOURCED) -> None:
    write_map(project, text)
    assert cli(project, "index").returncode == 0


def test_frame_asks_a_person_to_state_the_thesis(flow_project: Path) -> None:
    order = _order(flow_project)
    assert (order["stage"], order["kind"]) == ("frame", "state-thesis")
    assert order["needs_human"] is True and order["check"] is None


def test_map_stage_fill_gap_points_at_node_and_procedure(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)  # accepted thesis with no support
    order = _order(flow_project)
    assert (order["stage"], order["kind"]) == ("map", "fill-gap")
    assert order["nodes"] == ["t1"]
    assert order["procedure"] == "docs/procedures/blue-team.md"
    assert order["tier"] == "small" and order["check"] == "theses-lint"
    assert (flow_project / order["procedure"]).is_file()
    assert "Main claim" not in json.dumps(order)  # ids only, no node text


def test_discover_stage_find_related(flow_project: Path) -> None:
    write_map(flow_project, SOURCED)
    order = _order(flow_project)
    assert (order["stage"], order["kind"], order["nodes"]) == ("discover", "find-related", ["t1"])


def test_draft_stage_reindex_then_write_section(flow_project: Path) -> None:
    write_map(flow_project, CLEAN)
    order = _order(flow_project)
    assert (order["stage"], order["kind"], order["tier"]) == ("draft", "reindex", "script")
    sections = flow_project / "paper" / "sections"
    (sections / "01_introduction.tex").write_text("\\section{Intro}\n\\cite{nobody1999}\n")
    assert cli(flow_project, "index").returncode == 0
    broken = _order(flow_project)
    assert (broken["stage"], broken["kind"], broken["tier"]) == ("draft", "write-section", "large")


def test_verify_sources_stage_claim_check_and_attest(flow_project: Path) -> None:
    _reach_verify(flow_project, TWO_SOURCES)
    order = _order(flow_project)
    assert (order["stage"], order["kind"]) == ("verify-sources", "attest-claim")  # no local text
    assert order["needs_human"] is True
    sources = flow_project / "paper" / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "smith2020.txt").write_text("It is known that X holds.\n")
    order = _order(flow_project)
    assert (order["kind"], order["tier"], order["nodes"]) == ("claim-check", "small", ["s1"])
    assert order["procedure"] == "docs/procedures/claim-check.md"
    assert order["outputs"] == ["docs/ledger/claim-verdict"]


def test_adversarial_stage_red_team_and_blue_team(flow_project: Path) -> None:
    only_thesis = CLEAN.split("  - {id: o1")[0] + (
        "  - {id: d0, type: defense, text: D., status: proposed}\n"
        "edges:\n  - {from: d0, to: t1, type: supports}\n"
    )
    write_map(flow_project, only_thesis)
    cli(flow_project, "index")
    order = _order(flow_project)
    assert (order["stage"], order["kind"], order["nodes"]) == ("adversarial", "red-team", ["t1"])
    assert order["procedure"] == "docs/procedures/red-team.md"
    # A waiver on the map gate lets an undefended accepted objection reach adversarial.
    undefended = only_thesis.replace(
        "edges:",
        "  - {id: o1, type: objection, text: O., status: accepted, accepted-by: Ada}\nedges:",
    ).replace("edges:\n", "edges:\n  - {from: o1, to: t1, type: attacks}\n")
    write_map(flow_project, undefended)
    set_state(flow_project, waivers=[{
        "stage": "map", "by": "Ada", "at": "2026-01-01", "why": "test", "expires": "2999-01-01",
    }])
    order = _order(flow_project)
    assert (order["kind"], order["nodes"]) == ("blue-team", ["o1"])


def test_revise_stage_fix_validation(flow_project: Path) -> None:
    write_map(flow_project, CLEAN)
    cli(flow_project, "index")
    (flow_project / "scripts" / "lint-counts.py").write_text("raise SystemExit(1)\n")
    order = _order(flow_project)
    assert (order["stage"], order["kind"], order["check"]) == (
        "revise", "fix-validation", "lint-counts",
    )


def test_release_gate_stage_gated_bibliography_then_publish(flow_project: Path) -> None:
    write_map(flow_project, CLEAN)
    cli(flow_project, "index")
    order = _order(flow_project)
    assert (order["stage"], order["kind"]) == ("release-gate", "verify-bibliography")
    assert order["gated"] is True and order["confirm"] == "bibliography"
    set_state(flow_project, attestations=[{
        "name": "bibliography", "by": "Ada", "at": "2026-01-01", "why": "verified",
    }])
    cold = _order(flow_project)
    assert (cold["stage"], cold["kind"]) == ("release-gate", "run-cold")
    assert cold["gated"] is True and cold["confirm"] == "cold-run" and cold["check"] is None
    record_cold_run(flow_project)
    last = _order(flow_project)
    assert (last["stage"], last["kind"], last["needs_human"]) == ("publish", "publish", True)


def test_next_is_idempotent_and_does_not_rewrite_state(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    first = jcli(flow_project, "flow", "next")
    state = (flow_project / "flow.yaml").read_text()
    assert first["order"]["id"] in state  # the issued order is remembered
    second = jcli(flow_project, "flow", "next")
    assert first == second
    assert (flow_project / "flow.yaml").read_text() == state


def test_order_id_is_stable_across_node_order() -> None:
    import importlib.util
    import sys

    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import flow
    finally:
        sys.path.remove(str(TEMPLATE))
    assert flow.order_id("map", "fill-gap", ["b", "a"], None) == flow.order_id(
        "map", "fill-gap", ["a", "b"], None
    )
    assert importlib.util  # keep the import used
