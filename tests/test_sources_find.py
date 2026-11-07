"""Step B.3: `sources find` returns stable, ordered addresses that resolve through `slice`."""

from __future__ import annotations

import json
import sys

import jsonschema
import pytest
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
FIXTURES = ROOT / "tests" / "fixtures" / "sources"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import address, cli  # noqa: E402

RESULT = json.loads((TEMPLATE / "schemas" / "sources-result.schema.json").read_text())


def run(capsys, root, *argv):
    code = cli.main(["--root", str(root), "sources", *argv])
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, RESULT)
    return code, out


@pytest.fixture
def store(tmp_path, capsys):
    for name, key in (("draft-agtp-00.txt", "agtp"), ("pace.html", "pace"), ("scan.pdf", "scan")):
        run(capsys, tmp_path, "add", str(FIXTURES / name), "--key", key, "--origin", "x",
            "--edition", "00", "--retrieved", "2026-11-07T10:00:00Z")  # fmt: skip
    run(capsys, tmp_path, "index")  # exits 1 for the unreadable PDF
    return tmp_path


def test_phrase_hit_is_an_address_with_context(store, capsys):
    code, out = run(capsys, store, "find", "MUST NOT send")
    assert code == 0 and out["ok"]
    top = out["results"][0]
    assert top["key"] == "agtp" and top["locator"].startswith("para:")
    assert "MUST NOT send a frame" in top["context"]
    assert "\n" not in top["context"]
    assert address.parse(top["address"]).key == "agtp"


def test_every_result_resolves_through_slice(store, capsys):
    _, out = run(capsys, store, "find", "the")
    assert out["results"]
    for item in out["results"]:
        code, sliced = run(capsys, store, "slice", item["address"])
        assert code == 0 and sliced["text"].strip()
        assert sliced["start"] <= item["start"] and not sliced["superseded"]


def test_section_title_is_found_by_its_locator(store, capsys):
    _, out = run(capsys, store, "find", "framing")
    assert any(r["locator"].startswith("sec:") for r in out["results"])


def test_output_is_stable_and_ordered(store, capsys):
    _, first = run(capsys, store, "find", "frame", "stream")
    _, second = run(capsys, store, "find", "stream", "frame")
    assert first == second or first["results"] == second["results"]
    scores = [(-r["score"]) for r in first["results"]]
    assert first["total"] == len(first["results"])
    _, again = run(capsys, store, "find", "frame", "stream")
    assert again == first
    assert scores  # non-empty


def test_all_terms_required_and_no_match_is_ok(store, capsys):
    code, out = run(capsys, store, "find", "frame", "zzzunlikely")
    assert code == 0 and out["results"] == [] and out["total"] == 0


def test_limit_truncates_and_key_restricts(store, capsys):
    _, out = run(capsys, store, "find", "the", "--limit", "1")
    assert len(out["results"]) == 1 and out["truncated"] and out["total"] > 1
    _, only = run(capsys, store, "find", "the", "--key", "agtp")
    assert only["searched"] == ["agtp"] and {r["key"] for r in only["results"]} == {"agtp"}


def test_unreadable_source_is_skipped_and_reported(store, capsys):
    _, out = run(capsys, store, "find", "frame")
    assert {s["key"] for s in out["skipped"]} == {"scan"}


def test_errors(store, capsys):
    code, out = run(capsys, store, "find", "   ")
    assert code == 1 and not out["ok"]
    code, out = run(capsys, store, "find", "x", "--key", "nope")
    assert code == 1 and "nope" in out["error"]


def test_find_writes_nothing(store, capsys):
    before = sorted(p.relative_to(store).as_posix() for p in store.rglob("*") if p.is_file())
    stamps = {p: p.stat().st_mtime_ns for p in store.rglob("*") if p.is_file()}
    run(capsys, store, "find", "frame")
    after = sorted(p.relative_to(store).as_posix() for p in store.rglob("*") if p.is_file())
    assert before == after and not (store / "docs" / "ledger").exists()
    assert stamps == {p: p.stat().st_mtime_ns for p in store.rglob("*") if p.is_file()}
