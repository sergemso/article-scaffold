#!/usr/bin/env python3
"""Maintainer tool: fit the hand-off context threshold from measured runs.

Not shipped in the template. A segment of n calls costs n*c0 + g*n^2/2 + H in
cache-read terms (c0 start context, g context growth per call, H cost of one
handoff). Over N calls the cost is smallest at n* = sqrt(2H/g), and the matching
context threshold is c0 + sqrt(2*H*g). This script fits c0 and g by least
squares on each run's per-call contexts and prints n* and the threshold with
the inputs used. Tokens only: there is no term for quality drift.

Input is the JSON of `session-cost.py PROJECT_DIR --json --contexts` (rows with
a `contexts` list), or a file of `{"runs": [{"contexts": [...], "handoff": H}]}`.

    python3 -I scripts/context-threshold.py FILE [--handoff TOKENS]
        [--resume-handoff] [--agent SUBSTRING ...] [--min-calls N] [--json]

H comes from `--handoff` (tokens), or a run's own `handoff` field, or with
`--resume-handoff` from the segment's own cache-read (a resume re-sends the whole
context, so the reply costs as much as the segment).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def fit_line(ys: list[float]) -> tuple[float, float]:
    """Least squares ``y = c0 + g*i`` over call index i = 0..n-1; returns (c0, g)."""
    n = len(ys)
    mean_i = (n - 1) / 2
    mean_y = sum(ys) / n
    var = sum((i - mean_i) ** 2 for i in range(n))
    g = sum((i - mean_i) * (y - mean_y) for i, y in enumerate(ys)) / var
    return mean_y - g * mean_i, g


def optimum(c0: float, g: float, handoff: float) -> dict:
    """n* = sqrt(2H/g) and the threshold c0 + sqrt(2*H*g); both need g > 0 and H > 0."""
    if g <= 0 or handoff <= 0:
        raise ValueError("growth per call and handoff cost must both be positive")
    return {
        "n_star": math.sqrt(2 * handoff / g),
        "threshold": c0 + math.sqrt(2 * handoff * g),
    }


def runs_of(data: dict | list, agents: list[str], min_calls: int) -> list[dict]:
    rows = data["runs"] if isinstance(data, dict) and "runs" in data else (
        data["agents"] if isinstance(data, dict) else data)
    out = []
    for row in rows:
        ctx = row.get("contexts") or []
        label = f"{row.get('session', '')}/{row.get('agent', '')}"
        if len(ctx) < max(min_calls, 3):
            continue
        if agents and not any(a in label for a in agents):
            continue
        out.append({"label": label, "contexts": ctx, "handoff": row.get("handoff")})
    return out


def analyse(runs: list[dict], handoff: float | None, resume: bool) -> dict:
    """Pool the runs: g and c0 are the call-weighted means of the per-run fits."""
    fits, weights, handoffs = [], [], []
    for run in runs:
        c0, g = fit_line(run["contexts"])
        fits.append((c0, g))
        weights.append(len(run["contexts"]))
        if handoff is not None:
            handoffs.append(handoff)
        elif run["handoff"] is not None:
            handoffs.append(float(run["handoff"]))
        elif resume:
            handoffs.append(float(sum(run["contexts"])))
    total = sum(weights)
    c0 = sum(f[0] * w for f, w in zip(fits, weights, strict=True)) / total
    g = sum(f[1] * w for f, w in zip(fits, weights, strict=True)) / total
    if not handoffs:
        raise ValueError("no handoff cost: pass --handoff, --resume-handoff or a handoff field")
    h = sum(handoffs) / len(handoffs)
    return {
        "runs": [{"label": r["label"], "calls": len(r["contexts"])} for r in runs],
        "c0": round(c0), "g": round(g), "handoff": round(h),
        **{k: round(v) for k, v in optimum(c0, g, h).items()},
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path)
    ap.add_argument("--handoff", type=float, help="cost H of one handoff, in tokens")
    ap.add_argument("--resume-handoff", action="store_true")
    ap.add_argument("--agent", action="append", default=[])
    ap.add_argument("--min-calls", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    runs = runs_of(json.loads(a.file.read_text()), a.agent, a.min_calls)
    if not runs:
        print("no run with per-call contexts (use session-cost.py --json --contexts)",
              file=sys.stderr)
        return 1
    try:
        result = analyse(runs, a.handoff, a.resume_handoff)
    except ValueError as err:
        print(f"context-threshold: {err}", file=sys.stderr)
        return 1
    if a.json:
        json.dump(result, sys.stdout, indent=1)
        print()
        return 0
    print(f"runs: {len(runs)} ({sum(r['calls'] for r in result['runs'])} calls)")
    print(f"start context c0: {result['c0']} tokens")
    print(f"growth per call g: {result['g']} tokens")
    print(f"handoff cost H: {result['handoff']} tokens")
    print(f"n* = sqrt(2H/g): {result['n_star']} calls")
    print(f"max_context = c0 + sqrt(2*H*g): {result['threshold']} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
