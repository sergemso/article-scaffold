"""Smoke tests for the template repository itself.

These do not render the Cookiecutter template yet; the render helper arrives in
T03. Keeping one trivial test here means `make test` is meaningful from the
first bootstrap commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_floor() -> None:
    assert sys.version_info >= (3, 10), "the dev environment requires Python 3.10+"


def test_template_entry_points_exist() -> None:
    assert (ROOT / "cookiecutter.json").is_file()
    assert (ROOT / "hooks" / "post_gen_project.py").is_file()
    assert (ROOT / "{{cookiecutter.repo_name}}" / "Makefile").is_file()


def test_plan_files_exist() -> None:
    archive = ROOT / "docs" / "plans" / "archive" / "t-queue"
    assert (archive / "tasks.json").is_file()
    assert (archive / "state.json").is_file()
