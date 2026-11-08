"""Code index: symbol names and line ranges for supplementary Python and Rust.

Lets an agent read one function instead of a whole file. Offline and
deterministic: Python goes through the stdlib ``ast``, Rust through a
line-based scan that blanks comments and strings first. A file that cannot be
parsed is listed with its status, never fatal.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

INDEX_PATH = Path("paper") / "build" / "code-index.json"
CODE_ROOT = Path("paper") / "supplementary"
SUFFIXES = {".py": "python", ".rs": "rust"}
SKIP_DIRS = {"__pycache__", "target", "build", "node_modules", "venv", ".venv"}
HASH_LEN = 12
RERUN = "run `python3 -m scripts.article index`"


class CodeIndexError(Exception):
    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.extra = extra


def code_files(root: Path) -> list[Path]:
    base = root / CODE_ROOT
    if not base.is_dir():
        return []
    found = []
    for path in base.rglob("*"):
        rel = path.relative_to(base).parts
        if path.suffix in SUFFIXES and path.is_file():
            if not any(p in SKIP_DIRS or p.startswith(".") for p in rel[:-1]):
                found.append(path)
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def _lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def slice_hash(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:HASH_LEN]


def _symbol(name: str, kind: str, file: str, start: int, end: int, lines: list[str]) -> dict:
    return {
        "name": name,
        "kind": kind,
        "file": file,
        "lines": [start, end],
        "hash": slice_hash(lines[start - 1 : end]),
    }


# --- Python -----------------------------------------------------------------


def _python_symbols(file: str, lines: list[str], tree: ast.Module) -> list[dict]:
    out: list[dict] = []

    def visit(body: list[ast.stmt], prefix: str, in_class: bool) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                name, kind = prefix + node.name, "class"
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                kind = "test" if node.name.startswith("test") else (
                    "method" if in_class else "function"
                )
            else:
                continue
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            out.append(_symbol(name, kind, file, start, node.end_lineno or node.lineno, lines))
            if isinstance(node, ast.ClassDef):
                visit(node.body, name + ".", True)

    visit(tree.body, "", False)
    return out


# --- Rust -------------------------------------------------------------------


def _blank(text: str) -> str:
    """Comments and string or char contents replaced by spaces; newlines kept."""
    out: list[str] = []
    i, n = 0, len(text)

    def blank(chunk: str) -> str:
        return "".join(c if c == "\n" else " " for c in chunk)

    while i < n:
        c = text[i]
        two = text[i : i + 2]
        if two == "//":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(blank(text[i:j]))
            i = j
        elif two == "/*":
            depth, j = 1, i + 2
            while j < n and depth:
                if text[j : j + 2] == "/*":
                    depth, j = depth + 1, j + 2
                elif text[j : j + 2] == "*/":
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            out.append(blank(text[i:j]))
            i = j
        elif c == "r" and re.match(r'r#*"', text[i:]) and (i == 0 or not text[i - 1].isalnum()):
            hashes = len(re.match(r"r(#*)", text[i:]).group(1))  # type: ignore[union-attr]
            close = '"' + "#" * hashes
            j = text.find(close, i + 2 + hashes)
            j = n if j < 0 else j + len(close)
            out.append('r"' + blank(text[i + 2 : j - 1]) + '"' if j > i + 3 else text[i:j])
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            j = min(j, n - 1)
            out.append('"' + blank(text[i + 1 : j]) + '"')
            i = j + 1
        elif c == "'":
            m = re.match(r"'(?:\\.[^']*|[^\\'])'", text[i:])
            if m:  # char literal; otherwise a lifetime
                out.append("' '")
                i += m.end()
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


_VIS = r"(?:pub(?:\s*\([^)]*\))?\s+)?"
FN_RE = re.compile(
    rf"^{_VIS}(?:(?:default|const|async|unsafe)\s+)*(?:extern(?:\s+\"\s*\")?\s+)?fn\s+(?:r#)?(\w+)"
)
TYPE_RE = re.compile(rf"^{_VIS}(?:unsafe\s+)?(struct|enum|union|trait|mod)\s+(?:r#)?(\w+)")
IMPL_RE = re.compile(r"^(?:default\s+)?(?:unsafe\s+)?impl\b")
ATTR_RE = re.compile(r"#!?\[")


class _Scan:
    def __init__(self, file: str, source: list[str], blank: str) -> None:
        self.file, self.source, self.text = file, source, blank
        self.starts = [0]
        for line in blank.split("\n"):
            self.starts.append(self.starts[-1] + len(line) + 1)
        self.out: list[dict] = []
        self.broken = False

    def line_of(self, offset: int) -> int:
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def header_end(self, offset: int) -> tuple[int, str]:
        """Offset of the first top-level ``{`` or ``;`` after *offset*, and which."""
        depth = 0
        for i in range(offset, len(self.text)):
            c = self.text[i]
            if c in "([":
                depth += 1
            elif c in ")]":
                depth -= 1
            elif depth <= 0 and c in "{;":
                return i, c
        return -1, ""

    def match_brace(self, offset: int) -> int:
        depth = 0
        for i in range(offset, len(self.text)):
            c = self.text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def scan(self, lo: int, hi: int, prefix: str, container: str) -> None:
        """Items in text[lo:hi] (a module, impl or trait body)."""
        pos, attrs_start, attrs = lo, None, ""
        while pos < hi:
            if self.text[pos].isspace():
                pos += 1
                continue
            if ATTR_RE.match(self.text, pos):
                depth, i = 0, self.text.index("[", pos)
                while i < hi:
                    depth += self.text[i] == "["
                    depth -= self.text[i] == "]"
                    if depth == 0:
                        break
                    i += 1
                if i >= hi:
                    self.broken = True
                    return
                if attrs_start is None:
                    attrs_start = self.line_of(pos)
                attrs += self.text[pos : i + 1]
                pos = i + 1
                continue
            end = self.item(pos, hi, prefix, container, attrs_start, attrs)
            attrs_start, attrs = None, ""
            if end is not None:
                pos = end + 1
                continue
            newline = self.text.find("\n", pos, hi)
            newline = hi if newline < 0 else newline
            brace = self.text.find("{", pos, newline)
            if brace >= 0:
                close = self.match_brace(brace)
                if close < 0 or close >= hi:
                    self.broken = True
                    return
                pos = close + 1
            else:
                pos = newline + 1

    def item(self, offset, hi, prefix, container, attrs_start, attrs):
        """Record the item at *offset*; return the offset of its last character, or None."""
        newline = self.text.find("\n", offset)
        stripped = self.text[offset : len(self.text) if newline < 0 else newline]
        fn = FN_RE.match(stripped)
        typ = TYPE_RE.match(stripped)
        imp = IMPL_RE.match(stripped)
        if not (fn or typ or imp):
            return None
        stop, which = self.header_end(offset)
        end = -1
        if stop >= 0 and stop < hi:
            end = stop if which == ";" else self.match_brace(stop)
        if end < 0 or end >= hi:
            self.broken = True
            return hi - 1
        start = attrs_start if attrs_start else self.line_of(offset)
        last = self.line_of(end)
        if fn:
            is_test = bool(re.search(r"\btest\b", attrs))
            in_type = container in ("impl", "trait")
            kind = "test" if is_test else ("method" if in_type else "function")
            name = prefix + fn.group(1)
            self.out.append(_symbol(name, kind, self.file, start, last, self.source))
        elif typ:
            word, ident = typ.group(1), typ.group(2)
            name = prefix + ident
            self.out.append(_symbol(name, word, self.file, start, last, self.source))
            if word in ("mod", "trait") and which == "{":
                self.scan(stop + 1, end, name + "::", "mod" if word == "mod" else "trait")
        else:
            label = self.impl_label(self.text[offset:stop])
            self.out.append(
                _symbol(prefix + "impl " + label, "impl", self.file, start, last, self.source)
            )
            if which == "{":
                self.scan(stop + 1, end, prefix + label + "::", "impl")
        return end

    @staticmethod
    def impl_label(header: str) -> str:
        text = re.sub(r"\s+", " ", header).strip()
        text = re.sub(r"^(?:default )?(?:unsafe )?impl\b\s*", "", text)
        if text.startswith("<"):  # impl generics
            depth = 0
            for i, c in enumerate(text):
                depth += c == "<"
                depth -= c == ">" and text[i - 1] != "-"
                if depth == 0:
                    text = text[i + 1 :].strip()
                    break
        text = re.split(r"\swhere\b", text, maxsplit=1)[0].strip()
        parts, depth = [], 0
        for i, c in enumerate(text):
            if c == "<":
                depth += 1
            elif c == ">" and text[i - 1] != "-":
                depth -= 1
            elif depth == 0 and text[i : i + 5] == " for ":
                parts = [text[:i], text[i + 5 :]]
                break
        trait, target = (parts[0], parts[1]) if parts else ("", text)
        target = _strip_generics(target.lstrip("!").strip())
        return f"{trait.strip()} for {target}" if trait else target


def _strip_generics(text: str) -> str:
    out, depth = [], 0
    for i, c in enumerate(text):
        if c == "<":
            depth += 1
        elif c == ">" and text[i - 1] != "-":
            depth -= 1
        elif depth == 0:
            out.append(c)
    return "".join(out).strip()


def _rust_symbols(file: str, lines: list[str], text: str) -> tuple[list[dict], bool]:
    scan = _Scan(file, lines, _blank(text.replace("\r\n", "\n").replace("\r", "\n")))
    scan.scan(0, len(scan.text), "", "mod")
    return scan.out, scan.broken


# --- Index ------------------------------------------------------------------


def index_file(root: Path, path: Path) -> tuple[dict, list[dict]]:
    """The file entry and its symbols; failures become a status, never an exception."""
    rel = path.relative_to(root).as_posix()
    language = SUFFIXES[path.suffix]
    entry = {"file": rel, "language": language, "lines": 0, "status": "ok"}
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return {**entry, "status": "unreadable", "error": str(exc)}, []
    lines = _lines(text)
    entry["lines"] = len(lines)
    if language == "python":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError) as exc:
            where = f" (line {exc.lineno})" if getattr(exc, "lineno", None) else ""
            return {**entry, "status": "syntax-error", "error": f"{exc.args[0]}{where}"}, []
        return entry, _python_symbols(rel, lines, tree)
    symbols, broken = _rust_symbols(rel, lines, text)
    if broken:
        entry.update(status="syntax-error", error="unbalanced braces or unterminated item")
    return entry, symbols


def build_index(root: Path) -> dict:
    files, symbols = [], []
    for path in code_files(root):
        entry, found = index_file(root, path)
        files.append(entry)
        symbols += found
    symbols.sort(key=lambda s: (s["file"], s["lines"][0], s["name"]))
    return {"version": 1, "files": files, "symbols": symbols}


def write_index(root: Path) -> dict | None:
    """Write the code index; None when there is no code and no earlier index."""
    target = root / INDEX_PATH
    if not code_files(root) and not target.is_file():
        return None
    index = build_index(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def check_index(root: Path) -> list[str]:
    """Reasons the code index is stale; empty when fresh or when there is no code."""
    files = code_files(root)
    target = root / INDEX_PATH
    if not target.is_file():
        if not files:
            return []
        return [f"{INDEX_PATH.as_posix()} is missing; run `python3 -m scripts.article index`"]
    try:
        listed = {f["file"] for f in json.loads(target.read_text(encoding="utf-8"))["files"]}
    except (ValueError, KeyError, TypeError):
        return [f"{INDEX_PATH.as_posix()} is unreadable; run `python3 -m scripts.article index`"]
    built = target.stat().st_mtime_ns
    reasons = []
    current = {p.relative_to(root).as_posix() for p in files}
    for path in files:
        rel = path.relative_to(root).as_posix()
        if rel not in listed:
            reasons.append(f"{rel} is not in {INDEX_PATH.as_posix()}; {RERUN}")
        elif path.stat().st_mtime_ns > built:
            reasons.append(f"{rel} is newer than {INDEX_PATH.as_posix()}; {RERUN}")
    for rel in sorted(listed - current):
        reasons.append(f"{rel} was removed since {INDEX_PATH.as_posix()} was built; {RERUN}")
    return reasons


def slice_symbol(root: Path, name: str, file: str | None = None) -> dict:
    """The lines of one symbol. Exact qualified name first, then the last name part."""
    target = root / INDEX_PATH
    if not target.is_file():
        raise CodeIndexError(f"{INDEX_PATH.as_posix()} is missing; {RERUN}")
    symbols = json.loads(target.read_text(encoding="utf-8"))["symbols"]
    if file:
        symbols = [s for s in symbols if s["file"] == file]
    found = [s for s in symbols if s["name"] == name]
    if not found:
        found = [s for s in symbols if re.split(r"\.|::", s["name"])[-1] == name]
    if not found:
        raise CodeIndexError(f"no symbol named {name!r}", candidates=[])
    if len(found) > 1:
        raise CodeIndexError(
            f"{name!r} is ambiguous; use a qualified name or --file",
            candidates=[{k: s[k] for k in ("name", "kind", "file", "lines")} for s in found],
        )
    symbol = found[0]
    path = root / symbol["file"]
    lines = _lines(path.read_text(encoding="utf-8")) if path.is_file() else []
    start, end = symbol["lines"]
    chunk = lines[start - 1 : end]
    if len(chunk) != end - start + 1 or slice_hash(chunk) != symbol["hash"]:
        raise CodeIndexError(
            f"{symbol['file']} changed since {INDEX_PATH.as_posix()} was built; "
            "run `python3 -m scripts.article index`"
        )
    return {**symbol, "text": "\n".join(chunk)}
