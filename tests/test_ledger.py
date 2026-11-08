"""Step A.1: ledger keys cover every input, entries are append-only, the CLI is JSON-first."""

from __future__ import annotations

import json
import sys
import threading

import jsonschema
import pytest
import yaml
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import cli, companion, ledger  # noqa: E402

ENTRY_SCHEMA = json.loads((TEMPLATE / "schemas" / "ledger-entry.schema.json").read_text())
RESULT_SCHEMA = json.loads((TEMPLATE / "schemas" / "ledger-result.schema.json").read_text())

# One sample per registered kind: a test below fails when a kind has none, so a new kind
# cannot be registered without the change-each-input test covering it.
SAMPLES = {
    "claim-verdict": {"claim": "The draft defines X.", "excerpt": "X is defined as Y."},
    "check-outcome": {"paper/a.tex": "alpha\n", "paper/b.tex": "beta\n"},
    "cold-run": {"paper/a.tex": "alpha\n", "in.txt": "one\n"},
}


@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)


def _key(kind="claim-verdict", **changes):
    inputs = dict(SAMPLES[kind])
    inputs.update(changes.pop("inputs", {}))
    return ledger.key(
        kind,
        inputs,
        changes.pop("version", "1"),
        changes.pop("tier", "2"),
        changes.pop("tools", {"python": "3.12"}),
    )


def test_every_registered_kind_has_a_sample():
    assert set(SAMPLES) == set(ledger.KINDS)


@pytest.mark.parametrize("kind", sorted(ledger.KINDS))
def test_changing_each_declared_input_changes_the_key(kind):
    base = _key(kind)
    for name in SAMPLES[kind]:
        changed = _key(kind, inputs={name: SAMPLES[kind][name] + "x"})
        assert changed.key != base.key, f"{kind}: input {name} is not in the key"


@pytest.mark.parametrize("kind", sorted(ledger.KINDS))
def test_version_tier_and_tools_are_in_the_key(kind):
    base = _key(kind)
    assert _key(kind, version="2").key != base.key
    assert _key(kind, tier="1").key != base.key
    assert _key(kind, tools={"python": "3.13"}).key != base.key
    assert _key(kind, tools={}).key != base.key
    assert _key(kind).key == base.key


def test_closed_kind_refuses_missing_and_undeclared_inputs():
    with pytest.raises(ledger.LedgerError, match="missing input excerpt"):
        ledger.key("claim-verdict", {"claim": "c"}, "1", "2")
    with pytest.raises(ledger.LedgerError, match="undeclared input note"):
        ledger.key("claim-verdict", {**SAMPLES["claim-verdict"], "note": "n"}, "1", "2")
    with pytest.raises(ledger.LedgerError, match="at least one input"):
        ledger.key("check-outcome", {}, "1", "script")
    with pytest.raises(ledger.LedgerError, match="unregistered"):
        ledger.key("summary", {"a": "b"}, "1", "script")


def test_key_hashes_content_not_path_or_mtime(tmp_path):
    one, two = tmp_path / "one.txt", tmp_path / "two.txt"
    one.write_text("same\n")
    two.write_text("same\n")
    one.touch()
    assert ledger.hash_input(one) == ledger.hash_input(two)
    a = ledger.key("check-outcome", {"paper/a.tex": one}, "1", "script")
    b = ledger.key("check-outcome", {"paper/a.tex": two}, "1", "script")
    assert a.key == b.key


def test_crlf_only_change_is_a_hit(tmp_path):
    lf = ledger.key("claim-verdict", {"claim": "c", "excerpt": "a\nb\n"}, "1", "2")
    crlf = ledger.key("claim-verdict", {"claim": "c", "excerpt": "a\r\nb\r\n"}, "1", "2")
    assert lf.key == crlf.key


def test_unchanged_input_hits_and_changed_input_misses(tmp_path):
    keyed = _key()
    assert ledger.lookup(tmp_path, keyed) is None
    assert ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"}) == "created"
    hit = ledger.lookup(tmp_path, _key())
    assert hit and hit["status"] == "pass" and hit["result"] == {"verdict": "supports"}
    assert ledger.lookup(tmp_path, _key(inputs={"claim": "Another wording."})) is None
    assert ledger.stats(tmp_path) == {"hits": 1, "misses": 2, "conflicts": 0, "bypassed": 0}


