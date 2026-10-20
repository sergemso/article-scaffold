# Agent execution plan — cold-start entry point

This repository is being hardened with an **agent-executable plan**. If you are
an AI coding agent and have no prior conversation history, read this file, run
the three commands below, and continue from the task card. Do not re-plan from
scratch and do not rely on chat context: the plan, progress, evidence, and
blockers are all on disk.

The human roadmap and review findings are in `docs/improvement-plan.md`. That
document is **background**, not the task queue. The canonical queue is
`plan/tasks.json`; progress is `plan/state.json`; history is
`plan/journal.md`.

---

## 1. Cold start (do this first)

```bash
python3 plan/agentctl.py doctor          # environment + plan health
python3 plan/agentctl.py status          # where we are
python3 plan/agentctl.py next --card     # the exact task to do now
```

If `doctor` reports `state.json missing`, run:

```bash
python3 plan/agentctl.py init
```

Then read only the files listed under `READ` in the task card. The card is
self-contained. If you need more context, use `rg` to find it; do not read the
whole repository or the whole improvement plan.

Once T02 is done, run `make setup` (or activate the venv it creates) before
tasks whose card says `pytest`; `agentctl` shells out to `python3`, so it must
see the same environment.

---

## 2. The only lifecycle you need

```bash
# 1. Claim (no-op if already yours; refuses a live lease held by someone else)
python3 plan/agentctl.py claim T05

# 2. Work in small steps. Checkpoint after each meaningful step.
python3 plan/agentctl.py checkpoint T05 --note "tojson applied to metadata.yaml"

# 3. Run the task's verification commands (records evidence + output tails)
python3 plan/agentctl.py verify T05

# 4. Only after verify passes: scope-check, commit, and close
python3 plan/agentctl.py done T05 --note "YAML/JSON parse under special chars"

# If stuck after two honest attempts:
python3 plan/agentctl.py block T05 --reason "needs decision: ..."

# If a previous agent died and the lease expired:
python3 plan/agentctl.py reclaim T05
```

`done` refuses to close a task when:

* the verify commands fail (unless `--skip-verify`, which is recorded and
  flagged by `audit`);
* changed paths fall outside the task's `touch` list (unless
  `--allow-outside-scope`, which is recorded).

A normal `done` creates **one task commit** plus a tiny
`chore(plan): record <id> @ <sha>` commit. Do not squash or rewrite them.

---

## 3. Re-entrancy rules

1. **In-progress tasks always win.** `next` returns the active task before any
   new one. Resume it; do not start a parallel task.
2. **Leases serialize writers.** A lease is valid for 120 minutes by default.
   `heartbeat` extends it. `reclaim` is only for an expired lease or a
   confirmed-dead agent (`--force`).
3. **State is authoritative.** If `state.json` says `in_progress`, trust it
   over your memory of the conversation. If it says `done`, do not redo the
   task; run `audit` instead.
4. **Checkpoint before anything slow or risky** (full test suite, TeX build,
   bulk rename). A checkpoint writes state and journal atomically.
5. **Never revert work you did not make.** On resume, inspect
   `git status`/`git diff`. If the changes match the active task, continue and
   checkpoint. If they are unrelated, stop and ask the human; do not
   `git checkout -- .`, `git reset --hard`, or delete untracked files.
6. **Two attempts, then block.** Repeated flailing is worse than a precise
   blocker. Record the failing command, the hypothesis, and the decision
   needed.
7. **Do not edit completed tasks or rewrite history.** Plan changes go through
   a new task or a human edit of `plan/tasks.json`; append to the journal.
8. **No network in the critical path.** Tasks marked `network: true` may
   install dev dependencies or query a schema registry. Everything else must
   work offline.

---

## 4. Scope, commits, and evidence

* `touch` is a **hard scope allowlist**. Adding a file outside it is a signal
  that the task is too small or the plan is wrong; stop and record it.
* One task → one task commit. Message: `task(T05): <title>`, body includes the
  plan id, phase, and whether verify ran.
* Checkpoints are optional commits: `chore(plan): checkpoint T05`.
* Never force-push, never rewrite published commits, never amend a commit that
  is already on a shared branch.
* Evidence lives in `state.json`: each verify run records the command, exit
  code, expected exit code, output tail, timestamp, and HEAD sha. `audit`
  checks it.
* Missing tools are not a pass. If `latexmk`/`pandoc`/`cffconvert` is absent,
  `verify` exits `3` and records `missing_tools`. You may close the task with
  `--skip-verify --note "latexmk unavailable; CI job <name> is the evidence"`
  **only** when the implementation is otherwise complete. Never skip a failing
  test.

---

## 5. Context discipline (important for cold starts)

* The card lists at most a handful of files. Read those first. A `path#section` entry means read that section; it is not a literal filename.
* Prefer `rg -n "symbol" path` over opening large files.
* Do not read `docs/improvement-plan.md` end to end; the card quotes what you
  need. Use it only to resolve a design question.
* Do not read `plan/agentctl.py` unless you are changing the harness itself.
* Keep the working tree clean between tasks. If a build produces artifacts,
  they belong in `build/` or are gitignored.

---

## 6. Phase gates

After the last task of a phase, run:

```bash
make test
python3 plan/agentctl.py audit
python3 plan/agentctl.py render --write plan/STATUS.md
```

Record the gate in the journal with `checkpoint` or a dedicated note, and
commit. Do not start optional tasks (`P5`, `P6`) before the P0–P2 gates pass
and a human explicitly opts in.

Current gates:

| Gate | After | Must be true |
|---|---|---|
| G0 | T04 | harness + test skeleton green |
| G1 | T10 | escaping/SSOT regressions green, metadata idempotent |
| G1b | T17 | CFF/Zenodo/validator/license green |
| G2 | T24 | CLI `--json`, exit codes, Make/CI delegation green |
| G3 | T32 | v2 metadata, build, CI hardening green |
| G4 | T36 | automation/reproducibility/migration green |

---

## 7. Decisions and open questions

`plan/decisions.md` contains **provisional safe defaults** for the questions
the human has not answered yet. Proceed on them unless a task is explicitly
marked as gated. Do not silently change a decision; record it in
`plan/decisions.md` and, if it changes scope, create a task.

If a blocker is a product decision rather than a code problem, use `block`
with a one-line question, then stop. The human can answer in
`plan/decisions.md` and `unblock`.

---

## 8. What "done" means

A task is done only when all of the following are true:

1. every `verify` command exits with its expected code;
2. only paths in `touch` (plus `plan/`) changed;
3. `state.json` says `done` with a commit sha;
4. `journal.md` has the closing entry;
5. the next cold-start agent can run `doctor`/`next --card` and continue.

If any of these is missing, the task is not done, regardless of how good the
code looks.
