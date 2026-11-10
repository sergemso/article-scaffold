"""The maintainer replay wrapper: dry runs of the pilot orders, the spend limit, the handoff."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT

SCRIPT = ROOT / "scripts" / "replay-order.py"
SPEC = importlib.util.spec_from_file_location("replay_order", SCRIPT)
assert SPEC and SPEC.loader
ro = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ro)

ORDERS = ROOT / "scripts" / "replay-orders"

# sha256 of the task and brief files the pilot used (docs/notes/e3-pilot-comparison.md).
PILOT_HASHES = {
    "order1": ("f155607dfb8dcdd06e08745d7c209614396ccf59e640768f1eda627859f6ae6e",
               "c3bb89b9e1a6b46310c4ebb7c5d2de4b7b16d16d23c7f3c159c56a6cdb1bc934"),
    "order2": ("b4d096f961e44d1dd5831c5596fd246747d43e7cf8ae53539439516f616cf8a3",
               "e049ace451e997bbbff724e9f51586a67f887bae949fbda8a84250aea147e839"),
    "order3": ("841fde17c5da06ab6eade08109679b9c199f1fb2c1760608fbebfd59e3d511c6",
               "7f1ed1c5cf60563d79aad21a30cb5cfc1b13f1a60e2162725aaa4b9448f68a85"),
}

FAKE_CLAUDE = """\
#!/usr/bin/env python3
import json, sys
state = {state!r}
prompt = sys.stdin.read()
n = len(json.load(open(state))) if __import__("os").path.exists(state) else 0
calls = json.load(open(state)) if n else []
calls.append({{"argv": sys.argv[1:], "prompt": prompt}})
json.dump(calls, open(state, "w"))
if "--resume" in sys.argv:
    out = {{"result": '{{"done": ["a"], "remaining": [], "verify": "pass", '
                      '"evidence": ["pytest: 3 passed"]}}',
           "total_cost_usd": 1.05, "num_turns": 1, "subtype": "success"}}
elif "stopped at its call limit" in prompt:
    out = {{"result": '{{"done": ["a"], "remaining": ["b"], "verify": "not-run"}}',
           "total_cost_usd": 0.01, "num_turns": 1, "subtype": "success"}}
elif "Handoff from the previous segment" in prompt:
    out = {{"subtype": "success", "total_cost_usd": 1.0, "num_turns": 3, "session_id": "s2"}}
elif __import__("os").environ.get("FAKE_SELF_STOP"):
    out = {{"subtype": "success", "total_cost_usd": 1.0, "num_turns": 3, "session_id": "s1",
           "result": "I stopped at the tool-call budget with the work only partly done."}}
else:
    out = {{"subtype": "error_max_turns", "total_cost_usd": 1.0, "num_turns": 4,
           "session_id": "s1"}}
print(json.dumps(out))
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "article"
    r.mkdir()
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@e"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=r, check=True)
    (r / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=r, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=r, check=True)
    return r


@pytest.fixture()
def order(tmp_path: Path, repo: Path) -> Path:
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, text=True,
                          capture_output=True, check=True).stdout.strip()
    d = tmp_path / "orders"
    d.mkdir()
    (d / "task.txt").write_text("Fix it with {ENV} python.\n")
    (d / "brief.json").write_text('{"anchors": []}')
    (d / "check.sh").write_text("echo PASS fake\n")
    (d / "o.json").write_text(json.dumps({
        "id": "t", "base": base, "task": "task.txt", "brief": "brief.json",
        "outcome_check": "check.sh", "outcome_base": base, "cap": 4}))
    return d / "o.json"


