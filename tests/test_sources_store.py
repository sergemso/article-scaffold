"""Step B.1: the source store (add, index, slice, diff) is local, stable and keeps old editions."""

from __future__ import annotations

import json
import shutil
import sys

import jsonschema
import pytest
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
FIXTURES = ROOT / "tests" / "fixtures" / "sources"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import cli, sources  # noqa: E402

RESULT = json.loads((TEMPLATE / "schemas" / "sources-result.schema.json").read_text())
MANIFEST = json.loads((TEMPLATE / "schemas" / "sources-manifest.schema.json").read_text())
RETRIEVED = "2026-11-07T10:00:00Z"


def run(capsys, root, *argv):
    code = cli.main(["--root", str(root), "sources", *argv])
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, RESULT)
    return code, out


def add(capsys, root, name, key, edition="00", src=None):
    path = src or FIXTURES / name
    return run(
        capsys, root, "add", str(path), "--key", key, "--origin", "https://example.org/" + key,
        "--edition", edition, "--retrieved", RETRIEVED,
    )  # fmt: skip


def manifest(root):
    data = json.loads((root / "paper/sources/manifest.json").read_text())
    jsonschema.validate(data, MANIFEST)
    return data["sources"]


@pytest.fixture
def store(tmp_path, capsys):
    add(capsys, tmp_path, "draft-agtp-00.txt", "agtp")
    add(capsys, tmp_path, "pace.html", "pace")
    add(capsys, tmp_path, "scan.pdf", "scan")
    return tmp_path


def test_add_copies_under_raw_hash_and_appends_manifest(tmp_path, capsys):
    code, out = add(capsys, tmp_path, "draft-agtp-00.txt", "agtp")
    assert code == 0 and out["added"] is True
    raw = tmp_path / out["path"]
    assert raw.read_bytes() == (FIXTURES / "draft-agtp-00.txt").read_bytes()
    assert out["path"] == f"paper/sources/agtp/{out['raw_hash']}/raw.txt"
    (entry,) = manifest(tmp_path)
    assert entry["media_type"] == "text/plain" and entry["edition"] == "00"
    _, again = add(capsys, tmp_path, "draft-agtp-00.txt", "agtp")
    assert again["added"] is False and len(manifest(tmp_path)) == 1


def test_add_refuses_a_bad_key_and_a_missing_file(tmp_path, capsys):
    code, out = add(capsys, tmp_path, "draft-agtp-00.txt", "../escape")
    assert code == 1 and "invalid source key" in out["error"]
    code, out = add(capsys, tmp_path, "nope.txt", "x", src=tmp_path / "nope.txt")
    assert code == 1 and "not a file" in out["error"]


def test_index_plain_html_and_unreadable_pdf(store, capsys, monkeypatch):
    monkeypatch.setattr(sources.shutil, "which", lambda name: None)
    code, out = run(capsys, store, "index")
    assert code == 1  # an unreadable source is listed and reported, not guessed
    assert out["ok"] is False  # ok equals the exit code
    status = {row["key"]: row for row in out["sources"]}
    assert status["agtp"]["status"] == "indexed" and status["pace"]["status"] == "indexed"
    assert status["scan"]["status"] == "unreadable" and "pdftotext" in status["scan"]["reason"]
    entries = {e["key"]: e for e in manifest(store)}
    assert entries["agtp"]["normalizer"] == {"name": "plain-text", "version": "1"}
    assert entries["pace"]["normalizer"] == {"name": "html-text", "version": "1"}
    assert "normalized_hash" not in entries["scan"] and "normalizer" not in entries["scan"]
    text = (
        store / "paper/sources/pace" / entries["pace"]["raw_hash"] / "normalized.txt"
    ).read_text()
    assert text == "# Pace Notes\n\nIntro text here.\n\n## Scope\n\nThe scheme MUST be local.\n"
    assert "var a" not in text


def test_unreadable_pdf_with_pdftotext_present_or_not(store, capsys):
    code, out = run(capsys, store, "index", "scan")
    assert code == 1 and out["sources"][0]["status"] == "unreadable"


