# Development setup

This repository is a Cookiecutter template, not a Python package that users
install. The dev environment exists only to run the template's tests and
linters. Generated article repositories keep their own small runtime: Python
3.10+ standard library plus PyYAML.

## Prerequisites

- Python 3.10 or newer
- `git` and `make`
- Optional: `shellcheck`, `yamllint`, `latexmk`/TeX Live, `pandoc`

## First run

```bash
make setup     # creates .venv and installs the [dev] extra
make test      # runs pytest
make lint      # ruff + optional shellcheck/yamllint
```

`make setup` is the only step that needs the network. After it, tests and
validation run offline.

## Why `packages = []`

`pyproject.toml` deliberately sets `[tool.setuptools] packages = []`. The
template tree is Jinja, not importable Python, so an editable install must not
try to package `{{cookiecutter.repo_name}}/`. The install is only a convenient
way to get pytest, Cookiecutter, cffconvert, jsonschema, and ruff into one
virtual environment.

## Cookiecutter version

`pyproject.toml` allows `cookiecutter>=2.6` for development, while the bootstrap
workflow pins `cookiecutter==2.7.1` so a CI render is reproducible. The suite is
run against 2.7.1; a newer release is untested until the pin is bumped.

## Running a single test

```bash
.venv/bin/python -m pytest tests/test_smoke.py -q
```

## Generated repositories

Do not add pytest, Cookiecutter, or cffconvert to a generated repo's runtime
dependencies. Those tools belong to template development; the generated repo
must remain buildable with TeX + Python + PyYAML.
