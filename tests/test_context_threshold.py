"""``max_context`` in ``flow.yaml`` and the maintainer script that fits it."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT
from flow_helpers import cli, set_state
from test_flow_brief import FLOW_SCHEMA, ORDER_SCHEMA, _flow, project  # noqa: F401

SCRIPT = ROOT / "scripts" / "context-threshold.py"
SPEC = importlib.util.spec_from_file_location("context_threshold", SCRIPT)
assert SPEC and SPEC.loader
ct = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ct)

# Three pilot-shaped runs: 26K start context, 2.2K growth per call, small noise.
NOISE = [0, 400, -300, 200, -500, 300, -100, 500, -400, 100]


def pilot_runs() -> list[dict]:
    return [
        {"contexts": [26_000 + 2_200 * i + NOISE[(i + k) % 10] for i in range(n)]}
        for k, n in enumerate((61, 62, 60))
    ]


def test_fit_recovers_start_and_growth() -> None:
    c0, g = ct.fit_line([26_000 + 2_200 * i for i in range(50)])
    assert round(c0) == 26_000 and round(g) == 2_200


def test_pilot_runs_give_n_star_43_and_threshold_120k() -> None:
    result = ct.analyse(ct.runs_of({"runs": pilot_runs()}, [], 10), handoff=2_000_000, resume=False)
    assert 42 <= result["n_star"] <= 44
    assert 118_000 <= result["threshold"] <= 122_000
    assert result["handoff"] == 2_000_000 and result["g"] in range(2_100, 2_300)


def test_a_cheaper_handoff_lowers_the_optimum() -> None:
    result = ct.analyse(ct.runs_of({"runs": pilot_runs()}, [], 10), handoff=500_000, resume=False)
    assert 20 <= result["n_star"] <= 22


def test_resume_handoff_costs_the_segment_itself() -> None:
    runs = ct.runs_of({"runs": pilot_runs()}, [], 10)
    result = ct.analyse(runs, handoff=None, resume=True)
    assert result["handoff"] > 3_000_000  # a resume re-sends every call's context


def test_no_handoff_cost_or_no_growth_is_refused() -> None:
    runs = ct.runs_of({"runs": pilot_runs()}, [], 10)
    with pytest.raises(ValueError):
        ct.analyse(runs, handoff=None, resume=False)
    with pytest.raises(ValueError):
        ct.optimum(26_000, 0, 1_000_000)


def test_cli_prints_the_inputs_and_reads_session_cost_json(tmp_path: Path) -> None:
    import subprocess
    import sys

    src = tmp_path / "rows.json"
    rows = [{"session": "s1", "agent": f"a{i}", **r} for i, r in enumerate(pilot_runs())]
    src.write_text(json.dumps({"summary": {}, "agents": rows}))
    out = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(src), "--handoff", "2000000", "--json"],
        capture_output=True, text=True, check=True,
    )
    result = json.loads(out.stdout)
    assert len(result["runs"]) == 3 and 42 <= result["n_star"] <= 44


def test_max_context_is_advisory_text_in_order_and_brief(project: Path) -> None:  # noqa: F811
    order = _flow(project, "--brief")
    assert "max_context" not in order and "max_context" not in order["brief"]
    set_state(project, max_context=120_000)
    order = _flow(project, "--brief")
    assert order["max_context"] == 120_000 and order["max_calls"] == 40
    assert order["brief"]["max_context"] == 120_000
    note = order["brief"]["max_context_note"]
    assert "advisory" in note and "120000 tokens" in note and "40 tool calls" in note
    jsonschema.validate(order, ORDER_SCHEMA)


def test_the_ceiling_wins_when_it_is_smaller(project: Path) -> None:  # noqa: F811
    set_state(project, max_context=120_000, max_context_ceiling=90_000)
    assert _flow(project)["max_context"] == 90_000
    set_state(project, max_context=80_000, max_context_ceiling=90_000)
    assert _flow(project)["max_context"] == 80_000
    set_state(project, max_context_ceiling=70_000)
    assert _flow(project)["max_context"] == 70_000


def test_human_orders_carry_no_threshold(flow_project: Path) -> None:
    set_state(flow_project, max_context=120_000)
    order = _flow(flow_project)
    assert order["needs_human"] is True and "max_context" not in order


def test_flow_yaml_context_keys_are_validated(project: Path) -> None:  # noqa: F811
    for key in ("max_context", "max_context_ceiling"):
        for bad in (10, "120k", 0):
            set_state(project, **{key: bad})
            assert json.loads(cli(project, "flow", "next").stdout)["ok"] is False
        path = project / "flow.yaml"
        data = yaml.safe_load(path.read_text())
        data.pop(key)
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    set_state(project, max_context=120_000, max_context_ceiling=250_000)
    jsonschema.validate(yaml.safe_load((project / "flow.yaml").read_text()), FLOW_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**yaml.safe_load((project / "flow.yaml").read_text()),
                             "max_context": 5}, FLOW_SCHEMA)
