"""Terms section of the theses map (decision 0076): schema, lint and the tier 0 scan."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT, render, run

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SCHEMA = json.loads((TEMPLATE / "schemas" / "theses.schema.json").read_text())


def _modules():
    sys.path.insert(0, str(TEMPLATE))
    try:
        from scripts.article import terms, theses
    finally:
        sys.path.remove(str(TEMPLATE))
    return terms, theses


terms, theses = _modules()

TERM = {
    "id": "session-contract",
    "name": "session contract",
    "kind": "defined",
    "anchor": "def:sc",
    "status": "proposed",
}

DEFINITION = (
    "\\begin{definition}[Session contract]\\label{def:sc}\n"
    "A session contract binds the parties.\n"
    "\\end{definition}\n"
)


def _map(*term_overrides: dict) -> dict:
    items = [{**TERM, **o} for o in term_overrides] or [dict(TERM)]
    return {"version": 1, "nodes": [], "edges": [], "terms": items}


def _paper(tmp_path: Path, files: dict[str, str]) -> Path:
    sections = tmp_path / "paper" / "sections"
    sections.mkdir(parents=True)
    for name, text in files.items():
        (sections / name).write_text(text)
    return tmp_path


def _codes(report, severity: str = "warning") -> list[str]:
    return [d.code for d in report.diagnostics.items if d.severity == severity]


def _note_kinds(report) -> set[str]:
    return {n["kind"] for n in report.notes}


# ------------------------------------------------------------- schema and lint


def _structure(data: dict, labels: set[str] | None = None) -> dict[str, str]:
    found = theses.Diagnostics()
    theses.validate_map(data, labels, found)
    return {d.code: d.message for d in found.items if d.severity == "error"}


def test_a_valid_term_passes_schema_and_lint() -> None:
    data = _map({"children": [{"id": "item", "name": "an item"}], "match": "word",
                 "scope": ["02_methods.tex"], "forms": ["contracts"],
                 "senses": [{"anchor": "def:sc", "definition": "Narrow sense."}]})
    jsonschema.validate(data, SCHEMA)
    assert _structure(data, {"def:sc"}) == {}


def test_a_map_without_terms_is_unchanged() -> None:
    data = {"version": 1, "nodes": [], "edges": []}
    jsonschema.validate(data, SCHEMA)
    assert _structure(data) == {}


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda t: t.pop("anchor"), "T042"),
        (lambda t: t.update(kind="external"), "T042"),
        (lambda t: t.update(kind="acronym"), "T042"),
        (lambda t: t.update(kind="borrowed"), "T041"),
        (lambda t: t.update(match="fuzzy"), "T045"),
        (lambda t: t.update(forms="contract"), "T043"),
        (lambda t: t.update(scope=[""]), "T043"),
        (lambda t: t.update(author="bot"), "T044"),
        (lambda t: t.update(name="two\nlines"), "T040"),
        (lambda t: t.update(color="red"), "T002"),
        (lambda t: t.update(status="accepted"), "T012"),
        (lambda t: t.update(senses=[{"definition": "no anchor"}]), "T046"),
        (lambda t: t.update(children=[{"name": "no id"}]), "T048"),
    ],
)
def test_each_term_rule_has_a_failing_case(mutate, code) -> None:
    data = _map()
    mutate(data["terms"][0])
    assert code in _structure(data)


def test_kind_rules_each_pass_with_their_own_field() -> None:
    external = {"id": "ext", "name": "borrowed idea", "kind": "external",
                "source": "smith2020", "status": "proposed"}
    acronym = {"id": "sgd", "name": "SGD", "kind": "acronym",
               "expansion": "stochastic gradient descent", "status": "proposed"}
    data = {"version": 1, "nodes": [], "edges": [], "terms": [external, acronym]}
    jsonschema.validate(data, SCHEMA)
    assert _structure(data) == {}


def test_duplicate_term_ids_and_accepted_by_an_agent_are_errors() -> None:
    data = _map({}, {"status": "accepted", "accepted-by": "the review agent", "id": "other"})
    data["terms"][1]["id"] = "session-contract"
    errors = _structure(data)
    assert "T039" in errors and "T013" in errors


def test_dangling_anchor_is_an_error_only_when_labels_are_known() -> None:
    data = _map({"senses": [{"anchor": "def:gone"}]})
    assert _structure(data, None) == {}
    errors = _structure(data, {"def:sc"})
    assert errors.keys() == {"T047"} and "def:gone" in errors["T047"]
    assert "T047" in _structure(_map({"anchor": "def:missing"}), {"def:sc"})


# ------------------------------------------------------------ use before definition


def test_use_before_definition_warns_once_with_the_count(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "The session contract matters.\n\nThe session contract again.\n",
        "02_methods.tex": DEFINITION,
    })
    report = terms.check(root, _map())
    assert _codes(report) == ["T060"]
    message = report.diagnostics.warnings[0].message
    assert "paper/sections/01_intro.tex:1" in message and "1 more" in message


def test_use_before_definition_is_an_error_once_the_term_is_accepted(tmp_path: Path) -> None:
    root = _paper(tmp_path, {"01_intro.tex": "A session contract.\n", "02_m.tex": DEFINITION})
    data = _map({"status": "accepted", "accepted-by": "Ada Lovelace"})
    assert _codes(terms.check(root, data), "error") == ["T060"]


def test_a_sentence_that_refs_the_anchor_is_exempt(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "The session contract (Definition~\\ref{def:sc}) is defined later.\n",
        "02_m.tex": DEFINITION,
    })
    assert _codes(terms.check(root, _map())) == []


def test_use_after_definition_and_inside_it_is_fine(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": DEFINITION + "Later a session contract is used.\n",
    })
    assert _codes(terms.check(root, _map())) == []


def test_a_form_in_a_non_prose_context_is_not_a_use(tmp_path: Path) -> None:
    hidden = (
        "% a session contract in a comment\n"
        "Math $session contract$ and \\(session contract\\).\n"
        "\\begin{equation}\nsession contract\n\\end{equation}\n"
        "\\begin{verbatim}\nsession contract\n\\end{verbatim}\n"
        "\\begin{lstlisting}\nsession contract\n\\end{lstlisting}\n"
        "\\begin{quote}\nA session contract, quoted.\n\\end{quote}\n"
        "He wrote ``a session contract'' and \\verb|session contract|.\n"
        "See \\ref{session contract} and \\label{session contract}.\n"
        "% ABSTRACT:START\nThe session contract in a generated block.\n% ABSTRACT:END\n"
        "A 100\\% sure thing % session contract\n"
    )
    root = _paper(tmp_path, {"01_intro.tex": hidden, "02_m.tex": DEFINITION})
    assert _codes(terms.check(root, _map())) == []


def test_a_plural_and_any_case_count_as_a_use(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "Several Session Contracts hold.\n",
        "02_m.tex": DEFINITION,
    })
    assert _codes(terms.check(root, _map())) == ["T060"]


def test_matching_is_whole_word(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "A pre-session contract and session contractor.\n",
        "02_m.tex": DEFINITION,
    })
    assert _codes(terms.check(root, _map())) == []


def test_a_single_word_term_is_phrase_only_by_default(tmp_path: Path) -> None:
    files = {
        "01_intro.tex": "A contract is mentioned casually.\n",
        "02_m.tex": "\\begin{definition}\\label{def:sc}A contract.\\end{definition}\n",
    }
    root = _paper(tmp_path, files)
    word = {"id": "contract", "name": "contract"}
    assert _codes(terms.check(root, _map(word))) == []
    assert _codes(terms.check(root, _map({**word, "match": "word"}))) == ["T060"]


def test_a_scope_enables_single_words_inside_the_listed_sections_only(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "A contract in the introduction.\n",
        "02_m.tex": "A contract in the methods.\n",
        "03_def.tex": "\\begin{definition}\\label{def:sc}A contract.\\end{definition}\n",
    })
    data = _map({"id": "contract", "name": "contract", "scope": ["02_m.tex"]})
    report = terms.check(root, data)
    assert _codes(report) == ["T060"]
    assert "02_m.tex:1" in report.diagnostics.warnings[0].message


def test_listed_forms_and_children_are_searched(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "An agreement is meant, and one sub clause too.\n",
        "02_m.tex": DEFINITION,
    })
    data = _map({"forms": ["session agreement", "agreement"], "match": "word",
                 "children": [{"id": "clause", "name": "sub clause"}]})
    assert _codes(terms.check(root, data)) == ["T060"]


def test_only_defined_terms_are_checked_for_use_before_definition(tmp_path: Path) -> None:
    root = _paper(tmp_path, {"01_intro.tex": "The borrowed idea appears.\n"})
    data = _map({"id": "ext", "name": "borrowed idea", "kind": "external",
                 "source": "smith2020"})
    del data["terms"][0]["anchor"]
    assert _codes(terms.check(root, data)) == []


def test_a_section_anchor_defines_the_term_for_its_whole_span(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_intro.tex": "A session contract.\n",
        "02_m.tex": "\\section{Contracts}\\label{sec:c}\nA session contract here.\n",
    })
    assert _codes(terms.check(root, _map({"anchor": "sec:c"}))) == ["T060"]
    root2 = _paper(tmp_path / "again", {
        "01_intro.tex": "\\section{Contracts}\\label{sec:c}\nA session contract here.\n",
    })
    assert _codes(terms.check(root2, _map({"anchor": "sec:c"}))) == []


def test_a_retired_term_is_skipped(tmp_path: Path) -> None:
    root = _paper(tmp_path, {"01_intro.tex": "A session contract.\n", "02_m.tex": DEFINITION})
    assert terms.check(root, _map({"status": "retired"})).diagnostics.items == []


# ----------------------------------------------------- second site, gaps, notes


def test_a_second_defining_site_is_a_warning(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": DEFINITION,
        "02_m.tex": "\\begin{definition}[Session Contract]\\label{def:again}\n"
                    "Restated slightly.\n\\end{definition}\n",
    })
    report = terms.check(root, _map())
    assert _codes(report) == ["T061"] and report.gaps == []
    assert "02_m.tex" in report.diagnostics.warnings[0].path


def test_an_emphasised_form_inside_another_definition_is_a_second_site(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": DEFINITION,
        "02_m.tex": "\\begin{definition}\\label{def:x}\nA \\emph{session contract} again.\n"
                    "\\end{definition}\n",
    })
    assert _codes(terms.check(root, _map())) == ["T061"]


def test_an_emphasis_outside_a_definition_environment_defines_nothing(tmp_path: Path) -> None:
    root = _paper(tmp_path, {"01_m.tex": DEFINITION + "A \\emph{session contract} here.\n"})
    report = terms.check(root, _map())
    assert _codes(report) == [] and report.gaps == []


def test_an_unregistered_definition_is_a_gap(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": DEFINITION
        + "\\begin{definition}[Quorum]\\label{def:quorum}\nEnough members.\n"
        "\\end{definition}\n"
        + "\\begin{definition}\nA nameless one without a label.\n\\end{definition}\n",
    })
    report = terms.check(root, _map())
    assert report.gaps == [
        {"kind": "term-unregistered", "id": "def:quorum", "text": "Quorum"},
        {"kind": "term-unregistered", "id": "paper/sections/01_m.tex:7",
         "text": "A nameless one without a label."},
    ]


def test_a_definition_inside_a_registered_section_or_sense_is_registered(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": "\\section{Contracts}\\label{sec:c}\n"
        "\\begin{definition}[Other]\\label{def:other}\nBody.\n\\end{definition}\n"
        "\\section{Next}\n" + DEFINITION.replace("def:sc", "def:alt"),
    })
    data = _map({"anchor": "sec:c", "senses": [{"anchor": "def:alt"}]})
    assert terms.check(root, data).gaps == []


def test_an_orphan_term_is_a_note_and_a_used_one_is_not(tmp_path: Path) -> None:
    root = _paper(tmp_path, {"01_m.tex": DEFINITION})
    assert "term-orphan" in _note_kinds(terms.check(root, _map()))
    root2 = _paper(tmp_path / "used", {"01_m.tex": DEFINITION + "A session contract binds.\n"})
    assert "term-orphan" not in _note_kinds(terms.check(root2, _map()))


def test_an_orphan_uses_every_form_even_under_phrase_only(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": "\\begin{definition}\\label{def:sc}A contract.\\end{definition}\n"
                    "Later the contract is used.\n",
    })
    report = terms.check(root, _map({"id": "contract", "name": "contract"}))
    assert "term-orphan" not in _note_kinds(report)


def test_case_drift_is_a_note_naming_the_surface_form(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": DEFINITION
        + "Each Session Contract differs. A session contract is plain.\n",
    })
    notes = [n for n in terms.check(root, _map()).notes if n["kind"] == "term-drift"]
    assert len(notes) == 1
    assert "'Session Contract'" in notes[0]["text"] and "'session contract'" not in notes[0]["text"]


def test_an_unlisted_plural_is_drift_but_the_definition_itself_is_not(tmp_path: Path) -> None:
    root = _paper(tmp_path, {"01_m.tex": DEFINITION + "Several session contracts vary.\n"})
    notes = [n for n in terms.check(root, _map()).notes if n["kind"] == "term-drift"]
    assert len(notes) == 1 and "'session contracts'" in notes[0]["text"]
    assert "'Session contract'" not in notes[0]["text"]


def test_listed_plurals_and_a_capitalised_sentence_start_are_not_drift(tmp_path: Path) -> None:
    root = _paper(tmp_path, {
        "01_m.tex": DEFINITION + "Session contracts vary.\n\nSession contract again.\n"
                    "We note session contracts and \\item Session contract.\n",
    })
    report = terms.check(root, _map({"forms": ["session contracts"]}))
    assert "term-drift" not in _note_kinds(report)


# ----------------------------------------------------------------------- the CLI


def test_the_cli_reports_lint_gaps_and_notes(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    sections = project / "paper" / "sections"
    (sections / "01_introduction.tex").write_text(
        "A session contract is used early.\n"
        "\\begin{definition}[Quorum]\\label{def:quorum}Enough.\\end{definition}\n"
    )
    (sections / "02_methods.tex").write_text(DEFINITION)
    (project / "theses.yaml").write_text(yaml.safe_dump(_map()))

    lint = run(project, "python3", "-m", "scripts.article", "theses", "lint", "--json")
    assert lint.returncode == 0, lint.stderr
    assert [d["code"] for d in json.loads(lint.stdout)["diagnostics"]] == ["T060"]

    gaps = run(project, "python3", "-m", "scripts.article", "theses", "gaps")
    assert gaps.returncode == 1
    assert {"kind": "term-unregistered", "id": "def:quorum", "text": "Quorum"} in (
        json.loads(gaps.stdout)["gaps"]
    )
    only = run(project, "python3", "-m", "scripts.article", "theses", "gaps",
               "--kind", "single-source")
    assert only.returncode == 0

    notes = run(project, "python3", "-m", "scripts.article", "theses", "terms")
    body = json.loads(notes.stdout)
    assert body["command"] == "theses terms" and body["gaps"]
    assert {n["kind"] for n in body["notes"]} <= {"term-orphan", "term-drift"}


def test_a_bad_term_fails_theses_lint_before_the_scan(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    data = _map()
    data["terms"][0]["anchor"] = "def:missing"
    (project / "theses.yaml").write_text(yaml.safe_dump(copy.deepcopy(data)))
    result = run(project, "python3", "-m", "scripts.article", "theses", "lint", "--json")
    assert result.returncode == 1
    assert [d["code"] for d in json.loads(result.stdout)["diagnostics"]] == ["T047"]
