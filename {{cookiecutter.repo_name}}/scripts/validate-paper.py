#!/usr/bin/env python3
r"""
validate-paper.py — local mirror of .github/workflows/validate-latex.yml.

Run with `make validate` (or directly with python3 scripts/validate-paper.py).
Exits non-zero on any error so it can be used as a pre-push gate.

Checks performed:
  1. paper/article.tex exists and is readable.
  2. Every active \input{...}/\include{...} resolves under paper/. The include
     graph is walked recursively with a depth limit, and targets that escape
     paper/ are rejected. Commented-out occurrences are ignored.
  3. Every active citation command (\cite, \citep, \citet, \citealp,
     \citeauthor, \citeyear, \nocite, and starred forms) resolves to an entry
     in paper/refs.bib. Comma-separated key lists are supported. Duplicate
     BibTeX keys are errors; unused entries are warnings.
  4. \includegraphics targets resolve against paper/ and \graphicspath.
  5. \ref targets (and \eqref, \autoref, \pageref, \cref) have matching
     \label entries. Duplicate labels are errors; unused labels are warnings.
  6. Every paper/*.tex file has balanced braces after stripping comments and
     ignoring escaped braces such as \{ and \}.

Diagnostics are structured as `path:line: code: message`, while the command
still exits 0 on success and 1 on any failure. Warnings use `W###` codes and
are printed to stdout so CI can choose whether to treat them as fatal.

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
MAX_INCLUDE_DEPTH = 20

INPUT_RE = re.compile(r"\\(input|include)\s*\{([^}]+)\}")
CITE_RE = re.compile(
    r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}"
)
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\})+\s*)\}")
INNER_PATH_RE = re.compile(r"\{([^{}]*)\}")
INCLUDEGRAPHICS_RE = re.compile(
    r"\\includegraphics\*?(?:\[[^\]]*\])?\{([^}]+)\}"
)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
REF_RE = re.compile(
    r"\\(?:ref|eqref|autoref|pageref|cref|Cref)\*?\{([^}]+)\}"
)
GRAPHIC_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps")


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _relative(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def _diag(path: Path, line: int, code: str, message: str) -> None:
    """Print one machine-readable error without changing the CLI."""
    print(f"{_relative(path)}:{line}: {code}: {message}", file=sys.stderr)


def _warn(path: Path, line: int, code: str, message: str) -> None:
    """Print one machine-readable warning to stdout (not fatal)."""
    print(f"WARNING: {_relative(path)}:{line}: {code}: {message}")


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


def _resolve_include(target: str) -> tuple[Path | None, str | None]:
    """Resolve an include target, rejecting paths outside paper/."""
    if not target or Path(target).is_absolute():
        return None, "outside"
    paper_root = PAPER_DIR.resolve()
    candidates = [PAPER_DIR / target, PAPER_DIR / f"{target}.tex"]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file():
            if not resolved.is_relative_to(paper_root):
                return None, "outside"
            return resolved, None
    return None, "missing"


def check_input_targets() -> int:
    if not ARTICLE_TEX.is_file():
        _diag(ARTICLE_TEX, 0, "E000", "main TeX file not found")
        return 1

    errors = 0
    total = 0
    visited: set[Path] = set()

    def walk(path: Path, depth: int) -> None:
        nonlocal errors, total
        if depth > MAX_INCLUDE_DEPTH:
            _diag(path, 0, "E012", f"include depth exceeds {MAX_INCLUDE_DEPTH}")
            errors += 1
            return
        try:
            resolved_path = path.resolve()
        except OSError:
            _diag(path, 0, "E000", "could not resolve file")
            errors += 1
            return
        if resolved_path in visited:
            return
        visited.add(resolved_path)

        content = strip_comments(path.read_text(encoding="utf-8"))
        for lineno, line in enumerate(content.split("\n"), start=1):
            for match in INPUT_RE.finditer(line):
                command, target = match.group(1), match.group(2).strip()
                total += 1
                resolved, problem = _resolve_include(target)
                if problem == "outside":
                    _diag(
                        path,
                        lineno,
                        "E011",
                        f"\\{command}{{{target}}} escapes the paper directory",
                    )
                    errors += 1
                elif problem == "missing":
                    _diag(
                        path,
                        lineno,
                        "E001",
                        f"\\{command}{{{target}}} does not resolve to a file",
                    )
                    errors += 1
                else:
                    assert resolved is not None
                    print(f"  OK: \\{command}{{{target}}}")
                    walk(resolved, depth + 1)

    walk(ARTICLE_TEX, 0)
    if errors:
        return 1
    print(f"  All {total} active \\input/\\include targets resolved.")
    return 0


def check_cite_keys() -> int:
    if not REFS_BIB.is_file():
        _diag(REFS_BIB, 0, "E004", "BibTeX file not found")
        return 1
    bib = strip_comments(REFS_BIB.read_text(encoding="utf-8"))
    bib_key_lines: dict[str, list[int]] = {}
    for lineno, line in enumerate(bib.split("\n"), start=1):
        for match in BIB_KEY_RE.finditer(line):
            bib_key_lines.setdefault(match.group(1), []).append(lineno)
    if not bib_key_lines:
        _diag(REFS_BIB, 0, "E005", "no BibTeX entries found")
        return 1
    print(f"  Found {len(bib_key_lines)} BibTeX entries.")
    if not SECTIONS_DIR.is_dir():
        _diag(SECTIONS_DIR, 0, "E006", "sections directory not found")
        return 1

    errors = 0
    for key, lines in sorted(bib_key_lines.items()):
        if len(lines) > 1:
            for duplicate_line in lines[1:]:
                _diag(
                    REFS_BIB,
                    duplicate_line,
                    "E010",
                    f"duplicate BibTeX key {key!r}",
                )
                errors += 1

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

    bib_keys = set(bib_key_lines)
    missing = sorted(set(cited) - bib_keys)
    for key in missing:
        for tex, lineno in cited[key]:
            _diag(
                tex,
                lineno,
                "E002",
                f"citation key {key!r} is missing from refs.bib",
            )
            errors += 1

    if errors:
        return 1

    print(f"  Found {len(cited)} unique citation keys across TeX files.")
    unused = sorted(bib_keys - set(cited))
    for key in unused:
        _warn(
            REFS_BIB,
            bib_key_lines[key][0],
            "W002",
            f"BibTeX entry {key!r} is never cited",
        )
    print("  All citation keys resolve.")
    return 0


def _graphics_prefixes() -> list[str]:
    prefixes = [""]
    for tex in _tex_files():
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for match in GRAPHICSPATH_RE.finditer(content):
            for inner in INNER_PATH_RE.findall(match.group(1)):
                prefix = inner.strip()
                if prefix and prefix not in prefixes:
                    prefixes.append(prefix)
    return prefixes


def _resolve_graphic(target: str, prefixes: list[str]) -> Path | None:
    if not target or Path(target).is_absolute():
        return None
    names = [target]
    if not Path(target).suffix:
        names = [target + extension for extension in GRAPHIC_EXTENSIONS] + names
    paper_root = PAPER_DIR.resolve()
    for prefix in prefixes:
        for name in names:
            try:
                candidate = (PAPER_DIR / prefix / name).resolve()
            except OSError:
                continue
            if candidate.is_file() and candidate.is_relative_to(paper_root):
                return candidate
    return None


def check_graphics_paths() -> int:
    if not ARTICLE_TEX.is_file():
        _diag(ARTICLE_TEX, 0, "E000", "main TeX file not found")
        return 1
    prefixes = _graphics_prefixes()
    errors = 0
    total = 0
    for tex in _tex_files():
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for lineno, line in enumerate(content.split("\n"), start=1):
            for match in INCLUDEGRAPHICS_RE.finditer(line):
                target = match.group(1).strip()
                total += 1
                if _resolve_graphic(target, prefixes) is None:
                    _diag(
                        tex,
                        lineno,
                        "E007",
                        f"\\includegraphics{{{target}}} does not resolve to a file",
                    )
                    errors += 1
                else:
                    print(f"  OK: \\includegraphics{{{target}}}")
    if errors:
        return 1
    print(f"  All {total} active \\includegraphics targets resolved.")
    return 0


def check_references() -> int:
    if not ARTICLE_TEX.is_file():
        _diag(ARTICLE_TEX, 0, "E000", "main TeX file not found")
        return 1
    labels: dict[str, list[tuple[Path, int]]] = {}
    refs: list[tuple[str, Path, int]] = []
    for tex in _tex_files():
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for lineno, line in enumerate(content.split("\n"), start=1):
            for match in LABEL_RE.finditer(line):
                labels.setdefault(match.group(1).strip(), []).append((tex, lineno))
            for match in REF_RE.finditer(line):
                for raw_key in match.group(1).split(","):
                    key = raw_key.strip()
                    if key:
                        refs.append((key, tex, lineno))

    errors = 0
    for key, locations in sorted(labels.items()):
        if len(locations) > 1:
            for tex, lineno in locations[1:]:
                _diag(tex, lineno, "E008", f"duplicate label {key!r}")
                errors += 1

    referenced = {key for key, _, _ in refs}
    for key, tex, lineno in refs:
        if key not in labels:
            _diag(tex, lineno, "E009", f"reference {key!r} has no matching \\label")
            errors += 1

    if errors:
        return 1

    for key in sorted(set(labels) - referenced):
        tex, lineno = labels[key][0]
        _warn(tex, lineno, "W001", f"label {key!r} is never referenced")
    print("  All references resolve.")
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
        ("graphics targets resolve", check_graphics_paths),
        ("references resolve", check_references),
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
