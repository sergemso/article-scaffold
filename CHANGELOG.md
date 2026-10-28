# Changelog

All notable changes to the template are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). The version is stamped into every
generated repo as `template_version` in `template.json`.

## [Unreleased]

### Changed

- CI uploads a single `manuscript` artifact (`manuscript.docx`, `manuscript.pdf`, `supp/*.pdf`)
  instead of `manuscript-docx`, `manuscript-pdf` and `manuscript-supp`.
  - The DOCX, PDF and supplementary builds in `reusable-build.yml` are now steps of a single
    `build` job; the `upload-*` inputs still switch each of them off.
  - `release.yml` downloads that artifact once; the Pages job publishes only the PDF and `supp/`.

## [1.5.1] - 2026-10-26

### Fixed

- Upgrading to 1.5.0 conflicted in `metadata.yaml` and the abstract of repos whose author had
  edited them, because the template removed placeholder lines next to the author's values and a
  text merge cannot tell the two apart.
  - `upgrade` no longer text-merges `metadata.yaml`; it applies versioned, exact-line
    migrations (`scripts/article/migrations.py`) that remove only what an earlier template
    shipped and never touch a value.
  - The blocks generated from `metadata.yaml` (title block, abstract, backmatter version,
    README and CHANGES blocks) are left out of the template diff; `upgrade --finish` regenerates
    them.
  - `upgrade --apply` runs with the upgrade code of the template being upgraded to, so a fix to
    the upgrade takes effect on the upgrade it ships in, not the one after.
- New test upgrades the previous release to the working tree for a repo with an edited
  `metadata.yaml` and abstract, and requires no conflicts.

### Upgrading

A repo still on 1.4.x or 1.5.0 carries the old upgrade code and conflicts once more. Install the
new code first: see "Repos on 1.5.0 or older" in `docs/upgrading.md`.

## [1.5.0] - 2026-10-26

### Added

- Artifact builds regenerate the files derived from `metadata.yaml` first:
  `scripts.article build pdf|docx|supp` (so `make pdf`, `make docx`, `make supp`), and
  `make html` / `make quick`. An invalid `metadata.yaml` stops the build; `--no-regenerate`
  skips the refresh and `--dry-run` writes nothing.
- `reusable-build.yml` regenerates in each build job, so CI artifacts match `metadata.yaml`.
- `metadata-sync.yml` opens a pull request from the branch `metadata/sync` when the
  committed derived files have drifted on the default branch, and updates it if one is open.
- `docs/metadata.md` documents the optional `metadata.yaml` keys.

### Changed

- A new repo's `metadata.yaml` no longer carries commented-out examples, the placeholder
  `abstract_note`, or the legacy `description` duplicate. The "A note on evidence" paragraph is
  generated only when `abstract_note` is set.

### Upgrading

`make upgrade` (to template 1.5.0). Existing leftovers in `metadata.yaml` are not removed by the
merge when you have edited those lines; delete them by hand. See `docs/upgrading.md`.

## [1.4.1] - 2026-10-25

### Fixed

- The DOCX build produced a near-empty document (one page) because pandoc resolves
  `\input{sections/...}` against its working directory, not `--resource-path`, so none of
  the sections were loaded. `make docx`, `make html`, `scripts.article build docx` and the
  `reusable-build.yml` DOCX job now run pandoc inside `paper/`, with paths relative to it.
- New test builds a DOCX and asserts text from an `\input` section is in it.

### Upgrading

Generated repos pick this up with `make upgrade` (to template 1.4.1); then re-run the build.

## [1.4.0] - 2026-10-25

### Changed

- Workflows reference actions by major version tag instead of a commit SHA, and move to
  the current majors: `actions/checkout@v7`, `setup-python@v7`, `upload-artifact@v7`,
  `download-artifact@v8`, `configure-pages@v6`, `upload-pages-artifact@v5`,
  `softprops/action-gh-release@v3` and `xu-cheng/texlive-action@v3`. Dependabot keeps
  moving the tag. `go-getter-checks.yml` is generated and keeps its SHA pins.