def test_index_is_stable_and_normalized_text_is_not_regenerated(store, capsys, monkeypatch):
    monkeypatch.setattr(sources.shutil, "which", lambda name: None)
    run(capsys, store, "index")
    before = {p: p.read_bytes() for p in (store / "paper/sources").rglob("*") if p.is_file()}
    _, second = run(capsys, store, "index")
    assert {r["status"] for r in second["sources"]} == {"kept", "unreadable"}
    after = {p: p.read_bytes() for p in (store / "paper/sources").rglob("*") if p.is_file()}
    assert before == after
    # A hand-fixed committed text is kept; --force regenerates it.
    entry = next(e for e in manifest(store) if e["key"] == "agtp")
    text_path = store / "paper/sources/agtp" / entry["raw_hash"] / "normalized.txt"
    text_path.write_text("changed\n")
    code, out = run(capsys, store, "index", "agtp")
    assert code == 1 and "differs from the manifest" in out["error"]
    code, out = run(capsys, store, "index", "agtp", "--force")
    assert code == 0 and out["sources"][0]["status"] == "indexed"
    assert text_path.read_text().startswith("Internet-Draft")


def test_locator_index_covers_sections_paragraphs_and_requirements(store, capsys):
    run(capsys, store, "index", "agtp")
    entry = next(e for e in manifest(store) if e["key"] == "agtp")
    base = store / "paper/sources/agtp" / entry["raw_hash"]
    data = json.loads((base / "locators.json").read_text())
    locators = {
        item["locator"] for k in ("sections", "paragraphs", "requirements") for item in data[k]
    }
    assert "sec:Introduction" in locators
    assert "sec:Requirements/Framing" in locators
    assert "sec:Requirements/Security Considerations" in locators
    assert "sec:Examples" in locators  # "Appendix A.  Examples" is a heading
    assert {"req:MUST_NOT:1", "req:SHOULD:1", "req:MAY:1"} <= locators
    assert "para:1" in locators
    # The table of contents rows are not headings.
    assert not any("......" in item["title"] for item in data["sections"])


def test_slice_address_forms_and_caps(store, capsys):
    run(capsys, store, "index", "agtp")
    digest = next(e for e in manifest(store) if e["key"] == "agtp")["normalized_hash"]
    code, out = run(capsys, store, "slice", f"agtp@{digest[:12]}#sec:Requirements/Framing")
    assert code == 0 and out["superseded"] is False and out["truncated"] is False
    assert "MUST NOT send a frame larger than 64 KiB" in out["text"]
    assert "Implementations MAY" not in out["text"]  # a section ends at the next heading
    code, out = run(capsys, store, "slice", f"agtp@{digest}#req:MUST_NOT:1", "--window", "0")
    assert out["start"] == out["end"] and "MUST NOT" in out["text"]
    code, out = run(capsys, store, "slice", f"agtp@{digest[:12]}#req:MUST_NOT:1", "--window", "1")
    assert out["end"] - out["start"] == 2
    code, out = run(capsys, store, "slice", f"agtp@{digest[:12]}#para:1")
    assert code == 0 and out["locator"] == "para:1"
    code, out = run(capsys, store, "slice", f"agtp@{digest[:12]}#req:MUST:9")
    assert code == 1 and "not found" in out["error"]
    code, out = run(capsys, store, "slice", f"agtp@{digest[:12]}#line:3")
    assert code == 1 and "locator must be" in out["error"]
    # Same call, same bytes.
    first = run(capsys, store, "slice", f"agtp@{digest[:12]}#sec:Introduction")[1]
    second = run(capsys, store, "slice", f"agtp@{digest[:12]}#sec:Introduction")[1]
    assert first == second


def test_slice_is_capped_in_lines_and_bytes(tmp_path, capsys):
    big = tmp_path / "big.txt"
    big.write_text("1. Big\n\n" + "".join(f"line {n} " + "x" * 200 + "\n" for n in range(300)))
    add(capsys, tmp_path, "", "big", src=big)
    run(capsys, tmp_path, "index")
    digest = manifest(tmp_path)[0]["normalized_hash"]
    code, out = run(capsys, tmp_path, "slice", f"big@{digest[:12]}#sec:Big")
    assert out["truncated"] is True
    assert len(out["text"].encode()) <= sources.MAX_SLICE_BYTES
    assert out["text"].count("\n") < sources.MAX_SLICE_LINES


