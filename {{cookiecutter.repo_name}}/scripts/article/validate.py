"""Structural validation for a rendered article repository."""

from __future__ import annotations

import re
from pathlib import Path

from .build import is_standalone_tex
from .diagnostics import Diagnostics
from .latex import count_unescaped, strip_comments

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


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _tex_files(paper_dir: Path) -> list[Path]:
    return sorted(paper_dir.rglob("*.tex"))


def _resolve_include(
    paper_dir: Path, target: str
) -> tuple[Path | None, str | None]:
    """Resolve an include target, rejecting paths outside paper/."""
    if not target or Path(target).is_absolute():
        return None, "outside"
    paper_root = paper_dir.resolve()
    candidates = [paper_dir / target, paper_dir / f"{target}.tex"]
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


def _check_input_targets(root: Path, paper_dir: Path, diagnostics: Diagnostics) -> None:
    article = paper_dir / "article.tex"
    if not article.is_file():
        diagnostics.error(_relative(root, article), 0, "E000", "main TeX file not found")
        return

    visited: set[Path] = set()

    def walk(path: Path, depth: int) -> None:
        if depth > MAX_INCLUDE_DEPTH:
            diagnostics.error(
                _relative(root, path),
                0,
                "E012",
                f"include depth exceeds {MAX_INCLUDE_DEPTH}",
            )
            return
        try:
            resolved_path = path.resolve()
        except OSError:
            diagnostics.error(
                _relative(root, path), 0, "E000", "could not resolve file"
            )
            return
        if resolved_path in visited:
            return
        visited.add(resolved_path)
        content = strip_comments(path.read_text(encoding="utf-8"))
        for line_number, line in enumerate(content.split("\n"), start=1):
            for match in INPUT_RE.finditer(line):
                command, target = match.group(1), match.group(2).strip()
                resolved, problem = _resolve_include(paper_dir, target)
                if problem == "outside":
                    diagnostics.error(
                        _relative(root, path),
                        line_number,
                        "E011",
                        "\\" + command + "{" + target + "} escapes the paper directory",
                    )
                elif problem == "missing":
                    diagnostics.error(
                        _relative(root, path),
                        line_number,
                        "E001",
                        "\\" + command + "{" + target + "} does not resolve to a file",
                    )
                elif resolved is not None:
                    walk(resolved, depth + 1)

    walk(article, 0)


def _check_cite_keys(root: Path, paper_dir: Path, diagnostics: Diagnostics) -> None:
    refs_bib = paper_dir / "refs.bib"
    if not refs_bib.is_file():
        diagnostics.error(_relative(root, refs_bib), 0, "E004", "BibTeX file not found")
        return
    bib = strip_comments(refs_bib.read_text(encoding="utf-8"))
    bib_key_lines: dict[str, list[int]] = {}
    for line_number, line in enumerate(bib.split("\n"), start=1):
        for match in BIB_KEY_RE.finditer(line):
            bib_key_lines.setdefault(match.group(1), []).append(line_number)
    if not bib_key_lines:
        diagnostics.error(_relative(root, refs_bib), 0, "E005", "no BibTeX entries found")
        return
    if not (paper_dir / "sections").is_dir():
        diagnostics.error(
            _relative(root, paper_dir / "sections"),
            0,
            "E006",
            "sections directory not found",
        )
        return

    for key, lines in sorted(bib_key_lines.items()):
        if len(lines) > 1:
            for duplicate_line in lines[1:]:
                diagnostics.error(
                    _relative(root, refs_bib),
                    duplicate_line,
                    "E010",
                    f"duplicate BibTeX key {key!r}",
                )

    cited: dict[str, list[tuple[Path, int]]] = {}
    for tex in _tex_files(paper_dir):
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for line_number, line in enumerate(content.split("\n"), start=1):
            for match in CITE_RE.finditer(line):
                for raw_key in match.group(1).split(","):
                    key = raw_key.strip()
                    if not key or key == "*":
                        continue
                    cited.setdefault(key, []).append((tex, line_number))

    bib_keys = set(bib_key_lines)
    for key in sorted(set(cited) - bib_keys):
        for tex, line_number in cited[key]:
            diagnostics.error(
                _relative(root, tex),
                line_number,
                "E002",
                f"citation key {key!r} is missing from refs.bib",
            )

    for key in sorted(bib_keys - set(cited)):
        diagnostics.warning(
            _relative(root, refs_bib),
            bib_key_lines[key][0],
            "W002",
            f"BibTeX entry {key!r} is never cited",
        )


def _graphics_prefixes(paper_dir: Path) -> list[str]:
    prefixes = [""]
    for tex in _tex_files(paper_dir):
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for match in GRAPHICSPATH_RE.finditer(content):
            for inner in INNER_PATH_RE.findall(match.group(1)):
                prefix = inner.strip()
                if prefix and prefix not in prefixes:
                    prefixes.append(prefix)
    return prefixes


