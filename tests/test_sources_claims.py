"""Step B.2: source-claims use addresses, read only the slice and report staleness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
FIXTURES = ROOT / "tests" / "fixtures" / "sources"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import claims, cli, flow, sources, theses  # noqa: E402

SCHEMA = json.loads((TEMPLATE / "schemas" / "claims-result.schema.json").read_text())
QUOTE = "A sender MUST NOT send a frame larger than 64 KiB."
CLAIM = "The draft caps the frame size."


def _store(root: Path, text: str | None = None, edition: str = "00") -> str:
    src = root / f"draft-{edition}.txt"
    src.write_text(text if text is not None else (FIXTURES / "draft-agtp-00.txt").read_text())
    sources.add(root, src, origin="https://example.org/agtp", edition=edition, key="agtp",
                retrieved="2026-11-07T10:00:00Z")  # fmt: skip
    sources.index(root, "agtp")
    return sources.current_edition(root, "agtp")["normalized_hash"]


def _map(root: Path, locator: str, quote: str = QUOTE, **extra: str) -> Path:
    path = root / "theses.yaml"
    node = {"id": "c1", "type": "source-claim", "text": CLAIM, "status": "proposed",
            "quote": quote, "locator": locator, "bib_keys": ["agtp"], **extra}  # fmt: skip
    path.write_text(json.dumps({"version": 1, "nodes": [node], "edges": []}))
    return path


def _run(capsys, root: Path, *argv: str) -> tuple[int, dict]:
    code = cli.main(["--root", str(root), "claims", *argv])
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, SCHEMA)
    return code, out


def test_addressed_node_matches_the_slice_only(tmp_path, monkeypatch, capsys):
    digest = _store(tmp_path)
    _map(tmp_path, f"agtp@{digest[:12]}#sec:Requirements/Framing")
    full = (tmp_path / sources.manifest_path(tmp_path).parent / "agtp").rglob("normalized.txt")
    full_text = next(iter(full)).read_text()
    reads, seen = [], []
    real_read, real_find = Path.read_text, claims.find_quote

    def read(self, *a, **k):
        reads.append(self.name)
        return real_read(self, *a, **k)

    def find(source, quote):
        seen.append(len(source))
        return real_find(source, quote)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(claims, "find_quote", find)
    code, out = _run(capsys, tmp_path, "quote-check", "c1")
    assert code == 0 and out["results"][0]["verdict"] == "found"
    assert reads.count("normalized.txt") == 1  # one read: the hash check of the file on disk
    assert seen and max(seen) < len(full_text) / 2  # the quote was matched in the slice
    assert "stale" not in out["results"][0]
    assert out["results"][0]["source"].endswith("normalized.txt")


def test_ledger_input_is_the_passage_not_the_edition(tmp_path, capsys):
    digest = _store(tmp_path)
    _map(tmp_path, f"agtp@{digest[:12]}#para:10")
    assert _run(capsys, tmp_path, "quote-check", "c1")[1]["results"][0]["cached"] is None
    claims.record_verdict(tmp_path, CLAIM, claims.excerpt_for(tmp_path, "c1"), "supports")
    first = _run(capsys, tmp_path, "quote-check", "c1")[1]["results"][0]
    assert first["cached"] == "supports"
    # A new edition that leaves the passage alone: the old address is stale but the
    # rebased one hits the same ledger entry.
    new_digest = _store(tmp_path, (FIXTURES / "draft-agtp-00.txt").read_text() + "\nMore.\n", "01")
    assert new_digest != digest
    proposal = _run(capsys, tmp_path, "rebase", "c1")[1]
    _map(tmp_path, proposal["proposed"])
    again = _run(capsys, tmp_path, "quote-check", "c1")[1]["results"][0]
    assert again["cached"] == "supports" and "stale" not in again


def test_superseded_hash_marks_the_node_stale(tmp_path, capsys):
    digest = _store(tmp_path)
    _map(tmp_path, f"agtp@{digest[:12]}#sec:Requirements/Framing")
    new_text = (FIXTURES / "draft-agtp-00.txt").read_text().replace("64 KiB", "32 KiB")
    new_digest = _store(tmp_path, new_text, "01")
    code, out = _run(capsys, tmp_path, "quote-check", "c1")
    record = out["results"][0]
    assert code == 1 and record["verdict"] == "found"  # the pinned edition still has the quote
    assert record["stale"] is True and record["current_hash"] == new_digest

    class Facts:
        def attested(self, key):
            return False

    assert flow.source_claim_state(Facts(), record) == "stale"


def test_unresolvable_address_is_no_local_text_with_a_reason(tmp_path, capsys):
    _store(tmp_path)
    _map(tmp_path, "agtp@" + "0" * 12 + "#para:1")
    code, out = _run(capsys, tmp_path, "quote-check", "c1")
    record = out["results"][0]
    assert record["verdict"] == "no-local-text" and "no stored hash" in record["reason"]
    assert code == 0


def test_rebase_proposes_for_a_surviving_quote_and_never_edits_the_map(tmp_path, capsys):
    digest = _store(tmp_path)
    path = _map(tmp_path, f"agtp@{digest[:12]}#sec:Requirements/Framing")
    before = path.read_bytes()
    new_text = "Preface paragraph.\n\n" + (FIXTURES / "draft-agtp-00.txt").read_text()
    new_digest = _store(tmp_path, new_text, "01")
    code, out = _run(capsys, tmp_path, "rebase", "c1")
    assert code == 0 and out["status"] == "proposed"
    assert out["proposed"] == f"agtp@{new_digest[:12]}#sec:Requirements/Framing"
    assert out["address"] == f"agtp@{digest[:12]}#sec:Requirements/Framing"
    assert path.read_bytes() == before
    # The proposal verifies and is current once a person accepts it.
    _map(tmp_path, out["proposed"])
    assert _run(capsys, tmp_path, "rebase", "c1")[1]["status"] == "current"
    assert _run(capsys, tmp_path, "quote-check", "c1")[0] == 0


def test_rebase_reports_a_quote_that_does_not_survive(tmp_path, capsys):
    digest = _store(tmp_path)
    _map(tmp_path, f"agtp@{digest[:12]}#para:10")
    _store(tmp_path, (FIXTURES / "draft-agtp-00.txt").read_text().replace("MUST NOT", "MAY"), "01")
    code, out = _run(capsys, tmp_path, "rebase", "c1")
    assert code == 1 and out["ok"] is False
    assert out["status"] == "quote-missing" and "proposed" not in out


def test_rebase_migrates_a_legacy_locator_when_the_source_is_in_the_store(tmp_path, capsys):
    _store(tmp_path)
    _map(tmp_path, "p. 3")
    code, out = _run(capsys, tmp_path, "rebase", "c1")
    assert code == 0 and out["status"] == "proposed" and out["proposed"].startswith("agtp@")
    assert "address" not in out


def test_legacy_locator_nodes_are_unchanged(tmp_path, capsys):
    (tmp_path / "paper" / "sources").mkdir(parents=True)
    (tmp_path / "paper" / "sources" / "agtp.txt").write_text(f"Intro.\n{QUOTE}\n")
    _map(tmp_path, "p. 3")
    code, out = _run(capsys, tmp_path, "quote-check", "c1")
    assert code == 0
    assert out["results"] == [{"id": "c1", "locator": "p. 3", "verdict": "found",
                               "source": "paper/sources/agtp.txt", "cached": None}]  # fmt: skip


def test_manifest_md_is_parsed_by_the_store_parser(tmp_path):
    folder = tmp_path / "paper" / "sources"
    folder.mkdir(parents=True)
    (folder / "MANIFEST.md").write_text(
        "| key | file |\n|---|---|\n| a | a.txt |\n| b | b.pdf |\n- c: c.md\n"
    )
    assert sources.legacy_entries(tmp_path) == {"a": "a.txt", "b": "b.pdf", "c": "c.md"}
    assert claims._manifest_map(tmp_path) == {"a": "a.txt", "c": "c.md"}


def test_a_malformed_address_is_a_lint_error_and_a_free_text_locator_is_not():
    def node(locator):
        return {"id": "c1", "type": "source-claim", "text": "t", "status": "proposed",
                "quote": "q", "locator": locator}  # fmt: skip

    def codes(locator):
        data = {"version": 1, "nodes": [node(locator)], "edges": []}
        return [d.code for d in theses.structure_errors(data).items]

    assert "T049" in codes("agtp@abc#para:1")  # hash too short
    assert "T049" in codes("agtp@" + "a" * 12 + "#line:3")
    assert "T049" not in codes("agtp@" + "a" * 12 + "#para:1")
    assert "T049" not in codes("p. 3 @ the end #1")


def test_schema_rejects_a_bad_rebase_status():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"ok": True, "command": "claims rebase", "status": "maybe"}, SCHEMA)


def test_node_citing_a_colon_bib_key_resolves_its_legacy_text(tmp_path, capsys):
    sources_dir = tmp_path / "paper" / "sources"
    sources_dir.mkdir(parents=True)
    (sources_dir / "MANIFEST.md").write_text(
        "| key | file |\n| --- | --- |\n| smith:2020 | s.txt |\n"
    )
    (sources_dir / "s.txt").write_text(f"Intro.\n\n{QUOTE}\n")
    path = _map(tmp_path, "p. 1")
    data = json.loads(path.read_text())
    data["nodes"][0]["bib_keys"] = ["smith:2020"]
    path.write_text(json.dumps(data))
    _, out = _run(capsys, tmp_path, "quote-check", "c1")
    record = out["results"][0]
    assert record["verdict"] == "found" and record["source"] == "paper/sources/s.txt"


def test_old_locator_index_is_reported_not_called_not_found(tmp_path, capsys):
    digest = _store(tmp_path)
    _map(tmp_path, f"agtp@{digest[:12]}#sec:Requirements/Framing")
    entry = sources.current_edition(tmp_path, "agtp")
    index_path = sources.store_dir(tmp_path, "agtp", entry["raw_hash"]) / "locators.json"
    data = json.loads(index_path.read_text())
    data["index_version"] = "1"
    index_path.write_text(json.dumps(data))
    _, out = _run(capsys, tmp_path, "quote-check", "c1")
    record = out["results"][0]
    assert record["verdict"] == "no-local-text" and "run `sources index`" in record["reason"]


def test_record_and_cache_output_validate_against_the_schema(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)
    digest = _store(tmp_path)
    _map(tmp_path, f"agtp@{digest[:12]}#sec:Requirements/Framing")
    code, recorded = _run(capsys, tmp_path, "record", "c1", "--set", "supports")
    assert (code, recorded["command"], recorded["verdict"]) == (0, "claims record", "supports")
    code, read = _run(capsys, tmp_path, "cache", "c1")
    assert (code, read["command"], read["verdict"]) == (0, "claims cache", "supports")
    assert read["key"] == recorded["key"]