def test_entry_validates_against_schema_and_has_no_timestamp(tmp_path):
    keyed = _key()
    ledger.put(tmp_path, keyed, "fail", {"lines": ["x"]})
    entry = ledger.get(tmp_path, keyed.kind, keyed.key)
    jsonschema.validate(entry, ENTRY_SCHEMA)
    assert "recorded" not in json.dumps(entry)


def test_different_result_for_existing_key_is_refused(tmp_path):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"})
    with pytest.raises(ledger.LedgerConflict):
        ledger.put(tmp_path, keyed, "fail", {"verdict": "overstates"})
    assert ledger.get(tmp_path, keyed.kind, keyed.key)["status"] == "pass"
    assert ledger.stats(tmp_path)["conflicts"] == 1


def test_equal_result_is_a_noop_and_writes_no_second_provenance(tmp_path):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"})
    before = sorted(p.name for p in (tmp_path / ledger.LEDGER_DIR).rglob("*") if p.is_file())
    assert ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"}) == "exists"
    after = sorted(p.name for p in (tmp_path / ledger.LEDGER_DIR).rglob("*") if p.is_file())
    assert before == after


@pytest.mark.parametrize("status", ["error", "unavailable", "stale", ""])
def test_only_pass_and_fail_are_stored(tmp_path, status):
    with pytest.raises(ledger.LedgerError):
        ledger.put(tmp_path, _key(), status)
    assert ledger.verify(tmp_path) == []
    assert not (tmp_path / ledger.LEDGER_DIR).exists()


