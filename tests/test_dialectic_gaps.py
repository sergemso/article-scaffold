"""Dialectic gaps, the `theses dialectic` view and the advisory stage (decision 0083)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT
from flow_helpers import cli, jcli, set_state, stages, write_map
from test_dialectic import PLAIN, VALID, _contradiction, _move, _mutated, dialectic, theses

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
STATE_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow.schema.json").read_text())
STATUS_SCHEMA = json.loads((TEMPLATE / "schemas" / "flow-status.schema.json").read_text())
KINDS = ("contradiction-unmoved", "move-without-opening", "thesis-untraced")


def _dump(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def _kinds(data: dict) -> list[tuple[str, str]]:
    return [(g["kind"], g["id"]) for g in theses.gaps(data, None)]


def _closed() -> dict:
    """VALID with every gap closed: c3 moved, t1 opened by an opening."""
    data = copy.deepcopy(VALID)
    data["moves"].append(
        {"id": "m6", "type": "negation", "text": "Reject both poles.", "status": "proposed",
         "author": "agent", "cites": ["c3"]}
    )
    data["moves"].append(
        {"id": "m7", "type": "opening", "text": "Reopen the claim.", "status": "proposed",
         "author": "agent", "cites": ["m6"], "opens": "t1"}
    )
    return data


# ------------------------------------------------------------------- gap kinds


def test_gap_kinds_are_registered() -> None:
    for kind in KINDS:
        assert kind in theses.DEFAULT_GAP_KINDS and kind in theses.GAP_KINDS
    assert dialectic.GAP_KINDS == KINDS


def test_a_map_without_the_section_has_no_dialectic_gaps() -> None:
    assert [g for g in theses.gaps(PLAIN, None) if g["kind"] in KINDS] == []
    assert dialectic.gaps(PLAIN) == []


def test_empty_sections_are_not_a_use() -> None:
    data = _mutated(lambda d: d.update(contradictions=[], moves=[]), PLAIN)
    assert dialectic.gaps(data) == []


def test_the_valid_fixture_has_exactly_the_expected_gaps() -> None:
    assert [g for g in _kinds(VALID) if g[0] in KINDS] == [
        ("contradiction-unmoved", "c3"),
        ("thesis-untraced", "t1"),
    ]


def test_closing_everything_leaves_no_dialectic_gap() -> None:
    assert dialectic.gaps(_closed()) == []


def test_unmoved_contradiction_appears_and_disappears() -> None:
    data = _closed()
    _move(data, "m6")["cites"] = ["c1"]
    assert ("contradiction-unmoved", "c3") in _kinds(data)
    _move(data, "m6")["cites"] = ["c3"]
    assert ("contradiction-unmoved", "c3") not in _kinds(data)


def test_a_retired_move_does_not_move_a_contradiction() -> None:
    data = _closed()
    _move(data, "m6")["status"] = "retired"
    kinds = _kinds(data)
    assert ("contradiction-unmoved", "c3") in kinds


def test_a_retired_contradiction_is_not_a_gap() -> None:
    data = _mutated(lambda d: _contradiction(d, "c3").update(status="retired"))
    assert ("contradiction-unmoved", "c3") not in _kinds(data)


def test_move_without_opening_when_the_chain_ends_in_a_synthesis() -> None:
    data = _mutated(lambda d: d["moves"].pop())  # drop the opening m5
    assert ("move-without-opening", "m4") in _kinds(data)
    assert not any(k == "move-without-opening" and i != "m4" for k, i in _kinds(data))


def test_an_opening_closes_the_chain() -> None:
    assert not [g for g in _kinds(VALID) if g[0] == "move-without-opening"]


def test_a_dangling_negation_is_a_move_without_opening() -> None:
    data = _closed()
    data["moves"].append(
        {"id": "m8", "type": "negation", "text": "Loose.", "status": "proposed",
         "author": "agent", "cites": ["c1"]}
    )
    assert ("move-without-opening", "m8") in _kinds(data)


def test_a_retired_opening_reopens_the_gap() -> None:
    data = _mutated(lambda d: _move(d, "m5").update(status="retired"))
    assert ("move-without-opening", "m4") in _kinds(data)


def test_thesis_untraced_until_opened_or_explained() -> None:
    data = copy.deepcopy(VALID)
    assert ("thesis-untraced", "t1") in _kinds(data)
    data["nodes"][0]["untraced-reason"] = "Fixed by the call for papers."
    assert ("thesis-untraced", "t1") not in _kinds(data)
    assert not theses.structure_errors(data).items


def test_thesis_traced_by_an_opening() -> None:
    data = _mutated(lambda d: _move(d, "m5").update(opens="t1"))
    assert ("thesis-untraced", "t1") not in _kinds(data)


def test_a_hypothesis_is_never_untraced() -> None:
    assert ("thesis-untraced", "q1") not in _kinds(VALID)


def test_retired_thesis_is_not_untraced() -> None:
    data = _mutated(lambda d: d["nodes"][0].update(status="retired"))
    data["nodes"][0].pop("accepted-by")
    assert ("thesis-untraced", "t1") not in _kinds(data)


def test_untraced_reason_rules() -> None:
    on_objection = _mutated(lambda d: d["nodes"][1].update({"untraced-reason": "x"}))
    assert not theses.structure_errors(on_objection).ok
    multi = _mutated(lambda d: d["nodes"][0].update({"untraced-reason": "a\nb"}))
    assert not theses.structure_errors(multi).ok
    blank = _mutated(lambda d: d["nodes"][0].update({"untraced-reason": " "}))
    assert not theses.structure_errors(blank).ok


def test_untraced_reason_schema() -> None:
    schema = json.loads((TEMPLATE / "schemas" / "theses.schema.json").read_text())
    ok = _mutated(lambda d: d["nodes"][0].update({"untraced-reason": "why"}))
    jsonschema.validate(ok, schema)
    bad = _mutated(lambda d: d["nodes"][1].update({"untraced-reason": "why"}))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_kind_filter() -> None:
    only = theses.gaps(VALID, None, kinds=("thesis-untraced",))
    assert [g["kind"] for g in only] == ["thesis-untraced"]
    assert not [g for g in theses.gaps(VALID, None, kinds=("single-source",)) if g["kind"] in KINDS]


def test_gaps_carry_ids_and_one_line_text_only() -> None:
    for gap in dialectic.gaps(VALID):
        assert set(gap) == {"kind", "id", "text"}
        assert "\n" not in gap["text"] and gap["text"]


def test_a_contradiction_without_text_is_labelled_by_its_poles() -> None:
    gap = next(g for g in dialectic.gaps(VALID) if g["id"] == "c3")
    assert gap["text"] == "Be open / Be closed"


def test_gaps_are_deterministic_and_sorted() -> None:
    first = dialectic.gaps(VALID)
    assert first == dialectic.gaps(copy.deepcopy(VALID))
    assert first == sorted(first, key=lambda g: (g["kind"], g["id"]))


def test_gaps_do_not_mutate_the_map() -> None:
    before = copy.deepcopy(VALID)
    dialectic.gaps(VALID)
    dialectic.view(VALID)
    assert VALID == before


# ------------------------------------------------------------------------ view


def test_view_shape() -> None:
    view = dialectic.view(VALID)
    assert set(view) == {"used", "contradictions", "moves", "theses", "gaps"}
    assert view["used"] is True
    assert [c["id"] for c in view["contradictions"]] == ["c1", "c2", "c3"]
    assert view["contradictions"][0]["moved-by"] == ["m1", "m3"]
    assert view["contradictions"][2]["moved-by"] == []
    assert view["contradictions"][0]["poles"][0] == {"text": "X holds", "claim": "s1"}
    assert view["contradictions"][1]["poles"][0]["niche"].startswith("Studies")
    assert [m["id"] for m in view["moves"]] == ["m1", "m2", "m3", "m4", "m5"]
    assert view["moves"][-1]["opens"] == "q1"
    assert view["theses"] == [
        {"id": "t1", "status": "accepted", "opened-by": [], "untraced-reason": None}
    ]


def test_view_of_a_plain_map_is_unused() -> None:
    view = dialectic.view(PLAIN)
    assert view["used"] is False
    assert view["contradictions"] == [] and view["moves"] == [] and view["gaps"] == []
    assert "off" in dialectic.format_text(view)


def test_view_is_deterministic_and_json_serialisable() -> None:
    a = json.dumps(dialectic.view(VALID), sort_keys=False)
    b = json.dumps(dialectic.view(copy.deepcopy(VALID)), sort_keys=False)
    assert a == b


def test_view_lists_retired_contradictions_but_not_as_moving() -> None:
    data = _mutated(lambda d: _move(d, "m1").update(status="retired"))
    view = dialectic.view(data)
    assert view["contradictions"][0]["moved-by"] == ["m3"]
    assert all(m["id"] != "m1" or m["status"] == "retired" for m in view["moves"])


def test_text_rendering_lists_each_section() -> None:
    text = dialectic.format_text(dialectic.view(VALID))
    assert text == dialectic.format_text(dialectic.view(copy.deepcopy(VALID)))
    for needle in ("Contradictions:", "Moves:", "Gaps:", "c3", "unmoved", "m5", "opens q1"):
        assert needle in text
    closed = dialectic.format_text(dialectic.view(_closed()))
    assert "  none" in closed


# ------------------------------------------------------------------ CLI (render)


def _put(project: Path, data: dict) -> None:
    write_map(project, _dump(data))


def test_cli_dialectic_json(flow_project: Path) -> None:
    _put(flow_project, VALID)
    result = cli(flow_project, "theses", "dialectic", "--json")
    assert result.returncode == 0  # read-only view
    payload = json.loads(result.stdout)
    assert payload["command"] == "theses dialectic" and payload["ok"] is False
    assert {g["kind"] for g in payload["gaps"]} == {"contradiction-unmoved", "thesis-untraced"}
    assert payload["moves"][0]["id"] == "m1"
    again = cli(flow_project, "theses", "dialectic", "--json")
    assert again.stdout == result.stdout


def test_cli_dialectic_text_and_clean(flow_project: Path) -> None:
    _put(flow_project, _closed())
    text = cli(flow_project, "theses", "dialectic")
    assert text.returncode == 0 and "Contradictions:" in text.stdout
    payload = json.loads(cli(flow_project, "theses", "dialectic", "--json").stdout)
    assert payload["ok"] is True and payload["gaps"] == []


def test_cli_dialectic_without_the_section(flow_project: Path) -> None:
    payload = json.loads(cli(flow_project, "theses", "dialectic", "--json").stdout)
    assert payload["used"] is False and payload["ok"] is True


def test_cli_dialectic_refuses_an_invalid_map(flow_project: Path) -> None:
    broken = _mutated(lambda d: _move(d, "m1").update(cites=["m1"]))
    _put(flow_project, broken)
    result = cli(flow_project, "theses", "dialectic", "--json")
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_cli_dialectic_does_not_write(flow_project: Path) -> None:
    _put(flow_project, VALID)
    before = {p: p.read_bytes() for p in flow_project.glob("*.yaml")}
    cli(flow_project, "theses", "dialectic", "--json")
    assert before == {p: p.read_bytes() for p in flow_project.glob("*.yaml")}


def test_cli_gaps_includes_dialectic_kinds_and_filters(flow_project: Path) -> None:
    _put(flow_project, VALID)
    payload = json.loads(cli(flow_project, "theses", "gaps").stdout)
    assert {"contradiction-unmoved", "thesis-untraced"} <= {g["kind"] for g in payload["gaps"]}
    only = cli(flow_project, "theses", "gaps", "--kind", "thesis-untraced")
    assert only.returncode == 1
    assert [g["id"] for g in json.loads(only.stdout)["gaps"]] == ["t1"]
    clean = cli(flow_project, "theses", "gaps", "--kind", "move-without-opening")
    assert clean.returncode == 0


def test_cli_gaps_on_a_legacy_map_is_unchanged(flow_project: Path) -> None:
    payload = json.loads(cli(flow_project, "theses", "gaps").stdout)
    assert not [g for g in payload["gaps"] if g["kind"] in KINDS]


# -------------------------------------------------------------------- the stage


def test_legacy_repo_flow_status_is_unchanged(flow_project: Path) -> None:
    payload = jcli(flow_project, "flow", "status", "--json")
    assert [s["stage"] for s in payload["stages"]] == [
        "frame", "map", "discover", "draft", "verify-sources",
        "adversarial", "revise", "release-gate", "publish",
    ]
    assert all(s["status"] != "advisory" for s in payload["stages"])


def test_legacy_status_text_has_no_dialectic_line(flow_project: Path) -> None:
    assert "dialectic" not in cli(flow_project, "flow", "status").stdout


def test_a_map_without_contradictions_skips_the_stage(flow_project: Path) -> None:
    _put(flow_project, PLAIN)
    assert "dialectic" not in stages(jcli(flow_project, "flow", "status", "--json"))


def test_open_stage_with_an_unmoved_contradiction(flow_project: Path) -> None:
    _put(flow_project, VALID)
    result = cli(flow_project, "flow", "status", "--json")
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, STATUS_SCHEMA)
    entry = stages(payload)["dialectic"]
    assert entry["status"] == "advisory"
    assert "contradiction-unmoved" in entry["reason"] and "c3" in entry["reason"]
    assert "theses gaps" in entry["command"]
    names = [s["stage"] for s in payload["stages"]]
    assert names.index("dialectic") == names.index("frame") + 1
    assert names.index("dialectic") < names.index("map")


def test_advisory_stage_does_not_fail_or_take_over_the_current_stage(flow_project: Path) -> None:
    _put(flow_project, VALID)
    payload = jcli(flow_project, "flow", "status", "--json")
    assert payload["current_stage"] != "dialectic"
    others = {s["status"] for s in payload["stages"] if s["stage"] != "dialectic"}
    assert "advisory" not in others
    nxt = jcli(flow_project, "flow", "next")
    assert nxt["order"] is None or nxt["order"]["stage"] != "dialectic"


def test_gaps_closed_but_not_attested_stays_open(flow_project: Path) -> None:
    _put(flow_project, _closed())
    entry = stages(jcli(flow_project, "flow", "status", "--json"))["dialectic"]
    assert entry["status"] == "advisory" and "attested" in entry["reason"]
    assert "flow attest dialectic" in entry["command"]


def test_attestation_closes_the_stage(flow_project: Path) -> None:
    _put(flow_project, _closed())
    set_state(flow_project, attestations=[
        {"name": "dialectic", "by": "Ada Lovelace", "at": "2026-01-01", "why": "synthesis read"}
    ])
    entry = stages(jcli(flow_project, "flow", "status", "--json"))["dialectic"]
    assert entry["status"] == "pass"


def test_attestation_does_not_close_open_gaps(flow_project: Path) -> None:
    _put(flow_project, VALID)
    set_state(flow_project, attestations=[
        {"name": "dialectic", "by": "Ada Lovelace", "at": "2026-01-01", "why": "read"}
    ])
    entry = stages(jcli(flow_project, "flow", "status", "--json"))["dialectic"]
    assert entry["status"] == "advisory" and "c3" in entry["reason"]


def test_flow_attest_records_the_dialectic_attestation(flow_project: Path) -> None:
    import subprocess
    code = (
        "from pathlib import Path\nfrom scripts.article import flow\n"
        "flow.attest(Path('.'), 'dialectic', 'Ada Lovelace', 'read the moves', confirmed=True)\n"
    )
    done = subprocess.run(["python3", "-c", code], cwd=flow_project, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    _put(flow_project, _closed())
    assert stages(jcli(flow_project, "flow", "status", "--json"))["dialectic"]["status"] == "pass"


def test_required_promotion_makes_the_open_stage_fail(flow_project: Path) -> None:
    _put(flow_project, VALID)
    set_state(flow_project, required_stages=["dialectic"])
    result = cli(flow_project, "flow", "status", "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 1 and payload["ok"] is False
    entry = stages(payload)["dialectic"]
    assert entry["status"] == "fail" and not entry["reason"].startswith("advisory")


def test_required_stage_blocks_until_it_passes(flow_project: Path) -> None:
    _put(flow_project, _closed())
    set_state(flow_project, required_stages=["dialectic"])
    payload = jcli(flow_project, "flow", "status", "--json")
    assert payload["current_stage"] == "dialectic"
    order = jcli(flow_project, "flow", "next")["order"]
    assert order["stage"] == "dialectic" and order["needs_human"] is True
    set_state(flow_project, attestations=[
        {"name": "dialectic", "by": "Ada Lovelace", "at": "2026-01-01", "why": "ok"}
    ])
    assert stages(jcli(flow_project, "flow", "status", "--json"))["dialectic"]["status"] == "pass"


def test_required_stage_is_still_skipped_without_contradictions(flow_project: Path) -> None:
    set_state(flow_project, required_stages=["dialectic"])
    payload = jcli(flow_project, "flow", "status", "--json")
    assert "dialectic" not in stages(payload)


def test_a_required_stage_can_be_waived(flow_project: Path) -> None:
    _put(flow_project, VALID)
    set_state(flow_project, required_stages=["dialectic"], waivers=[
        {"stage": "dialectic", "by": "Ada Lovelace", "at": "2026-01-01", "why": "later",
         "expires": "2999-01-01"}
    ])
    assert stages(jcli(flow_project, "flow", "status", "--json"))["dialectic"]["status"] == "waived"


def test_status_output_is_deterministic(flow_project: Path) -> None:
    _put(flow_project, VALID)
    assert (
        cli(flow_project, "flow", "status", "--json").stdout
        == cli(flow_project, "flow", "status", "--json").stdout
    )


def test_an_invalid_map_skips_the_stage(flow_project: Path) -> None:
    broken = _mutated(lambda d: _move(d, "m1").update(cites=["m1"]))
    _put(flow_project, broken)
    assert "dialectic" not in stages(jcli(flow_project, "flow", "status", "--json"))


# ---------------------------------------------------------------- state validation


def test_flow_schema_accepts_required_stages(flow_project: Path) -> None:
    data = yaml.safe_load((flow_project / "flow.yaml").read_text())
    data["required_stages"] = ["dialectic"]
    jsonschema.validate(data, STATE_SCHEMA)
    data["required_stages"] = ["map"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, STATE_SCHEMA)
    data["required_stages"] = ["dialectic", "dialectic"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, STATE_SCHEMA)


def test_flow_schema_allows_a_dialectic_waiver() -> None:
    waiver = STATE_SCHEMA["definitions"]["waiver"]["properties"]["stage"]["enum"]
    assert waiver.index("dialectic") == waiver.index("frame") + 1


def test_status_schema_allows_advisory() -> None:
    item = STATUS_SCHEMA["properties"]["stages"]["items"]
    assert "advisory" in item["properties"]["status"]["enum"]


@pytest.mark.parametrize("value", ["dialectic", ["map"], [1], ["dialectic", "dialectic"]])
def test_flow_state_rejects_bad_required_stages(value) -> None:
    from scripts.article import flow
    data = flow.default_state()
    data["required_stages"] = value
    assert any("required_stages" in e for e in flow.state_errors(data))


def test_flow_state_accepts_good_required_stages() -> None:
    from scripts.article import flow
    data = flow.default_state()
    for value in ([], ["dialectic"]):
        data["required_stages"] = value
        assert flow.state_errors(data) == []


def test_flow_py_stays_host_neutral() -> None:
    text = (TEMPLATE / "scripts" / "article" / "flow.py").read_text().lower()
    assert "go-getter" not in text
