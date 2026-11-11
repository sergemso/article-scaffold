"""Reading a source once: page markers, page and section slices, OCR fallback, coverage."""

from __future__ import annotations

import json
import shutil
import stat
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

needs_pdftotext = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="no pdftotext")


def run(capsys, root, *argv):
    code = cli.main(["--root", str(root), "sources", *argv])
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, RESULT)
    return code, out


def manifest(root):
    data = json.loads((root / "paper/sources/manifest.json").read_text())
    jsonschema.validate(data, MANIFEST)
    return data["sources"]


def make_pdf(path, pages):
    """A minimal PDF with one line of Helvetica text per page."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None]
    kids = []
    for i, text in enumerate(pages):
        page_id, content_id = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{page_id} 0 R")
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents {content_id} 0 R "
            "/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
            ">> >> >>"
        )
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def add(capsys, root, path, key):
    return run(
        capsys, root, "add", str(path), "--key", key, "--origin", "https://example.org/" + key,
        "--edition", "v1", "--retrieved", "2026-11-09T10:00:00Z",
    )  # fmt: skip


@pytest.fixture
def paper(tmp_path, capsys):
    pdf = tmp_path / "paper.pdf"
    make_pdf(pdf, ["First page alpha", "Second page beta", "Third page gamma"])
    add(capsys, tmp_path, pdf, "paper")
    run(capsys, tmp_path, "index")
    return tmp_path


def stored_text(root):
    entry = manifest(root)[0]
    return (root / "paper/sources/paper" / entry["raw_hash"] / "normalized.txt").read_text()


@needs_pdftotext
def test_pdf_text_carries_page_markers(paper):
    text = stored_text(paper)
    assert "[page 1]\n\nFirst page alpha" in text
    assert text.index("[page 2]") < text.index("Second page beta") < text.index("[page 3]")
    assert manifest(paper)[0]["normalizer"] == {"name": "pdftotext", "version": "2"}


@needs_pdftotext
def test_slice_pages_returns_only_the_requested_pages(paper, capsys):
    code, out = run(capsys, paper, "slice", "paper", "--pages", "2")
    assert code == 0 and out["locator"] == "pages:2-2"
    assert "Second page beta" in out["text"]
    assert "First page" not in out["text"] and "Third page" not in out["text"]
    _, wide = run(capsys, paper, "slice", "paper", "--pages", "2-3")
    assert "Second page beta" in wide["text"] and "Third page gamma" in wide["text"]


@needs_pdftotext
def test_slice_pages_refuses_a_page_past_the_end_and_bad_ranges(paper, capsys):
    code, out = run(capsys, paper, "slice", "paper", "--pages", "4")
    assert code == 1 and "3 pages" in out["error"]
    code, out = run(capsys, paper, "slice", "paper", "--pages", "3-1")
    assert code == 1 and "ascending" in out["error"]
    code, out = run(capsys, paper, "slice", "paper")
    assert code == 1 and "--pages or --section" in out["error"]


def test_pages_need_a_pdf_with_markers(tmp_path, capsys):
    add(capsys, tmp_path, FIXTURES / "draft-agtp-00.txt", "agtp")
    run(capsys, tmp_path, "index")
    code, out = run(capsys, tmp_path, "slice", "agtp", "--pages", "1")
    assert code == 1 and "no page markers" in out["error"]


def test_slice_section_by_number(tmp_path, capsys):
    text = tmp_path / "doc.txt"
    text.write_text("Abstract\n\nIntro.\n\n1. Scope\n\nScope text.\n\n1.1 Detail\n\nDeep.\n\n"
                    "2. Method\n\nMethod text.\n")  # fmt: skip
    add(capsys, tmp_path, text, "doc")
    run(capsys, tmp_path, "index")
    _, out = run(capsys, tmp_path, "slice", "doc", "--section", "1")
    assert "Scope text." in out["text"] and "Deep." in out["text"]
    assert "Method text." not in out["text"]
    _, sub = run(capsys, tmp_path, "slice", "doc", "--section", "1.1")
    assert "Deep." in sub["text"] and "Scope text." not in sub["text"]
    code, out = run(capsys, tmp_path, "slice", "doc", "--section", "9")
    assert code == 1 and "no section" in out["error"]


def test_address_slice_still_works_and_rejects_page_flags(tmp_path, capsys):
    add(capsys, tmp_path, FIXTURES / "pace.html", "pace")
    run(capsys, tmp_path, "index")
    _, found = run(capsys, tmp_path, "find", "scheme")
    address = found["results"][0]["address"]
    _, out = run(capsys, tmp_path, "slice", address)
    assert "scheme" in out["text"]
    code, bad = run(capsys, tmp_path, "slice", address, "--pages", "1")
    assert code == 1 and "take a key" in bad["error"]


@needs_pdftotext
def test_read_coverage_is_recorded_and_unread_pages_listed(paper, capsys):
    code, out = run(capsys, paper, "read", "paper", "--pages", "1-2", "--by", "model",
                    "--note", "appendix not read")  # fmt: skip
    assert code == 0 and out["pages"] == 3 and out["unread_pages"] == ["3"]
    _, again = run(capsys, paper, "read", "paper", "--pages", "1-2", "--by", "model",
                   "--note", "appendix not read")  # fmt: skip
    assert len(again["read"]) == 1  # the same record is not stored twice
    run(capsys, paper, "read", "paper", "--pages", "3", "--by", "owner", "--verified")
    entry = manifest(paper)[0]
    assert [r["by"] for r in entry["read"]] == ["model", "owner"]
    assert entry["read"][1]["verified"] is True
    _, listed = run(capsys, paper, "list")
    row = listed["sources"][0]
    assert row["unread_pages"] == [] and row["pages"] == 3


@needs_pdftotext
def test_read_refuses_what_cannot_be_checked(paper, tmp_path, capsys):
    code, out = run(capsys, paper, "read", "paper", "--pages", "9", "--by", "model")
    assert code == 1 and "3 pages" in out["error"]
    code, out = run(capsys, paper, "read", "paper", "--by", "model")
    assert code == 1 and "exactly one" in out["error"]
    code, out = run(capsys, paper, "read", "missing", "--pages", "1", "--by", "model")
    assert code == 1 and "no source" in out["error"]
    # A source with no stored text cannot carry coverage.
    add(capsys, paper, FIXTURES / "scan.pdf", "scan")
    code, out = run(capsys, paper, "read", "scan", "--pages", "1", "--by", "model")
    assert code == 1 and "no stored text" in out["error"]


def test_read_section_needs_a_real_section(tmp_path, capsys):
    text = tmp_path / "doc.txt"
    text.write_text("1. Scope\n\nScope text.\n")
    add(capsys, tmp_path, text, "doc")
    run(capsys, tmp_path, "index")
    code, out = run(capsys, tmp_path, "read", "doc", "--section", "1", "--by", "owner")
    assert code == 0 and out["read"][0]["section"] == "1"
    code, out = run(capsys, tmp_path, "read", "doc", "--section", "7", "--by", "owner")
    assert code == 1 and "no section" in out["error"]


def fake_tool(directory, name, body):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@needs_pdftotext
def test_scan_is_ocred_once_and_never_again(tmp_path, capsys, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    log = tmp_path / "ocr.log"
    pdftoppm = fake_tool(
        tools, "pdftoppm",
        f"echo pdftoppm >> {log}\nfor prefix; do :; done\n"
        'for n in 1 2; do : > "$prefix-$n.png"; done\n',
    )  # fmt: skip
    tesseract = fake_tool(
        tools, "tesseract",
        f'echo tesseract >> {log}\necho "scanned text of $(basename "$1")"\n',
    )  # fmt: skip
    real = shutil.which
    monkeypatch.setattr(
        sources.shutil, "which",
        lambda n: {"pdftoppm": pdftoppm, "tesseract": tesseract}.get(n) or real(n),
    )  # fmt: skip
    scan = tmp_path / "scan.pdf"
    make_pdf(scan, [" ", " "])  # pages with no text layer
    add(capsys, tmp_path, scan, "scan")
    code, out = run(capsys, tmp_path, "index", "scan")
    assert code == 0 and out["sources"][0]["status"] == "indexed"
    assert out["sources"][0]["normalizer"] == {"name": "tesseract", "version": "1"}
    entry = manifest(tmp_path)[0]
    text = (tmp_path / "paper/sources/scan" / entry["raw_hash"] / "normalized.txt").read_text()
    assert "[page 1]" in text and "[page 2]" in text and "scanned text of p-1.png" in text
    calls = log.read_text().split()
    assert calls.count("pdftoppm") == 1 and calls.count("tesseract") == 2
    # Same hash, same text: a second index reuses it and runs no OCR.
    _, second = run(capsys, tmp_path, "index", "scan")
    assert second["sources"][0]["status"] == "kept"
    assert log.read_text().split() == calls


@needs_pdftotext
def test_scan_without_ocr_tools_is_listed_unreadable(tmp_path, capsys, monkeypatch):
    real = shutil.which
    monkeypatch.setattr(
        sources.shutil, "which", lambda n: None if n in ("pdftoppm", "tesseract") else real(n)
    )
    scan = tmp_path / "scan.pdf"
    make_pdf(scan, [" "])
    add(capsys, tmp_path, scan, "scan")
    code, out = run(capsys, tmp_path, "index", "scan")
    assert code == 1 and "install pdftoppm and tesseract" in out["sources"][0]["reason"]
