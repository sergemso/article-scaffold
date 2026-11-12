"""Tier 2 verdicts, the one-time window widening and tier 3 routing (decision 0075)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import ROOT
from test_ledger_claims import FAR, _repo

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import claims, flow, ledger  # noqa: E402
from test_claims import _node  # noqa: E402


@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)


def _one(tmp_path: Path, **extra: object) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return _repo(tmp_path, _node("c1", "Alpha holds under load.", **extra), source=FAR)


def _cached(root: Path) -> str | None:
    return claims.quote_check(root, "c1")[0].get("cached")


def test_new_verdicts_round_trip_with_status(tmp_path):
    for verdict in ("out-of-context", "translation-sensitive", "supports-with-reading", "unclear"):
        root = _one(tmp_path / verdict)
        claims.verdict_for_node(root, "c1", verdict)
        assert _cached(root) == verdict
        status = "pass" if verdict == "supports-with-reading" else "fail"
        (key,) = ledger.keys(root, "claim-verdict")
        entry = ledger.get(root, "claim-verdict", key)
        assert entry["status"] == status


def test_default_node_keeps_the_key_it_had(tmp_path):
    root = _one(tmp_path)
    node = claims.source_claims(root)[0]
    excerpt = claims.excerpt_for(root, "c1")
    assert claims.key_extras(node) == {}
    assert claims.verdict_key(node["text"], excerpt, {}).key == claims.verdict_key(
        node["text"], excerpt
    ).key


@pytest.mark.parametrize(
    "before, after",
    [
        ({}, {"context": {"stance": "reports"}}),
        ({"context": {"stance": "reports"}}, {"context": {"stance": "rejects"}}),
        ({"context": {"scope-note": "a"}}, {"context": {"scope-note": "b"}}),
        ({}, {"context": {"window": 50}}),
        ({}, {"translation": {"original": "x", "original-quote": "Alpha"}}),
    ],
)
def test_a_changed_context_field_invalidates_the_cached_verdict(tmp_path, before, after):
    root = _one(tmp_path, **before)
    claims.verdict_for_node(root, "c1", "supports")
    assert _cached(root) == "supports"
    edited = _node("c1", "Alpha holds under load.", **after)
    (root / "theses.yaml").write_text("version: 1\nnodes:\n" + edited + "edges: []\n")
    assert _cached(root) is None


def test_needs_wider_context_widens_once_then_reports_unclear(tmp_path):
    root = _one(tmp_path)
    narrow = claims.excerpt_for(root, "c1")
    wide = claims.excerpt_for(root, "c1", widen=True)
    assert len(wide) > len(narrow)
    first = claims.verdict_for_node(root, "c1", claims.NEEDS_WIDER)
    assert first == {"id": "c1", "key": None, "verdict": None, "next": "widen"}
    assert ledger.keys(root, "claim-verdict") == []  # nothing stored by the request
    second = claims.verdict_for_node(root, "c1", claims.NEEDS_WIDER, widen=True)
    assert second["verdict"] == "unclear"
    assert _cached(root) == "unclear"  # read at the normal window, found at the widened one
    assert len(ledger.keys(root, "claim-verdict")) == 1


def test_a_verdict_at_the_widened_window_is_its_own_entry(tmp_path):
    root = _one(tmp_path)
    claims.verdict_for_node(root, "c1", "overstates")
    claims.verdict_for_node(root, "c1", "supports", widen=True)
    assert len(ledger.keys(root, "claim-verdict")) == 2
    assert _cached(root) == "overstates"  # the normal window answers first


def test_tier3_routing(tmp_path):
    plain = claims.quote_check(_one(tmp_path / "a"), "c1")[0]
    assert "tier3" not in plain
    interp = claims.quote_check(_one(tmp_path / "b", reading="interpretive"), "c1")[0]
    assert interp["tier3"] == ["interpretive-reading"] and interp["consult"] == ["edition"]
    root = _one(tmp_path / "c")
    claims.verdict_for_node(root, "c1", "translation-sensitive")
    assert claims.quote_check(root, "c1")[0]["tier3"] == ["kept-translation-sensitive"]
    root = _one(tmp_path / "d")
    claims.verdict_for_node(root, "c1", "supports-with-reading")
    assert "tier3" not in claims.quote_check(root, "c1")[0]
    (tmp_path / "e").mkdir()
    missing = _repo(tmp_path / "e", _node("c1", "Alpha.", locator={"edition": "nope"}), source=FAR)
    record = claims.quote_check(missing, "c1")[0]
    assert record["tier3"] == ["edition-unverifiable"]


class _Facts:
    def __init__(self, *attestations: dict):
        self.state = {"attestations": list(attestations)}

    def attested(self, name: str) -> bool:
        return any(a["name"] == name for a in self.state["attestations"])


def _attestation(**extra: str) -> dict:
    return {"name": "claim:c1", "by": "Ada", "at": "2026-11-11", "why": "read it", **extra}


def test_tier3_needs_an_attestation_naming_the_edition(tmp_path):
    record = claims.quote_check(_one(tmp_path, reading="interpretive"), "c1")[0]
    assert flow.source_claim_state(_Facts(), record) == "needs-attestation"
    bare = _Facts(_attestation())
    assert flow.source_claim_state(bare, record) == "needs-attestation"
    full = _Facts(_attestation(edition="smith2020"))
    assert flow.source_claim_state(full, record) == "attested"


def test_translation_attestation_also_names_the_translation(tmp_path):
    translation = {"original": "orig", "translator": "T"}
    root = _one(tmp_path, reading="interpretive", translation=translation)
    record = claims.quote_check(root, "c1")[0]
    assert record["consult"] == ["edition", "translation"]
    only_edition = _Facts(_attestation(edition="e"))
    assert flow.source_claim_state(only_edition, record) == "needs-attestation"
    both = _Facts(_attestation(edition="e", translation="t"))
    assert flow.source_claim_state(both, record) == "attested"


def test_gate_states_for_the_new_verdicts():
    base = {"id": "c1", "verdict": "found"}
    facts = _Facts()
    for cached, state in [
        ("supports", "ok"), ("supports-with-reading", "ok"), ("out-of-context", "out-of-context"),
        ("unclear", "unclear"), (None, "needs-check"),
    ]:
        assert flow.source_claim_state(facts, {**base, "cached": cached}) == state


def test_a_legacy_attestation_without_tier3_still_counts():
    record = {"id": "c1", "verdict": "no-local-text"}
    assert flow.source_claim_state(_Facts(_attestation()), record) == "attested"


def test_attest_records_edition_and_translation(tmp_path):
    flow.attest(
        tmp_path, "claim:c1", "Ada", "read it", confirmed=True, edition="e1", translation="t1"
    )
    entry = flow.load_state(tmp_path)["attestations"][0]
    assert entry["edition"] == "e1" and entry["translation"] == "t1"
