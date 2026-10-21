# Decisions (confirmed 2026-10-21)

These answers replace the provisional defaults. The agent may proceed on them.
Changing one again requires an explicit edit here plus a plan update if the
task scope changes.

| # | Question | Decision | Status |
|---|---|---|---|
| 1 | Audience | Personal template only; docs stay generic and neutral | confirmed |
| 2 | Manuscript kind | Perspective **and** empirical are both core; review remains selectable | confirmed |
| 3 | Branch policy | Keep `master` for v1; make branch names configurable in T29; allow `main` for new repos | confirmed |
| 4 | v2 metadata break | Allowed, **without** an automated migration tool; T36 becomes manual migration documentation only | confirmed |
| 5 | License matrix | `CC-BY-4.0` (default paper license) and `MIT` (code license; also selectable for paper) | confirmed |
| 6 | Journal classes | None now; T38 stays parked and optional until a concrete target appears | confirmed |
| 7 | Python / deps | Python 3.10+; generated repos use stdlib + PyYAML at runtime; dev tooling may use pytest/ruff/cookiecutter/cffconvert/jsonschema | confirmed |
| 8 | MCP timing | After Phase 2, optional, read-only first; never in CI/pre-push/Make | confirmed |
| 9 | Personal defaults | Move ORCID/GitHub/user identity out of tracked defaults into an optional user config; T31 implements and documents it | confirmed |
| 10 | Plan location | Keep `docs/improvement-plan.md` and `plan/` in this repo | confirmed |

## Consequences for the task graph

* **T27** must treat empirical as a first-class path, not a stub: methods and
  results sections, the right packages, and a supported `manuscript_kind`
  choice. Perspective stays the default.
* **T37** (data/analysis pipeline) is promoted from optional P5 to core P3,
  after T27/T28, because empirical manuscripts need a reproducible data path.
* **T36** is no longer `article migrate`. It documents the manual v1 → v2
  mapping, backups, and validation; no migration command is built.
* **T14** offers only CC-BY-4.0 and MIT. Code is MIT; if the paper is also MIT,
  one LICENSE is enough.
* **T31** removes personal defaults from `cookiecutter.json` and reads an
  optional user config at generation time. The config is never committed into
  a generated repo.
* **T38** (journal classes) remains `optional: true` and must not be started
  without a new decision.
* **T28** validates ORCID only when one is supplied; an empty ORCID is valid.
* **T26 scope extension (2026-10-21).** After T21/T23 the metadata renderers
  live in `scripts/article/metadata.py`, not the deprecated
  `generate-metadata.py` shim. T26 therefore also changes that core module;
  the shim stays a re-export only.

## Architecture decisions already firm

These come from the review and are not reopened by the answers above:

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
2. If the change affects task scope, edit `plan/tasks.json` and run
   `python3 plan/agentctl.py init` (this acknowledges the new plan hash).
3. Append a note to `plan/journal.md` (or use `agentctl checkpoint` on the
   active task).
4. If a task was blocked on the question, `unblock` it with the decision id.
