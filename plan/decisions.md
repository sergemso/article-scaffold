# Provisional decisions (agent may proceed)

The human has not answered the open questions from §10 of
`docs/improvement-plan.md`. To keep the plan re-entrant, the agent proceeds on
the **safe defaults** below. Each entry records the assumption, the rationale,
and what would change if the human decides otherwise.

Status values: `provisional` (agent may proceed), `confirmed` (human said so),
`gated` (stop before the affected task).

| # | Question | Decision | Status | Impact if changed |
|---|---|---|---|---|
| 1 | Audience | Personal template, but docs stay neutral and generic | provisional | Public/shared raises the bar for migration, support, and license docs; T36/T42 grow |
| 2 | Manuscript kind | `perspective` is the default; `empirical` and `review` are selectable in v2 | provisional | If only perspective, T27 and P5 shrink; if empirical is core, T27 moves into P1/P2 |
| 3 | Branch policy | Keep `master` for v1; make branch names configurable/dynamic in T29, then allow `main` for new repos | provisional | If `main` now, T29 moves earlier and all workflows/docs use `main` |
| 4 | v2 metadata break | Allowed, with `author:` → `authors:` migration and a compatibility loader + `article migrate` | provisional | If no break, T25/T26 must keep the v1 shape indefinitely; T36 becomes read-only |
| 5 | License matrix | `CC-BY-4.0` (default), `CC-BY-SA-4.0`, `CC0-1.0`, `MIT` for code | provisional | Fewer licenses is a smaller T14 matrix; more licenses add texts and mappings |
| 6 | Journal classes | None until P5; P5 adds `elsarticle`, `acmart`, `IEEEtran` as optional examples, not defaults | provisional | A specific target moves that class into P3 and adds a submission checklist |
| 7 | Python floor / deps | Python 3.10+; generated repos use stdlib + PyYAML at runtime; dev tooling may use pytest/ruff/cookiecutter/cffconvert/jsonschema | provisional | A click/typer CLI would be an extra runtime dep; stdlib argparse is the default |
| 8 | MCP timing | After P2, optional, separate extra; never in CI/pre-push/Make; read-only first | provisional | "Never" drops T43/T44; "now" would invert the architecture and is rejected |
| 9 | Personal defaults | Keep current ORCID/GitHub defaults in `cookiecutter.json` for now; T31 documents how to override them; do not hard-code into generated metadata | provisional | Moving to user config adds a pre-gen config file and changes T28 |
| 10 | Plan doc | Keep `docs/improvement-plan.md` and `plan/` in this repo | provisional | Moving to private notes changes links in AGENTS.md/README only |

## Architecture decisions already treated as firm

These come from the review and are not reopened by the task plan:

* **Core is canonical.** `scripts/article/` contains pure logic; the CLI,
  Makefile, hooks, CI, and MCP are adapters. Never CLI → MCP.
* **Stable JSON contract + exit codes.** `0` ok, `1` diagnostics/failure,
  `2` usage, `3` internal. Every machine-facing command supports `--json`.
* **Generated repos stay archival.** TeX + Python only for the build; no
  service, database, or network in `make pdf`/`make validate`/`make metadata`.
* **MCP is optional and outside the critical path.** Never in CI, pre-push, or
  Make. Read-only by default.
* **Template semver.** v1.1 correctness, v1.2 core/CLI, v2.0 metadata schema,
  v2.1 automation, v2.2+ optional extensions; MCP is 0.x.

## How to change a decision

1. Edit the row: set status to `confirmed`, state the decision and the date.
2. If the change affects task scope, edit `plan/tasks.json` (new id or updated
   `touch`/`steps`/`verify`) and run `python3 plan/agentctl.py doctor`.
3. Append a note to `plan/journal.md` (or use `agentctl checkpoint` on the
   active task).
4. If a task was blocked on the question, `unblock` it with the decision id.
