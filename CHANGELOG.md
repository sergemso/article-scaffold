# Changelog

All notable changes to the template are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). The version is stamped into every
generated repo as `template_version` in `template.json`.

## [1.1.6] - 2026-10-24

### Fixed

- The title block's `\date{...}` line separates the version label and the date with
  the LaTeX em-dash `---`, in `paper/article.tex` and in what `make metadata`
  regenerates, instead of a raw Unicode U+2014, which some PDF text extractors break
  on. A test checks both the rendered file and that `make metadata` writes it back
  unchanged.

## [1.1.5] - 2026-10-24

### Fixed

- `make metadata` and `metadata-check` find the abstract and backmatter sections by
  name (`NN_abstract.tex`, `NN_backmatter.tex`) instead of by the template's numbers.
  A repo whose sections were renumbered failed with `required file is missing:
  paper/sections/08_backmatter.tex`, which also stopped `upgrade --finish`.

## [1.1.4] - 2026-10-24

### Fixed

- The generated `validate-latex.yml` installs PyYAML before running the validator.
  It imported `yaml` without installing it, so the "Validate LaTeX" check failed with
  `ModuleNotFoundError` in every generated repo the first time it ran (any push or PR
  touching `paper/` or `scripts/`). A new test runs the validator with only PyYAML
  importable.

## [1.1.3] - 2026-10-24

### Changed

- `docs/upgrading.md`: step-by-step setup for the optional `UPGRADE_TOKEN` secret,
  with the permissions it needs (Contents, Pull requests and Workflows, all write),
  how to check it and what happens when it expires.

### Fixed

- The `UPGRADE_TOKEN` notes in the docs and the workflow header said Workflows takes
  "read and write"; it is write-only. They also said PRs opened with the default
  token get no checks; they are held for approval.

## [1.1.2] - 2026-10-24

### Fixed

- `upgrade` resolves `--to` by exact ref name (branch, then tag) and an annotated tag
  to its commit, instead of the first ref ending in the name.
- The scratch repository that diffs the two renders ignores the user's git config
  (signing, hooks, global ignores) and fails loudly instead of reporting "no changes".
- File names with non-ASCII characters or spaces are handled (`-z` parsing).
- A relative template path in `template.json` works for `--apply`, not only `--plan`.
- A failed `--apply` is rolled back to the starting branch; no half-applied branch.
- Only the root `template.json` is excluded from the renders, not one at any depth.
- A `template.json` whose `context` is not an object is refused (`U002`), not a crash.
- `--apply` on an up-to-date repo says "already up to date".
- The weekly workflow passes the planned commit to `--apply --to`, and uses the
  optional `UPGRADE_TOKEN` secret so it can push changes to workflow files.

## [1.1.1] - 2026-10-24

### Fixed

- `docs/upgrading.md`: the bootstrap recipe now removes the downloaded script and
  commits the installed command before `upgrade --plan`, which refuses a dirty tree.

## [1.1.0] - 2026-10-24

### Added

- `article upgrade` (`--plan`, `--apply`, `--finish`): bring a generated repo up to
  a newer template by rendering the old and new template with the stored answers
  and applying the difference on a branch `upgrade/<sha>`. `--to REF` selects a
  branch, tag or commit. JSON contract in `schemas/upgrade.schema.json`.
- A weekly `upgrade.yml` workflow in generated repos that opens an upgrade pull
  request when the template has a newer commit.
- `scripts/bootstrap-upgrader.py`: a one-file script that installs the upgrade
  command into a repo generated before it existed.
- `docs/upgrading.md`: the upgrade procedure, its limits and a manual fallback.

### Fixed

- The chosen default branch is written into the branch filters of generated
  workflows.

## [1.0.0]

Initial release: the cookiecutter template with the `scripts/article` CLI,
v2 authors/affiliations metadata, reproducible builds, hardened CI, release
planning and the empirical analysis pipeline. See `docs/improvement-plan.md`.
