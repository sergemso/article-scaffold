# Plan state machine — human notes

`plan/` is a small, dependency-free task harness so that an AI agent (or a
human) can stop at any point and resume without chat history.

```
plan/
├── tasks.json     immutable task graph: specs, deps, scope, verify
├── state.json     mutable progress: status, leases, evidence, commit shas
├── journal.md     append-only human-readable log
├── decisions.md   provisional decisions + open questions
├── STATUS.md      generated summary (agentctl render)
└── agentctl.py    stdlib-only CLI; the only supported writer
```

`AGENTS.md` at the repo root is the cold-start entry point. This file explains
the mechanics for a human reviewing the plan.

## Why JSON and not YAML

The harness must work before project dependencies are installed. `state.json`
and `tasks.json` are parsed with the Python standard library. The generated
article repo still uses YAML for `metadata.yaml`; only the harness is JSON.

## Commands

| Command | Purpose |
|---|---|
| `init` | create/reconcile `state.json`; never clobbers progress |
| `doctor [--fix]` | environment, plan graph, state, leases, tools |
| `status [--json]` | table + per-phase progress |
| `next [--card\|--json]` | active task first, else lowest-order ready task |
| `claim ID [--ttl 120]` | set an in-progress lease |
| `heartbeat ID` | extend a lease without checkpointing |
| `reclaim ID [--force]` | take over an expired lease |
| `checkpoint ID --note ... [--step N] [--commit]` | record progress |
| `verify ID` | run the task's verify commands and record evidence |
| `done ID [--note] [--skip-verify] [--allow-outside-scope]` | close + commit |
| `block ID --reason ...` | stop dependents; record why |
| `unblock ID` | return to todo after a decision |
| `audit [--json]` | check done tasks have evidence and real commits |
| `render [--write plan/STATUS.md]` | Markdown status |
| `log [-n 60]` | tail the journal |

Global `--root PATH` (before or after the subcommand) points the harness at a
copy, which is how the self-test runs without touching real progress.

## Invariants enforced by the tool

* Plan graph: unique ids/orders, known dependencies, no cycles, non-empty
  steps/verify, every verify entry has `cmd`.
* State: known statuses; every plan task has a state entry; unknown tasks are
  reported by `doctor`.
* Drift: `state.json` stores a `plan_hash`; `doctor` warns when `tasks.json`
  changed since the last `init`, so an agent cannot silently execute a
  different plan than the one it checkpointed.
* Leases: a live lease owned by another agent blocks `claim`; expired leases
  are reported; `reclaim` requires expiry or `--force`.
* `done`: task must be `in_progress`; verify must pass unless explicitly
  skipped; changed paths must match `touch` unless explicitly overridden;
  closing writes state, appends the journal, creates the task commit, then a
  record commit with the sha.
* Writes: exclusive `flock` on `plan/.lock` and atomic `os.replace`, so a
  crash cannot leave a half-written JSON file.

## Single-writer model

The harness supports **one active writer at a time**. Leases prevent two
agents from working the same task, and `next` always returns the active task.
There is no merge protocol for concurrent `state.json` edits. If parallel work
is ever needed, give each agent a separate worktree with its own plan copy and
merge code, not state.

## Cold-start recovery matrix

| On disk | Meaning | Action |
|---|---|---|
| `in_progress`, valid lease, clean tree | agent died before doing work | resume the card |
| `in_progress`, valid lease, dirty tree | agent died mid-task | read `last_checkpoint`, inspect diff, continue |
| `in_progress`, expired lease | stale | `reclaim ID`, then resume |
| `blocked` | decision or repeated failure | read notes; answer in `decisions.md`; `unblock` |
| `done` with commit | finished | do not redo; `next` |
| `done` without commit | inconsistent | `audit`; treat as not done; record a repair note |

## Adding or changing tasks

Only edit `tasks.json` when the plan itself changes. Rules:

1. New ids are `T45`, `T46`, …; never reuse an id.
2. `order` is globally unique; append at the end unless the task is genuinely
   urgent.
3. `depends_on` must be acyclic and refer to existing ids.
4. `touch` is a scope allowlist; keep it narrow.
5. `verify` must be runnable and deterministic. If it needs a tool, list it in
   `requires`.
6. Mark speculative work `optional: true`; `next` skips it unless
   `--include-optional` is passed.
7. Run `python3 plan/agentctl.py doctor` after editing.

## Self-test

The harness was exercised against a throwaway copy with `--root`:
claim → checkpoint → verify → done, plus block/unblock, an expired lease,
`reclaim`, a scope refusal, and the `--json`/`render` outputs. To repeat it,
copy the repo to a temporary directory, commit once, and run the same commands
with `--root` pointing at the copy. Real progress in this repo is untouched.

## Design lineage

The structure follows the "task graph + mutable state + append-only journal"
pattern: task specs are code-reviewed and stable; progress is data; history is
append-only. This is what makes the plan re-entrant and cold-start-ready
without a server or a database.
