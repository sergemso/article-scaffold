"""Step A.3: named checks are recorded in the ledger and read without running anything."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml
from conftest import ROOT
from flow_helpers import THESIS_MAP, cli

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import flow, ledger  # noqa: E402

SCHEMA = json.loads((TEMPLATE / "schemas" / "flow.schema.json").read_text())


@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)


@pytest.fixture
def fixture_check(tmp_path, monkeypatch):
    """A fixture table check that appends to a marker file each time it really runs."""
    (tmp_path / "in.txt").write_text("one\n")
    marker = tmp_path / "marker"
    script = tmp_path / "run.py"
    script.write_text(
        "import sys, pathlib\n"
        f"pathlib.Path({str(marker)!r}).open('a').write('x')\n"
        "text = pathlib.Path('in.txt').read_text()\n"
        "if 'bad' in text:\n    print('first line ' + 'AKIA' + 'ABCDEFGHIJKLMNOP' + ' leaked')\n"
        "    print('second line password = hunter2')\n    sys.exit(1)\n"
    )
    monkeypatch.setitem(flow.CHECKS, "fixture", ("python", str(script)))
    monkeypatch.setitem(flow.CHECK_SPECS, "fixture", flow.CheckSpec(("in.txt",)))
    return tmp_path, marker


def runs(marker: Path) -> int:
    return len(marker.read_text()) if marker.exists() else 0


def test_record_twice_runs_once_and_read_then_hits(fixture_check):
    root, marker = fixture_check
    assert flow.check_read(root, "fixture")["state"] == "miss"
    first = flow.check_record(root, "fixture")
    assert (first["state"], first["verdict"], first["stored"]) == ("ran", "pass", True)
    second = flow.check_record(root, "fixture")
    assert (second["state"], second["stored"]) == ("hit", False)
    assert runs(marker) == 1
    read = flow.check_read(root, "fixture")
    assert (read["state"], read["verdict"]) == ("hit", "pass")
    assert runs(marker) == 1


def test_editing_a_matched_input_is_stale_and_rerun_records_again(fixture_check):
    root, marker = fixture_check
    flow.check_record(root, "fixture")
    (root / "in.txt").write_text("two\n")
    read = flow.check_read(root, "fixture")
    assert read["state"] == "stale" and read["changed"] == ["in.txt"]
    assert flow.check_record(root, "fixture")["state"] == "ran"
    assert runs(marker) == 2


def test_a_crlf_only_change_still_hits(fixture_check):
    root, _ = fixture_check
    flow.check_record(root, "fixture")
    (root / "in.txt").write_bytes(b"one\r\n")
    assert flow.check_read(root, "fixture")["state"] == "hit"


def test_fail_is_stored_with_redacted_capped_lines(fixture_check):
    root, marker = fixture_check
    (root / "in.txt").write_text("bad\n")
    result = flow.check_record(root, "fixture")
    assert (result["verdict"], result["stored"], result["ok"]) == ("fail", True, False)
    joined = " ".join(result["failing"])
    assert "AKIA" not in joined and "hunter2" not in joined and "[redacted]" in joined
    read = flow.check_read(root, "fixture")
    assert (read["state"], read["verdict"]) == ("hit", "fail")
    assert read["failing"] == result["failing"]
    assert set(read) <= {"ok", "command", "name", "state", "verdict", "key", "failing"}
    assert runs(marker) == 1


def test_failing_lines_are_capped():
    lines = [f"line {n} " + "x" * 500 for n in range(20)]
    out = flow.failing_lines(lines)
    assert len(out) == flow.FAILING_LINES and all(len(line) <= flow.FAILING_WIDTH for line in out)


def test_non_deterministic_check_is_never_stored(fixture_check, monkeypatch):
    root, marker = fixture_check
    monkeypatch.setitem(
        flow.CHECK_SPECS, "fixture", flow.CheckSpec(("in.txt",), deterministic=False)
    )
    assert flow.check_read(root, "fixture")["state"] == "uncacheable"
    for _ in range(2):
        assert flow.check_record(root, "fixture")["stored"] is False
    assert runs(marker) == 2
    assert not (root / "docs" / "ledger").exists()


def test_timeout_and_unavailable_are_errors_and_not_stored(fixture_check, monkeypatch):
    root, _ = fixture_check

    def timeout(*args, **kwargs):
        raise flow.subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(flow.subprocess, "run", timeout)
    result = flow.check_record(root, "fixture")
    assert (result["state"], result["stored"], result["ok"]) == ("error", False, False)
    monkeypatch.undo()
    assert not (root / "docs" / "ledger").exists()


def test_missing_script_is_unavailable_and_not_stored(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "article.pdf").write_bytes(b"%PDF")
    result = flow.check_record(tmp_path, "layout-check")
    assert (result["state"], result["stored"]) == ("unavailable", False)
    assert not (tmp_path / "docs" / "ledger").exists()


def test_unknown_name_is_refused(tmp_path):
    for call in (flow.check_read, flow.check_record):
        with pytest.raises(flow.FlowError):
            call(tmp_path, "rm -rf")


def test_every_table_check_declares_inputs():
    assert set(flow.CHECK_SPECS) == set(flow.CHECKS)


def test_changing_each_declared_glob_changes_the_key(tmp_path, monkeypatch):
    monkeypatch.setitem(flow.CHECKS, "fixture", ("python", "x.py"))
    monkeypatch.setitem(flow.CHECK_SPECS, "fixture", flow.CheckSpec(("a.txt", "b/*.txt")))
    (tmp_path / "b").mkdir()
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b" / "c.txt").write_text("c")
    base = flow.check_keyed(tmp_path, "fixture").key
    (tmp_path / "a.txt").write_text("A")
    assert flow.check_keyed(tmp_path, "fixture").key != base
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b" / "c.txt").write_text("C")
    assert flow.check_keyed(tmp_path, "fixture").key != base
    (tmp_path / "b" / "c.txt").write_text("c")
    (tmp_path / "b" / "d.txt").write_text("new")
    assert flow.check_keyed(tmp_path, "fixture").key != base


def test_two_checks_over_the_same_inputs_have_different_keys(tmp_path):
    (tmp_path / "theses.yaml").write_text(THESIS_MAP)
    assert (
        flow.check_keyed(tmp_path, "theses-lint").key
        != flow.check_keyed(tmp_path, "theses-gaps").key
    )


def test_flow_done_uses_the_same_key_and_hits(flow_project, monkeypatch):
    (flow_project / "theses.yaml").write_text(THESIS_MAP)
    keyed = flow.check_keyed(flow_project, "theses-lint")
    first = flow.check_record(flow_project, "theses-lint")
    assert first["stored"] is True
    assert ledger.get(flow_project, "check-outcome", keyed.key) is not None
    # done reuses the stored outcome: a hit never launches a process
    monkeypatch.setattr(flow.subprocess, "run", lambda *a, **k: pytest.fail("ran"))
    again = flow.check_record(flow_project, "theses-lint")
    assert again["state"] == "hit"


def test_cli_check_is_a_read_and_record_writes(flow_project):
    (flow_project / "theses.yaml").write_text(THESIS_MAP)
    missed = cli(flow_project, "check", "theses-lint")
    assert missed.returncode == 1 and json.loads(missed.stdout)["state"] == "miss"
    assert not (flow_project / "docs" / "ledger" / "check-outcome").exists()
    recorded = cli(flow_project, "check", "record", "theses-lint")
    assert recorded.returncode == 0 and json.loads(recorded.stdout)["stored"] is True
    hit = cli(flow_project, "check", "theses-lint")
    assert hit.returncode == 0 and json.loads(hit.stdout)["state"] == "hit"


def test_cli_refuses_unknown_name_and_extra_arguments(flow_project):
    assert cli(flow_project, "check", "nope").returncode == 1
    assert cli(flow_project, "check", "record", "nope").returncode == 1
    assert cli(flow_project, "check", "theses-lint", "extra").returncode == 2
    assert cli(flow_project, "check", "record", "theses-lint", "extra").returncode == 2
    assert cli(flow_project, "flow", "done", "o-1", "extra").returncode == 2
    done = cli(flow_project, "flow", "done", "o-unknown")
    assert done.returncode == 1 and "unknown order" in done.stdout


def test_flow_file_with_a_command_field_is_rejected_by_the_schema(flow_project):
    jsonschema = pytest.importorskip("jsonschema")
    state = yaml.safe_load((flow_project / "flow.yaml").read_text())
    jsonschema.validate(state, SCHEMA)
    state["command"] = "make test"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(state, SCHEMA)


def test_old_editions_are_not_check_inputs(tmp_path):
    from scripts.article import sources

    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "a.tex").write_text("alpha\n")
    for edition, body in (("01", "first draft\n"), ("02", "second draft\n")):
        src = tmp_path / "ext.txt"
        src.write_text(body)
        sources.add(tmp_path, src, origin="https://example.org/x", edition=edition, key="draft-x")
        sources.index(tmp_path)
    inputs = flow.check_keyed(tmp_path, "theses-lint").inputs
    store = sorted(n for n in inputs if n.startswith("paper/sources/"))
    current = sources.current_edition(tmp_path, "draft-x")
    assert store == [
        "paper/sources/draft-x/" + current["raw_hash"] + "/normalized.txt",
        "paper/sources/manifest.json",
    ]
    # nothing of the first edition (raw, normalized, locators) is an input
    first = next(e for e in sources.load_manifest(tmp_path) if e["edition"] == "01")
    assert not any(first["raw_hash"] in n for n in inputs)


def test_check_ok_agrees_with_the_exit_code(flow_project):
    """`check NAME`: ok is true (exit 0) only for a hit with a stored pass."""
    (flow_project / "theses.yaml").write_text(THESIS_MAP)
    missed = cli(flow_project, "check", "theses-lint")
    assert (json.loads(missed.stdout)["ok"], missed.returncode) == (False, 1)
    cli(flow_project, "check", "record", "theses-lint")
    hit = cli(flow_project, "check", "theses-lint")
    assert (json.loads(hit.stdout)["ok"], hit.returncode) == (True, 0)
    (flow_project / "theses.yaml").write_text(THESIS_MAP + "# edited\n")
    stale = cli(flow_project, "check", "theses-lint")
    assert (json.loads(stale.stdout)["state"], json.loads(stale.stdout)["ok"]) == ("stale", False)
    assert stale.returncode == 1


def test_stored_fail_reads_as_not_ok(fixture_check):
    root, _ = fixture_check
    (root / "in.txt").write_text("bad\n")
    flow.check_record(root, "fixture")
    assert flow.check_read(root, "fixture")["ok"] is False


def test_index_check_is_never_stored_so_a_built_index_passes(tmp_path, monkeypatch):
    """G.2: the check reads untracked build output the key cannot see."""
    assert flow.CHECK_SPECS["index-check"].deterministic is False
    (tmp_path / "in.txt").write_text("one\n")
    script = tmp_path / "run.py"
    script.write_text(
        "import sys, pathlib\n"
        "sys.exit(0 if pathlib.Path('index.json').exists() else 1)\n"
    )
    monkeypatch.setitem(flow.CHECKS, "index-check", ("python", str(script)))
    spec = flow.CheckSpec(("in.txt",), deterministic=False)
    monkeypatch.setitem(flow.CHECK_SPECS, "index-check", spec)
    failed = flow.check_record(tmp_path, "index-check")
    assert (failed["verdict"], failed["stored"]) == ("fail", False)
    (tmp_path / "index.json").write_text("{}")
    passed = flow.check_record(tmp_path, "index-check")
    assert (passed["ok"], passed["state"]) == (True, "ran")

