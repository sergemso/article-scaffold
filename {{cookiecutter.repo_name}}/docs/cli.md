# CLI and JSON contract

The vendored CLI is the machine-readable entry point for Make, hooks, CI, and
optional editors or agent adapters. It has no install step and no network
dependency:

```bash
python3 -m scripts.article <command> [--json]
```

Run `python3 -m scripts.article --help` or
`python3 -m scripts.article <command> --help` for the full option list.

## Commands

| Command | Purpose |
| --- | --- |
| `validate` | Run the same structural checks as `make validate` and CI. |
| `metadata` | Regenerate every derived file from `metadata.yaml`. |
| `metadata --check` | Compare derived files with disk; write nothing. |
| `metadata --dry-run` | List files that would change; write nothing. |
| `status` | Report template, repository, metadata, diagnostics, and tool state. |
| `build pdf` | Regenerate the files derived from `metadata.yaml`, then build `paper/article.pdf`. |
| `build docx` | Regenerate the derived files, then build `manuscript.docx`. |
| `build supp` | Build every standalone supplementary document (`paper/supplementary.tex`, `paper/supplementary/*.tex` with a `\documentclass`) to `paper/supplementary/NAME.pdf`. |
| `build <kind> --dry-run` | Print the build plan without running it or writing any file. |
| `build <kind> --no-regenerate` | Build without refreshing the derived files first. |
| `companion` | Plan, build or gate the public companion snapshot (`--plan`, `--build DIR`, `--gate TAG`). See [companion.md](companion.md). |
| `ledger get\|explain\|verify\|evict\|gc\|stats` | Read and maintain the committed results ledger in `docs/ledger/`. `get` exits 1 on a miss; `explain` names the input that differs from the nearest entry; `evict` is the only delete and is logged. There is no command that writes a result by hand. |
| `check NAME` / `check record NAME` / `check --cold` | The declared checks of the fixed table, as ledger lookups. `check NAME` is a pure read whose `ok` and the exit code always agree: `ok` is true (exit 0) only for a `hit` with a stored `pass`; `miss`, `stale`, `uncacheable` and a stored `fail` are `ok: false` and exit 1, and the `state` field tells them apart. It is `hit` (with the stored verdict and up to five failing lines, capped in width and redacted for secrets), `stale` (an input changed) or `miss`; a check marked non-deterministic reports `uncacheable`. `check record NAME` runs the table entry (never a command from a repo file) and stores a `pass` or `fail`; a timeout or a missing tool is an error and is not stored. `check --cold` ignores lookups, runs every deterministic check, evicts (and logs) any stored outcome that differs, and on a clean run writes the `cold-run` record that the release gate and `flow round close` require; run it in CI or by hand, never inside `flow next`. `ARTICLE_LEDGER=off` or `--no-ledger` bypasses lookups. |
| `claims quote-check\|excerpt\|cache\|record\|rebase` | Tier 1 and tier 2 of the source-claim checks (`schemas/claims-result.schema.json`). `quote-check [ID\|--all]` matches each quote in local text and reports verdicts and locators, never text; a `locator` written as a source address (`key@hash#locator`) is matched in that passage of the store only, and a node whose hash is no longer the current edition is reported `stale` (exit 1). `rebase ID` finds the quote in the current edition and prints `proposed`, the new address, for a person to put in `theses.yaml`; it never edits the map; `status` is `current`, `proposed`, `quote-missing` or `no-locator` (exit 1 for the last two). `record ID --set V` (alias `cache`) stores a tier 2 verdict in the ledger. No network call. |
| `index [--check]` | Write `paper/build/section-index.json` (labels, line ranges, summaries of `paper/sections/*.tex`) and, when `paper/supplementary/` holds `.py` or `.rs` files, `paper/build/code-index.json` (`schemas/index-result.schema.json`): each function, class, method, test, struct, enum, trait, mod and impl with a qualified name (`Class.method`, `Type::method`, `Trait for Type::method`), its line range and a 12-hex hash of its lines. Python goes through the standard-library `ast`, Rust through a line-based scan, so unusual Rust macros can mislead it. A file that does not parse is listed with its status (`unparsed` in the output) and indexed without symbols; it is not fatal. `--check` exits 1 when either index is missing, older than a source file, or lists a file that was added or removed; it writes nothing. |
| `index slice NAME [--file PATH]` | Print one code symbol's lines as JSON (`text`, `file`, `lines`, `hash`). `NAME` is the qualified name, or the last part when that is unique. An ambiguous name exits 1 with `candidates`; `--file` narrows it. A file changed since the index was built exits 1 and asks for `index`. |
| `sources add\|index\|slice\|diff\|find\|list` | The local source store in `paper/sources/` (`schemas/sources-result.schema.json`, manifest in `schemas/sources-manifest.schema.json`). `add FILE --origin ... --edition ...` copies a file to `paper/sources/<key>/<raw hash>/raw.<ext>` and appends an entry to `manifest.json` (older hashes stay; the key defaults to the `MANIFEST.md` row for that file, which is read and never changed). `index [KEY] [--force]` writes the committed normalized text and the locator index next to it (plain text, HTML through the standard library, PDF through `pdftotext` when installed; otherwise the source is listed as unreadable and the command exits 1); existing text is kept unless `--force`. `slice ADDRESS [--window N]` prints the passage of `source-key@hash#locator` (`sec:`, `para:` or `req:` locators), capped at 80 lines and 8000 bytes, with `superseded: true` when a newer edition exists; an ambiguous hash prefix is an error listing `candidates`. `diff KEY OLD NEW` lists locators added, removed and changed. `find QUERY... [--key K] [--limit N]` searches the current edition of each indexed source for passages holding every term (case and spacing folded) and returns `results`, each an `address` (`source-key@hash#sec:` or `para:`) with its line range, a `score` and a one-line `context`; whole-phrase matches rank first, then score, then section before paragraph, then store order, so output is stable; `total` and `truncated` report the cut at `--limit` (default 20), and `skipped` lists sources not searched. Results are locators only: resolve one with `sources slice` before any claim check; nothing is written to the ledger. `list` shows stored sources and `MANIFEST.md` rows not yet added. No network call. |
| `flow status` | Per-stage gate results computed from the repo (`flow.yaml` stores only round, attestations, waivers and budget). Exit 1 when a gate fails. |
| `flow next` | Print the first open work order for the earliest failing gate, as JSON (`schemas/flow-order.schema.json`). Calling it again re-issues the same order. |
| `flow next --open` | List every open order of the current stage; `parallel_safe` is true only when nodes and output files are disjoint and the order is in no group. Give each concurrent order its own working copy and merge the branches. Orders that write the same file are listed under `groups` (see below). |
| `flow next --brief` | Add a compiled `brief` to the order (also with `--open`): the finding or gap row (its `source` names the CLI part it came from), the slices of the order's `anchors` from the section and code index, the first line of each active guardrail in `docs/guardrails/` whose tags match the order kind (rule table `GUARDRAIL_RULES` in `scripts/article/brief.py`), ledger entries already valid for the order's inputs, and the one verify command (`check record NAME`). It is built from the repo alone (no model, no network) and is byte-identical for the same repo state. Over the byte cap the slices become `file:start-end@hash` addresses, then the digest lines are dropped. |
| `flow handoff <order-id> --file FILE` | Record what an agent hands back at its call cap (`-` reads stdin). The JSON holds `version` `"1.0"`, `order`, `done` and `remaining` anchors (`{name, file}`), `files` touched, `ledger_keys` written and `verify` (`{check, outcome}`, outcome `pass`, `fail` or `not-run`); it names no model or host and is validated (`schemas/flow-handoff.schema.json`, which also states the output). It is stored in the order's entry in `flow.yaml`; recording again replaces it. See below. |
| `flow done <order-id>` | Run the order's named check and record a pass; takes nothing but the id. |
| `flow round open --review FILE` / `flow round close` | Turn a review file into proposed objection nodes; close the round once the gates pass. |
| `flow attest`, `flow waive` | A person records an attestation or a waiver; refused without a terminal. |
| `release` | Reserved for release planning; currently a stub. |
| `upgrade` | Plan, apply or finish an upgrade to a newer template commit. |

