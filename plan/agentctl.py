#!/usr/bin/env python3
"""agentctl — re-entrant task state machine for the article-scaffold plan.

Stdlib only, so it works before any project dependency is installed.
Protocol and cold-start instructions live in AGENTS.md. Human overview
lives in plan/README.md.

Design rules:
  * tasks.json is immutable during execution (edit only when the plan changes)
  * state.json is the mutable checkpoint; it is committed with the work
  * journal.md is append-only and human-readable
  * every mutating command takes an exclusive lock and writes atomically
  * a task is only "done" after its verify commands pass, unless explicitly
    overridden; the override is recorded and audit reports it

Usage (global --root must precede the subcommand):
    python3 plan/agentctl.py doctor
    python3 plan/agentctl.py next --card
    python3 plan/agentctl.py claim T05
    python3 plan/agentctl.py checkpoint T05 --note "template edited"
    python3 plan/agentctl.py verify T05
    python3 plan/agentctl.py done T05 --note "green"
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = 1
DEFAULT_OWNER = os.environ.get("AGENT_ID", "agent")
DEFAULT_TTL_MIN = 120
DEFAULT_TIMEOUT_S = 600
STATUSES = {"todo", "in_progress", "blocked", "done", "skipped"}
TAIL_CHARS = 4000

ROOT = Path(__file__).resolve().parent.parent
PLAN_DIR = ROOT / "plan"
TASKS_PATH = PLAN_DIR / "tasks.json"
STATE_PATH = PLAN_DIR / "state.json"
JOURNAL_PATH = PLAN_DIR / "journal.md"
LOCK_PATH = PLAN_DIR / ".lock"


# ─────────────────────────────────────────────────────────────
# Root / time / IO helpers
# ─────────────────────────────────────────────────────────────


def configure_root(path: str | None) -> None:
    global ROOT, PLAN_DIR, TASKS_PATH, STATE_PATH, JOURNAL_PATH, LOCK_PATH
    if path:
        ROOT = Path(path).expanduser().resolve()
        PLAN_DIR = ROOT / "plan"
        TASKS_PATH = PLAN_DIR / "tasks.json"
        STATE_PATH = PLAN_DIR / "state.json"
        JOURNAL_PATH = PLAN_DIR / "journal.md"
        LOCK_PATH = PLAN_DIR / ".lock"


def utcnow() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


@contextlib.contextmanager
def locked():
    """Exclusive writer lock. POSIX flock; no-op on platforms without it."""
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        handle.close()


def journal(action: str, task_id: str, note: str = "", lines: list[str] | None = None) -> None:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    entry = [f"\n## {utcnow()} — {task_id} — {action}\n"]
    if note:
        entry.append(f"- {note}\n")
    for line in lines or []:
        entry.append(f"- {line}\n")
    with JOURNAL_PATH.open("a", encoding="utf-8") as fh:
        fh.write("".join(entry))


# ─────────────────────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────────────────────


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def git_out(*args: str) -> str:
    return git(*args).stdout.strip()


def head_sha() -> str | None:
    sha = git_out("rev-parse", "HEAD")
    return sha or None


def changed_paths() -> list[str]:
    # -uall expands untracked directories into files, so the scope check sees
    # tests/test_smoke.py rather than the opaque "tests/" entry.
    out = git("status", "--porcelain", "-uall").stdout
    paths: list[str] = []
    for raw in out.splitlines():
        if len(raw) < 4:
            continue
        path = raw[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if path:
            paths.append(path)
    return paths


def scope_ok(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        prefix = pat.rstrip("*").rstrip("/")
        if prefix and (path == prefix or path.startswith(prefix + "/")):
            return True
    return False


# ─────────────────────────────────────────────────────────────
# Plan / state loading and validation
# ─────────────────────────────────────────────────────────────


def load_tasks() -> list[dict]:
    if not TASKS_PATH.is_file():
        fail(f"plan file not found: {TASKS_PATH}")
    data = load_json(TASKS_PATH)
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        fail("tasks.json: missing 'tasks' list")
    return tasks


def validate_plan(tasks: list[dict]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    orders: set[int] = set()
    for task in tasks:
        tid = task.get("id")
        if not tid or not isinstance(tid, str):
            errors.append("task without a string id")
            continue
        if tid in ids:
            errors.append(f"{tid}: duplicate id")
        ids.add(tid)
        for key in ("title", "phase", "order", "steps", "verify", "touch"):
            if key not in task:
                errors.append(f"{tid}: missing '{key}'")
        order = task.get("order")
        if not isinstance(order, int):
            errors.append(f"{tid}: 'order' must be an integer")
        elif order in orders:
            errors.append(f"{tid}: duplicate order {order}")
        else:
            orders.add(order)
        if not isinstance(task.get("steps"), list) or not task.get("steps"):
            errors.append(f"{tid}: 'steps' must be a non-empty list")
        if not isinstance(task.get("touch"), list):
            errors.append(f"{tid}: 'touch' must be a list")
        verify = task.get("verify")
        if not isinstance(verify, list) or not verify:
            errors.append(f"{tid}: 'verify' must be a non-empty list")
        else:
            for check in verify:
                if not isinstance(check, dict) or not check.get("cmd"):
                    errors.append(f"{tid}: each verify entry needs 'cmd'")
                elif not isinstance(check.get("expect_exit", 0), int):
                    errors.append(f"{tid}: 'expect_exit' must be an integer")
    for task in tasks:
        for dep in task.get("depends_on", []):
            if dep not in ids:
                errors.append(f"{task.get('id')}: unknown dependency {dep}")
            if dep == task.get("id"):
                errors.append(f"{task.get('id')}: depends on itself")

    # Cycle detection (Kahn). Unknown/self deps are reported above, so they are
    # ignored here rather than turning into a spurious cycle.
    incoming = {
        t["id"]: {d for d in t.get("depends_on", []) if d in ids and d != t["id"]}
        for t in tasks
        if "id" in t
    }
    while incoming:
        ready = [tid for tid, deps in incoming.items() if not deps]
        if not ready:
            errors.append("dependency cycle: " + ", ".join(sorted(incoming)))
            break
        for tid in ready:
            del incoming[tid]
        for deps in incoming.values():
            deps.difference_update(ready)
    return errors


def default_state(tasks: list[dict]) -> dict:
    now = utcnow()
    entries: dict[str, dict] = {}
    for task in tasks:
        seeded = task.get("initial_status") == "done"
        entries[task["id"]] = {
            "status": "done" if seeded else "todo",
            "attempts": 1 if seeded else 0,
            "lease": None,
            "last_checkpoint": now if seeded else None,
            "commit": None,
            "seeded": seeded,
            "evidence": (
                [{"at": now, "kind": "seed", "ok": True, "note": "delivered by planner"}]
                if seeded
                else []
            ),
            "notes": [],
            "steps_done": [],
        }
    return {
        "schema": SCHEMA,
        "plan_version": load_json(TASKS_PATH).get("plan_version", "0"),
        "created": now,
        "updated": now,
        "tasks": entries,
    }


def load_state(tasks: list[dict], create: bool = False) -> dict:
    if STATE_PATH.is_file():
        state = load_json(STATE_PATH)
    elif create:
        state = default_state(tasks)
        atomic_write_json(STATE_PATH, state)
        journal("init", "plan", "state initialised")
    else:
        fail("plan/state.json not found; run: python3 plan/agentctl.py init")
    state.setdefault("tasks", {})
    # Reconcile new/removed tasks without clobbering progress.
    for task in tasks:
        if task["id"] not in state["tasks"]:
            state["tasks"][task["id"]] = {
                "status": "todo",
                "attempts": 0,
                "lease": None,
                "last_checkpoint": None,
                "commit": None,
                "seeded": False,
                "evidence": [],
                "notes": [],
                "steps_done": [],
            }
    return state


def save_state(state: dict) -> None:
    state["updated"] = utcnow()
    atomic_write_json(STATE_PATH, state)


def task_by_id(tasks: list[dict], tid: str) -> dict:
    for task in tasks:
        if task["id"] == tid:
            return task
    fail(f"unknown task id: {tid}")


def entry_for(state: dict, tid: str) -> dict:
    return state["tasks"][tid]


def fail(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


# ─────────────────────────────────────────────────────────────
# Readiness / lease logic
# ─────────────────────────────────────────────────────────────


def deps_done(task: dict, state: dict) -> bool:
    return all(
        state["tasks"].get(dep, {}).get("status") in {"done", "skipped"}
        for dep in task.get("depends_on", [])
    )


def lease_valid(entry: dict) -> bool:
    lease = entry.get("lease") or {}
    expires = parse_ts(lease.get("expires"))
    return bool(expires and expires > datetime.now(timezone.utc))


def lease_text(entry: dict) -> str:
    lease = entry.get("lease") or {}
    if not lease:
        return "none"
    state = "valid" if lease_valid(entry) else "EXPIRED"
    return f"{lease.get('owner')} until {lease.get('expires')} ({state})"


def ready_tasks(tasks: list[dict], state: dict, include_optional: bool) -> list[dict]:
    ready = []
    for task in tasks:
        if task.get("optional") and not include_optional:
            continue
        entry = state["tasks"][task["id"]]
        if entry["status"] != "todo":
            continue
        if deps_done(task, state):
            ready.append(task)
    return sorted(ready, key=lambda t: t["order"])


def current_tasks(tasks: list[dict], state: dict) -> list[dict]:
    found = [
        task
        for task in tasks
        if state["tasks"][task["id"]]["status"] == "in_progress"
    ]
    return sorted(found, key=lambda t: t["order"])


def next_action(tasks: list[dict], state: dict, include_optional: bool) -> tuple[dict | None, bool]:
    """Return (task, is_resume). In-progress tasks always win."""
    active = current_tasks(tasks, state)
    if active:
        return active[0], True
    ready = ready_tasks(tasks, state, include_optional)
    return (ready[0], False) if ready else (None, False)


# ─────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────


def run_check(check: dict, default_timeout: int) -> dict:
    cmd = check["cmd"]
    expect = int(check.get("expect_exit", 0))
    timeout = int(check.get("timeout", default_timeout))
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        tail = (proc.stdout + proc.stderr)[-TAIL_CHARS:]
        ok = proc.returncode == expect
        return {
            "cmd": cmd,
            "exit": proc.returncode,
            "expect_exit": expect,
            "ok": ok,
            "tail": tail,
            "at": utcnow(),
        }
    except subprocess.TimeoutExpired as exc:
        tail = ((exc.stdout or "") + (exc.stderr or ""))[-TAIL_CHARS:]
        return {
            "cmd": cmd,
            "exit": None,
            "expect_exit": expect,
            "ok": False,
            "tail": tail + f"\nTIMEOUT after {timeout}s",
            "at": utcnow(),
        }


def missing_requirements(task: dict) -> list[str]:
    return [tool for tool in task.get("requires", []) if shutil.which(tool) is None]


def verify_task(task: dict, record: bool = True, timeout: int = DEFAULT_TIMEOUT_S) -> int:
    missing = missing_requirements(task)
    if missing:
        print(f"SKIP: missing tools for {task['id']}: {', '.join(missing)}")
        if record:
            state = load_state(load_tasks())
            entry = entry_for(state, task["id"])
            entry["evidence"] = (entry.get("evidence", []) + [
                {"at": utcnow(), "kind": "missing_tools", "ok": False, "tools": missing}
            ])[-10:]
            save_state(state)
        return 3

    checks = [run_check(check, timeout) for check in task.get("verify", [])]
    all_ok = all(c["ok"] for c in checks)
    for check in checks:
        mark = "PASS" if check["ok"] else "FAIL"
        print(f"{mark}: {check['cmd']} (exit {check['exit']}, want {check['expect_exit']})")
        if not check["ok"]:
            print(textwrap.indent((check.get("tail") or "")[-2000:], "    "))

    if record:
        state = load_state(load_tasks())
        entry = entry_for(state, task["id"])
        entry["evidence"] = (entry.get("evidence", []) + [
            {
                "at": utcnow(),
                "kind": "verify",
                "ok": all_ok,
                "commit": head_sha(),
                "checks": checks,
            }
        ])[-10:]
        save_state(state)
    return 0 if all_ok else 1


def last_verify_ok(state: dict, tid: str) -> bool:
    entry = state["tasks"][tid]
    for item in reversed(entry.get("evidence", [])):
        if item.get("kind") == "verify":
            return bool(item.get("ok"))
    return False


# ─────────────────────────────────────────────────────────────
# Task card
# ─────────────────────────────────────────────────────────────


def print_card(task: dict, entry: dict, resume: bool, include_optional: bool) -> None:
    deps = ", ".join(task.get("depends_on", [])) or "none"
    print()
    print("=" * 72)
    print(f"TASK {task['id']} — {task['title']}")
    print("=" * 72)
    print(f"phase: {task['phase']}   effort: {task.get('effort', '?')}   "
          f"optional: {bool(task.get('optional'))}   dependencies: {deps}")
    print(f"status: {entry['status']}   attempts: {entry['attempts']}   "
          f"lease: {lease_text(entry)}")
    if task.get("why"):
        print()
        print(f"why: {task['why']}")
    if resume:
        print()
        print("RESUME MODE — a previous attempt is in progress.")
        print(f"last checkpoint: {entry.get('last_checkpoint') or 'none'}")
        if entry.get("notes"):
            for note in entry["notes"][-5:]:
                print(f"  note: {note}")
        if not lease_valid(entry):
            print(f"  lease expired: python3 plan/agentctl.py reclaim {task['id']}")
        status = git("status", "--short").stdout.strip()
        if status:
            print("  uncommitted changes:")
            print(textwrap.indent(status, "    "))
            print("  inspect with: git diff; do not revert work you did not make.")
        else:
            print("  working tree clean.")

    print()
    print("READ (only these; use rg for anything else):")
    for item in task.get("context", []):
        print(f"  - {item}")

    print()
    print("STEPS:")
    for idx, step in enumerate(task["steps"], 1):
        print(f"  {idx}. {step}")

    print()
    print("VERIFY (all must pass):")
    for check in task["verify"]:
        expect = check.get("expect_exit", 0)
        print(f"  - {check['cmd']}   (expect exit {expect})")
    if task.get("requires"):
        print(f"  requires: {', '.join(task['requires'])}")
    if task.get("network"):
        print("  network: yes — run only if the task needs it")

    print()
    print("SCOPE — only these paths may change:")
    for pattern in task["touch"]:
        print(f"  - {pattern}")
    print("  - plan/state.json, plan/journal.md (always allowed)")

    print()
    print("PROTOCOL:")
    print(f"  python3 plan/agentctl.py claim {task['id']}          # if not claimed")
    print(f"  python3 plan/agentctl.py checkpoint {task['id']} --note '...'")
    print(f"  python3 plan/agentctl.py verify {task['id']}")
    print(f"  python3 plan/agentctl.py done {task['id']} --note '...'")
    print(f"  python3 plan/agentctl.py block {task['id']} --reason '...'   # after 2 failed attempts")

    print()
    print("DONE MEANS:")
    print(textwrap.indent(task.get("done", "verify passes and scope is clean"), "  "))
    if task.get("notes"):
        print()
        print("NOTES:")
        print(textwrap.indent(str(task["notes"]), "  "))
    print()


# ─────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────


def cmd_init(args) -> int:
    tasks = load_tasks()
    errors = validate_plan(tasks)
    if errors:
        for err in errors:
            print(f"PLAN ERROR: {err}", file=sys.stderr)
        return 1
    with locked():
        existed = STATE_PATH.is_file()
        state = load_state(tasks, create=True)
        save_state(state)
    print(f"{'kept' if existed else 'created'} {STATE_PATH.relative_to(ROOT)}")
    print(f"tasks: {len(tasks)}")
    return 0


def cmd_doctor(args) -> int:
    tasks = load_tasks()
    state = load_state(tasks, create=False) if STATE_PATH.is_file() else None
    problems: list[str] = []
    warnings: list[str] = []

    def check(level: str, msg: str) -> None:
        if level == "ERROR":
            problems.append(msg)
        elif level == "WARN":
            warnings.append(msg)
        print(f"{level:5} {msg}")

    check("INFO", f"repo: {ROOT}")
    py = sys.version_info
    if py < (3, 10):
        check("ERROR", f"python {py.major}.{py.minor} < 3.10")
    else:
        check("INFO", f"python {py.major}.{py.minor}.{py.micro}")

    if not (ROOT / ".git").is_dir():
        check("WARN", "not a git work tree (checkpoints cannot be committed)")
    else:
        branch = git_out("rev-parse", "--abbrev-ref", "HEAD")
        check("INFO", f"git branch: {branch or '?'}")
        dirty = changed_paths()
        if dirty:
            check("WARN", f"working tree has {len(dirty)} changed path(s)")
        else:
            check("INFO", "working tree clean")

    plan_errors = validate_plan(tasks)
    for err in plan_errors:
        check("ERROR", f"plan: {err}")
    if not plan_errors:
        check("INFO", f"plan valid: {len(tasks)} tasks")

    if state is None:
        check("WARN", "state.json missing; run: python3 plan/agentctl.py init")
    else:
        unknown = set(state.get("tasks", {})) - {t["id"] for t in tasks}
        for tid in sorted(unknown):
            check("WARN", f"state has unknown task {tid}")
        for task in tasks:
            entry = state["tasks"].get(task["id"], {})
            if entry.get("status") not in STATUSES:
                check("ERROR", f"{task['id']}: invalid status {entry.get('status')!r}")
        for task in tasks:
            entry = state["tasks"].get(task["id"], {})
            if entry.get("status") == "in_progress":
                lvl = "INFO" if lease_valid(entry) else "WARN"
                check(lvl, f"{task['id']} in progress; lease {lease_text(entry)}")
            if entry.get("status") == "done" and not entry.get("seeded"):
                if not entry.get("commit"):
                    check("WARN", f"{task['id']} done without a commit sha")
                if not any(e.get("kind") == "verify" and e.get("ok") for e in entry.get("evidence", [])):
                    check("WARN", f"{task['id']} done without a passing verify record")

    for tool in ("git", "python3", "make", "pytest", "latexmk", "pandoc", "cffconvert", "actionlint", "shellcheck"):
        if shutil.which(tool):
            check("INFO", f"tool: {tool}")
        else:
            check("WARN", f"tool missing: {tool}" + (" (needed for PDF tasks)" if tool == "latexmk" else ""))

    if args.fix and state is None:
        with locked():
            state = load_state(tasks, create=True)
            save_state(state)
        check("INFO", "initialised plan/state.json")

    if state is not None:
        task, resume = next_action(tasks, state, include_optional=args.include_optional)
        if task:
            check("INFO", f"next: {task['id']}{' (resume)' if resume else ''} — {task['title']}")
        else:
            check("INFO", "next: none (all non-optional tasks done)")
    if problems:
        print(f"\n{len(problems)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"\nOK — {len(warnings)} warning(s)")
    return 0


def cmd_status(args) -> int:
    tasks = load_tasks()
    state = load_state(tasks, create=False)
    entries = state["tasks"]
    counts: dict[str, int] = {}
    for task in tasks:
        status = entries[task["id"]]["status"]
        counts[status] = counts.get(status, 0) + 1
    phases: dict[str, list[int]] = {}
    for task in tasks:
        done = 1 if entries[task["id"]]["status"] in {"done", "skipped"} else 0
        phases.setdefault(task["phase"], [0, 0])
        phases[task["phase"]][0] += done
        phases[task["phase"]][1] += 1

    if args.json:
        payload = {
            "updated": state.get("updated"),
            "counts": counts,
            "phases": {k: {"done": v[0], "total": v[1]} for k, v in phases.items()},
            "tasks": {
                task["id"]: {
                    "status": entries[task["id"]]["status"],
                    "title": task["title"],
                    "phase": task["phase"],
                    "attempts": entries[task["id"]]["attempts"],
                    "lease": lease_text(entries[task["id"]]),
                }
                for task in tasks
            },
        }
        print(json.dumps(payload, indent=2))
        return 0

    total = len(tasks)
    done = counts.get("done", 0) + counts.get("skipped", 0)
    print(f"plan {state.get('plan_version')} — updated {state.get('updated')}")
    print(f"progress: {done}/{total} ({100 * done // max(total, 1)}%)   "
          f"{counts}")
    print()
    print(f"{'ID':4} {'STATUS':12} {'PHASE':5} {'ATT':3} TITLE")
    for task in sorted(tasks, key=lambda t: t["order"]):
        entry = entries[task["id"]]
        status = entry["status"]
        if status == "in_progress" and not lease_valid(entry):
            status = "in_progress!"
        print(f"{task['id']:4} {status:12} {task['phase']:5} {entry['attempts']:3} {task['title']}")
    print()
    for phase in sorted(phases):
        d, t = phases[phase]
        print(f"  {phase}: {d}/{t}")
    active = current_tasks(tasks, state)
    if active:
        print()
        print(f"in progress: {active[0]['id']} — {active[0]['title']} "
              f"(lease {lease_text(entries[active[0]['id']])})")
    task, resume = next_action(tasks, state, include_optional=args.include_optional)
    if task:
        print(f"next: {task['id']}{' (resume)' if resume else ''} — {task['title']}")
        print(f"      python3 plan/agentctl.py next --card")
    else:
        print("next: none")
    return 0


def cmd_next(args) -> int:
    tasks = load_tasks()
    state = load_state(tasks, create=False)
    task, resume = next_action(tasks, state, include_optional=args.include_optional)
    if task is None:
        print("No ready tasks. Run: python3 plan/agentctl.py status")
        return 0
    entry = entry_for(state, task["id"])
    if args.json:
        print(json.dumps({"task": task, "state": entry, "resume": resume}, indent=2))
    elif args.card:
        print_card(task, entry, resume, args.include_optional)
    else:
        print(f"{task['id']}{' (resume)' if resume else ''} — {task['title']}")
    return 0


def cmd_claim(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        task = task_by_id(tasks, args.task)
        entry = entry_for(state, args.task)
        if entry["status"] == "done":
            print(f"{args.task} is already done.")
            return 0
        if entry["status"] == "blocked":
            fail(f"{args.task} is blocked; run: unblock {args.task}")
        if not deps_done(task, state):
            fail(f"{args.task} dependencies not done: {task.get('depends_on')}")
        if entry["status"] == "in_progress":
            lease = entry.get("lease") or {}
            if lease_valid(entry):
                if lease.get("owner") != args.owner:
                    fail(
                        f"{args.task} is claimed by {lease.get('owner')} until "
                        f"{lease.get('expires')}; use reclaim only after expiry"
                    )
                print(f"{args.task} already claimed by {args.owner}; resuming.")
                return 0
            fail(
                f"{args.task} has an expired lease ({lease_text(entry)}); "
                f"run: reclaim {args.task} --owner {args.owner}"
            )
        entry["status"] = "in_progress"
        entry["attempts"] += 1
        entry["lease"] = {
            "owner": args.owner,
            "started": utcnow(),
            "heartbeat": utcnow(),
            "expires": (
                datetime.now(timezone.utc) + timedelta(minutes=args.ttl)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        entry["last_checkpoint"] = utcnow()
        save_state(state)
        journal("claim", args.task, f"owner={args.owner} ttl={args.ttl}m")
    print(f"claimed {args.task} (owner {args.owner}, ttl {args.ttl}m)")
    print(f"next: python3 plan/agentctl.py next --card")
    return 0


def cmd_heartbeat(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        entry = entry_for(state, args.task)
        if entry["status"] != "in_progress":
            fail(f"{args.task} is not in progress")
        entry["lease"] = entry.get("lease") or {"owner": args.owner, "started": utcnow()}
        entry["lease"]["heartbeat"] = utcnow()
        entry["lease"]["expires"] = (
            datetime.now(timezone.utc) + timedelta(minutes=args.ttl)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        save_state(state)
    print(f"heartbeat {args.task}: lease until {entry['lease']['expires']}")
    return 0


def cmd_reclaim(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        entry = entry_for(state, args.task)
        if entry["status"] != "in_progress":
            fail(f"{args.task} is not in progress")
        if lease_valid(entry) and not args.force:
            fail(
                f"lease still valid ({lease_text(entry)}); use --force only if the "
                "previous agent is gone"
            )
        entry["lease"] = {
            "owner": args.owner,
            "started": utcnow(),
            "heartbeat": utcnow(),
            "expires": (
                datetime.now(timezone.utc) + timedelta(minutes=args.ttl)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        entry["attempts"] += 1
        entry["last_checkpoint"] = utcnow()
        save_state(state)
        journal("reclaim", args.task, f"owner={args.owner}")
    print(f"reclaimed {args.task}; resume with: python3 plan/agentctl.py next --card")
    return 0


def cmd_checkpoint(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        entry = entry_for(state, args.task)
        if entry["status"] != "in_progress":
            fail(f"{args.task} is not in progress; claim it first")
        note = args.note or "checkpoint"
        entry["notes"] = (entry.get("notes", []) + [note])[-20:]
        entry["last_checkpoint"] = utcnow()
        if args.step:
            entry["steps_done"] = list(dict.fromkeys(entry.get("steps_done", []) + [args.step]))
        save_state(state)
        journal("checkpoint", args.task, note, [f"step: {args.step}"] if args.step else [])
        commit = None
        if args.commit:
            git("add", "-A")
            proc = git("commit", "-m", f"chore(plan): checkpoint {args.task}", "-m", note)
            if proc.returncode == 0:
                commit = head_sha()
            elif "nothing to commit" not in (proc.stdout + proc.stderr):
                print(proc.stdout + proc.stderr, file=sys.stderr)
                fail("checkpoint commit failed")
    print(f"checkpointed {args.task}{' @ ' + commit[:8] if commit else ''}")
    return 0


def cmd_verify(args) -> int:
    tasks = load_tasks()
    task = task_by_id(tasks, args.task)
    return verify_task(task, record=True, timeout=args.timeout)


def cmd_done(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        task = task_by_id(tasks, args.task)
        entry = entry_for(state, args.task)
        if entry["status"] == "done":
            print(f"{args.task} already done.")
            return 0
        if entry["status"] != "in_progress":
            fail(f"{args.task} is not in progress; claim it first")

    if not args.skip_verify:
        rc = verify_task(task, record=True, timeout=args.timeout)
        if rc != 0:
            fail("verify failed; fix it or record a block. Do not mark done.")

    with locked():
        state = load_state(tasks, create=False)
        entry = entry_for(state, args.task)
        changed = [p for p in changed_paths() if not p.startswith("plan/")]
        allowed = list(task.get("touch", [])) + ["plan/**"]
        outside = [p for p in changed if not scope_ok(p, allowed)]
        if outside and not args.allow_outside_scope:
            print("Changes outside the task scope:", file=sys.stderr)
            for path in outside:
                print(f"  - {path}", file=sys.stderr)
            fail("refusing to mark done; move the change to its own task or pass --allow-outside-scope")

        commit = entry.get("commit")
        if args.skip_verify:
            entry["notes"] = (entry.get("notes", []) + ["DONE WITHOUT VERIFY: " + (args.note or "")])[-20:]
        elif args.note:
            entry["notes"] = (entry.get("notes", []) + [args.note])[-20:]
        entry["status"] = "done"
        entry["lease"] = None
        entry["last_checkpoint"] = utcnow()
        entry["commit"] = commit
        save_state(state)
        journal(
            "done",
            args.task,
            args.note or "",
            [
                "verify: skipped" if args.skip_verify else "verify: passed",
                "scope: " + ("override" if outside else "clean"),
            ],
        )

        if args.commit:
            git("add", "-A")
            body = (
                f"Plan: {args.task}\n"
                f"Phase: {task['phase']}\n"
                f"Verify: {'skipped' if args.skip_verify else 'passed'}\n"
            )
            message = f"task({args.task}): {task['title']}"
            proc = git("commit", "-m", message, "-m", body, "--allow-empty")
            if proc.returncode != 0:
                print(proc.stdout + proc.stderr, file=sys.stderr)
                fail("task commit failed; state is marked done on disk but has no commit")
            commit = head_sha()
            entry["commit"] = commit
            save_state(state)
            # Second, tiny commit records the sha inside state.json. The task's
            # own commit is the one stored in entry["commit"].
            git("add", "plan/state.json")
            git("commit", "-m", f"chore(plan): record {args.task} @ {commit[:8]}", "--allow-empty")

    print(f"done {args.task}{' @ ' + commit[:8] if commit else ''}")
    nxt, resume = next_action(tasks, state, include_optional=args.include_optional)
    if nxt:
        print(f"next: {nxt['id']}{' (resume)' if resume else ''} — {nxt['title']}")
    else:
        print("next: none")
    return 0


def cmd_block(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        entry = entry_for(state, args.task)
        if entry["status"] == "done":
            fail(f"{args.task} is already done")
        entry["status"] = "blocked"
        entry["lease"] = None
        entry["notes"] = (entry.get("notes", []) + [f"BLOCKED: {args.reason}"])[-20:]
        save_state(state)
        journal("block", args.task, args.reason)
    print(f"blocked {args.task}: {args.reason}")
    print("Do not start dependent tasks. Record the decision needed in plan/decisions.md.")
    return 0


def cmd_unblock(args) -> int:
    tasks = load_tasks()
    with locked():
        state = load_state(tasks, create=False)
        entry = entry_for(state, args.task)
        if entry["status"] != "blocked":
            fail(f"{args.task} is not blocked")
        entry["status"] = "todo"
        entry["lease"] = None
        entry["notes"] = (entry.get("notes", []) + [f"UNBLOCKED: {args.note or ''}"])[-20:]
        save_state(state)
        journal("unblock", args.task, args.note or "")
    print(f"unblocked {args.task}")
    return 0


def cmd_audit(args) -> int:
    tasks = load_tasks()
    state = load_state(tasks, create=False)
    errors: list[str] = []
    warnings: list[str] = []
    for task in tasks:
        entry = state["tasks"][task["id"]]
        if entry["status"] != "done" or entry.get("seeded"):
            continue
        verify_ok = any(e.get("kind") == "verify" and e.get("ok") for e in entry.get("evidence", []))
        if not verify_ok:
            warnings.append(f"{task['id']}: done without a passing verify record")
        if not entry.get("commit"):
            warnings.append(f"{task['id']}: done without a commit sha")
        elif git("cat-file", "-e", f"{entry['commit']}^{{commit}}").returncode != 0:
            errors.append(f"{task['id']}: recorded commit {entry['commit'][:8]} not found")
    for task in tasks:
        entry = state["tasks"][task["id"]]
        if entry["status"] == "in_progress" and not lease_valid(entry):
            warnings.append(f"{task['id']}: stale in-progress lease")
    print(f"audit: {len(tasks)} tasks, "
          f"{sum(1 for t in tasks if state['tasks'][t['id']]['status'] == 'done')} done")
    for warn in warnings:
        print(f"WARN  {warn}")
    for err in errors:
        print(f"ERROR {err}")
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, indent=2))
    return 1 if errors else 0


def cmd_render(args) -> int:
    tasks = load_tasks()
    state = load_state(tasks, create=False)
    phases: dict[str, list[int]] = {}
    for task in tasks:
        phases.setdefault(task["phase"], [0, 0])
        phases[task["phase"]][0] += 1 if state["tasks"][task["id"]]["status"] in {"done", "skipped"} else 0
        phases[task["phase"]][1] += 1
    lines = [
        "# Implementation status",
        "",
        f"Updated: {state.get('updated')}",
        "",
        "| Phase | Done | Total |",
        "|---|---|---|",
    ]
    for phase in sorted(phases):
        d, total = phases[phase]
        lines.append(f"| {phase} | {d} | {total} |")
    lines += ["", "## In progress", ""]
    active = current_tasks(tasks, state)
    if active:
        for task in active:
            lines.append(f"- `{task['id']}` {task['title']} — lease {lease_text(state['tasks'][task['id']])}")
    else:
        lines.append("_none_")
    lines += ["", "## Blocked", ""]
    blocked = [t for t in tasks if state["tasks"][t["id"]]["status"] == "blocked"]
    lines += [f"- `{t['id']}` {t['title']}" for t in blocked] or ["_none_"]
    lines += ["", "## Next", ""]
    nxt, resume = next_action(tasks, state, include_optional=args.include_optional)
    lines.append(f"- `{nxt['id']}` {nxt['title']}{' (resume)' if resume else ''}" if nxt else "_none_")
    text = "\n".join(lines) + "\n"
    if args.write:
        Path(args.write).write_text(text, encoding="utf-8")
        print(f"wrote {args.write}")
    else:
        print(text)
    return 0


def cmd_log(args) -> int:
    if not JOURNAL_PATH.is_file():
        print("no journal yet")
        return 0
    lines = JOURNAL_PATH.read_text(encoding="utf-8").splitlines()
    print("\n".join(lines[-args.lines:]))
    return 0


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS is important: without it the subparser's default None would
    # overwrite a --root given before the subcommand.
    common.add_argument("--root", default=argparse.SUPPRESS, help="repo root (default: plan/..)")

    parser = argparse.ArgumentParser(description="agentctl — plan state machine")
    parser.add_argument("--root", default=None, help="repo root (default: plan/..)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", parents=[common], help="create/reconcile state.json")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", parents=[common], help="check environment and plan health")
    p.add_argument("--fix", action="store_true", help="create state.json if missing")
    p.add_argument("--include-optional", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("status", parents=[common], help="task table and progress")
    p.add_argument("--json", action="store_true")
    p.add_argument("--include-optional", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("next", parents=[common], help="print the next task or resume task")
    p.add_argument("--card", action="store_true", help="print the full task card")
    p.add_argument("--json", action="store_true")
    p.add_argument("--include-optional", action="store_true")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("claim", parents=[common], help="claim a task")
    p.add_argument("task")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.add_argument("--ttl", type=int, default=DEFAULT_TTL_MIN)
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("heartbeat", parents=[common], help="extend a lease")
    p.add_argument("task")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.add_argument("--ttl", type=int, default=DEFAULT_TTL_MIN)
    p.set_defaults(func=cmd_heartbeat)

    p = sub.add_parser("reclaim", parents=[common], help="take over an expired lease")
    p.add_argument("task")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.add_argument("--ttl", type=int, default=DEFAULT_TTL_MIN)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_reclaim)

    p = sub.add_parser("checkpoint", parents=[common], help="record progress")
    p.add_argument("task")
    p.add_argument("--note", default="")
    p.add_argument("--step", default=None)
    p.add_argument("--commit", action="store_true")
    p.set_defaults(func=cmd_checkpoint)

    p = sub.add_parser("verify", parents=[common], help="run the task's verify commands")
    p.add_argument("task")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("done", parents=[common], help="verify, scope-check, commit and close")
    p.add_argument("task")
    p.add_argument("--note", default="")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--allow-outside-scope", action="store_true")
    p.add_argument("--commit", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--include-optional", action="store_true")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("block", parents=[common], help="mark a task blocked")
    p.add_argument("task")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_block)

    p = sub.add_parser("unblock", parents=[common], help="return a blocked task to todo")
    p.add_argument("task")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_unblock)

    p = sub.add_parser("audit", parents=[common], help="consistency check for done tasks")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("render", parents=[common], help="render a Markdown status summary")
    p.add_argument("--write", default=None)
    p.add_argument("--include-optional", action="store_true")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("log", parents=[common], help="tail the journal")
    p.add_argument("-n", "--lines", type=int, default=60)
    p.set_defaults(func=cmd_log)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_root(args.root)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
