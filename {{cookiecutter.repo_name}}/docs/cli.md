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
| `build pdf` | Build `paper/article.pdf`. |
| `build docx` | Build `manuscript.docx`. |
| `build <kind> --dry-run` | Print the build plan without running it. |
| `release` | Reserved for release planning; currently a stub. |
| `upgrade` | Plan, apply or finish an upgrade to a newer template commit. |

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
