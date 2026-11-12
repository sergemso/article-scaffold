"""``theses lint | gaps | slice | accept`` and the guardrail they enforce."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import render, run

MAP = """\
# Theses map (test fixture)
version: 1
nodes:
  # the central claim
  - id: t1
    type: thesis
    text: Main claim.
    status: proposed
  - id: t2   # unsupported thesis
    type: thesis
    text: Lonely claim.
    status: proposed
  - id: t3
    type: thesis
    text: Single-sourced claim.
    status: proposed
  - id: o1
    type: objection
    text: Objection one.
    status: proposed
  - id: o2
    type: objection
    text: Objection two.
    status: proposed
  - id: d1
    type: defense
    text: Defense of one.
    status: proposed
  - id: s1
    type: source-claim
    text: Smith says X.
    status: proposed
    quote: X holds
    locator: p. 3
    bib_keys: [smith2020]
    anchor: null
  - id: s2
    type: source-claim
    text: Smith again.
    status: proposed
    quote: Y holds
    locator: p. 4
    bib_keys:
      - smith2020
  - id: h1
    type: hypothesis
    text: Anchored guess.
    status: proposed
    anchor: sec:gone
edges:
  - {from: o1, to: t1, type: attacks}
  - {from: d1, to: o1, type: rebuts}
  - {from: s1, to: t3, type: supports}
  - {from: s2, to: t3, type: supports}
  - {from: s1, to: t1, type: supports}
  - {from: s1, to: h1, type: supports}
