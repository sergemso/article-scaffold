#!/usr/bin/env python3
"""Deprecated compatibility shim for the legacy validator entry point.

The implementation lives in ``scripts/article/validate.py``. This file only
maps the old stdout/stderr conventions onto the shared diagnostics, so
existing Makefiles, CI jobs and pre-push hooks keep working.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

try:
    from scripts.article import validate_paper
except ImportError:  # direct execution from a checkout without repo root on sys.path
    sys.path.insert(0, str(SCRIPTS_DIR))
    from article import validate_paper


def main(argv: list[str] | None = None) -> int:
    del argv
    diagnostics = validate_paper(REPO_ROOT)

    for item in diagnostics.warnings:
        print(f"WARNING: {item.path}:{item.line}: {item.code}: {item.message}")

    for item in diagnostics.errors:
        print(
            f"{item.path}:{item.line}: {item.code}: {item.message}",
            file=sys.stderr,
        )

    if diagnostics.ok:
        print("  All citation keys resolve.")
        print("All validation checks passed.")
        return 0

    print(f"ERROR: {len(diagnostics.errors)} check(s) failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
