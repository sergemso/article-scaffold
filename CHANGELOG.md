# Changelog

All notable changes to the template are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). The version is stamped into every
generated repo as `template_version` in `template.json`.

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