def test_concurrent_identical_puts_leave_one_valid_entry(tmp_path):
    keyed = _key()
    outcomes, errors = [], []

    def work():
        try:
            outcomes.append(ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"}))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert outcomes.count("created") == 1 and outcomes.count("exists") == 7
    assert ledger.verify(tmp_path) == []
    assert len(ledger._entry_files(tmp_path)) == 1


def test_two_worktrees_write_identical_entry_bytes(tmp_path):
    keyed = _key()
    first, second = tmp_path / "a", tmp_path / "b"
    ledger.put(first, keyed, "pass", {"verdict": "supports"}, {"tier": "2", "by": "agent"})
    ledger.put(second, keyed, "pass", {"verdict": "supports"}, {"tier": "2", "by": "human"})
    path = ledger._entry_path(first, keyed.kind, keyed.key)
    assert path.read_bytes() == ledger._entry_path(second, keyed.kind, keyed.key).read_bytes()
    # provenance differs per writer and lives under names that cannot collide
    prov_a = {p.name for p in path.parent.glob("*.prov.json")}
    prov_b = {
        p.name for p in ledger._entry_path(second, keyed.kind, keyed.key).parent.glob("*.prov.json")
    }
    assert prov_a and prov_b and prov_a.isdisjoint(prov_b)


def test_provenance_is_returned_with_the_entry(tmp_path):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass", None, {"by": "agent", "procedure": "claim-check"})
    (info,) = ledger.provenance(tmp_path, keyed.kind, keyed.key)
    assert info["by"] == "agent" and "recorded" in info and "python" in info


def test_verify_reports_tampering_and_misplacement(tmp_path):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"})
    assert ledger.verify(tmp_path) == []
    path = ledger._entry_path(tmp_path, keyed.kind, keyed.key)
    entry = json.loads(path.read_text())
    entry["inputs"]["claim"] = "0" * 64  # an input edited by hand: the key no longer recomputes
    path.write_text(json.dumps(entry))
    (problem,) = ledger.verify(tmp_path)
    assert "does not match the entry's inputs" in problem
    with pytest.raises(ledger.LedgerError):
        ledger.get(tmp_path, keyed.kind, keyed.key)  # a corrupt entry is never served
    path.unlink()
    other = ledger._entry_path(tmp_path, keyed.kind, keyed.key).parent.parent / "ff"
    other.mkdir()
    (other / path.name).write_text(_dump_of(keyed))
    assert "wrong shard" in ledger.verify(tmp_path)[0]


def _dump_of(keyed):
    return ledger._dump(ledger._entry_for(keyed, "pass", None))


def test_evict_is_logged_and_removes_provenance(tmp_path):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"})
    with pytest.raises(ledger.LedgerError, match="reason"):
        ledger.evict(tmp_path, keyed.kind, keyed.key, "  ")
    ledger.evict(tmp_path, keyed.kind, keyed.key, "cold run differed")
    assert ledger.get(tmp_path, keyed.kind, keyed.key) is None
    assert not list((tmp_path / ledger.LEDGER_DIR).rglob("*.prov.json"))
    (line,) = (tmp_path / ledger.EVICTIONS).read_text().splitlines()
    log = json.loads(line)
    assert log["key"] == keyed.key and log["reason"] == "cold run differed"
    with pytest.raises(ledger.LedgerError, match="no claim-verdict entry"):
        ledger.evict(tmp_path, keyed.kind, keyed.key, "again")


def test_a_key_that_is_not_hex_cannot_leave_the_ledger(tmp_path):
    with pytest.raises(ledger.LedgerError):
        ledger.get(tmp_path, "claim-verdict", "../../etc/passwd")
    with pytest.raises(ledger.LedgerError):
        ledger.get(tmp_path, "../x", "0" * 64)


def test_switch_off_bypasses_lookups_and_writes(tmp_path, monkeypatch):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass", {"verdict": "supports"})
    monkeypatch.setenv("ARTICLE_LEDGER", "off")
    assert ledger.lookup(tmp_path, keyed) is None
    assert ledger.put(tmp_path, _key(inputs={"claim": "new"}), "pass") == "skipped"
    monkeypatch.delenv("ARTICLE_LEDGER")
    assert len(ledger._entry_files(tmp_path)) == 1
    assert ledger.stats(tmp_path)["bypassed"] == 2


def test_explain_names_the_input_that_differs(tmp_path):
    ledger.put(tmp_path, _key(), "pass", {"verdict": "supports"})
    report = ledger.explain(tmp_path, _key(inputs={"excerpt": "changed"}))
    assert report["changed"] == ["excerpt"] and report["other"] == []
    assert ledger.explain(tmp_path, _key(version="2"))["other"] == ["version"]
    assert ledger.explain(tmp_path / "empty", _key())["nearest"] is None


def test_gc_lists_missing_inputs_not_changed_ones(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "a.tex").write_text("alpha\n")
    (tmp_path / "paper" / "b.tex").write_text("beta\n")
    live = ledger.key("check-outcome", {"paper/a.tex": tmp_path / "paper/a.tex"}, "1", "script")
    ledger.put(tmp_path, live, "pass")
    old = ledger.key("check-outcome", {"paper/b.tex": tmp_path / "paper/b.tex"}, "1", "script")
    ledger.put(tmp_path, old, "pass")
    (tmp_path / "paper" / "b.tex").write_text("beta v2\n")  # changed: still not an orphan
    assert ledger.gc(tmp_path)["orphans"] == []
    (tmp_path / "paper" / "b.tex").unlink()  # gone: now it is
    report = ledger.gc(tmp_path)
    assert [o["key"] for o in report["orphans"]] == [old.key]
    assert report["orphans"][0]["reason"] == "input missing: paper/b.tex"
    assert len(ledger._entry_files(tmp_path)) == 2  # report only
    ledger.gc(tmp_path, apply=True)
    assert len(ledger._entry_files(tmp_path)) == 1
    assert "gc: input missing" in (tmp_path / ledger.EVICTIONS).read_text()


def test_gc_lists_verdict_of_a_claim_that_left_the_map(tmp_path, monkeypatch):
    kept = ledger.key("claim-verdict", {"claim": "Kept claim.", "excerpt": "e"}, "1", "2")
    gone = ledger.key("claim-verdict", {"claim": "Deleted claim.", "excerpt": "e"}, "1", "2")
    ledger.put(tmp_path, kept, "pass")
    ledger.put(tmp_path, gone, "pass")
    from scripts.article import theses

    monkeypatch.setattr(
        theses, "load_map",
        lambda root: {"nodes": [{"id": "n1", "text": "Kept claim."}]},
    )  # fmt: skip
    monkeypatch.setattr(theses, "structure_errors", lambda data: type("R", (), {"ok": True})())
    report = ledger.gc(tmp_path)
    assert [(o["key"], o["reason"]) for o in report["orphans"]] == [
        (gone.key, "claim no longer in the map")
    ]
    assert len(ledger._entry_files(tmp_path)) == 2  # report-only without --apply
    ledger.gc(tmp_path, apply=True)
    assert [e.stem for e in ledger._entry_files(tmp_path)] == [kept.key]
    assert "gc: claim no longer in the map" in (tmp_path / ledger.EVICTIONS).read_text()


def test_gc_touches_no_verdict_when_the_map_is_unreadable(tmp_path):
    ledger.put(tmp_path, _key(), "pass")
    assert ledger.gc(tmp_path)["orphans"] == []  # no theses.yaml at all
    (tmp_path / "theses.yaml").write_text("not: [valid", encoding="utf-8")
    assert ledger.gc(tmp_path)["orphans"] == []


# ------------------------------------------------------------------------ CLI


def _run(capsys, root, *argv):
    code = cli.main(["--root", str(root), "ledger", *argv])
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, RESULT_SCHEMA)
    return code, out


