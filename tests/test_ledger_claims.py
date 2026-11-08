"""Step A.2: tier 2 verdicts live in the ledger; tier 1 and summaries do not."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import ROOT
from test_claims import SOURCE, _node

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import claims, ledger  # noqa: E402
from scripts.article import index as section_index  # noqa: E402

LEDGER = Path("docs") / "ledger"


@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)


def _repo(tmp_path: Path, *nodes: str, source: str = SOURCE) -> Path:
    (tmp_path / "theses.yaml").write_text("version: 1\nnodes:\n" + "".join(nodes) + "edges: []\n")
    sources = tmp_path / "paper" / "sources"
    sources.mkdir(parents=True)
    (sources / "smith2020.txt").write_text(source, encoding="utf-8")
    return tmp_path


FAR = "Alpha holds under load. " + "x " * 600 + "Beta follows from gamma. " + "y " * 600


def _two(tmp_path: Path) -> Path:
    """Two nodes whose excerpts are far apart, so their ledger keys differ."""
    return _repo(
        tmp_path,
        _node("c1", "Alpha holds under load."),
        _node("c2", "Beta follows from gamma."),
        source=FAR,
    )


def _cached(root: Path) -> dict[str, str | None]:
    return {r["id"]: r.get("cached") for r in claims.quote_check(root)}


def _count_puts(monkeypatch) -> list[str]:
    calls: list[str] = []
    real = ledger.put

    def counting(*args, **kwargs):
        calls.append(args[1].key)
        return real(*args, **kwargs)

    monkeypatch.setattr(ledger, "put", counting)
    return calls


def test_second_run_hits_every_entry_and_writes_nothing(tmp_path, monkeypatch):
    root = _two(tmp_path)
    assert _cached(root) == {"c1": None, "c2": None}
    claims.verdict_for_node(root, "c1", "supports")
    claims.verdict_for_node(root, "c2", "overstates")
    ledger.stats(root, reset=True)
    puts = _count_puts(monkeypatch)
    assert _cached(root) == {"c1": "supports", "c2": "overstates"}
    assert ledger.stats(root) == {"hits": 2, "misses": 0, "conflicts": 0, "bypassed": 0}
    assert puts == []


def test_editing_wording_or_excerpt_is_a_miss_and_a_far_change_is_not(tmp_path):
    padded = "x " * 600 + SOURCE + "y " * 600
    root = _repo(tmp_path, _node("c1", "A second sentence follows."), source=padded)
    claims.verdict_for_node(root, "c1", "supports")
    source = root / "paper" / "sources" / "smith2020.txt"
    source.write_text(padded.replace("x x ", "z z ", 1))
    assert _cached(root) == {"c1": "supports"}
    source.write_text(padded.replace("A second sentence follows.", "A second sentence follows!"))
    assert _cached(root)["c1"] is None  # the excerpt itself changed
    source.write_text(padded)
    theses = root / "theses.yaml"
    theses.write_text(theses.read_text().replace("first contract holds", "contract fails"))
    assert _cached(root)["c1"] is None  # the claim wording changed


def test_verdict_entry_holds_hashes_and_verdict_never_text(tmp_path):
    root = _two(tmp_path)
    claims.verdict_for_node(root, "c1", "contradicts")
    (path,) = [p for p in (root / LEDGER).rglob("*.json") if not p.name.endswith(".prov.json")]
    text = path.read_text()
    assert "second sentence" not in text and "first contract holds" not in text
    entry = json.loads(text)
    assert entry["kind"] == "claim-verdict" and entry["status"] == "fail"
    assert entry["tier"] == "2" and entry["version"] == claims.PROCEDURE_VERSION
    (info,) = ledger.provenance(root, "claim-verdict", entry["key"])
    assert info["author"] == "agent" and info["tier"] == "2"


def test_same_verdict_twice_is_fine_and_a_different_one_names_the_evict_command(tmp_path):
    root = _two(tmp_path)
    first = claims.verdict_for_node(root, "c1", "supports")
    assert claims.verdict_for_node(root, "c1", "supports")["key"] == first["key"]
    with pytest.raises(ValueError, match=rf"ledger evict claim-verdict {first['key']}"):
        claims.verdict_for_node(root, "c1", "overstates")
    assert claims.verdict_for_node(root, "c1")["verdict"] == "supports"
    ledger.evict(root, "claim-verdict", first["key"], "re-judged by the author")
    assert claims.verdict_for_node(root, "c1", "overstates")["verdict"] == "overstates"


def test_unknown_verdict_is_refused(tmp_path):
    root = _two(tmp_path)
    with pytest.raises(ValueError, match="verdict must be one of"):
        claims.record_verdict(root, "a", "b", "maybe")


def test_switch_off_refuses_to_record_and_reports_no_hit(tmp_path, monkeypatch):
    root = _two(tmp_path)
    claims.verdict_for_node(root, "c1", "supports")
    monkeypatch.setenv("ARTICLE_LEDGER", "off")
    assert _cached(root)["c1"] is None
    with pytest.raises(ValueError, match="switched off"):
        claims.verdict_for_node(root, "c2", "supports")


def test_legacy_cache_entry_moves_into_the_ledger_on_first_read(tmp_path):
    root = _two(tmp_path)
    node = claims._one(root, "c1")
    excerpt = claims.excerpt_for(root, "c1")
    legacy = root / claims.LEGACY_CACHE_PATH
    legacy.parent.mkdir()
    body = json.dumps({claims._legacy_key(node["text"], excerpt): {"verdict": "overstates"}})
    legacy.write_text(body)
    assert _cached(root) == {"c1": "overstates", "c2": None}
    entry = ledger.get(root, "claim-verdict", claims.verdict_key(node["text"], excerpt).key)
    assert entry["status"] == "fail"
    (info,) = ledger.provenance(root, "claim-verdict", entry["key"])
    assert info["imported"] == ".theses/claims-cache.json"
    legacy.unlink()  # the ledger alone answers from now on
    assert _cached(root)["c1"] == "overstates"
    assert ledger.verify(root) == []


def test_bad_legacy_entries_are_ignored(tmp_path):
    root = _two(tmp_path)
    node = claims._one(root, "c1")
    legacy = root / claims.LEGACY_CACHE_PATH
    legacy.parent.mkdir()
    key = claims._legacy_key(node["text"], claims.excerpt_for(root, "c1"))
    legacy.write_text(json.dumps({key: {"verdict": "maybe"}}))
    assert _cached(root)["c1"] is None
    legacy.write_text("not json")
    assert _cached(root)["c1"] is None


def test_quote_matching_and_summaries_are_not_ledgered(tmp_path):
    root = _two(tmp_path)
    claims.quote_check(root)
    assert not (root / LEDGER).exists()
    sections = root / "paper" / "sections"
    sections.mkdir()
    (sections / "intro.tex").write_text("\\section{Intro}\\label{sec:intro}\nIt holds. More.\n")
    section_index.write_index(root)
    assert not (root / LEDGER).exists()


def test_a_corrupt_entry_is_a_miss_and_verify_reports_it(tmp_path):
    root = _two(tmp_path)
    key = claims.verdict_for_node(root, "c1", "supports")["key"]
    path = ledger._entry_path(root, "claim-verdict", key)
    path.write_text("{}")
    assert _cached(root)["c1"] is None
    (problem,) = ledger.verify(root)
    assert key in problem


def test_record_does_not_count_as_a_lookup(tmp_path):
    root = _two(tmp_path)
    ledger.stats(root, reset=True)
    claims.verdict_for_node(root, "c1", "supports")
    claims.verdict_for_node(root, "c1", "supports")  # repeat record
    assert ledger.stats(root)["hits"] == 0
    claims.verdict_for_node(root, "c1")  # a plain read is a lookup
    assert ledger.stats(root)["hits"] == 1
