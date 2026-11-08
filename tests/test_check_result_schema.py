"""Step G.7: `check`, `check record` and `check --cold` output validates against its schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import cli, flow  # noqa: E402

SCHEMA = json.loads((TEMPLATE / "schemas" / "check-result.schema.json").read_text())
jsonschema.Draft7Validator.check_schema(SCHEMA)


@pytest.fixture(autouse=True)
def _ledger_on(monkeypatch):
    monkeypatch.delenv("ARTICLE_LEDGER", raising=False)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fixture table: `fix` reads in.txt and fails on 'bad'; `volatile` is never stored."""
    (tmp_path / "in.txt").write_text("one\n")
    script = tmp_path / "run.py"
    script.write_text(
        "import sys, pathlib\n"
        "if 'bad' in pathlib.Path('in.txt').read_text():\n"
        "    print('first failing line'); sys.exit(1)\n"
    )
    command = ("python", str(script))
    monkeypatch.setattr(flow, "CHECKS", {"fix": command, "volatile": command})
    monkeypatch.setattr(
        flow, "CHECK_SPECS",
        {"fix": flow.CheckSpec(("in.txt",)),
         "volatile": flow.CheckSpec(("in.txt",), deterministic=False)},
    )
    monkeypatch.setattr(flow, "CHECK_SCRIPTS", {})
    return tmp_path


def run(root: Path, capsys, *argv: str) -> tuple[int, dict]:
    code = cli.main(["--root", str(root), "check", *argv])
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, SCHEMA)
    return code, out


def test_read_states_validate(repo, capsys):
    code, miss = run(repo, capsys, "fix")
    assert (code, miss["state"]) == (1, "miss")
    run(repo, capsys, "record", "fix")
    code, hit = run(repo, capsys, "fix")
    assert (code, hit["state"], hit["verdict"]) == (0, "hit", "pass")
    (repo / "in.txt").write_text("two\n")
    code, stale = run(repo, capsys, "fix")
    assert (code, stale["state"], stale["changed"]) == (1, "stale", ["in.txt"])
    assert run(repo, capsys, "volatile")[1]["state"] == "uncacheable"


def test_record_states_validate(repo, capsys):
    _, ran = run(repo, capsys, "record", "fix")
    assert (ran["state"], ran["stored"]) == ("ran", True)
    _, hit = run(repo, capsys, "record", "fix")
    assert (hit["state"], hit["stored"]) == ("hit", False)
    (repo / "in.txt").write_text("bad\n")
    code, failed = run(repo, capsys, "record", "fix")
    assert (code, failed["verdict"], failed["failing"]) == (1, "fail", ["first failing line"])
    _, volatile = run(repo, capsys, "record", "volatile")
    assert volatile["stored"] is False


def test_unavailable_and_unknown_validate(repo, capsys, monkeypatch):
    monkeypatch.setattr(flow, "CHECK_SCRIPTS", {"fix": "scripts/missing.py"})
    _, error = run(repo, capsys, "record", "fix")
    assert (error["state"], error["stored"]) == ("unavailable", False)
    code, unknown = run(repo, capsys, "nope")
    assert (code, unknown["ok"]) == (1, False) and "error" in unknown
    assert run(repo, capsys, "record", "nope")[1]["command"] == "check record"


def test_cold_run_validates(repo, capsys, monkeypatch):
    code, cold = run(repo, capsys, "--cold")
    assert (code, cold["ok"], cold["recorded"]) == (0, True, True)
    assert cold["checks"] == {"fix": "pass", "volatile": "skipped"}
    (repo / "in.txt").write_text("bad\n")
    code, failed = run(repo, capsys, "--cold")
    assert (code, failed["failed"]) == (1, ["fix"])
    monkeypatch.setenv("ARTICLE_LEDGER", "off")
    code, off = run(repo, capsys, "--cold")
    assert (code, off["ok"]) == (1, False) and "error" in off


def test_schema_is_strict():
    bad = {"ok": True, "command": "check", "name": "fix", "state": "miss", "extra": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)