def test_cli_get_miss_hit_explain_and_stats(tmp_path, capsys, monkeypatch):
    # `--no-ledger` sets the variable in-process; restore it when the test ends
    monkeypatch.setenv("ARTICLE_LEDGER", "on")
    (tmp_path / "claim.txt").write_text("The draft defines X.\n")
    args = [
        "claim-verdict", "--version", "1", "--tier", "2",
        "--input", "claim=claim.txt", "--text", "excerpt=X is Y.",
    ]  # fmt: skip
    code, out = _run(capsys, tmp_path, "get", *args)
    assert code == 1 and out["hit"] is False
    ledger.put(
        tmp_path,
        ledger.key(
            "claim-verdict", {"claim": tmp_path / "claim.txt", "excerpt": "X is Y."}, "1", "2"
        ),
        "pass",
    )
    code, out = _run(capsys, tmp_path, "get", *args)
    assert code == 0 and out["hit"] is True and out["entry"]["status"] == "pass"
    assert len(out["provenance"]) == 1
    (tmp_path / "claim.txt").write_text("A changed claim.\n")
    code, out = _run(capsys, tmp_path, "explain", *args)
    assert code == 0 and out["changed"] == ["claim"]
    code, out = _run(capsys, tmp_path, "get", *args, "--no-ledger")
    assert out["hit"] is False and out["bypassed"] is True
    code, out = _run(capsys, tmp_path, "stats")
    assert out["stats"]["hits"] == 1


def test_cli_verify_evict_gc_and_usage_errors(tmp_path, capsys):
    keyed = _key()
    ledger.put(tmp_path, keyed, "pass")
    assert _run(capsys, tmp_path, "verify")[0] == 0
    code, out = _run(capsys, tmp_path, "gc")
    assert code == 0 and out["orphans"] == [] and out["applied"] is False
    code, out = _run(capsys, tmp_path, "evict", "claim-verdict", keyed.key, "--reason", "test")
    assert code == 0 and out["evicted"] is True
    code, out = _run(capsys, tmp_path, "get", "claim-verdict", "--tier", "2")
    assert code == 1 and "give --version and --tier" in out["error"]
    code, out = _run(
        capsys, tmp_path, "get", "claim-verdict", "--version", "1", "--tier", "2", "--input", "bad"
    )
    assert code == 1 and "name=PATH" in out["error"]


def test_there_is_no_cli_verb_that_writes_an_entry():
    actions = {"get", "explain", "verify", "evict", "gc", "stats"}
    parser = cli.build_parser()
    sub = next(
        a for a in parser._subparsers._group_actions[0].choices["ledger"]._subparsers._group_actions
    )
    assert set(sub.choices) == actions


# ------------------------------------------------------------------- template


def test_companion_default_excludes_ledger_and_source_store():
    config = yaml.safe_load((TEMPLATE / "companion.yaml").read_text())
    denied = companion._matcher(config["exclude"])
    allowed = companion._matcher(config["include"])
    for path in (
        "docs/ledger/claim-verdict/ab/" + "ab" * 32 + ".json",
        "docs/ledger/evictions.jsonl",
        "paper/sources/draft-x/raw.txt",
    ):
        assert denied(path), path
    assert allowed("paper/article.tex") and not denied("paper/article.tex")


def test_template_ships_the_ledger_directory_and_attributes():
    assert (TEMPLATE / "docs" / "ledger" / "README.md").is_file()
    assert "docs/ledger/**" in (TEMPLATE / ".gitattributes").read_text()
