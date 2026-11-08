#!/usr/bin/env python3
"""Maintainer tool: sum Claude Code transcript usage per session and subagent.

Not shipped in the template. Reads ~/.claude/projects/<project>/*.jsonl and
<session>/subagents/*.jsonl, counts each assistant message.id once, and prints
calls, token sums, maximum context, files read more than N times, repeated
shell commands and an estimated cost from a prices file.

    python3 -I scripts/session-cost.py PROJECT_DIR [--since YYYY-MM-DD]
        [--until YYYY-MM-DD] [--session ID ...] [--min-repeat N]
        [--prices FILE] [--json] [--contexts]

--contexts adds each agent's per-call context sizes to the JSON rows, which
scripts/context-threshold.py reads.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PRICES = Path(__file__).with_name("session-cost-prices.json")
READ_CMD = re.compile(
    r"\b(?:cat|head|tail|sed(?:\s+-n)?\s+'[^']*'|less|nl)\s+(?:-\S+\s+)*([\w./-]+\.\w+)"
)


def load_prices(path: Path) -> dict:
    return json.loads(path.read_text())


def price_of(prices: dict, model: str) -> dict | None:
    for prefix, row in prices["models"].items():
        if model.startswith(prefix):
            return row
    return None


def parse(path: Path, since: str | None, until: str | None) -> dict:
    """One transcript -> totals. The last entry per message.id wins."""
    msgs: dict[str, dict] = {}
    calls: list[tuple[str, dict]] = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        ts = (d.get("timestamp") or "")[:10]
        if (since and ts and ts < since) or (until and ts and ts > until):
            continue
        m = d.get("message") or {}
        mid = m.get("id")
        if not mid or not m.get("usage"):
            continue
        msgs[mid] = m
        for c in m.get("content") or []:
            if c.get("type") == "tool_use":
                calls.append((c.get("name", ""), c.get("input") or {}))
    return {"messages": list(msgs.values()), "tools": calls}


def contexts(parsed: dict) -> list[int]:
    """The context size (input plus cache read and creation) of each call, in order."""
    out = []
    for m in parsed["messages"]:
        u = m["usage"]
        cc = u.get("cache_creation") or {}
        c5 = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0))
        out.append(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                   + c5 + cc.get("ephemeral_1h_input_tokens", 0))
    return out


def totals(parsed: dict, prices: dict) -> dict:
    t = Counter()
    max_ctx = 0
    cost = 0.0
    unpriced = set()
    for m in parsed["messages"]:
        u = m["usage"]
        cc = u.get("cache_creation") or {}
        c5 = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0))
        c1 = cc.get("ephemeral_1h_input_tokens", 0)
        t["input"] += u.get("input_tokens", 0)
        t["output"] += u.get("output_tokens", 0)
        t["cache_read"] += u.get("cache_read_input_tokens", 0)
        t["cache_create_5m"] += c5
        t["cache_create_1h"] += c1
        ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + c5 + c1
        max_ctx = max(max_ctx, ctx)
        p = price_of(prices, m.get("model") or "")
        if p is None:
            unpriced.add(m.get("model") or "?")
            continue
        cost += (u.get("input_tokens", 0) * p["input"] + u.get("output_tokens", 0) * p["output"]
                 + u.get("cache_read_input_tokens", 0) * p["cache_read"]
                 + c5 * p["cache_write_5m"] + c1 * p["cache_write_1h"]) / 1e6
    return {"calls": len(parsed["messages"]), "tool_calls": len(parsed["tools"]),
            **dict(t), "max_context": max_ctx, "est_usd": round(cost, 2),
            "unpriced_models": sorted(unpriced)}


def repeated(parsed: dict) -> tuple[Counter, Counter]:
    reads: Counter = Counter()
    cmds: Counter = Counter()
    for name, inp in parsed["tools"]:
        if name == "Read" and inp.get("file_path"):
            whole = not inp.get("limit") and not inp.get("offset")
            reads[inp["file_path"] + ("" if whole else " (part)")] += 1
        elif name == "Bash" and inp.get("command"):
            cmd = " ".join(inp["command"].split())
            cmds[cmd[:100]] += 1
            for m in READ_CMD.finditer(cmd):
                reads[m.group(1) + " (shell)"] += 1
    return reads, cmds


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project_dir", type=Path)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--session", action="append", default=[])
    ap.add_argument("--min-repeat", type=int, default=5)
    ap.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--contexts", action="store_true")
    a = ap.parse_args(argv)
    prices = load_prices(a.prices)
    rows, all_reads, all_cmds = [], Counter(), Counter()
    for top in sorted(a.project_dir.glob("*.jsonl")):
        sid = top.stem
        if a.session and sid not in a.session:
            continue
        subs = sorted((a.project_dir / sid / "subagents").glob("*.jsonl"))
        files = [("main", top)] + [(p.stem, p) for p in subs]
        for label, p in files:
            parsed = parse(p, a.since, a.until)
            if not parsed["messages"]:
                continue
            row = {"session": sid, "agent": label, **totals(parsed, prices)}
            if a.contexts:
                row["contexts"] = contexts(parsed)
            rows.append(row)
            r, c = repeated(parsed)
            all_reads.update(r)
            all_cmds.update(c)
    sums = Counter()
    for r in rows:
        for k in ("calls", "tool_calls", "input", "output", "cache_read",
                  "cache_create_5m", "cache_create_1h"):
            sums[k] += r.get(k, 0)
    summary = {"agents": len(rows), **dict(sums),
               "max_context": max((r["max_context"] for r in rows), default=0),
               "est_usd": round(sum(r["est_usd"] for r in rows), 2),
               "prices_are": prices.get("note", "")}
    rep_reads = [(k, n) for k, n in all_reads.most_common() if n >= a.min_repeat]
    rep_cmds = [(k, n) for k, n in all_cmds.most_common() if n >= a.min_repeat]
    if a.json:
        json.dump({"summary": summary, "agents": rows, "repeated_reads": rep_reads,
                   "repeated_commands": rep_cmds}, sys.stdout, indent=1)
        print()
        return 0
    print("summary:", json.dumps(summary))
    print(f"{'session':10} {'agent':20} {'calls':>5} {'tools':>5} "
          f"{'max_ctx':>8} {'cache_read':>11} {'usd':>6}")
    for r in sorted(rows, key=lambda r: -r["est_usd"]):
        print(f"{r['session'][:8]:10} {r['agent'][-18:]:20} {r['calls']:>5} "
              f"{r['tool_calls']:>5} {r['max_context']:>8} "
              f"{r.get('cache_read', 0):>11} {r['est_usd']:>6}")
    print(f"\nfiles read >= {a.min_repeat} times:")
    for k, n in rep_reads[:25]:
        print(f"  {n:>4}  {k}")
    print(f"\ncommands run >= {a.min_repeat} times:")
    for k, n in rep_cmds[:25]:
        print(f"  {n:>4}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
