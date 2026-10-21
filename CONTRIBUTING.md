# Contributing to article-scaffold

Thank you for considering a contribution! This document describes how to
propose changes, run the test suite, and what standards we expect.

## Ways to contribute

- **Bug reports:** File an issue with a minimal reproduction case.
- **Feature requests:** Open an issue with a clear use case and rationale.
- **Pull requests:** Follow the workflow below.

## Development setup

```bash
# Create and activate the dev virtual environment
make setup

# Run the full test suite
make test

# Lint only
make lint

# Validate the agent plan
make doctor
```

The `make setup` command creates a `.venv` with all dev dependencies:
pytest, Cookiecutter, ruff, cffconvert, jsonschema, yamllint, jinja2-time.

## Running tests

```bash
# All tests
.venv/bin/python -m pytest -q

# A single test file
.venv/bin/python -m pytest tests/test_build.py -q

# With coverage
.venv/bin/python -m pytest --cov=scripts/article --cov-report=term-missing
```

## Code style

- Python: `ruff` (configured in `pyproject.toml`, line length 100).
- YAML: `yamllint` (configured in `.yamllint.yaml`).
- Shell: `shellcheck` (if installed).

Run `make lint` to check everything.

## Making a pull request

1. Fork the repository and create a feature branch.
2. Make your changes. Keep commits focused and write clear messages.
3. Run `make test` and `make lint` locally. Both must pass.
4. If you added or changed behavior, add or update tests.
5. Push your branch and open a PR against `master`.

### Commit message format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) style:

```
type(scope): brief description

Optional body explaining the change.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`.

Example:
```
feat(validate): add check for duplicate bibliography keys
```

### Changelog

User-facing changes should be noted in `CHANGES.md` under an "Unreleased"
section. The maintainer will move them to a version heading on release.

## Template changes

Changes to the template live in `{{cookiecutter.repo_name}}/`. After editing
template files:

1. Run the test suite to ensure generated repositories still pass all checks.
2. Test locally with `cookiecutter . --no-input` and build the PDF in the
   rendered project.
3. If you change the metadata schema, update `schemas/metadata.schema.json`
   and the corresponding loader in `scripts/article/metadata.py`.

## Code of conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating, you are expected to uphold this code.

## Questions?

Open a GitHub Discussion or file an issue — we're happy to help.