"""


def _cli(project: Path, *args: str):
    return run(project, "python3", "-m", "scripts.article", *args)


def _setup(tmp_path: Path, text: str = MAP, labels: str = "") -> Path:
    project = render(tmp_path=tmp_path)
    (project / "theses.yaml").write_text(text)
    if labels:
        section = project / "paper" / "sections" / "01_introduction.tex"
        section.write_text(section.read_text() + labels)
    return project


def _json(result) -> dict:
    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout)


def _gaps(project: Path, *extra: str) -> list[dict]:
    result = _cli(project, "theses", "gaps", *extra)
    return _json(result)["gaps"]


def test_lint_clean_and_dirty(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels="\n\\label{sec:gone}\n")
    result = _cli(project, "theses", "lint")
    assert result.returncode == 0, result.stderr
    (project / "theses.yaml").write_text(MAP.replace("to: t3", "to: nope", 1))
    result = _cli(project, "theses", "lint", "--json")
    assert result.returncode == 1
    assert any(i["code"] == "T016" for i in _json(result)["diagnostics"])


def test_each_gap_kind(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    found = {(g["kind"], g["id"]) for g in _gaps(project, "--kind", "thesis-unattacked")
             + _gaps(project)}
    assert ("thesis-unsupported", "t2") in found
    assert ("thesis-unsupported", "t1") not in found
    assert ("objection-undefended", "o2") in found
    assert ("objection-undefended", "o1") not in found
    assert ("single-source", "t3") in found  # two nodes, one source
    assert ("single-source", "t1") in found
    assert ("anchor-missing", "h1") in found
    assert ("thesis-unattacked", "t1") in found  # o1 is only proposed


def test_gaps_exit_code_kind_filter_and_output_is_small(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    result = _cli(project, "theses", "gaps")
    assert result.returncode == 1
    payload = _json(result)
    assert payload["ok"] is False
    assert all(set(g) == {"kind", "id", "text"} for g in payload["gaps"])
    assert "X holds" not in result.stdout  # source text never appears
    kinds = [g["kind"] for g in payload["gaps"]]
    assert kinds == sorted(kinds)
    only = _cli(project, "theses", "gaps", "--kind", "anchor-missing")
    assert [g["id"] for g in _json(only)["gaps"]] == ["h1"]


def test_gaps_clean_map_exits_zero(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _cli(project, "theses", "gaps")
    assert result.returncode == 0
    assert _json(result)["gaps"] == []


def test_slice_depth_and_stable_order(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    one = _json(_cli(project, "theses", "slice", "o1"))
    assert [n["id"] for n in one["nodes"]] == ["d1", "o1", "t1"]
    assert "quote" not in json.dumps(one)
    two = _json(_cli(project, "theses", "slice", "o1", "--depth", "2"))
    assert [n["id"] for n in two["nodes"]] == ["d1", "o1", "s1", "t1"]
    zero = _json(_cli(project, "theses", "slice", "o1", "--depth", "0"))
    assert [n["id"] for n in zero["nodes"]] == ["o1"] and zero["edges"] == []
    again = _cli(project, "theses", "slice", "o1", "--depth", "2")
    assert json.loads(again.stdout) == two
    missing = _cli(project, "theses", "slice", "nope")
    assert missing.returncode == 1 and _json(missing)["ok"] is False


def test_accept_proposed_node_preserves_the_rest(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels="\n\\label{sec:gone}\n")
    result = _cli(project, "theses", "accept", "t2", "--by", "Ada Lovelace")
    assert result.returncode == 0, result.stderr + result.stdout
    assert _json(result)["changed"] is True
    new = (project / "theses.yaml").read_text()
    expected = MAP.replace(
        "  - id: t2   # unsupported thesis\n    type: thesis\n    text: Lonely claim.\n"
        "    status: proposed\n",
        "  - id: t2   # unsupported thesis\n    type: thesis\n    text: Lonely claim.\n"
        '    status: accepted\n    accepted-by: "Ada Lovelace"\n',
    )
    assert new == expected
    assert _cli(project, "theses", "lint").returncode == 0


def test_accept_node_ending_in_a_list_and_at_end_of_file(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels="\n\\label{sec:gone}\n")
    assert _cli(project, "theses", "accept", "s2", "--by", "Ada").returncode == 0
    text = (project / "theses.yaml").read_text()
    assert "      - smith2020\n    accepted-by: \"Ada\"\n  - id: h1" in text
    assert _cli(project, "theses", "lint").returncode == 0
    trailing = _setup(tmp_path / "b", text="version: 1\nnodes:\n  - id: z\n    type: thesis\n"
                      "    text: Z.\n    status: proposed\nedges: []")
    assert _cli(trailing, "theses", "accept", "z", "--by", "Ada").returncode == 0
    assert _cli(trailing, "theses", "lint").returncode == 0


@pytest.mark.parametrize("name", ["red-team", "Claude", "blue team agent", "gpt-5", "LLM"])
def test_accept_refuses_agent_names(tmp_path: Path, name: str) -> None:
    project = _setup(tmp_path)
    before = (project / "theses.yaml").read_text()
    result = _cli(project, "theses", "accept", "t2", "--by", name)
    assert result.returncode == 1
    assert "agent role" in _json(result)["error"]
    assert (project / "theses.yaml").read_text() == before


def test_accept_is_idempotent_and_does_not_overwrite_another_person(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    assert _cli(project, "theses", "accept", "t2", "--by", "Ada").returncode == 0
    first = (project / "theses.yaml").read_text()
    again = _cli(project, "theses", "accept", "t2", "--by", "Ada")
    assert again.returncode == 0 and _json(again)["changed"] is False
    assert (project / "theses.yaml").read_text() == first
    other = _cli(project, "theses", "accept", "t2", "--by", "Grace")
    assert other.returncode == 1
    assert (project / "theses.yaml").read_text() == first


def test_accept_unknown_and_retired_nodes_are_refused(tmp_path: Path) -> None:
    project = _setup(tmp_path, MAP.replace("text: Lonely claim.\n    status: proposed",
                                           "text: Lonely claim.\n    status: retired"))
    assert _cli(project, "theses", "accept", "nope", "--by", "Ada").returncode == 1
    assert _cli(project, "theses", "accept", "t2", "--by", "Ada").returncode == 1


def test_lint_flags_agent_acceptance_and_missing_accepted_by(tmp_path: Path) -> None:
    project = _setup(tmp_path)
    text = MAP.replace("text: Lonely claim.\n    status: proposed",
                       "text: Lonely claim.\n    status: accepted")
    (project / "theses.yaml").write_text(text)
    result = _cli(project, "theses", "lint", "--json")
    assert any(i["code"] == "T012" for i in _json(result)["diagnostics"])
    text = text.replace("status: accepted", "status: accepted\n    accepted-by: red-team")
    (project / "theses.yaml").write_text(text)
    result = _cli(project, "theses", "lint", "--json")
    assert any(i["code"] == "T013" for i in _json(result)["diagnostics"])


# ------------------------------ theses add and accept for contradictions and moves (0084)

CONTRADICTION = {
    "id": "c1", "text": "X holds and X fails.", "kind": "dialectical", "author": "agent",
    "poles": [{"text": "X holds", "claim": "s1"}, {"text": "X fails", "claim": "s2"}],
}
MOVE = {"id": "m1", "type": "negation", "text": "Deny one pole.", "author": "agent",
        "cites": ["c1"]}


LABELS = "\n\\label{sec:gone}\n"


def _add(project: Path, tmp_path: Path, payload, section: str):
    path = tmp_path / f"{section}.json"
    path.write_text(json.dumps(payload))
    return _cli(project, "theses", "add", "--section", section, "--file", str(path))


def test_add_contradiction_and_move_round_trip(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    before = (project / "theses.yaml").read_text()
    added = _add(project, tmp_path, CONTRADICTION, "contradictions")
    assert added.returncode == 0, added.stderr + added.stdout
    assert _json(added) == {"ok": True, "command": "theses add", "section": "contradictions",
                            "added": ["c1"]}
    after = (project / "theses.yaml").read_text()
    assert after.startswith(before)  # only lines were appended
    assert 'contradictions:\n  - id: "c1"\n' in after
    assert '    poles:\n      - text: "X holds"\n        claim: "s1"\n' in after
    assert '    status: "proposed"\n' in after
    assert _cli(project, "theses", "lint").returncode == 0
    assert _add(project, tmp_path, [MOVE], "moves").returncode == 0
    assert '    cites:\n      - "c1"\n' in (project / "theses.yaml").read_text()
    assert _cli(project, "theses", "lint").returncode == 0
    view = _json(_cli(project, "theses", "dialectic", "--json"))
    assert [c["id"] for c in view["contradictions"]] == ["c1"]
    assert view["contradictions"][0]["moved-by"] == ["m1"]


def test_accept_a_contradiction_and_a_move(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    assert _add(project, tmp_path, CONTRADICTION, "contradictions").returncode == 0
    assert _add(project, tmp_path, MOVE, "moves").returncode == 0
    before = (project / "theses.yaml").read_text()
    for item in ("c1", "m1"):
        result = _cli(project, "theses", "accept", item, "--by", "Ada Lovelace")
        assert result.returncode == 0, result.stderr + result.stdout
        assert _json(result)["changed"] is True
    after = (project / "theses.yaml").read_text()
    quoted = 'accepted-by: "Ada Lovelace"'
    assert after.count(quoted) == before.count(quoted) + 2
    assert after.count("status: accepted") == before.count("status: accepted") + 2
    assert _cli(project, "theses", "lint").returncode == 0
    changed = [line for line in after.splitlines() if line not in before.splitlines()]
    assert all("accepted" in line for line in changed), changed
    again = _cli(project, "theses", "accept", "m1", "--by", "Ada Lovelace")
    assert _json(again)["changed"] is False


@pytest.mark.parametrize("name", ["red-team", "dialectic agent"])
def test_accept_a_move_refuses_an_agent_name(tmp_path: Path, name: str) -> None:
    project = _setup(tmp_path, labels=LABELS)
    assert _add(project, tmp_path, CONTRADICTION, "contradictions").returncode == 0
    before = (project / "theses.yaml").read_text()
    result = _cli(project, "theses", "accept", "c1", "--by", name)
    assert result.returncode == 1 and "agent role" in _json(result)["error"]
    assert (project / "theses.yaml").read_text() == before


def test_add_appends_to_an_existing_section_without_touching_it(tmp_path: Path) -> None:
    head = MAP + (
        "contradictions:\n"
        "  - id: c0   # kept as written\n    kind: physical\n    status: proposed\n"
        "    author: human\n    poles:\n"
        "      - {text: Be open, niche: Data should be shared}\n"
        "      - {text: Be closed, niche: Data should be private}\n"
    )
    project = _setup(tmp_path, text=head, labels=LABELS)
    assert _cli(project, "theses", "lint").returncode == 0
    assert _add(project, tmp_path, CONTRADICTION, "contradictions").returncode == 0
    after = (project / "theses.yaml").read_text()
    assert after.startswith(head)
    assert after.count("- id:") == head.count("- id:") + 1
    assert _cli(project, "theses", "lint").returncode == 0


def test_add_refuses_what_would_not_validate_and_writes_nothing(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    before = (project / "theses.yaml").read_text()
    bad = {**CONTRADICTION, "poles": [CONTRADICTION["poles"][0]]}  # one pole: T079
    result = _add(project, tmp_path, bad, "contradictions")
    assert result.returncode == 1 and "validate" in _json(result)["error"]
    assert (project / "theses.yaml").read_text() == before
    accepted = _add(project, tmp_path, {**CONTRADICTION, "status": "accepted"}, "contradictions")
    assert accepted.returncode == 1 and "proposed" in _json(accepted)["error"]
    assert (project / "theses.yaml").read_text() == before
    assert _cli(project, "theses", "add", "--section", "edges", "--file", "x").returncode == 2


def test_add_to_nodes_keeps_the_flat_quoted_form(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    objection = {"id": "o9", "type": "objection", "text": "A new objection."}
    assert _add(project, tmp_path, objection, "nodes").returncode == 0
    text = (project / "theses.yaml").read_text()
    assert '  - id: "o9"\n    type: "objection"\n    text: "A new objection."\n' \
           '    status: "proposed"\n' in text
    assert _cli(project, "theses", "lint").returncode == 0


# ------------------------------------- acceptance records, T096 and --because (0085)


def _accept_entries(project: Path) -> list[Path]:
    return sorted((project / "docs" / "ledger" / "accept").rglob("*.json")) if (
        project / "docs" / "ledger" / "accept"
    ).is_dir() else []


def _entries_without_provenance(project: Path) -> list[Path]:
    return [p for p in _accept_entries(project) if ".prov." not in p.name]


def test_accept_records_the_acceptance_in_the_ledger(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    result = _cli(project, "theses", "accept", "t2", "--by", "Ada Lovelace")
    assert result.returncode == 0, result.stderr + result.stdout
    assert _json(result)["changed"] is True and _json(result)["recorded"] == "created"
    entries = _entries_without_provenance(project)
    assert len(entries) == 1
    entry = json.loads(entries[0].read_text())
    assert entry["kind"] == "accept" and set(entry["inputs"]) == {"node", "text"}
    assert entry["result"]["by"] == "Ada Lovelace" and "because" not in entry["result"]
    again = _cli(project, "theses", "accept", "t2", "--by", "Ada Lovelace")
    assert _json(again) == {"ok": True, "command": "theses accept", "id": "t2",
                            "changed": False, "recorded": "exists"}
    assert len(_entries_without_provenance(project)) == 1


def test_changed_accepted_text_is_t096_until_reaccepted_with_a_cause(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    assert _cli(project, "theses", "accept", "t2", "--by", "Ada").returncode == 0
    assert _cli(project, "theses", "lint").returncode == 0
    path = project / "theses.yaml"
    path.write_text(path.read_text().replace("text: Lonely claim.", "text: Lonely claim, revised."))
    lint = _cli(project, "theses", "lint", "--json")
    assert lint.returncode == 1
    codes = [d["code"] for d in _json(lint)["diagnostics"]]
    assert codes == ["T096"]
    assert "theses accept t2 --by NAME --because <id>" in _json(lint)["diagnostics"][0]["message"]
    refused = _cli(project, "theses", "accept", "t2", "--by", "Ada")
    assert refused.returncode == 1 and "--because" in _json(refused)["error"]
    unknown = _cli(project, "theses", "accept", "t2", "--by", "Ada", "--because", "ghost")
    assert unknown.returncode == 1 and "ghost" in _json(unknown)["error"]
    wrong_type = _cli(project, "theses", "accept", "t2", "--by", "Ada", "--because", "t1")
    assert wrong_type.returncode == 1
    fixed = _cli(project, "theses", "accept", "t2", "--by", "Ada", "--because", "o1")
    assert fixed.returncode == 0, fixed.stderr + fixed.stdout
    assert _json(fixed)["changed"] is False and _json(fixed)["recorded"] == "created"
    assert _cli(project, "theses", "lint").returncode == 0
    entries = [json.loads(p.read_text()) for p in _entries_without_provenance(project)]
    assert len(entries) == 2
    assert sorted(e["result"].get("because", "") for e in entries) == ["", "o1"]


LEGACY = MAP.replace(
    "  - id: t1\n    type: thesis\n    text: Main claim.\n    status: proposed\n",
    "  - id: t1\n    type: thesis\n    text: Main claim.\n    status: accepted\n"
    "    accepted-by: Ada\n",
    1,
)


def test_a_legacy_accepted_node_is_a_note_not_an_error(tmp_path: Path) -> None:
    project = _setup(tmp_path, text=LEGACY, labels=LABELS)  # accepted by hand, no ledger
    assert "status: accepted" in (project / "theses.yaml").read_text()
    lint = _cli(project, "theses", "lint", "--json")
    assert lint.returncode == 0
    payload = _json(lint)
    assert payload["ok"] is True and payload["diagnostics"] == []
    assert [n["id"] for n in payload["notes"]] == ["t1"]
    assert "theses accept t1 --by NAME" in payload["notes"][0]["message"]
    text = _cli(project, "theses", "lint")
    assert text.returncode == 0 and "note N096" in text.stderr and "t1" in text.stderr
    assert _cli(project, "theses", "accept", "t1", "--by", "Ada").returncode == 0
    assert _json(_cli(project, "theses", "lint", "--json"))["notes"] == []


def test_acceptance_of_a_contradiction_is_recorded_against_its_poles(tmp_path: Path) -> None:
    project = _setup(tmp_path, labels=LABELS)
    poles_only = {k: v for k, v in CONTRADICTION.items() if k != "text"}
    assert _add(project, tmp_path, poles_only, "contradictions").returncode == 0
    assert _cli(project, "theses", "accept", "c1", "--by", "Ada").returncode == 0
    assert _json(_cli(project, "theses", "lint", "--json"))["diagnostics"] == []
    path = project / "theses.yaml"
    path.write_text(path.read_text().replace('text: "X fails"', 'text: "X never holds"'))
    assert [d["code"] for d in _json(_cli(project, "theses", "lint", "--json"))["diagnostics"]] == [
        "T096"
    ]


def test_ledger_off_skips_acceptance_records(tmp_path: Path, monkeypatch) -> None:
    import sys

    from conftest import ROOT

    project = _setup(tmp_path, text=LEGACY, labels=LABELS)
    monkeypatch.setenv("ARTICLE_LEDGER", "off")
    sys.path.insert(0, str(ROOT / "{{cookiecutter.repo_name}}"))
    try:
        from scripts.article import theses
        from scripts.article.diagnostics import Diagnostics

        outcome = theses.accept(project, "t2", "Ada")
        assert outcome == {"changed": True, "recorded": "skipped"}
        assert _entries_without_provenance(project) == []
        found = Diagnostics()
        notes = theses.acceptance_check(project, theses.load_map(project), found)
        assert found.ok and notes == []  # t1 accepted by hand: no note while the ledger is off
    finally:
        sys.path.remove(str(ROOT / "{{cookiecutter.repo_name}}"))