def fake_claude(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / "calls.json"
    exe = tmp_path / "claude"
    exe.write_text(FAKE_CLAUDE.format(state=str(state)))
    exe.chmod(0o755)
    return exe, state


@pytest.mark.parametrize("name", sorted(PILOT_HASHES))
def test_dry_run_prints_the_pilot_hashes_and_spends_nothing(
        name: str, tmp_path: Path, repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "run"
    assert ro.main([str(ORDERS / f"{name}.json"), "--repo", str(repo), "--out", str(out),
                    "--dry-run"]) == 0
    text = capsys.readouterr().out
    task_hash, brief_hash = PILOT_HASHES[name]
    assert task_hash in text and brief_hash in text
    assert "spends nothing" in text
    assert not out.exists()


@pytest.mark.parametrize("name", sorted(PILOT_HASHES))
def test_order_files_hash_as_recorded(name: str) -> None:
    order = ro.load_order(ORDERS / f"{name}.json")
    got = (hashlib.sha256(order["task_path"].read_bytes()).hexdigest(),
           hashlib.sha256(order["brief_path"].read_bytes()).hexdigest())
    assert got == PILOT_HASHES[name]


def test_real_run_needs_a_budget(tmp_path: Path, repo: Path, order: Path) -> None:
    with pytest.raises(SystemExit):
        ro.main([str(order), "--repo", str(repo), "--out", str(tmp_path / "run")])


def test_order_cannot_name_a_script_outside_its_directory(tmp_path: Path, order: Path) -> None:
    data = json.loads(order.read_text())
    data["outcome_check"] = "../claude"
    (tmp_path / "claude").write_text("echo hi\n")
    order.write_text(json.dumps(data))
    with pytest.raises(SystemExit):
        ro.load_order(order)


def test_spend_over_the_limit_is_refused_before_any_call(
        tmp_path: Path, repo: Path, order: Path) -> None:
    exe, state = fake_claude(tmp_path)
    out = tmp_path / "run"
    rc = ro.main([str(order), "--repo", str(repo), "--out", str(out), "--claude", str(exe),
                  "--max-usd", "2", "--segment-usd", "3"])
    assert rc == 3
    assert not state.exists()


def test_segment_at_the_cap_hands_off_to_the_next(tmp_path: Path, repo: Path, order: Path) -> None:
    exe, state = fake_claude(tmp_path)
    out = tmp_path / "run"
    rc = ro.main([str(order), "--repo", str(repo), "--out", str(out), "--claude", str(exe),
                  "--max-usd", "10", "--segment-usd", "2", "--env-wrapper", "/w/env"])
    assert rc == 0
    calls = json.loads(state.read_text())
    assert [("--max-turns" in c["argv"], c["argv"][c["argv"].index("--max-turns") + 1])
            for c in calls] == [(True, "4"), (True, "2"), (True, "4")]
    assert "Fix it with /w/env python." in calls[0]["prompt"]
    assert "about 4 tool calls" in calls[0]["prompt"]
    assert "Handoff from the previous segment" not in calls[0]["prompt"]
    assert '"remaining": [\n  "b"\n ]' in calls[2]["prompt"]
    handoff = json.loads((out / "handoff-1.json").read_text())
    assert handoff["handoff"]["done"] == ["a"]
    assert (out / "result-2.json").exists()
    assert json.loads((out / "result-1.json").read_text())["transcript"].endswith("s1.jsonl")
    assert json.loads((out / "spend.json").read_text())["total"] == 2.01
    assert (out / "outcome.txt").read_text().strip() == "PASS fake"


def test_evidence_handoff_resumes_once_without_tools_and_carries_the_evidence(
        tmp_path: Path, repo: Path, order: Path) -> None:
    exe, state = fake_claude(tmp_path)
    out = tmp_path / "run"
    rc = ro.main([str(order), "--repo", str(repo), "--out", str(out), "--claude", str(exe),
                  "--max-usd", "10", "--segment-usd", "2", "--env-wrapper", "/w/env",
                  "--handoff", "evidence"])
    assert rc == 0
    calls = json.loads(state.read_text())
    assert len(calls) == 3
    last = calls[1]["argv"]
    assert last[last.index("--resume") + 1] == "s1"
    assert "--allowedTools" not in last and last[last.index("--max-turns") + 1] == "2"
    assert "evidence" in calls[1]["prompt"] and "Do not use tools" in calls[1]["prompt"]
    saved = json.loads((out / "handoff-1.json").read_text())["handoff"]
    assert saved["evidence"] == ["pytest: 3 passed"] and saved["verify"] == "pass"
    assert "pytest: 3 passed" in calls[2]["prompt"]
    assert json.loads((out / "spend.json").read_text())["total"] == 2.05


def test_default_handoff_is_the_cheap_one(tmp_path: Path, repo: Path, order: Path) -> None:
    exe, state = fake_claude(tmp_path)
    ro.main([str(order), "--repo", str(repo), "--out", str(tmp_path / "run"),
             "--claude", str(exe), "--max-usd", "10", "--segment-usd", "2"])
    assert all("--resume" not in c["argv"] for c in json.loads(state.read_text()))


def test_continue_resumes_from_the_last_saved_handoff(
        tmp_path: Path, repo: Path, order: Path) -> None:
    exe, state = fake_claude(tmp_path)
    out = tmp_path / "run"
    args = [str(order), "--repo", str(repo), "--out", str(out), "--claude", str(exe),
            "--max-usd", "10", "--segment-usd", "2", "--handoff", "evidence"]
    assert ro.main(args + ["--segments", "1"]) == 0
    assert (out / "handoff-1.handoff.json").exists()
    state.unlink()
    assert ro.main(args + ["--continue"]) == 0
    calls = json.loads(state.read_text())
    assert "Handoff from the previous segment" in calls[0]["prompt"]
    assert "pytest: 3 passed" in calls[0]["prompt"]


@pytest.mark.parametrize("res,expected", [
    ({"subtype": "error_max_turns", "num_turns": 4}, True),
    ({"subtype": "success", "num_turns": 37,
      "result": "I stopped at the tool-call budget."}, True),
    ({"subtype": "success", "num_turns": 30,
      "result": "Reached the call limit; Rust half undone."}, True),
    ({"subtype": "success", "num_turns": 12,
      "result": "I stopped at the tool-call budget."}, False),
    ({"subtype": "success", "num_turns": 38,
      "result": "All done, well inside the budget."}, False),
    ({"subtype": "error_max_budget_usd", "num_turns": 38,
      "result": "stopped at the budget"}, False),
])
def test_hit_cap_reads_the_turn_limit_or_a_self_stop_near_the_cap(
        res: dict, expected: bool) -> None:
    assert ro.hit_cap(res, 40) is expected
    assert ro.hit_cap({"subtype": "success", "num_turns": 38,
                       "result": "I stopped at the budget."}, None) is False


def test_self_stop_below_the_turn_limit_still_hands_off(
        tmp_path: Path, repo: Path, order: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SELF_STOP", "1")
    exe, state = fake_claude(tmp_path)
    out = tmp_path / "run"
    rc = ro.main([str(order), "--repo", str(repo), "--out", str(out), "--claude", str(exe),
                  "--max-usd", "10", "--segment-usd", "2"])
    assert rc == 0
    calls = json.loads(state.read_text())
    assert len(calls) == 3
    assert '"remaining": [\n  "b"\n ]' in calls[2]["prompt"]
    assert json.loads((out / "result-1.json").read_text())["stopped_early"] is True
    assert "stopped_early" not in json.loads((out / "result-2.json").read_text())
