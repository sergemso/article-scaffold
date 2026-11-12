"""``flow status``: gates are computed from the repo; flow.yaml stores only decisions."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml
from conftest import ROOT
from flow_helpers import (  # noqa: F401  (fixtures)
    THESIS_MAP,
    cli,
    jcli,
    set_state,
    stages,
    write_map,
)

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
STATUS_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-status.schema.json").read_text())
STATE_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow.schema.json").read_text())

GAPPY = THESIS_MAP.replace(
    "edges: []",
    "  - id: o1\n    type: objection\n    text: An objection.\n    status: proposed\nedges: []",
)


def test_state_file_is_shipped_and_valid(flow_project: Path) -> None:
    data = yaml.safe_load((flow_project / "flow.yaml").read_text())
    jsonschema.validate(data, STATE_SCHEMA)
    assert data["round"] == 0 and data["budget"]["used"] == 0
    assert "stage" not in data and "current_stage" not in data  # no stored pointer


def test_fresh_repo(flow_project: Path) -> None:
    result = cli(flow_project, "flow", "status", "--json")
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, STATUS_SCHEMA)
    assert result.returncode == 1  # a gate fails
    assert [s["stage"] for s in payload["stages"]] == [
        "frame", "map", "discover", "draft", "verify-sources",
        "adversarial", "revise", "release-gate", "publish",
    ]
    assert payload["current_stage"] == "frame"
    frame = stages(payload)["frame"]
    assert frame["status"] == "fail"
    assert "accepted" in frame["reason"]
    assert "scripts.article" in frame["command"]
    assert stages(payload)["publish"]["status"] == "human"


def test_map_gaps_fail_the_map_gate(flow_project: Path) -> None:
    write_map(flow_project, GAPPY)
    payload = jcli(flow_project, "flow", "status", "--json")
    assert stages(payload)["frame"]["status"] == "pass"
    assert payload["current_stage"] == "map"
    reason = stages(payload)["map"]["reason"]
    assert "o1" in reason and "thesis-unsupported" in reason
    assert "theses gaps" in stages(payload)["map"]["command"]


def test_editing_outside_the_flow_changes_status_without_state_update(flow_project: Path) -> None:
    write_map(flow_project, THESIS_MAP)
    before = (flow_project / "flow.yaml").read_text()
    first = jcli(flow_project, "flow", "status", "--json")
    write_map(flow_project, GAPPY)
    second = jcli(flow_project, "flow", "status", "--json")
    assert first["stages"] != second["stages"]
    assert (flow_project / "flow.yaml").read_text() == before  # status never writes


def test_stale_check_cache_fails_verify_sources(flow_project: Path) -> None:
    source_map = THESIS_MAP.replace(
        "edges: []",
        "  - id: s1\n    type: source-claim\n    text: Smith says X.\n    status: proposed\n"
        "    quote: X holds\n    locator: p. 3\n    bib_keys: [smith2020]\nedges: []",
    )
    write_map(flow_project, source_map)
    sources = flow_project / "paper" / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "smith2020.txt").write_text("It is known that X holds in general.\n")
    stale = stages(jcli(flow_project, "flow", "status", "--json"))["verify-sources"]
    assert stale["status"] == "fail" and "s1" in stale["reason"]
    assert "claims quote-check" in stale["command"]
    cached = jcli(flow_project, "claims", "cache", "s1", "--set", "supports")
    assert cached["verdict"] == "supports"
    fresh = stages(jcli(flow_project, "flow", "status", "--json"))["verify-sources"]
    assert fresh["status"] == "pass"
    # Rewording the claim changes the cache key: the cached verdict is stale again.
    write_map(flow_project, source_map.replace("Smith says X.", "Smith proves X."))
    again = stages(jcli(flow_project, "flow", "status", "--json"))["verify-sources"]
    assert again["status"] == "fail"


def test_waiver_turns_a_failure_into_waived_until_it_expires(flow_project: Path) -> None:
    waiver = {
        "stage": "frame", "by": "Ada Lovelace", "at": "2026-01-01",
        "why": "thesis pending", "expires": "2999-01-01",
    }
    set_state(flow_project, waivers=[waiver])
    payload = jcli(flow_project, "flow", "status", "--json")
    frame = stages(payload)["frame"]
    assert frame["status"] == "waived"
    assert "Ada Lovelace" in frame["reason"] and "accepted" in frame["reason"]  # still shown
    assert payload["current_stage"] == "draft"  # empty map has no gaps; the index is missing
    set_state(flow_project, waivers=[{**waiver, "expires": "2020-01-01"}])
    expired = jcli(flow_project, "flow", "status", "--json")
    assert stages(expired)["frame"]["status"] == "fail"
    assert expired["current_stage"] == "frame"


def test_invalid_state_is_reported(flow_project: Path) -> None:
    set_state(flow_project, round=-1, waivers=[{"stage": "nope"}])
    result = cli(flow_project, "flow", "status", "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False and "flow.yaml is invalid" in payload["error"]


def test_agent_named_waiver_is_refused(flow_project: Path) -> None:
    waiver = {
        "stage": "frame", "by": "the-claude-agent", "at": "2026-01-01",
        "why": "x", "expires": "2999-01-01",
    }
    set_state(flow_project, waivers=[waiver])
    assert "agent role" in jcli(flow_project, "flow", "status", "--json")["error"]


# ------------------------------------------------- the derived quality vector (0085)


def _quality(project: Path) -> dict:
    payload = jcli(project, "flow", "status", "--json")
    jsonschema.validate(payload, STATUS_SCHEMA)
    return payload["quality"]


def test_quality_of_a_repo_without_a_map_is_zero(flow_project: Path) -> None:
    (flow_project / "theses.yaml").unlink()
    assert _quality(flow_project) == {
        "theses_accepted": 0, "theses_opened": 0, "contradictions_moved": 0,
        "claims_verified": 0, "objections_defended": 0, "gaps": {},
    }


def test_quality_counts_match_a_known_map(flow_project: Path) -> None:
    import copy

    from test_dialectic import VALID

    data = copy.deepcopy(VALID)  # t1 accepted; c1, c2 moved, c3 unmoved; o1 undefended
    data["moves"].append(
        {"id": "m9", "type": "opening", "text": "Open t1.", "status": "accepted",
         "author": "human", "accepted-by": "Ada", "cites": ["m4"], "opens": "t1"}
    )
    data["nodes"].append(
        {"id": "d1", "type": "defense", "text": "Answered.", "status": "proposed",
         "answers": "o1", "anchor": None}
    )
    write_map(flow_project, yaml.safe_dump(data, sort_keys=False))
    vector = _quality(flow_project)
    assert vector["theses_accepted"] == 1 and vector["theses_opened"] == 1
    assert vector["contradictions_moved"] == 2
    assert vector["objections_defended"] == 1
    assert vector["claims_verified"] == 0  # no local text for s1, s2
    assert vector["gaps"]["contradiction-unmoved"] == 1
    assert "thesis-untraced" not in vector["gaps"]
    data["moves"][-1]["status"] = "proposed"
    write_map(flow_project, yaml.safe_dump(data, sort_keys=False))
    assert _quality(flow_project)["theses_opened"] == 0  # only an accepted opening counts


def test_quality_is_derived_and_deterministic(flow_project: Path) -> None:
    write_map(flow_project, GAPPY)
    first = cli(flow_project, "flow", "status", "--json").stdout
    assert first == cli(flow_project, "flow", "status", "--json").stdout
    state = yaml.safe_load((flow_project / "flow.yaml").read_text())
    assert "quality" not in state
    text = cli(flow_project, "flow", "status").stdout
    assert "quality: theses_accepted=" in text and "gaps:" in text


def test_quality_lists_the_niche_gap_when_the_stage_is_required(flow_project: Path) -> None:
    from test_dialectic import PLAIN

    write_map(flow_project, yaml.safe_dump(PLAIN, sort_keys=False))
    set_state(flow_project, required_stages=["dialectic"])
    assert _quality(flow_project)["gaps"].get("niche-unmapped") == 1