- The CI hardening tests now require a major tag (`@vN`) on every remote action and
  check each ref against the table of expected majors. The `RUN_NETWORK=1` test resolves
  tags and SHAs upstream.

## [1.3.1] - 2026-10-25

### Fixed

- `reusable-build.yml` pinned `xu-cheng/texlive-action` to a commit that does not exist
  upstream, so the PDF and supplementary jobs failed at action resolution. Both uses now
  point at the real v2 commit and pass `texlive_version` (the action's input name).
- `release.yml` pinned `actions/configure-pages`, `actions/upload-pages-artifact` and
  `softprops/action-gh-release` to SHAs that do not exist upstream; they now point at v5,
  v3 and v2.2.1.
- `make html` and the pre-2.11 `make docx` fallback no longer pass
  `--metadata=citation-style=numeric`; pandoc 3 reads that as a CSL file name.

### Added

- A network-gated test (`RUN_NETWORK=1`) that every SHA-pinned `uses:` resolves upstream.

## [1.3.0] - 2026-10-25

### Added

- Several PDFs per repository. `make supp-pdf` and `article build supp` now build every
  standalone supplementary document: `paper/supplementary.tex` (as before) and each
  `paper/supplementary/*.tex` that has a `\documentclass`. Each PDF is published next to
  its source and `paper/supplementary/*.pdf` is gitignored. `make clean` removes them.
- `reusable-build.yml` gains an `upload-supp` input (default `true`) and a `build-supp`
  job that uploads the `manuscript-supp` artifact the release workflow already expected.

### Fixed

- `validate` treats a standalone document other than `article.tex` as its own label
  namespace, so a supplementary file may reuse a label (`tab:tests`) from the main paper.
- `release.yml` no longer fails when there is no `manuscript-supp` artifact.

## [1.2.0] - 2026-10-24

### Added

- Optional `release_notes` in `metadata.yaml`: Markdown that `make metadata` prints under
  the current version heading in `CHANGES.md`. Until now the block held only the
  heading, so hand-written release notes there were overwritten by regeneration (and
  blocked `upgrade --finish` through the drift guard). Without the field the output is
  unchanged.

## [1.1.9] - 2026-10-24

### Fixed

- `upgrade --apply` (and so the weekly workflow) no longer creates a branch or opens a
  pull request when the template has a newer commit that changes none of the files
  generated for the repository, such as a changelog-only release. It reports
  `no_changes: true` and the workflow prints a notice. The stamp stays where it is, so
  the next real change is still diffed from the commit the files match.

## [1.1.8] - 2026-10-24

### Changed

- The pull request that `upgrade.yml` opens explains `U019` and `--regenerate`, so a
  reviewer who hits the drift guard knows the two ways out.

## [1.1.7] - 2026-10-24

### Added

- `upgrade --finish` refuses (`U019`) when a derived file (`CITATION.cff`, `README.md`,
  `CHANGES.md`, `paper/article.tex`, ...) differs from what `metadata.yaml` generates,
  and names the files. Regenerating would silently overwrite hand edits. Put the edits
  into `metadata.yaml`, or pass the new `--regenerate` to overwrite on purpose.

### Changed

- `docs/cli.md` no longer says a repo without the command must upgrade by hand; it points
  to `scripts/bootstrap-upgrader.py`.

## [1.1.6] - 2026-10-24

### Fixed

- The title block's `\date{...}` line separates the version label and the date with
  the LaTeX em-dash `---`, in `paper/article.tex` and in what `make metadata`
  regenerates, instead of a raw Unicode U+2014, which some PDF text extractors break
  on. A test checks both the rendered file and that `make metadata` writes it back
  unchanged.
- `article build pdf` copies its output to `paper/article.pdf` after a successful build,
  as `make pdf` does, and reports it as `published_to` in the JSON. `release` looks
  for that file, so a CLI-only build previously left it with no artifact. (This change
  was released in 1.1.6 without being listed; it was added here afterwards.)

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