def test_changed_raw_file_gets_new_hash_and_old_address_is_superseded(store, capsys):
    run(capsys, store, "index", "agtp")
    old = next(e for e in manifest(store) if e["key"] == "agtp")
    v2 = store / "agtp-01.txt"
    v2.write_text(
        (FIXTURES / "draft-agtp-00.txt")
        .read_text()
        .replace("64 KiB", "128 KiB")
        .replace("None yet.", "One example.")
    )
    code, out = add(capsys, store, "", "agtp", edition="01", src=v2)
    assert out["supersedes"] == [old["raw_hash"]]
    run(capsys, store, "index", "agtp")
    entries = [e for e in manifest(store) if e["key"] == "agtp"]
    assert len(entries) == 2 and entries[0]["raw_hash"] != entries[1]["raw_hash"]
    assert (store / "paper/sources/agtp" / old["raw_hash"] / "raw.txt").is_file()  # old stays
    old_addr = f"agtp@{old['normalized_hash'][:12]}#req:MUST_NOT:1"
    code, out = run(capsys, store, "slice", old_addr)
    assert code == 0 and out["superseded"] is True and "64 KiB" in out["text"]
    assert out["current_hash"] == entries[1]["normalized_hash"]
    new_addr = f"agtp@{entries[1]['normalized_hash'][:12]}#req:MUST_NOT:1"
    code, out = run(capsys, store, "slice", new_addr)
    assert out["superseded"] is False and "128 KiB" in out["text"]
    code, out = run(capsys, store, "diff", "agtp", old["normalized_hash"][:12],
                    entries[1]["normalized_hash"][:12])  # fmt: skip
    assert code == 0 and out["added"] == [] and out["removed"] == []
    assert "req:MUST_NOT:1" in out["changed"] and "sec:Examples" in out["changed"]
    assert "sec:Introduction" not in out["changed"]


def test_diff_lists_added_and_removed_locators(tmp_path, capsys):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("1. One\n\nThe first MUST hold.\n\n2. Two\n\nText.\n")
    b.write_text("1. One\n\nThe first MUST hold.\n\n3. Three\n\nMore.\n")
    add(capsys, tmp_path, "", "d", edition="a", src=a)
    add(capsys, tmp_path, "", "d", edition="b", src=b)
    run(capsys, tmp_path, "index")
    first, second = (e["normalized_hash"][:12] for e in manifest(tmp_path))
    _, out = run(capsys, tmp_path, "diff", "d", first, second)
    assert out["added"] == ["sec:Three"] and out["removed"] == ["sec:Two"]


def test_ambiguous_and_unknown_hash_prefixes_are_reported(tmp_path, capsys, monkeypatch):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("1. One\n\nA.\n")
    b.write_text("1. One\n\nB.\n")
    add(capsys, tmp_path, "", "d", edition="a", src=a)
    add(capsys, tmp_path, "", "d", edition="b", src=b)
    run(capsys, tmp_path, "index")
    hashes = [e["normalized_hash"] for e in manifest(tmp_path)]
    # Force a shared 12-character prefix by rewriting the manifest hashes.
    data = json.loads((tmp_path / "paper/sources/manifest.json").read_text())
    data["sources"][0]["normalized_hash"] = "0123456789ab" + hashes[0][12:]
    data["sources"][1]["normalized_hash"] = "0123456789ab" + hashes[1][12:]
    (tmp_path / "paper/sources/manifest.json").write_text(json.dumps(data))
    code, out = run(capsys, tmp_path, "slice", "d@0123456789ab#sec:One")
    assert code == 1 and "ambiguous" in out["error"] and len(out["candidates"]) == 2
    code, out = run(capsys, tmp_path, "slice", "d@aaaaaaaaaaaa#sec:One")
    assert code == 1 and "no stored hash" in out["error"]
    code, out = run(capsys, tmp_path, "slice", "missing@aaaaaaaaaaaa#sec:One")
    assert code == 1 and "no source" in out["error"]


