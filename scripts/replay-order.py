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
        [--env-wrapper EXE] [--claude EXE] [--no-check]

``--dry-run`` prints the plan, the task and brief hashes and spends nothing.
A real run needs ``--max-usd``: the total this invocation may spend, counting
what RUN_DIR/spend.json already holds. A segment that could pass it is refused
before it starts. ``ANTHROPIC_API_KEY`` is read from the environment by the
CLI and is never printed or written here.

Each segment runs with ``--max-turns`` equal to the cap. A segment that ends at
the cap (``error_max_turns``) is followed by a cheap handoff: ``git status``,
``git diff --stat`` and a fresh two-turn summary, with no resume. Results,
handoffs and transcript paths are written under RUN_DIR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def transcript_path(cwd: Path, session: str | None) -> str | None:
    if not session:
        return None
    slug = str(cwd.resolve()).replace("/", "-").replace(".", "-")
    return str(Path.home() / ".claude" / "projects" / slug / f"{session}.jsonl")


def claude(exe: str, cwd: Path, prompt: str, turns: int, usd: float, env: dict) -> dict:
    cmd = [exe, "-p", "--bare", "--model", MODEL, "--output-format", "json",
           "--max-turns", str(turns), "--max-budget-usd", str(usd),
           "--permission-mode", "acceptEdits", "--allowedTools", *TOOLS]
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
    print(f"would: claude -p --max-turns {cap} per segment, cheap handoff at the cap, "
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
    handoff, rc = None, 0
    for seg in range(1, a.segments + 1):
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
        if res.get("subtype") != "error_max_turns":
            break
        if not spend.allows(HANDOFF_USD):
            print("spend limit: no room for the handoff", file=sys.stderr)
            return 3
        hand = cheap_handoff(a.claude, wt, order["task_path"].read_text(), env)
        spend.record(f"handoff {seg}", hand)
        handoff = hand["handoff"]
        (a.out / f"handoff-{seg}.json").write_text(json.dumps(hand, indent=1)[:8000])
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
