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
