#!/usr/bin/env python3
r"""
validate-paper.py — local mirror of .github/workflows/validate-latex.yml.

Run with `make validate` (or directly with python3 scripts/validate-paper.py).
Exits non-zero on any error so it can be used as a pre-push gate.

Checks performed:
  1. paper/article.tex exists and is readable.
  2. Every active \input{...}/\include{...} in any paper/*.tex file resolves
     to a file under paper/. Commented-out occurrences are ignored, including
     inline comments and escaped percent signs.
  3. Every active citation command (\cite, \citep, \citet, \citealp,
     \citeauthor, \citeyear, \nocite, and starred forms) resolves to an entry
     in paper/refs.bib. Comma-separated key lists are supported. Unused
     entries produce a warning but do not fail.
  4. Every paper/*.tex file has balanced braces after stripping comments and
     ignoring escaped braces such as \{ and \}.

Diagnostics are structured as `path:line: code: message`, while the command
still exits 0 on success and 1 on any failure.

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

INPUT_RE = re.compile(r"\\(input|include)\s*\{([^}]+)\}")
CITE_RE = re.compile(
    r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}"
)
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _diag(path: Path, line: int, code: str, message: str) -> None:
    """Print one machine-readable diagnostic without changing the CLI."""
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        rel = path
    print(f"{rel}:{line}: {code}: {message}", file=sys.stderr)


def _strip_comment_from_line(line: str) -> str:
    """Remove a TeX comment, respecting an odd number of preceding backslashes."""
    out: list[str] = []
    for char in line:
        if char == "%":
            backslashes = 0
            for previous in reversed(out):
                if previous == "\\":
                    backslashes += 1
                else:
                    break
            if backslashes % 2 == 0:
                break
        out.append(char)
    return "".join(out)


def strip_comments(text: str) -> str:
    """Strip comments line by line while preserving line numbers."""
    return "\n".join(_strip_comment_from_line(line) for line in text.split("\n"))


def _tex_files() -> list[Path]:
    return sorted(PAPER_DIR.rglob("*.tex"))


def _count_unescaped(text: str, char: str) -> int:
    """Count `char` occurrences that are not escaped by a backslash."""
    count = 0
    backslashes = 0
    for current in text:
        if current == "\\":
            backslashes += 1
            continue
        if current == char and backslashes % 2 == 0:
            count += 1
        backslashes = 0
    return count


def check_input_targets() -> int:
    if not ARTICLE_TEX.is_file():
        _diag(ARTICLE_TEX, 0, "E000", "main TeX file not found")
        return 1
    errors = 0
    total = 0
    for tex in _tex_files():
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for lineno, line in enumerate(content.split("\n"), start=1):
            for match in INPUT_RE.finditer(line):
                command, target = match.group(1), match.group(2).strip()
                total += 1
                candidates = [PAPER_DIR / target, PAPER_DIR / f"{target}.tex"]
                if not any(candidate.is_file() for candidate in candidates):
                    _diag(
                        tex,
                        lineno,
                        "E001",
                        f"\\{command}{{{target}}} does not resolve to a file",
                    )
                    errors += 1
                else:
                    print(f"  OK: \\{command}{{{target}}}")
    if errors:
        return 1
    print(f"  All {total} active \\input/\\include targets resolved.")
    return 0


def check_cite_keys() -> int:
    if not REFS_BIB.is_file():
        _diag(REFS_BIB, 0, "E004", "BibTeX file not found")
        return 1
    bib = strip_comments(REFS_BIB.read_text(encoding="utf-8"))
    bib_keys = set(BIB_KEY_RE.findall(bib))
    if not bib_keys:
        _diag(REFS_BIB, 0, "E005", "no BibTeX entries found")
        return 1
    print(f"  Found {len(bib_keys)} BibTeX entries.")
    if not SECTIONS_DIR.is_dir():
        _diag(SECTIONS_DIR, 0, "E006", "sections directory not found")
        return 1

    cited: dict[str, list[tuple[Path, int]]] = {}
    for tex in _tex_files():
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for lineno, line in enumerate(content.split("\n"), start=1):
            for match in CITE_RE.finditer(line):
                for raw_key in match.group(1).split(","):
                    key = raw_key.strip()
                    if not key or key == "*":
                        continue
                    cited.setdefault(key, []).append((tex, lineno))

    missing = sorted(set(cited) - bib_keys)
    if missing:
        for key in missing:
            for tex, lineno in cited[key]:
                _diag(
                    tex,
                    lineno,
                    "E002",
                    f"citation key {key!r} is missing from refs.bib",
                )
        return 1

    print(f"  Found {len(cited)} unique citation keys across TeX files.")
    unused = sorted(bib_keys - set(cited))
    if unused:
        print(f"  WARNING: {len(unused)} BibTeX entries defined but never cited:")
        for key in unused:
            print(f"    - {key}")
    print("  All citation keys resolve.")
    return 0


def check_balanced_braces() -> int:
    if not ARTICLE_TEX.is_file():
        _diag(ARTICLE_TEX, 0, "E000", "main TeX file not found")
        return 1
    errors = 0
    tex_files = _tex_files()
    for tex in tex_files:
        content = strip_comments(tex.read_text(encoding="utf-8"))
        opens = _count_unescaped(content, "{")
        closes = _count_unescaped(content, "}")
        if opens != closes:
            _diag(
                tex,
                1,
                "E003",
                f"brace mismatch: {opens} '{{' vs {closes} '}}'",
            )
            errors += 1
    if errors:
        return 1
    print(f"  OK: braces balanced in {len(tex_files)} TeX files.")
    return 0


def main() -> int:
    if not PAPER_DIR.is_dir():
        _diag(PAPER_DIR, 0, "E000", "paper/ directory not found")
        return 1
    checks = [
        ("input targets resolve", check_input_targets),
        ("citation keys exist in refs.bib", check_cite_keys),
        ("TeX braces balanced", check_balanced_braces),
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
