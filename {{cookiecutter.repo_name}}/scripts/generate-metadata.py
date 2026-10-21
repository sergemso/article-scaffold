#!/usr/bin/env python3
"""Deprecated compatibility shim for the legacy metadata generator.

The implementation lives in ``scripts/article/metadata.py``. This file keeps
the historical ``--check`` output and module-level helpers that older tests
and user scripts may import, while all generation goes through the core.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

try:
    from scripts.article import metadata as _metadata
except ImportError:  # direct execution from a checkout without repo root on sys.path
    sys.path.insert(0, str(SCRIPTS_DIR))
    from article import metadata as _metadata

# Preserve the old module-level API (latex_escape, gen_* helpers, constants).
for _name in dir(_metadata):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_metadata, _name)


def _check(expected: dict[Path, str]) -> int:
    drift = _metadata.compare_outputs(REPO_ROOT, expected)
    for item in drift:
        if item.actual is None:
            print(f"ERROR: missing {item.path}", file=sys.stderr)
            continue
        print(f"drift: {item.path}", file=sys.stderr)
        diff = difflib.unified_diff(
            item.actual.splitlines(keepends=True),
            item.expected.splitlines(keepends=True),
            fromfile=f"{item.path} (on disk)",
            tofile=f"{item.path} (expected from metadata.yaml)",
        )
        sys.stderr.writelines(diff)
    if drift:
        print(
            "\nmetadata-check: generated files are out of date; run `make metadata`.",
            file=sys.stderr,
        )
        return 1
    print("metadata-check: generated files are up to date.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate derived metadata from metadata.yaml."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated files with disk and exit 1 on drift; write nothing",
    )
    args = parser.parse_args(argv)

    try:
        metadata = _metadata.load_metadata(REPO_ROOT / "metadata.yaml")
        expected = _metadata.collect_expected(REPO_ROOT, metadata)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        return _check(expected)

    for path in _metadata.write_expected(expected):
        print(f"  updated {path.relative_to(REPO_ROOT)}")

    print("\nDone. Review with `git diff` before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
