"""Step A.4: a cold run ignores lookups, evicts what disagrees, and opens the release gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import ROOT
from flow_helpers import cli

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import flow, ledger  # noqa: E402


@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Two fixture table checks reading in.txt; every real check is made inert."""
    (tmp_path / "in.txt").write_text("one\n")
    marker = tmp_path / "marker"
    script = tmp_path / "run.py"
    script.write_text(
        "import sys, pathlib\n"
        f"pathlib.Path({str(marker)!r}).open('a').write('x')\n"
        "sys.exit(1 if 'bad' in pathlib.Path('in.txt').read_text() else 0)\n"
    )
    monkeypatch.setattr(flow, "CHECKS", {"fix": ("python", str(script))})
    monkeypatch.setattr(flow, "CHECK_SPECS", {"fix": flow.CheckSpec(("in.txt",))})
    monkeypatch.setattr(flow, "CHECK_SCRIPTS", {})
    return tmp_path, marker


def runs(marker: Path) -> int:
    return len(marker.read_text()) if marker.exists() else 0


def test_clean_cold_run_records_and_opens_the_gate(repo):
    root, _ = repo
    assert flow.cold_run_recorded(root) is False
    result = flow.cold_run(root)
    assert result["ok"] and result["recorded"] and result["differences"] == []
    assert flow.cold_run_recorded(root) is True


def test_a_warm_hit_never_satisfies_the_gate(repo):
    root, marker = repo
    flow.check_record(root, "fix")  # a warm entry exists
    assert flow.cold_run_recorded(root) is False
    flow.cold_run(root)
    assert runs(marker) == 2  # the cold run ran the check despite the hit


def test_a_stale_ledgered_result_fails_the_cold_run_and_is_evicted(repo):
    root, _ = repo
    flow.check_record(root, "fix")
    keyed = flow.check_keyed(root, "fix")
    path = root / "docs" / "ledger" / "check-outcome" / keyed.key[:2] / f"{keyed.key}.json"
    entry = json.loads(path.read_text())
    entry["status"] = "fail"  # the ledger now claims a result the cold run will contradict
    path.write_text(json.dumps(entry))
    result = flow.cold_run(root)
    assert result["ok"] is False and result["recorded"] is False
    assert result["differences"] == [{"check": "fix", "ledger": "fail", "cold": "pass"}]
    log = (root / ledger.EVICTIONS).read_text().splitlines()
    assert len(log) == 1 and keyed.key in log[0] and "cold run differs" in log[0]
    assert flow.cold_run_recorded(root) is False
    assert ledger.get(root, "check-outcome", keyed.key)["status"] == "pass"  # replaced
    assert flow.cold_run(root)["ok"] is True  # the next cold run is clean


def test_a_failing_check_fails_the_cold_run(repo):
    root, _ = repo
    (root / "in.txt").write_text("bad\n")
    result = flow.cold_run(root)
    assert result["ok"] is False and result["failed"] == ["fix"]
    assert flow.cold_run_recorded(root) is False


def test_any_input_change_after_the_cold_run_closes_the_gate(repo):
    root, _ = repo
    flow.cold_run(root)
    (root / "in.txt").write_text("two\n")
    assert flow.cold_run_recorded(root) is False
    (root / "in.txt").write_text("one\n")
    assert flow.cold_run_recorded(root) is True


def test_ledger_off_neither_records_nor_satisfies(repo, monkeypatch):
    root, _ = repo
    flow.cold_run(root)
    monkeypatch.setenv("ARTICLE_LEDGER", "off")
    assert flow.cold_run_recorded(root) is True  # a file read: the record is real
    assert flow.cold_run(root)["ok"] is False


def test_unavailable_and_error_do_not_record(repo, monkeypatch):
    root, _ = repo

    def timeout(*args, **kwargs):
        raise flow.subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(flow.subprocess, "run", timeout)
    result = flow.cold_run(root)
    assert result["ok"] is False and result["errors"]
    assert flow.cold_run_recorded(root) is False


def test_non_deterministic_checks_are_skipped(repo, monkeypatch):
    root, marker = repo
    monkeypatch.setitem(flow.CHECKS, "git", ("python", "nothing.py"))
    monkeypatch.setitem(
        flow.CHECK_SPECS, "git", flow.CheckSpec(("in.txt",), deterministic=False)
    )
    result = flow.cold_run(root)
    assert result["checks"]["git"] == "skipped" and result["ok"] is True


