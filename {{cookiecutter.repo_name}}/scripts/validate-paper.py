#!/usr/bin/env python3
r"""
validate-paper.py — local mirror of .github/workflows/validate-latex.yml.

Run with `make validate` (or directly with python3 scripts/validate-paper.py).
Exits non-zero on any error so it can be used as a pre-push gate.

Checks performed:
  1. paper/article.tex exists and is readable.
  2. Every active \input{...} in article.tex resolves to a file
     under paper/. Lines starting with % are skipped.
  3. Every \cite{key} in paper/sections/*.tex (after stripping comments)
     resolves to an entry in paper/refs.bib. Unused entries produce a
     warning but do not fail.
  4. paper/article.tex has balanced braces (after stripping comments
     and accounting for escaped \%).

No LaTeX compilation is performed — that's the build-artifacts.yml job.
The point of this script is to fail fast on cheap syntactic errors so
you don't push something that the CI will then take 5 minutes to reject.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = REPO_ROOT / "paper"
SECTIONS_DIR = PAPER_DIR / "sections"
ARTICLE_TEX = PAPER_DIR / "article.tex"
REFS_BIB = PAPER_DIR / "refs.bib"


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def check_input_targets() -> int:
    if not ARTICLE_TEX.is_file():
        _err(f"main TeX file not found: {ARTICLE_TEX.relative_to(REPO_ROOT)}")
        return 1
    content = ARTICLE_TEX.read_text(encoding="utf-8")
    inputs = []
    for line in content.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("%"):
            continue
        inputs.extend(re.findall(r"\\input\{([^}]+)\}", line))
    errors = 0
    for inp in inputs:
        candidates = [PAPER_DIR / inp, PAPER_DIR / f"{inp}.tex"]
        if not any(c.is_file() for c in candidates):
            _err(f"\\input{{{inp}}} in article.tex does not resolve to a file")
            errors += 1
        else:
            print(f"  OK: \\input{{{inp}}}")
    if errors:
        return 1
    print(f"  All {len(inputs)} active \\input targets resolved.")
    return 0


def check_cite_keys() -> int:
    if not REFS_BIB.is_file():
        _err(f"BibTeX file not found: {REFS_BIB.relative_to(REPO_ROOT)}")
        return 1
    bib = REFS_BIB.read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    print(f"  Found {len(bib_keys)} BibTeX entries.")
    if not SECTIONS_DIR.is_dir():
        _err(f"sections directory not found: {SECTIONS_DIR.relative_to(REPO_ROOT)}")
        return 1
    cited: set[str] = set()
    for fname in sorted(SECTIONS_DIR.iterdir()):
        if not fname.name.endswith(".tex"):
            continue
        text = fname.read_text(encoding="utf-8")
        text = re.sub(r"(?m)%.*$", "", text)
        for match in re.findall(r"\\cite\{([^}]+)\}", text):
            for key in match.split(","):
                cited.add(key.strip())
    print(f"  Found {len(cited)} unique \\cite keys across section files.")
    missing = cited - bib_keys
    if missing:
        _err("The following \\cite keys are missing from refs.bib:")
        for k in sorted(missing):
            print(f"    - {k}", file=sys.stderr)
        return 1
    unused = bib_keys - cited
    if unused:
        print(f"  WARNING: {len(unused)} BibTeX entries defined but never cited:")
        for k in sorted(unused):
            print(f"    - {k}")
    print("  All \\cite keys resolve.")
    return 0


def check_balanced_braces() -> int:
    if not ARTICLE_TEX.is_file():
        _err(f"file not found: {ARTICLE_TEX.relative_to(REPO_ROOT)}")
        return 1
    content = ARTICLE_TEX.read_text(encoding="utf-8")
    # Strip comments: an unescaped % to end of line.
    stripped = re.sub(r"(?<!\\)%.*$", "", content)
    opens = stripped.count("{")
    closes = stripped.count("}")
    if opens != closes:
        rel = ARTICLE_TEX.relative_to(REPO_ROOT)
        _err(f"Brace mismatch in {rel}: {opens} '{{' vs {closes} '}}'")
        return 1
    print(f"  OK: braces balanced ({opens} pairs).")
    return 0


def main() -> int:
    if not PAPER_DIR.is_dir():
        _err(f"paper/ directory not found at {PAPER_DIR.relative_to(REPO_ROOT)}")
        return 1
    checks = [
        ("input targets resolve", check_input_targets),
        ("\\cite keys exist in refs.bib", check_cite_keys),
        ("article.tex braces balanced", check_balanced_braces),
    ]
    failures = 0
    for name, fn in checks:
        print(f"\n[{name}]")
        if fn() != 0:
            failures += 1
    print()
    if failures:
        _err(f"{failures} check(s) failed.")
        return 1
    print("All validation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