Orders may carry two optional fields, both computed on every `flow next`: `anchors` (omitted from the order when there are none, for example on a `state-thesis` order, which names no node, or when every anchor was reported done; present as a list, possibly empty, inside `--brief`'s `brief`) (up to six places, each a section label from the node's `anchor`, a code symbol or a `path:start-end` range written in backticks in the node text, or the lines of a validation diagnostic, with a 12-hex hash of the slice) and `max_calls` (advisory: hand back state after about that many tool calls; the host counts, nothing enforces it). `flow.yaml` may set `max_calls: {small: N, large: N}` (defaults 40 and 60; script and human orders carry none) and `brief_bytes: N` (default 6000, at least 200). Both are optional, so existing `flow.yaml` files stay valid.

Each anchor carries a `mode`: `write` when the order's `outputs` cover the anchor's file (a `#fragment` of an output is ignored, a trailing `/` covers the directory), otherwise `read`. Ready orders whose `write` anchors share a file, directly or through a chain of orders, are one group for one agent: `flow next` adds `group` (id, member `orders`, shared `files`, summed `max_calls`, merged `anchors`, and with `--brief` one combined `brief` whose `row.members` lists each member's row) and `orders` (the full members; each carries `group` and no brief of its own), and `flow next --open` adds `groups`. A shared `read` anchor never groups, and orders on disjoint files stay separate and parallel. A group holds at most `group_size` orders (`flow.yaml`, default 3, 1 turns grouping off); the rest are listed under `deferred` in `--open`, are not issued, and are offered on a later call once the group is done. Output validates against the `group` definition in `schemas/flow-order.schema.json`; `group_size` is optional in `flow.yaml`.

After `flow handoff`, `flow next` (and `--open`) rebuilds the order from the repo and the handoff: anchors listed as `done` (matched by file and name) are left out of `anchors` and of the brief, and `--brief` adds `handoffs` (the recorded handoff, sorted by order id; a group lists its members'), so a fresh agent resumes without rediscovery. The same repo state and handoff give byte-identical output. The handoff is dropped when `flow done` closes the order. The field is optional; an order without a handoff is unchanged.

Upgrading an older repo adds the ledger and the source store without touching your files: `docs/ledger/` and `.gitattributes` arrive with the template diff, a missing `docs/ledger/**` line is appended to an existing `.gitattributes`, `paper/sources/manifest.json` is created empty when `paper/sources/` exists (`sources add` fills it and reads `MANIFEST.md` without changing it), and commented examples of `max_calls`, `brief_bytes` and `group_size` are appended to `flow.yaml`. `metadata.yaml`, `theses.yaml` and the values in `flow.yaml` are never changed. `companion.yaml` is yours: `upgrade --plan` prints notice `N002` when its `exclude` list lacks `paper/sources/**` (third-party texts) or `docs/ledger/**`, and `N003` when the old untracked `.theses/claims-cache.json` still exists (its verdicts are imported into the ledger on first read; delete the file afterwards).

`--root PATH` selects a repository root explicitly. Commands default to the
current directory.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Diagnostics, drift, failed build, or another expected failure. |
| `2` | Usage error: unknown command, missing argument, or bad flag. |
| `3` | Internal error: an unexpected exception at the CLI boundary. |

`--json` writes one JSON object to stdout. Human-readable logs and diagnostics
go to stderr. A successful `status` still exits `0` when it reports a problem
(such as invalid metadata); the report is the result, not a validation gate.

## Status JSON

`python3 -m scripts.article status --json` is read-only and offline. Its shape
is validated by `schemas/status.schema.json`:

```json
{
  "schema_version": "1.0",
  "template_version": "1.2.0",
  "repo": {
    "root": "/path/to/repository",
    "branch": "master",
    "dirty": false
  },
  "metadata": {
    "valid": true,
    "drift": false
  },
  "diagnostics": {
    "errors": 0,
    "warnings": 7
  },
  "tools": {
    "python": "3.10.12",
    "pandoc": "3.1.1",
    "latexmk": "4.76",
    "git": "2.34.1",
    "pyyaml": "6.0.1"
  }
}
```

Field notes:

- `schema_version` versions the JSON shape. It changes only for a documented
  contract change.
- `template_version` identifies the template line that produced the repo. It
  can be overridden by `template_version` in `metadata.yaml`; otherwise the
  vendored template default is used.
- `repo.branch` is `null` outside git or on a detached HEAD. `repo.dirty`
  reports whether `git status --porcelain` has any entries.
- `metadata.valid` is false when `metadata.yaml` is missing or unparseable.
  `metadata.drift` is true when any generated file differs from what the
  metadata would produce.
- `diagnostics` is a summary. Use `validate --json` for the full
  `schemas/diagnostics.schema.json` records.
- `tools` contains detected versions, or `null` when a tool is absent. No
  version check is enforced by `status`.

The contract is versioned with the template: adding a required field or
changing a field's meaning requires a template major version. Optional
additions may appear in a minor version and are accepted by consumers that
ignore unknown tool keys.

## Compatibility entry points

`scripts/validate-paper.py` and `scripts/generate-metadata.py` remain as
deprecated shims for existing repositories. They accept their historical flags
and delegate to the same core; new automation should call the CLI directly.

## Upgrading to a newer template

`upgrade` brings a generated repository up to a newer commit of the template it
was generated from, using the `template.json` stamp. Unlike the other commands
it needs `git`, network access to the template when that is a URL, and
`cookiecutter` installed for the Python that runs it (`python3 -m pip install
cookiecutter`). It never merges silently.

```bash
python3 -m scripts.article upgrade --plan  [--to REF] [--json]   # default; read-only
python3 -m scripts.article upgrade --apply [--commit] [--to REF] [--json]   # new branch upgrade/<sha>
python3 -m scripts.article upgrade --finish [--regenerate] [--json]   # after resolving conflicts
```

- `--plan` writes nothing. It refuses, with a code `U001` to `U008`, when the
  stamp is missing or has no `template_commit`, the working tree is dirty or not
  a git repository, `metadata.yaml` is still schema 1 (see
  `docs/migrating-to-v2.md`), or the template or ref cannot be found.
- `--apply` renders the old and the new template with the stored answers,
  applies the difference with `git apply --3way` on a new branch, and reports
  `applied`, `conflicted` and `skipped` files. It never commits and never
  resolves a conflict. `template.json` does not change yet.
- `--apply --commit` also commits the result, conflict markers included, with a
  tracked `.upgrade-state.json`, so a fresh checkout of the branch can run
  `--finish` (which removes that file). The scheduled workflow uses it.
- `--finish` refuses while any path is unmerged or has conflict markers. It also
  refuses (`U019`) when a derived file (`CITATION.cff`, `README.md`, `CHANGES.md`,
  `paper/article.tex`, ...) differs from what `metadata.yaml` generates, because
  `make metadata` would overwrite those edits. Move them into `metadata.yaml`, or pass
  `--regenerate` to overwrite. It then runs `make metadata` and `make validate`,
  updates `template_version` and `template_commit` and stages the result for you to
  review and commit.

`make upgrade` runs `--plan`. `.github/workflows/upgrade.yml` runs it weekly and
opens a pull request; see the template's `docs/upgrading.md` ("Automatic upgrade
pull requests"). A repository generated before this command existed
installs it once with the template's `scripts/bootstrap-upgrader.py`; see the
template's `docs/upgrading.md`. The shape of the `--json` output is
`schemas/upgrade.schema.json`. Exit code `1` also covers refusals and
conflicts.
