"""``flow done``: named checks only, retry caps, budget, no double count, gated orders."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from conftest import ROOT
from flow_helpers import THESIS_MAP, cli, jcli, set_state, write_map

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SUPPORT = "  - {id: d1, type: defense, text: A defense., status: proposed}\n"
SUPPORTED = THESIS_MAP.replace(
    "edges: []", SUPPORT + "edges:\n  - {from: d1, to: t1, type: supports}"
)


def _state(project: Path) -> dict:
    return yaml.safe_load((project / "flow.yaml").read_text())


def _issue(project: Path) -> dict:
    return jcli(project, "flow", "next")["order"]


def test_check_table_is_fixed_argument_vectors() -> None:
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import flow
    finally:
        sys.path.remove(str(TEMPLATE))
    assert flow.CHECKS
    for name, vector in flow.CHECKS.items():
        assert isinstance(vector, tuple) and all(isinstance(p, str) for p in vector), name
        assert vector[0] in ("article", "python"), name
        argv = flow.argv_for(name)
        assert all(isinstance(p, str) for p in argv) and not any(" " in p for p in argv[1:])


def test_done_takes_only_an_order_id(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    for extra in (["extra"], ["--check", "x"], ["--cmd", "true"]):
        result = cli(flow_project, "flow", "done", order["id"], *extra)
        assert result.returncode == 2, extra
    assert cli(flow_project, "flow", "done").returncode == 2


def test_unknown_check_name_is_refused_and_nothing_runs(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    marker = flow_project / "pwned"
    state = _state(flow_project)
    state["orders"][order["id"]]["check"] = f"touch {marker}"
    (flow_project / "flow.yaml").write_text(yaml.safe_dump(state, sort_keys=False))
    result = cli(flow_project, "flow", "done", order["id"])
    assert result.returncode == 1 and "unknown check" in result.stdout
    assert not marker.exists()
    unknown = cli(flow_project, "flow", "done", "o-000000000000")
    assert unknown.returncode == 1 and "unknown order" in unknown.stdout


def test_pass_records_and_charges_once(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    assert order["kind"] == "fill-gap"
    _issue(flow_project)  # re-issued, still one order, nothing charged
    assert _state(flow_project)["budget"]["used"] == 0
    write_map(flow_project, SUPPORTED)  # the agent did the work, then crashed before `done`
    result = jcli(flow_project, "flow", "done", order["id"])
    assert result["ok"] is True and result["charged"] == 1
    again = jcli(flow_project, "flow", "done", order["id"])
    assert again["ok"] is True and again["charged"] == 0
    state = _state(flow_project)
    assert state["budget"]["used"] == 1
    assert state["orders"][order["id"]]["done"] is True


def test_failed_done_counts_a_retry_and_the_cap_hands_over(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    set_state(flow_project, retry_cap=2)
    order = _issue(flow_project)
    for expected in (1, 2):
        result = cli(flow_project, "flow", "done", order["id"])
        assert result.returncode == 1
        assert _state(flow_project)["orders"][order["id"]]["retries"] == expected
    handed = jcli(flow_project, "flow", "next")["order"]
    assert handed["needs_human"] is True and handed["kind"] == "needs-human"
    assert handed["nodes"] == ["t1"] and handed["retries"] == 2
    assert handed["evidence"]["order"] == order["id"]
    assert "still holds" in handed["evidence"]["output"]
    assert "retry cap" in handed["reason"]


def test_spent_budget_refuses_large_orders_but_not_script_orders(flow_project: Path) -> None:
    write_map(flow_project, SUPPORTED)  # reach the draft stage: reindex (script) first
    set_state(flow_project, budget={"limit": 5, "used": 5})
    script = _issue(flow_project)
    assert (script["kind"], script["needs_human"]) == ("reindex", False)
    assert cli(flow_project, "index").returncode == 0
    (flow_project / "paper" / "sections" / "01_introduction.tex").write_text("\\cite{nobody1999}\n")
    assert cli(flow_project, "index").returncode == 0
    refused = _issue(flow_project)
    assert refused["needs_human"] is True and "budget spent" in refused["reason"]
    assert refused["evidence"]["check"] == "make-validate"
    set_state(flow_project, budget={"limit": 5, "used": 0})
    large = _issue(flow_project)
    assert (large["kind"], large["tier"]) == ("write-section", "large")
    assert not (flow_project / "x").exists()


def test_gated_order_is_refused_without_confirmation(flow_project: Path) -> None:
    clean = (
        "version: 1\nnodes:\n"
        "  - {id: t1, type: thesis, text: T., status: accepted, accepted-by: Ada}\n"
        "  - {id: o1, type: objection, text: O., status: accepted, accepted-by: Ada}\n"
        "  - {id: d1, type: defense, text: D., status: proposed}\n"
        "edges:\n  - {from: d1, to: t1, type: supports}\n"
        "  - {from: o1, to: t1, type: attacks}\n  - {from: d1, to: o1, type: rebuts}\n"
    )
    write_map(flow_project, clean)
    cli(flow_project, "index")
    order = _issue(flow_project)
    assert order["gated"] is True
    result = cli(flow_project, "flow", "done", order["id"])
    assert result.returncode == 1 and "gated" in result.stdout
    # An agent shell has no terminal: attest is refused and records nothing.
    refused = cli(flow_project, "flow", "attest", "bibliography", "--by", "Ada", "--why", "ok")
    assert refused.returncode == 1 and "terminal" in refused.stdout
    assert _state(flow_project)["attestations"] == []
    set_state(flow_project, attestations=[{
        "name": "bibliography", "by": "Ada", "at": "2026-01-01", "why": "verified",
    }])
    assert jcli(flow_project, "flow", "done", order["id"])["ok"] is True


def test_waive_and_attest_refuse_agent_names_and_need_a_terminal(flow_project: Path) -> None:
    refused = cli(
        flow_project, "flow", "waive", "frame", "--by", "claude", "--why", "x",
        "--expires", "2999-01-01",
    )
    assert refused.returncode == 1
    assert _state(flow_project)["waivers"] == []


def test_attest_and_waive_record_when_a_person_confirms(flow_project: Path) -> None:
    code = (
        "from pathlib import Path\nfrom scripts.article import flow\n"
        "flow.attest(Path('.'), 'bibliography', 'Ada', 'checked', confirmed=True)\n"
        "flow.waive(Path('.'), 'map', 'Ada', 'later', '2999-01-01', confirmed=True)\n"
        "try:\n    flow.attest(Path('.'), 'x', 'claude', 'y', confirmed=True)\n"
        "except flow.FlowError as exc:\n    print(exc)\n"
    )
    from conftest import run

    result = run(flow_project, "python3", "-c", code)
    assert result.returncode == 0, result.stderr
    assert "agent role" in result.stdout
    state = _state(flow_project)
    assert [a["name"] for a in state["attestations"]] == ["bibliography"]
    assert [w["stage"] for w in state["waivers"]] == ["map"]


# ---------------------------------------------- closing dialectic orders (decision 0084)

CLAIMED = THESIS_MAP.replace(
    "edges: []",
    "  - {id: s1, type: source-claim, text: Smith says X., status: proposed,\n"
    "     quote: X holds, locator: p. 3, bib_keys: [smith2020]}\n"
    "  - {id: s2, type: source-claim, text: Jones says not X., status: proposed,\n"
    "     quote: X fails, locator: p. 9, bib_keys: [jones2021]}\n"
    "edges: []",
)
CONTRADICTION = (
    "contradictions:\n"
    "  - id: c1\n    text: X holds and X fails.\n    kind: dialectical\n"
    "    status: proposed\n    author: agent\n"
    "    poles:\n      - {text: X holds, claim: s1}\n      - {text: X fails, claim: s2}\n"
)


def test_map_contradictions_closes_once_a_contradiction_is_proposed(flow_project: Path) -> None:
    write_map(flow_project, CLAIMED)
    set_state(flow_project, required_stages=["dialectic"])
    order = _issue(flow_project)
    assert order["kind"] == "map-contradictions"
    unchanged = jcli(flow_project, "flow", "done", order["id"])
    assert unchanged["ok"] is False and "still holds" in unchanged["output"]
    assert unchanged["retries"] == 1
    write_map(flow_project, CLAIMED + CONTRADICTION)
    closed = jcli(flow_project, "flow", "done", order["id"])
    assert closed["ok"] is True and closed["charged"] == 1
    following = _issue(flow_project)
    assert (following["stage"], following["kind"], following["nodes"]) == (
        "dialectic", "move-contradiction", ["c1"],
    )


def test_move_contradiction_fails_to_close_on_a_lint_error(flow_project: Path) -> None:
    write_map(flow_project, CLAIMED + CONTRADICTION)
    set_state(flow_project, required_stages=["dialectic"])
    order = _issue(flow_project)
    assert order["kind"] == "move-contradiction"
    broken = CLAIMED + CONTRADICTION + (
        "moves:\n  - {id: m1, type: negation, text: Deny., status: proposed, author: agent}\n"
    )
    write_map(flow_project, broken)  # a negation with no cites: T084
    failed = jcli(flow_project, "flow", "done", order["id"])
    assert failed["ok"] is False and "theses-lint" in failed["output"]
    fixed = CLAIMED + CONTRADICTION + (
        "moves:\n  - {id: m1, type: negation, text: Deny., status: proposed, author: agent,\n"
        "     cites: [c1]}\n"
    )
    write_map(flow_project, fixed)
    assert jcli(flow_project, "flow", "done", order["id"])["ok"] is True


# ------------------------------------------- the ratchet on the accepted set (0085)

RETIRED = THESIS_MAP.replace(
    "    status: accepted\n    accepted-by: Ada Lovelace\n", "    status: retired\n"
)
REWRITTEN = SUPPORTED.replace("text: Main claim.", "text: Main claim, softened to fit.")
PROMOTED = SUPPORTED.replace(
    "  - {id: d1, type: defense, text: A defense., status: proposed}",
    "  - {id: d1, type: defense, text: A defense., status: accepted, accepted-by: Ada}",
)
assert PROMOTED != SUPPORTED


def test_issue_records_the_accepted_set(flow_project: Path) -> None:
    import json

    import jsonschema

    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    entry = _state(flow_project)["orders"][order["id"]]
    assert entry["accepted_ids"] == ["t1"] and len(entry["accepted_hash"]) == 64
    schema = json.loads((TEMPLATE / "schemas" / "flow.schema.json").read_text())
    jsonschema.validate(_state(flow_project), schema)
    _issue(flow_project)
    assert _state(flow_project)["orders"][order["id"]] == entry  # unchanged, not rewritten


def test_closing_by_retiring_the_accepted_thesis_fails_and_counts(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    assert order["kind"] == "fill-gap"
    write_map(flow_project, RETIRED)  # the gap is gone, and so is the thesis
    result = jcli(flow_project, "flow", "done", order["id"])
    assert result["ok"] is False and result["retries"] == 1
    assert "ratchet" in result["output"] and "no longer accepted: t1" in result["output"]
    assert _state(flow_project)["budget"]["used"] == 0
    write_map(flow_project, SUPPORTED)  # restored and answered: closes
    assert jcli(flow_project, "flow", "done", order["id"])["ok"] is True


def test_closing_with_a_rewritten_accepted_text_fails(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)  # accepted by hand: no ledger record, lint notes only
    order = _issue(flow_project)
    write_map(flow_project, REWRITTEN)
    result = jcli(flow_project, "flow", "done", order["id"])
    assert result["ok"] is False
    assert "ratchet" in result["output"] and "accepted text changed: t1" in result["output"]


def test_a_recorded_acceptance_makes_the_rewrite_fail_lint_first(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    cli(flow_project, "theses", "accept", "t1", "--by", "Ada Lovelace")  # records the text
    order = _issue(flow_project)
    write_map(flow_project, REWRITTEN)
    result = jcli(flow_project, "flow", "done", order["id"])
    assert result["ok"] is False and "T096" in result["output"]


def test_closing_with_a_newly_accepted_item_fails(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    write_map(flow_project, PROMOTED)
    result = jcli(flow_project, "flow", "done", order["id"])
    assert result["ok"] is False
    assert "newly accepted" in result["output"] and "d1" in result["output"]


def test_an_order_issued_before_the_ratchet_closes_as_before(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    order = _issue(flow_project)
    state = _state(flow_project)
    state["orders"][order["id"]].pop("accepted_hash")
    state["orders"][order["id"]].pop("accepted_ids")
    (flow_project / "flow.yaml").write_text(yaml.safe_dump(state, sort_keys=False))
    write_map(flow_project, RETIRED)
    assert jcli(flow_project, "flow", "done", order["id"])["ok"] is True


def test_a_gated_order_is_not_ratcheted(flow_project: Path) -> None:
    from flow_helpers import CLEAN_MAP

    write_map(flow_project, CLEAN_MAP)
    cli(flow_project, "index")
    seen = set()
    for _ in range(6):
        order = _issue(flow_project)
        if order is None or order["kind"] in seen:
            break
        seen.add(order["kind"])
        if order["gated"]:
            assert "accepted_hash" not in _state(flow_project)["orders"][order["id"]]
            return
        if order["needs_human"]:
            break
        jcli(flow_project, "flow", "done", order["id"])
    import pytest

    pytest.skip("no gated order reached in this fixture")