def test_gate_lists_the_tier_2_entries_it_relied_on(repo):
    root, _ = repo
    keyed = ledger.key("claim-verdict", {"claim": "c", "excerpt": "e"}, "1", "2")
    ledger.put(root, keyed, "pass", None, {"author": "agent"})
    info = flow.relied_on(root)
    assert info["count"] == 1
    assert info["entries"][0]["author"] == "agent" and info["entries"][0]["key"] == keyed.key[:12]


def test_next_order_runs_no_check_and_no_subprocess_but_git(flow_project, monkeypatch):
    """The release plan the gate already read shells out to `git` (read-only); nothing else."""
    from flow_helpers import CLEAN_MAP, write_map

    write_map(flow_project, CLEAN_MAP)
    seen: list[list[str]] = []
    real = flow.subprocess.run

    def spy(argv, *args, **kwargs):
        seen.append(list(argv))
        return real(argv, *args, **kwargs)

    for name in ("run_check", "check_record", "cold_run"):
        monkeypatch.setattr(flow, name, lambda *a, **k: pytest.fail("a check ran"))
    monkeypatch.setattr(flow.subprocess, "run", spy)
    flow.status(flow_project)
    flow.next_order(flow_project)
    assert all(argv[0] == "git" for argv in seen), seen


def test_cli_cold_takes_no_name(flow_project):
    assert cli(flow_project, "check", "--cold", "theses-lint").returncode == 2
    assert cli(flow_project, "check").returncode == 2


def _with_missing_script(monkeypatch, name, optional):
    monkeypatch.setitem(flow.CHECKS, name, ("python", f"scripts/{name}.py"))
    monkeypatch.setitem(flow.CHECK_SCRIPTS, name, f"scripts/{name}.py")
    monkeypatch.setitem(
        flow.CHECK_SPECS, name, flow.CheckSpec((f"scripts/{name}.py",), optional=optional)
    )


def test_a_missing_script_of_a_declared_optional_check_is_not_applicable(repo, monkeypatch):
    root, _ = repo
    _with_missing_script(monkeypatch, "extra", optional=True)
    result = flow.cold_run(root)
    assert result["ok"] is True and result["recorded"] is True
    assert result["checks"]["extra"] == "not-applicable" and result["errors"] == []
    assert flow.cold_run_recorded(root) is True


def test_adding_the_optional_script_later_closes_the_gate(repo, monkeypatch):
    root, _ = repo
    _with_missing_script(monkeypatch, "extra", optional=True)
    flow.cold_run(root)
    (root / "scripts").mkdir()
    (root / "scripts" / "extra.py").write_text("import sys\nsys.exit(0)\n")
    assert flow.cold_run_recorded(root) is False


def test_an_undeclared_unavailable_check_fails_the_cold_run(repo, monkeypatch):
    root, _ = repo
    _with_missing_script(monkeypatch, "needed", optional=False)
    result = flow.cold_run(root)
    assert result["ok"] is False and result["recorded"] is False
    assert result["checks"]["needed"] == "unavailable"
    assert any(e.startswith("needed:") for e in result["errors"])
    assert flow.cold_run_recorded(root) is False


def test_the_shipped_table_declares_only_the_two_script_checks_optional():
    optional = {n for n, s in flow.CHECK_SPECS.items() if s.optional}
    assert optional == {"layout-check", "lint-counts"}
    assert optional <= set(flow.CHECK_SCRIPTS)
    for name in set(flow.CHECK_SCRIPTS) - optional:
        raise AssertionError(f"{name} needs a script but is not declared optional")


def test_cold_run_on_a_repo_without_the_optional_scripts_opens_the_gate(repo, monkeypatch):
    root, _ = repo
    monkeypatch.setattr(flow, "CHECKS", {"fix": flow.CHECKS["fix"]})
    for name in ("layout-check", "lint-counts"):
        monkeypatch.setitem(flow.CHECKS, name, ("python", f"scripts/{name}.py"))
        monkeypatch.setitem(flow.CHECK_SCRIPTS, name, f"scripts/{name}.py")
        spec = flow.CheckSpec((f"scripts/{name}.py",), optional=True)
        monkeypatch.setitem(flow.CHECK_SPECS, name, spec)
    result = flow.cold_run(root)
    assert result["ok"] and result["checks"]["lint-counts"] == "not-applicable"
