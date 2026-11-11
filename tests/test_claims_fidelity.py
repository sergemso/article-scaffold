"""Source-claim edition, translation and context fields: schema, lint and tier 1 (0075)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import ROOT, render, run

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
SCHEMA = json.loads((TEMPLATE / "schemas" / "theses.schema.json").read_text())
RESULT_SCHEMA = json.loads((TEMPLATE / "schemas" / "claims-result.schema.json").read_text())

FIRST = "Chapter 1\n\nThe first edition says the contract holds.\n"
SECOND = "Chapter 1\n\nThe second edition says the contract holds under load.\n"
GERMAN = "Der Vertrag gilt.\n"


def _cli(project: Path, *args: str):
    return run(project, "python3", "-m", "scripts.article", *args)


def _claim(node_id: str = "c1", quote: str = "the contract holds", **extra: object) -> dict:
    node = {
        "id": node_id, "type": "source-claim", "text": "The book says the contract holds.",
        "status": "proposed", "quote": quote, "locator": "p. 3", "bib_keys": ["smith2020"],
    }
    node.update(extra)
    return node


def _project(tmp_path: Path, nodes: list[dict], files: dict[str, str] | None = None) -> Path:
    project = render(tmp_path=tmp_path)
    data = {"version": 1, "nodes": nodes, "edges": []}
    (project / "theses.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    sources = project / "paper" / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    for name, text in (files or {}).items():
        (sources / name).write_text(text, encoding="utf-8")
    return project


def _check(project: Path, node_id: str = "c1") -> dict:
    result = _cli(project, "claims", "quote-check", node_id)
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, RESULT_SCHEMA)
    return payload["results"][0]


def _lint(project: Path) -> dict:
    return json.loads(_cli(project, "theses", "lint", "--json").stdout)


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["diagnostics"] if item["severity"] == "error"}


# --------------------------------------------------------------- editions


def test_a_string_locator_still_reads_the_bib_key_file(tmp_path: Path) -> None:
    project = _project(tmp_path, [_claim()], {"smith2020.txt": FIRST})
    record = _check(project)
    assert record["verdict"] == "found" and record["locator"] == "p. 3"
    assert "edition" not in record


def test_a_named_edition_reads_that_editions_file(tmp_path: Path) -> None:
    node = _claim(quote="under load", locator={"edition": "smith2020-2", "page": 7})
    project = _project(
        tmp_path, [node], {"smith2020.txt": FIRST, "smith2020-2.txt": SECOND}
    )
    record = _check(project)
    assert record["verdict"] == "found"
    assert record["source"] == "paper/sources/smith2020-2.txt"
    assert record["edition"] == "smith2020-2"
    assert record["locator"] == "ed. smith2020-2, p. 7"


def test_the_first_edition_does_not_satisfy_a_quote_from_the_second(tmp_path: Path) -> None:
    node = _claim(quote="under load", locator={"edition": "smith2020-1"})
    project = _project(tmp_path, [node], {"smith2020-1.txt": FIRST})
    assert _check(project)["verdict"] == "not-found"


def test_a_missing_edition_is_listed_and_no_other_file_is_guessed(tmp_path: Path) -> None:
    node = _claim(locator={"edition": "smith2020-3"})
    project = _project(tmp_path, [node], {"smith2020.txt": FIRST})
    record = _check(project)
    assert record["verdict"] == "no-local-text"
    assert record["missing_editions"] == ["smith2020-3"]
    assert "source" not in record


def test_edition_map_lists_editions_without_a_file(tmp_path: Path) -> None:
    node = _claim(**{"edition-map": {"smith2020-2": "p. 9", "smith2020-4": "p. 11"}})
    project = _project(tmp_path, [node], {"smith2020.txt": FIRST, "smith2020-2.txt": SECOND})
    record = _check(project)
    assert record["verdict"] == "found"
    assert record["missing_editions"] == ["smith2020-4"]


def test_a_manifest_row_names_the_editions_file(tmp_path: Path) -> None:
    node = _claim(locator={"edition": "second"})
    project = _project(
        tmp_path, [node],
        {"MANIFEST.md": "- second: smith-reprint.txt\n", "smith-reprint.txt": FIRST},
    )
    assert _check(project)["source"] == "paper/sources/smith-reprint.txt"


# ------------------------------------------------------------ translation


def test_a_translation_with_a_local_original_matches_the_original_quote(tmp_path: Path) -> None:
    node = _claim(translation={
        "original": "smith2020-de", "translator": "Ada", "original-quote": "Der Vertrag gilt",
        "load-bearing-terms": ["Vertrag"],
    })
    project = _project(tmp_path, [node], {"smith2020.txt": FIRST, "smith2020-de.txt": GERMAN})
    record = _check(project)
    assert record["original"] == "found" and "advice" not in record


def test_a_translation_with_a_changed_original_quote_is_reported_and_fails(
    tmp_path: Path,
) -> None:
    node = _claim(translation={"original": "smith2020-de", "original-quote": "Der Vertrag fällt"})
    project = _project(tmp_path, [node], {"smith2020.txt": FIRST, "smith2020-de.txt": GERMAN})
    result = _cli(project, "claims", "quote-check", "c1")
    assert result.returncode == 1
    assert json.loads(result.stdout)["results"][0]["original"] == "not-found"


def test_a_translation_without_a_local_original_is_advice_only(tmp_path: Path) -> None:
    node = _claim(translation={"original": "smith2020-de", "original-quote": "Der Vertrag gilt"})
    project = _project(tmp_path, [node], {"smith2020.txt": FIRST})
    result = _cli(project, "claims", "quote-check", "c1")
    record = json.loads(result.stdout)["results"][0]
    assert result.returncode == 0
    assert record["verdict"] == "found"
    assert record["original"] == "unavailable" and record["advice"] == ["original-unavailable"]


def test_a_translation_with_no_original_named_is_unavailable(tmp_path: Path) -> None:
    node = _claim(translation={"translator": "Ada", "original-quote": "Der Vertrag gilt"})
    project = _project(tmp_path, [node], {"smith2020.txt": FIRST})
    assert _check(project)["original"] == "unavailable"


# ----------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    ("source", "quote", "how", "folds"),
    [
        ("The contract holds.", "The contract holds", "exact", None),
        ("The  contract\nholds.", "The contract holds", "normalised", ["whitespace"]),
        ("a well—known rule", "a well-known rule", "normalised", ["dashes"]),
        ("the “contract” holds", 'the "contract" holds', "normalised", ["quotes"]),
        ("the ﬁrst contract", "the first contract", "normalised", ["unicode"]),
        ("evalu-\nation", "evaluation", "normalised", ["whitespace", "dashes"]),
    ],
)
def test_the_match_report_names_the_normalisation_used(
    tmp_path: Path, source: str, quote: str, how: str, folds: list[str] | None
) -> None:
    project = _project(tmp_path, [_claim(quote=quote)], {"smith2020.txt": source + "\n"})
    match = _check(project)["match"]
    assert match["how"] == how
    assert match.get("folds") == folds


def test_ellipsis_segments_are_each_compared(tmp_path: Path) -> None:
    source = "The “first” part and, further on, the  second part.\n"
    quote = 'The "first" part ... the second part'
    project = _project(tmp_path, [_claim(quote=quote)], {"smith2020.txt": source})
    match = _check(project)["match"]
    assert match == {"how": "normalised", "folds": ["whitespace", "quotes"]}


def test_a_not_found_quote_has_no_match_report(tmp_path: Path) -> None:
    project = _project(tmp_path, [_claim(quote="nowhere")], {"smith2020.txt": FIRST})
    assert "match" not in _check(project)


# ------------------------------------------------------------ schema, lint

FULL = {
    "locator": {"edition": "smith2020-2", "page": 7, "section": "2.1"},
    "bib": "smith2020",
    "rests-on": "wording",
    "edition-map": {"smith2020-1": "p. 5"},
    "translation": {
        "original": "smith2020-de", "translator": "Ada", "original-quote": "Der Vertrag gilt",
        "load-bearing-terms": ["Vertrag"],
    },
    "context": {"stance": "reports", "scope-note": "Smith reports Jones.", "window": 400},
    "reading": "paraphrase",
}


def test_a_node_with_every_new_field_is_schema_valid_and_lints_clean(tmp_path: Path) -> None:
    node = _claim(**FULL)
    data = {"version": 1, "nodes": [node], "edges": []}
    jsonschema.validate(data, SCHEMA)
    project = _project(tmp_path, [node])
    assert _lint(project)["ok"] is True


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("locator", {}, "T050"),
        ("locator", {"edition": "smith2020", "chapter": "2"}, "T050"),
        ("locator", {"page": ""}, "T050"),
        ("locator", {"edition": "../theses"}, "T057"),
        ("rests-on", "vibes", "T051"),
        ("reading", "telepathic", "T052"),
        ("edition-map", {"smith2020-1": ""}, "T053"),
        ("edition-map", {"../x": "p. 1"}, "T057"),
        ("translation", {"translator": "Ada", "colour": "red"}, "T054"),
        ("translation", {"original": "a/b"}, "T057"),
        ("translation", {"load-bearing-terms": "Vertrag"}, "T054"),
        ("context", {"stance": "shouts"}, "T055"),
        ("context", {"window": -1}, "T055"),
        ("context", {"window": True}, "T055"),
        ("bib", "", "T056"),
    ],
)
def test_lint_rejects_malformed_fields(
    tmp_path: Path, field: str, value: object, code: str
) -> None:
    project = _project(tmp_path, [_claim(**{field: value})])
    assert code in _codes(_lint(project))


def test_the_schema_rejects_the_same_malformed_fields() -> None:
    for field, value in [
        ("locator", {}), ("locator", {"chapter": "2"}), ("rests-on", "vibes"),
        ("reading", "telepathic"), ("edition-map", {"../x": "p. 1"}),
        ("translation", {"colour": "red"}), ("context", {"window": -1}),
    ]:
        data = {"version": 1, "nodes": [_claim(**{field: value})], "edges": []}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, SCHEMA)


def test_the_new_fields_belong_to_source_claims_only(tmp_path: Path) -> None:
    thesis = {"id": "t1", "type": "thesis", "text": "A thesis.", "status": "proposed",
              "reading": "direct"}
    data = {"version": 1, "nodes": [thesis], "edges": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, SCHEMA)
    assert "T017" in _codes(_lint(_project(tmp_path, [thesis])))


def test_a_map_without_the_new_fields_is_unchanged(tmp_path: Path) -> None:
    node = copy.deepcopy(_claim())
    jsonschema.validate({"version": 1, "nodes": [node], "edges": []}, SCHEMA)
    assert _lint(_project(tmp_path, [node]))["ok"] is True