def test_legacy_manifest_is_read_not_lost(tmp_path, capsys):
    sources_dir = tmp_path / "paper" / "sources"
    sources_dir.mkdir(parents=True)
    legacy = (
        "# Sources\n\n| key | file |\n| --- | --- |\n"
        "| ietf-agtp | draft-agtp-00.txt |\n- gar: gar.pdf\n"
    )
    (sources_dir / "MANIFEST.md").write_text(legacy)
    shutil.copy(FIXTURES / "draft-agtp-00.txt", sources_dir / "draft-agtp-00.txt")
    _, listed = run(capsys, tmp_path, "list")
    assert listed["legacy"] == [
        {"key": "gar", "file": "gar.pdf", "imported": False},
        {"key": "ietf-agtp", "file": "draft-agtp-00.txt", "imported": False},
    ]
    code, out = run(
        capsys, tmp_path, "add", str(sources_dir / "draft-agtp-00.txt"),
        "--origin", "https://example.org/agtp", "--edition", "00",
    )  # fmt: skip
    assert code == 0 and out["key"] == "ietf-agtp"  # the key comes from MANIFEST.md
    assert (sources_dir / "MANIFEST.md").read_text() == legacy
    assert (sources_dir / "draft-agtp-00.txt").is_file()
    _, listed = run(capsys, tmp_path, "list")
    assert {row["key"]: row["imported"] for row in listed["legacy"]} == {
        "gar": False, "ietf-agtp": True,
    }  # fmt: skip


def test_sources_makes_no_subprocess_but_pdftotext(tmp_path, capsys, monkeypatch):
    calls = []
    real = sources.subprocess.run

    def spy(argv, *a, **kw):
        calls.append(argv[0].split("/")[-1])
        return real(argv, *a, **kw)

    monkeypatch.setattr(sources.subprocess, "run", spy)
    add(capsys, tmp_path, "scan.pdf", "scan")
    add(capsys, tmp_path, "pace.html", "pace")
    run(capsys, tmp_path, "index")
    assert set(calls) <= {"pdftotext"}


def _add_default_key(capsys, root, path, edition):
    return run(
        capsys, root, "add", str(path), "--origin", "https://example.org/x",
        "--edition", edition, "--retrieved", RETRIEVED,
    )  # fmt: skip


@pytest.mark.parametrize(
    "stem, key",
    [
        ("draft-x-01", "draft-x"),
        ("draft-x_02", "draft-x"),
        ("spec-v2", "spec"),
        ("spec-v1.2", "spec"),
        ("spec-rev3", "spec"),
        ("rfc-9110", "rfc-9110"),
        ("rfc9110", "rfc9110"),
        ("draft-x", "draft-x"),
        ("my paper", "my-paper"),
        ("01", "01"),
    ],
)
def test_default_key_drops_trailing_edition_suffix(stem, key):
    assert sources.default_key(stem) == key


def test_two_editions_added_without_key_supersede_each_other(tmp_path, capsys):
    v1, v2 = tmp_path / "draft-x-01.txt", tmp_path / "draft-x-02.txt"
    v1.write_text("1. One\n\nThe first MUST hold.\n")
    v2.write_text("1. One\n\nThe first MUST hold, always.\n")
    code, first = _add_default_key(capsys, tmp_path, v1, "01")
    code, second = _add_default_key(capsys, tmp_path, v2, "02")
    assert first["key"] == second["key"] == "draft-x"
    assert second["supersedes"] == [first["raw_hash"]]
    run(capsys, tmp_path, "index")
    old = manifest(tmp_path)[0]["normalized_hash"]
    code, out = run(capsys, tmp_path, "slice", f"draft-x@{old[:12]}#sec:One")
    assert code == 0 and out["superseded"] is True


def _numbered(paragraphs):
    return "1. One\n\n" + "\n\n".join(paragraphs) + "\n"