def _resolve_graphic(paper_dir: Path, target: str, prefixes: list[str]) -> Path | None:
    if not target or Path(target).is_absolute():
        return None
    names = [target]
    if not Path(target).suffix:
        names = [target + extension for extension in GRAPHIC_EXTENSIONS] + names
    paper_root = paper_dir.resolve()
    for prefix in prefixes:
        for name in names:
            try:
                candidate = (paper_dir / prefix / name).resolve()
            except OSError:
                continue
            if candidate.is_file() and candidate.is_relative_to(paper_root):
                return candidate
    return None


def _check_graphics(root: Path, paper_dir: Path, diagnostics: Diagnostics) -> None:
    article = paper_dir / "article.tex"
    if not article.is_file():
        diagnostics.error(_relative(root, article), 0, "E000", "main TeX file not found")
        return
    prefixes = _graphics_prefixes(paper_dir)
    for tex in _tex_files(paper_dir):
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for line_number, line in enumerate(content.split("\n"), start=1):
            for match in INCLUDEGRAPHICS_RE.finditer(line):
                target = match.group(1).strip()
                if _resolve_graphic(paper_dir, target, prefixes) is None:
                    diagnostics.error(
                        _relative(root, tex),
                        line_number,
                        "E007",
                        "\\includegraphics{" + target + "} does not resolve to a file",
                    )


def _check_references(root: Path, paper_dir: Path, diagnostics: Diagnostics) -> None:
    article = paper_dir / "article.tex"
    if not article.is_file():
        diagnostics.error(_relative(root, article), 0, "E000", "main TeX file not found")
        return
    # Standalone documents other than article.tex (supplementary PDFs) are
    # compiled on their own, so their labels live in a separate namespace.
    scopes: dict[Path, list[Path]] = {article: []}
    for tex in _tex_files(paper_dir):
        if tex != article and is_standalone_tex(tex):
            scopes[tex] = [tex]
        else:
            scopes[article].append(tex)
    for files in scopes.values():
        _check_scope_references(root, files, diagnostics)


def _check_scope_references(root: Path, files: list[Path], diagnostics: Diagnostics) -> None:
    labels: dict[str, list[tuple[Path, int]]] = {}
    refs: list[tuple[str, Path, int]] = []
    for tex in files:
        content = strip_comments(tex.read_text(encoding="utf-8"))
        for line_number, line in enumerate(content.split("\n"), start=1):
            for match in LABEL_RE.finditer(line):
                labels.setdefault(match.group(1).strip(), []).append((tex, line_number))
            for match in REF_RE.finditer(line):
                for raw_key in match.group(1).split(","):
                    key = raw_key.strip()
                    if key:
                        refs.append((key, tex, line_number))

    for key, locations in sorted(labels.items()):
        if len(locations) > 1:
            for tex, line_number in locations[1:]:
                diagnostics.error(
                    _relative(root, tex),
                    line_number,
                    "E008",
                    f"duplicate label {key!r}",
                )

    referenced = {key for key, _, _ in refs}
    for key, tex, line_number in refs:
        if key not in labels:
            diagnostics.error(
                _relative(root, tex),
                line_number,
                "E009",
                f"reference {key!r} has no matching \\label",
            )

    for key in sorted(set(labels) - referenced):
        tex, line_number = labels[key][0]
        diagnostics.warning(
            _relative(root, tex),
            line_number,
            "W001",
            f"label {key!r} is never referenced",
        )


def _check_balanced_braces(
    root: Path, paper_dir: Path, diagnostics: Diagnostics
) -> None:
    article = paper_dir / "article.tex"
    if not article.is_file():
        diagnostics.error(_relative(root, article), 0, "E000", "main TeX file not found")
        return
    for tex in _tex_files(paper_dir):
        content = strip_comments(tex.read_text(encoding="utf-8"))
        opens = count_unescaped(content, "{")
        closes = count_unescaped(content, "}")
        if opens != closes:
            diagnostics.error(
                _relative(root, tex),
                1,
                "E003",
                "brace mismatch: "
                + str(opens)
                + " '{' vs "
                + str(closes)
                + " '}'",
            )


def validate_paper(root: Path) -> Diagnostics:
    """Validate a repository rooted at *root* and return all diagnostics."""
    diagnostics = Diagnostics()
    paper_dir = root / "paper"
    if not paper_dir.is_dir():
        diagnostics.error(_relative(root, paper_dir), 0, "E000", "paper/ directory not found")
        return diagnostics
    _check_input_targets(root, paper_dir, diagnostics)
    _check_cite_keys(root, paper_dir, diagnostics)
    _check_graphics(root, paper_dir, diagnostics)
    _check_references(root, paper_dir, diagnostics)
    _check_balanced_braces(root, paper_dir, diagnostics)
    return diagnostics
