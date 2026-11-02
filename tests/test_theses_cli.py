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