def test_diff_matches_paragraphs_by_content_so_one_insert_is_one_added(tmp_path, capsys):
    paras = [f"Paragraph number {n} says something distinct." for n in range(15)]
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text(_numbered(paras))
    b.write_text(_numbered(paras[:2] + ["A brand new paragraph."] + paras[2:]))
    add(capsys, tmp_path, "", "d", edition="a", src=a)
    add(capsys, tmp_path, "", "d", edition="b", src=b)
    run(capsys, tmp_path, "index")
    first, second = (e["normalized_hash"][:12] for e in manifest(tmp_path))
    _, out = run(capsys, tmp_path, "diff", "d", first, second)
    assert out["added"] == ["para:4"] and out["removed"] == []
    assert [c for c in out["changed"] if c.startswith("para:")] == []
    # A deletion is one removed locator, named by its old number; an edit is one changed.
    _, out = run(capsys, tmp_path, "diff", "d", second, first)
    assert out["removed"] == ["para:4"] and out["added"] == []
    c = tmp_path / "c.txt"
    c.write_text(_numbered(paras[:5] + ["Edited."] + paras[6:]))
    add(capsys, tmp_path, "", "d", edition="c", src=c)
    run(capsys, tmp_path, "index")
    third = manifest(tmp_path)[2]["normalized_hash"][:12]
    _, out = run(capsys, tmp_path, "diff", "d", first, third)
    assert [x for x in out["changed"] if x.startswith("para:")] == ["para:7"]
    assert out["added"] == [] and out["removed"] == []


def test_rfc2119_boilerplate_is_not_numbered_as_a_requirement(tmp_path, capsys):
    src = tmp_path / "bp.txt"
    src.write_text(
        "1. Conventions\n\n"
        '   The key words "MUST", "MUST NOT", "SHOULD", "MAY" in this document are to\n'
        "   be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only\n"
        "   when, they appear in all capitals, as shown here.\n\n"
        "2. Rules\n\n"
        "   A sender MUST sign.\n   A sender MAY retry.\n"
    )
    add(capsys, tmp_path, "", "bp", src=src)
    run(capsys, tmp_path, "index")
    digest = manifest(tmp_path)[0]["normalized_hash"][:12]
    code, out = run(capsys, tmp_path, "slice", f"bp@{digest}#req:MUST:1", "--window", "0")
    assert code == 0 and "A sender MUST sign." in out["text"]
    code, out = run(capsys, tmp_path, "slice", f"bp@{digest}#req:MUST:2")
    assert code == 1 and "not found" in out["error"]
    code, out = run(capsys, tmp_path, "slice", f"bp@{digest}#req:MUST_NOT:1")
    assert code == 1 and "not found" in out["error"]


def test_legacy_key_with_a_colon_is_listed_and_add_refuses_it_clearly(tmp_path, capsys):
    sources_dir = tmp_path / "paper" / "sources"
    sources_dir.mkdir(parents=True)
    (sources_dir / "MANIFEST.md").write_text(
        "| key | file |\n| --- | --- |\n| smith:2020 | s.txt |\n"
    )
    shutil.copy(FIXTURES / "draft-agtp-00.txt", sources_dir / "s.txt")
    assert sources.legacy_entries(tmp_path) == {"smith:2020": "s.txt"}
    code, out = run(
        capsys, tmp_path, "add", str(sources_dir / "s.txt"),
        "--origin", "https://example.org/s", "--edition", "00",
    )  # fmt: skip
    assert code == 1 and "smith:2020" in out["error"] and "--key" in out["error"]
    code, out = add(capsys, tmp_path, "draft-agtp-00.txt", "smith-2020", src=sources_dir / "s.txt")
    assert code == 0 and out["key"] == "smith-2020"


def test_an_older_locator_index_is_refused_with_a_reindex_hint(store, capsys):
    run(capsys, store, "index", "agtp")
    entry = sources.current_edition(store, "agtp")
    index_path = sources.store_dir(store, "agtp", entry["raw_hash"]) / "locators.json"
    data = json.loads(index_path.read_text())
    data["index_version"] = "1"
    index_path.write_text(json.dumps(data))
    with pytest.raises(sources.SourcesError, match="run `sources index`"):
        sources.load_locators(store, entry)
    sources.index(store, "agtp")  # reindexing restores it
    sources.load_locators(store, entry)
