#!/usr/bin/env python3
"""Maintainer tool: replay one fix-round order through the Claude CLI, one arm.

Not shipped in the template. Rebuilds the E.3 pilot wrapper so the follow-up
measurements are repeatable. An order is a small JSON file in
``scripts/replay-orders/`` (base commit, task text file, brief file, outcome
check script file, call cap). The outcome check is a script file named in the
order and resolved inside that directory; no command string is read from an
order. The article repo and the spend limit come from the command line.

    python3 -I scripts/replay-order.py ORDER.json --repo ARTICLE_REPO --out RUN_DIR
        [--dry-run] [--max-usd X --segment-usd Y] [--cap N] [--segments N]
        [--env-wrapper EXE] [--claude EXE] [--no-check] [--handoff evidence|cheap] [--continue]

``--dry-run`` prints the plan, the task and brief hashes and spends nothing.
A real run needs ``--max-usd``: the total this invocation may spend, counting
what RUN_DIR/spend.json already holds. A segment that could pass it is refused
before it starts. ``ANTHROPIC_API_KEY`` is read from the environment by the
CLI and is never printed or written here.

Each segment runs with ``--max-turns`` equal to the cap. A segment that ends at
the cap (``error_max_turns``, or a ``success`` after at least 75% of the cap whose reply says
it stopped at the budget; marked ``stopped_early`` in its result) is followed by a handoff.
``--handoff evidence`` (default) asks the capped session for one last turn, without tools,
with done, remaining, verify and an evidence line per done item; the diff fields are added by
the wrapper. ``--handoff cheap`` is ``git status``, ``git diff --stat`` and a fresh two-turn
summary, with no resume. Results,
handoffs and transcript paths are written under RUN_DIR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ORDERS = Path(__file__).resolve().parent / "replay-orders"
MODEL = "claude-sonnet-5-5"
TOOLS = ["Bash", "Read", "Edit", "Write", "Grep", "Glob"]
TAIL = ("Read symbols with `python3 -m scripts.article index slice NAME` "
        "instead of whole files.")
HANDOFF_USD = 0.5
# An agent told to "stop and say so" at the budget may do it a few calls early and end with
# `success`; that is a cap, not a finished task.
SELF_STOP = re.compile(
    r"(stopp\w*|reach\w*|hit|ran out|exhaust\w*)\W.{0,40}(budget|limit)", re.I | re.S)
SELF_STOP_SHARE = 0.75


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def load_order(path: Path) -> dict:
    order = json.loads(path.read_text())
    for key in ("id", "base", "task", "brief", "outcome_check", "outcome_base", "cap"):
        if key not in order:
            raise SystemExit(f"{path}: missing {key!r}")
    root = path.resolve().parent
    for key in ("task", "brief", "outcome_check"):
        target = (root / order[key]).resolve()
        if root not in target.parents or not target.is_file():
            raise SystemExit(f"{path}: {key} must name a file inside {root}")
        order[key + "_path"] = target
    return order


def build_prompt(order: dict, cap: int | None, env_wrapper: str, handoff: dict | None) -> str:
    task = order["task_path"].read_text().replace("{ENV}", env_wrapper or "the tool wrapper")
    brief = order["brief_path"].read_text()
    budget = (f"You have a budget of about {cap} tool calls for this segment. " if cap else "")
    stop = " If you reach the budget, stop and say so." if cap else ""
    out = [task, "\n\n## Brief (compiled by the repo tooling)\n", brief,
           "\n\n" + budget + order.get("tail", TAIL) + stop]
    if handoff:
        out += ["\n\n## Handoff from the previous segment (do not redo the done items)\n",
                json.dumps(handoff, indent=1)]
    return "".join(out)


class Spend:
    def __init__(self, path: Path, limit: float | None):
        self.path, self.limit = path, limit
        self.data = json.loads(path.read_text()) if path.exists() else {"total": 0.0, "runs": []}

    def allows(self, usd: float) -> bool:
        return self.limit is not None and self.data["total"] + usd <= self.limit

    def record(self, label: str, res: dict) -> None:
        self.data["total"] = round(self.data["total"] + (res.get("total_cost_usd") or 0), 4)
        self.data["runs"].append({"label": label, "usd": res.get("total_cost_usd"),
                                  "turns": res.get("num_turns"), "subtype": res.get("subtype"),
                                  "session": res.get("session_id")})
        self.path.write_text(json.dumps(self.data, indent=1))


def hit_cap(res: dict, cap: int | None) -> bool:
    """True when the segment ended at the cap: by the turn limit, or by the agent saying so."""
    if res.get("subtype") == "error_max_turns":
        return True
    if not cap or res.get("subtype") != "success":
        return False
    if (res.get("num_turns") or 0) < cap * SELF_STOP_SHARE:
        return False
    return bool(SELF_STOP.search(res.get("result") or ""))


def transcript_path(cwd: Path, session: str | None) -> str | None:
    if not session:
        return None
    slug = str(cwd.resolve()).replace("/", "-").replace(".", "-")
    return str(Path.home() / ".claude" / "projects" / slug / f"{session}.jsonl")


def claude(exe: str, cwd: Path, prompt: str, turns: int, usd: float, env: dict,
           resume: str | None = None, tools: list[str] = TOOLS) -> dict:
    cmd = [exe, "-p", "--bare", "--model", MODEL, "--output-format", "json",
           "--max-turns", str(turns), "--max-budget-usd", str(usd),
           "--permission-mode", "acceptEdits"]
    if resume:
        cmd += ["--resume", resume]
    if tools:
        cmd += ["--allowedTools", *tools]
    r = subprocess.run(cmd, input=prompt, text=True, capture_output=True, cwd=cwd, env=env)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"subtype": "unparsed", "total_cost_usd": 0, "stderr": r.stderr[-400:]}


def cheap_handoff(exe: str, wt: Path, task: str, env: dict) -> dict:
    """Handoff from the worktree state plus a short summary by a fresh session (no resume)."""
    def sh(*c: str) -> str:
        return subprocess.run(c, cwd=wt, text=True, capture_output=True).stdout
    status, stat = sh("git", "status", "--short"), sh("git", "diff", "--stat")
    p = ("A previous agent worked on this task in this repository and stopped at its "
         "call limit.\n\n"
         "## Task\n" + task[:3500] + "\n\n## git status --short\n" + status[:3000]
         + "\n## git diff --stat\n" + stat[:3000]
         + "\nFrom the task and the changed files only, reply with only JSON: "
         '{"done": [short items likely finished], "remaining": [short items not yet '
         'evidenced in the diff], "verify": "not-run"}. Each item is one line. Do not use tools.')
    res = claude(exe, wt, p, 2, HANDOFF_USD, env)
    try:
        txt = res.get("result", "")
        summary = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    except ValueError:
        summary = {"note": "summary was not JSON", "raw": res.get("result", "")[:500]}
    res["handoff"] = {"files": [ln[3:] for ln in status.splitlines()],
                      "diff_stat": stat.strip().splitlines()[-1:], **summary}
    return res


def evidence_handoff(exe: str, wt: Path, session: str | None, env: dict,
                     prior_usd: float = 0.0) -> dict:
    """Handoff from the capped agent's own last turn: one call at its full context.

    The agent is asked for done, remaining, verify and one evidence line per done item (the
    command run and its result, or ``not-run``); no tools are allowed, so it cannot start more
    work. The wrapper adds the diff-derived fields. Without a session id the cheap handoff is
    used instead.
    """
    if not session:
        return cheap_handoff(exe, wt, "", env)
    def sh(*c: str) -> str:
        return subprocess.run(c, cwd=wt, text=True, capture_output=True).stdout
    status, stat = sh("git", "status", "--short"), sh("git", "diff", "--stat")
    p = ("You reached your call limit. Reply with only JSON: "
         '{"done": [short items finished], "remaining": [short items not finished], '
         '"verify": "pass" or "fail" or "not-run", "evidence": [one short line per done item: '
         'the command you ran and its result, or "not-run"]}. Each item is one line. '
         "Do not use tools.")
    res = claude(exe, wt, p, 2, HANDOFF_USD, env, resume=session, tools=[])
    # A resumed session reports its cumulative cost; keep only what this call added.
    res["cumulative_cost_usd"] = res.get("total_cost_usd")
    res["total_cost_usd"] = round((res.get("total_cost_usd") or 0) - prior_usd, 6)
    try:
        txt = res.get("result", "")
        summary = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    except ValueError:
        summary = {"note": "summary was not JSON", "raw": res.get("result", "")[:500]}
    res["handoff"] = {"files": [ln[3:] for ln in status.splitlines()],
                      "diff_stat": stat.strip().splitlines()[-1:], **summary}
    return res


def dry_run(order: dict, a: argparse.Namespace, cap: int | None) -> None:
    prompt = build_prompt(order, cap, a.env_wrapper, None)
    print(f"order {order['id']}: base {order['base']} "
          f"(outcome diff against {order['outcome_base']})")
    print(f"task  sha256 {sha(order['task_path'].read_text())}")
    print(f"brief sha256 {sha(order['brief_path'].read_text())} "
          f"({len(order['brief_path'].read_bytes())} bytes)")
    print(f"prompt {len(prompt)} chars; cap {cap}; segments up to {a.segments}; "
          f"segment limit {a.segment_usd} USD; total limit {a.max_usd}")
    print(f"would: git worktree add --detach {a.out / 'worktree'} {order['base']} "
          f"(in {a.repo})")
    print(f"would: claude -p --max-turns {cap} per segment, {a.handoff} handoff at the cap, "
          f"then {order['outcome_check_path'].name}")
    print("spends nothing")


def run(order: dict, a: argparse.Namespace, cap: int | None) -> int:
    a.out.mkdir(parents=True, exist_ok=True)
    spend = Spend(a.out / "spend.json", a.max_usd)
    wt = a.out / "worktree"
    if not wt.exists():
        subprocess.run(["git", "-C", str(a.repo), "worktree", "add", "--detach",
                        str(wt), order["base"]], check=True, capture_output=True)
    env = {**os.environ, "REPLAY_RUN_DIR": str(a.out.resolve()), "REPLAY_ENV": a.env_wrapper}
    handoff, rc, first = None, 0, 1
    if a.cont:
        saved = sorted(a.out.glob("handoff-*.handoff.json"))
        if saved:
            handoff = json.loads(saved[-1].read_text())
            first = int(saved[-1].name.split("-")[1].split(".")[0]) + 1
    for seg in range(first, a.segments + 1):
        if not spend.allows(a.segment_usd):
            print(f"spend limit: {spend.data['total']} + {a.segment_usd} would pass {a.max_usd}",
                  file=sys.stderr)
            return 3
        started = time.time()
        res = claude(a.claude, wt, build_prompt(order, cap, a.env_wrapper, handoff),
                     cap or 250, a.segment_usd, env)
        res["wall_seconds"] = round(time.time() - started, 1)
        res["transcript"] = transcript_path(wt, res.get("session_id"))
        spend.record(f"segment {seg}", res)
        (a.out / f"result-{seg}.json").write_text(json.dumps(res, indent=1)[:20000])
        print(f"segment {seg}: {res.get('subtype')} turns={res.get('num_turns')} "
              f"usd={res.get('total_cost_usd')} total={spend.data['total']}")
        failed = res.get("is_error") and res.get("subtype") != "error_max_turns"
        if res.get("subtype") == "unparsed" or failed:
            print(f"segment {seg} failed: {str(res.get('result') or res.get('stderr'))[:200]}",
                  file=sys.stderr)
            return 2
        if not hit_cap(res, cap):
            break
        res["stopped_early"] = res.get("subtype") == "success"
        (a.out / f"result-{seg}.json").write_text(json.dumps(res, indent=1)[:20000])
        if not spend.allows(HANDOFF_USD):
            print("spend limit: no room for the handoff", file=sys.stderr)
            return 3
        if a.handoff == "evidence":
            hand = evidence_handoff(a.claude, wt, res.get("session_id"), env,
                                    res.get("total_cost_usd") or 0)
        else:
            hand = cheap_handoff(a.claude, wt, order["task_path"].read_text(), env)
        spend.record(f"handoff {seg}", hand)
        handoff = hand["handoff"]
        (a.out / f"handoff-{seg}.json").write_text(json.dumps(hand, indent=1)[:8000])
        (a.out / f"handoff-{seg}.handoff.json").write_text(json.dumps(handoff, indent=1))
    if not a.no_check:
        r = subprocess.run(["sh", str(order["outcome_check_path"]), str(wt), order["outcome_base"]],
                           text=True, capture_output=True, env=env)
        (a.out / "outcome.txt").write_text(r.stdout)
        print(r.stdout, end="")
        rc = 0 if "FAIL" not in r.stdout and r.returncode == 0 else 1
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("order", type=Path)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-usd", type=float)
    ap.add_argument("--segment-usd", type=float, default=3.5)
    ap.add_argument("--cap", type=int, help="tool calls per segment; 0 for no cap")
    ap.add_argument("--segments", type=int, default=3)
    ap.add_argument("--env-wrapper", default="")
    ap.add_argument("--claude", default="claude")
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--continue", dest="cont", action="store_true",
                    help="resume an interrupted run in OUT from its last saved handoff")
    ap.add_argument("--handoff", choices=("cheap", "evidence"), default="evidence",
                    help="evidence: the capped agent's last turn with an evidence list; "
                         "cheap: diff plus a fresh summary")
    a = ap.parse_args(argv)
    order = load_order(a.order)
    cap = order["cap"] if a.cap is None else (a.cap or None)
    if a.dry_run:
        dry_run(order, a, cap)
        return 0
    if a.max_usd is None:
        ap.error("a real run needs --max-usd (the owner-confirmed budget)")
    return run(order, a, cap)


if __name__ == "__main__":
    sys.exit(main())
