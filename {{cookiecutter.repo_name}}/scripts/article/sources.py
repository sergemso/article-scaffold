"""Source store (decision 0080): add, normalize, index, slice and diff third-party sources.

Layout under ``paper/sources/``::

    manifest.json                       entries (schemas/sources-manifest.schema.json)
    <key>/<raw hash>/raw.<ext>          the file as added; older hashes stay
    <key>/<raw hash>/normalized.txt     canonical text, committed, not regenerated
    <key>/<raw hash>/locators.json      locator index derived from the text

Everything is local: no network, and the only program ever run is ``pdftotext`` by its
fixed name (never a command from a repo file). ``MANIFEST.md`` is read, never written.
An address is ``source-key@hash#locator`` where ``hash`` is a prefix of the normalized
text hash (see ``address.py``).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from . import address

SOURCES_DIR = Path("paper") / "sources"
MANIFEST_JSON = "manifest.json"
LEGACY_MANIFEST = "MANIFEST.md"
SCHEMA_VERSION = "1.0"
INDEX_VERSION = "1"
MAX_SLICE_LINES = 80
MAX_SLICE_BYTES = 8000
DEFAULT_WINDOW = 2
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPES = {
    ".txt": "text/plain",
    ".md": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
}


class SourcesError(ValueError):
    """A request the store refuses; ``extra`` carries structured detail for the JSON output."""

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.extra = extra


# ------------------------------------------------------------------- helpers


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _check_key(key: str) -> str:
    if not _KEY.match(key):
        raise SourcesError(f"invalid source key {key!r}: letters, digits, '.', '_' and '-' only")
    return key


def store_dir(root: Path, key: str, raw_hash: str) -> Path:
    return root / SOURCES_DIR / _check_key(key) / raw_hash


def manifest_path(root: Path) -> Path:
    return root / SOURCES_DIR / MANIFEST_JSON


# ------------------------------------------------------------------ manifest


def load_manifest(root: Path) -> list[dict[str, Any]]:
    path = manifest_path(root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourcesError(f"cannot read {path.relative_to(root).as_posix()}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != SCHEMA_VERSION
        or not isinstance(data.get("sources"), list)
    ):
        raise SourcesError(f"{MANIFEST_JSON} is not a version {SCHEMA_VERSION} source manifest")
    return data["sources"]


def _save_manifest(root: Path, entries: list[dict[str, Any]]) -> None:
    _atomic_write(
        manifest_path(root), _json_bytes({"schema_version": SCHEMA_VERSION, "sources": entries})
    )


def legacy_entries(root: Path) -> dict[str, str]:
    """Key to file name from the hand-written ``MANIFEST.md`` (read only; any file type)."""
    path = root / SOURCES_DIR / LEGACY_MANIFEST
    mapping: dict[str, str] = {}
    if not path.is_file():
        return mapping
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and len(cells) >= 2:
            key, name = cells[0], cells[1]
        else:
            bullet = re.match(r"\s*[-*]\s+`?([^`:\s]+)`?\s*:\s*`?([^`\s]+)`?", line)
            if not bullet:
                continue
            key, name = bullet.group(1), bullet.group(2)
        if _KEY.match(key) and "." in name and key.lower() not in ("key", "source"):
            mapping.setdefault(key, name)
    return mapping


def _entries_for(root: Path, key: str) -> list[dict[str, Any]]:
    return [e for e in load_manifest(root) if e["key"] == key]


def _current(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    return entries[-1] if entries else None


def _is_superseded(entry: dict[str, Any], current: dict[str, Any] | None) -> bool:
    if current is None or entry["raw_hash"] == current["raw_hash"]:
        return False
    return not (
        entry.get("normalized_hash")
        and entry.get("normalized_hash") == current.get("normalized_hash")
    )


# ----------------------------------------------------------------------- add


def add(
    root: Path,
    file: Path,
    *,
    origin: str,
    edition: str,
    key: str | None = None,
    terms: str | None = None,
    retrieved: str | None = None,
    media_type: str | None = None,
) -> dict[str, Any]:
    """Copy *file* into the store under its raw hash and append a manifest entry."""
    if not origin or not edition:
        raise SourcesError("give --origin and --edition")
    if not file.is_file():
        raise SourcesError(f"not a file: {file}")
    legacy = legacy_entries(root)
    if key is None:
        by_name = {name: k for k, name in legacy.items()}
        key = by_name.get(file.name) or re.sub(r"[^A-Za-z0-9._-]+", "-", file.stem).strip("-._")
    _check_key(key)
    data = file.read_bytes()
    raw_hash = _sha256(data)
    suffix = file.suffix.lower()
    ext = suffix.lstrip(".") if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else "bin"
    media = media_type or _MEDIA_TYPES.get(suffix, "application/octet-stream")
    if not re.fullmatch(r"[a-z]+/[a-z0-9.+-]+", media):
        raise SourcesError(f"invalid media type {media!r}")
    entries = load_manifest(root)
    for entry in entries:
        if entry["key"] == key and entry["raw_hash"] == raw_hash:
            return {"key": key, "raw_hash": raw_hash, "added": False, "entry": entry}
    target = store_dir(root, key, raw_hash) / f"raw.{ext}"
    if not (target.exists() and target.read_bytes() == data):
        _atomic_write(target, data)
    entry = {
        "key": key,
        "origin": origin,
        "retrieved": retrieved or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_hash": raw_hash,
        "media_type": media,
        "edition": edition,
    }
    if terms:
        entry["terms"] = terms
    entries.append(entry)
    _save_manifest(root, entries)
    superseded = [e["raw_hash"] for e in entries[:-1] if e["key"] == key]
    return {
        "key": key,
        "raw_hash": raw_hash,
        "added": True,
        "path": target.relative_to(root).as_posix(),
        "supersedes": superseded[-1:] if superseded else [],
        "entry": entry,
    }


def list_sources(root: Path) -> dict[str, Any]:
    entries = load_manifest(root)
    current = {e["key"]: e for e in entries}
    rows = [
        {
            "key": e["key"],
            "raw_hash": e["raw_hash"],
            "edition": e["edition"],
            "normalized_hash": e.get("normalized_hash"),
            "readable": "normalized_hash" in e,
            "superseded": _is_superseded(e, current[e["key"]]),
        }
        for e in entries
    ]
    stored = {e["key"] for e in entries}
    legacy = [
        {"key": k, "file": name, "imported": k in stored}
        for k, name in sorted(legacy_entries(root).items())
    ]
    return {"sources": rows, "legacy": legacy}


# ------------------------------------------------------------- normalization

_BLOCK = {
    "p", "div", "br", "li", "ul", "ol", "table", "tr", "section", "article", "pre", "blockquote",
    "header", "footer", "nav", "aside", "dl", "dt", "dd", "hr", "figure", "figcaption", "main",
    "h1", "h2", "h3", "h4", "h5", "h6",
}  # fmt: skip
_SKIP = {"script", "style", "head", "template", "noscript"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._heading = 0
        self._pre = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP:
            self._skip += 1
            return
        if tag == "pre":
            self._pre += 1
        if tag in _BLOCK:
            self.parts.append("\n\n" if tag != "br" else "\n")
        if len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self._heading = int(tag[1])
            self.parts.append("#" * self._heading + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "pre":
            self._pre = max(0, self._pre - 1)
        if tag in _BLOCK and tag != "br":
            self.parts.append("\n\n")
        if len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self._heading = 0

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.parts.append(data if self._pre else re.sub(r"\s+", " ", data))


def _tidy(text: str) -> str:
    """Newlines to LF, trailing blanks stripped, runs of blank lines collapsed, one final LF."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if not line and (not out or not out[-1]):
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n" if out else ""


def _html_lines(text: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(text)
    extractor.close()
    joined = "".join(extractor.parts)
    return "\n".join(
        line.strip() if not line.startswith(" ") else line for line in joined.split("\n")
    )


def normalize(raw: Path, media_type: str) -> tuple[str, str, str] | str:
    """(text, normalizer name, normalizer version), or a reason string when unreadable."""
    if media_type == "application/pdf":
        program = shutil.which("pdftotext")
        if program is None:
            return "pdftotext is not installed"
        try:
            done = subprocess.run(
                [program, "-layout", "-enc", "UTF-8", str(raw), "-"],
                capture_output=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"pdftotext failed: {exc}"
        if done.returncode != 0:
            return f"pdftotext exited {done.returncode}"
        text = _tidy(done.stdout.decode("utf-8", errors="replace"))
        return (text, "pdftotext", "1") if text.strip() else "pdftotext produced no text"
    if media_type == "text/html":
        decoded = raw.read_bytes().decode("utf-8", errors="replace")
        text = _tidy(_html_lines(decoded))
        return (text, "html-text", "1") if text.strip() else "no text in the HTML"
    if media_type in ("text/plain", "text/markdown"):
        data = raw.read_bytes()
        if b"\x00" in data:
            return "binary content"
        text = _tidy(data.decode("utf-8", errors="replace"))
        return (text, "plain-text", "1") if text.strip() else "empty text"
    return f"no normalizer for {media_type}"


# ------------------------------------------------------------ locator index

_REQ = re.compile(
    r"\b(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|REQUIRED|SHALL|SHOULD"
    r"|RECOMMENDED|MAY|OPTIONAL)\b"
)
_MD_HEADING = re.compile(r"^(#{1,6})\s+(\S.*)$")
_NUMBERED = re.compile(r"^((?:[A-Z]\.)?\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_APPENDIX = re.compile(r"^Appendix\s+([A-Z](?:\.\d+)*)\.?\s+(\S.*)$")
_UNNUMBERED = {
    "abstract", "status of this memo", "status of this memo.", "copyright notice",
    "table of contents", "acknowledgements", "acknowledgments", "references",
    "normative references", "informative references", "authors' addresses",
    "author's address", "authors' address",
}  # fmt: skip
_TOC_LINE = re.compile(r"\.{3,}|\s\d+$")


def _heading(line: str) -> tuple[int, str] | None:
    """(depth, title) when *line* is a heading. Column zero only; table-of-contents rows skip."""
    if not line or line[0].isspace():
        return None
    found = _MD_HEADING.match(line)
    if found:
        return len(found.group(1)), found.group(2).strip()
    if len(line) > 100 or _TOC_LINE.search(line):
        return None
    found = _NUMBERED.match(line)
    if found:
        title = found.group(2).strip()
        if (
            (title[:1].isupper() or title[:1].isdigit())
            and not title.endswith((".", ",", ";", ":"))
            and len(title.split()) <= 12
        ):
            return found.group(1).count(".") + 1, title
        return None
    found = _APPENDIX.match(line)
    if found:
        return found.group(1).count(".") + 1, found.group(2).strip()
    if line.strip().lower() in _UNNUMBERED:
        return 1, line.strip().rstrip(".")
    return None


def _text_hash(lines: list[str]) -> str:
    return _sha256("\n".join(lines).encode("utf-8"))[:16]


def build_locators(text: str) -> dict[str, Any]:
    """Locator index: sections, numbered paragraphs and RFC 2119 requirement lines."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    headings: list[tuple[int, int, str]] = []  # line, depth, title
    in_fence = False
    for number, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence:
            continue
        found = _heading(line)
        if found:
            headings.append((number, found[0], found[1].replace("/", "-")))
    sections: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    for index, (number, depth, title) in enumerate(headings):
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, title))
        path = "/".join(t for _, t in stack)
        seen[path] = seen.get(path, 0) + 1
        if seen[path] > 1:  # a repeated heading path gets a number, so locators stay unique
            title = f"{title} ({seen[path]})"
            stack[-1] = (depth, title)
            path = "/".join(t for _, t in stack)
        end = len(lines)
        for later_number, later_depth, _ in headings[index + 1 :]:
            if later_depth <= depth:
                end = later_number - 1
                break
        sections.append(
            {
                "locator": f"sec:{path}",
                "title": title,
                "depth": depth,
                "start": number,
                "end": end,
                "text_hash": _text_hash(lines[number - 1 : end]),
            }
        )
    paragraphs: list[dict[str, Any]] = []
    start = None
    for number, line in enumerate(lines + [""], 1):
        if line.strip():
            if start is None:
                start = number
        elif start is not None:
            paragraphs.append(
                {
                    "locator": f"para:{len(paragraphs) + 1}",
                    "start": start,
                    "end": number - 1,
                    "text_hash": _text_hash(lines[start - 1 : number - 1]),
                }
            )
            start = None
    counters: dict[str, int] = {}
    requirements: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        for match in _REQ.finditer(line):
            keyword = match.group(1).replace(" ", "_")
            counters[keyword] = counters.get(keyword, 0) + 1
            requirements.append(
                {
                    "locator": f"req:{keyword}:{counters[keyword]}",
                    "start": number,
                    "end": number,
                    "text_hash": _text_hash([line]),
                }
            )
    return {
        "index_version": INDEX_VERSION,
        "normalized_hash": _sha256(text.encode("utf-8")),
        "lines": len(lines),
        "sections": sections,
        "paragraphs": paragraphs,
        "requirements": requirements,
    }


# --------------------------------------------------------------------- index


def _paths(root: Path, entry: dict[str, Any]) -> tuple[Path, Path, Path]:
    base = store_dir(root, entry["key"], entry["raw_hash"])
    raws = sorted(base.glob("raw.*"))
    if not raws:
        raise SourcesError(f"raw file missing for {entry['key']}@{entry['raw_hash'][:12]}")
    return raws[0], base / "normalized.txt", base / "locators.json"


def index(root: Path, key: str | None = None, force: bool = False) -> dict[str, Any]:
    """Normalize and index every entry (or those of *key*). Existing text is kept."""
    entries = load_manifest(root)
    if key is not None:
        _check_key(key)
        if not any(e["key"] == key for e in entries):
            raise SourcesError(f"no source with key {key}")
    results: list[dict[str, Any]] = []
    changed = False
    for entry in entries:
        if key is not None and entry["key"] != key:
            continue
        raw, text_path, index_path = _paths(root, entry)
        row: dict[str, Any] = {"key": entry["key"], "raw_hash": entry["raw_hash"]}
        if text_path.is_file() and not force:
            text = text_path.read_text(encoding="utf-8")
            digest = _sha256(text.encode("utf-8"))
            if entry.get("normalized_hash") not in (None, digest):
                raise SourcesError(
                    f"normalized text of {entry['key']}@{entry['raw_hash'][:12]} differs from the "
                    "manifest; keep the committed text or re-run with --force",
                    key=entry["key"],
                )
            row["status"] = "kept"
            normalizer = entry.get("normalizer") or {"name": "unknown", "version": "0"}
        else:
            outcome = normalize(raw, entry["media_type"])
            if isinstance(outcome, str):
                row.update(status="unreadable", reason=outcome)
                results.append(row)
                continue
            text, name, version = outcome
            _atomic_write(text_path, text.encode("utf-8"))
            digest = _sha256(text.encode("utf-8"))
            normalizer = {"name": name, "version": version}
            row["status"] = "indexed"
        if entry.get("normalized_hash") != digest or entry.get("normalizer") != normalizer:
            entry["normalized_hash"] = digest
            entry["normalizer"] = normalizer
            changed = True
        locators = _json_bytes(build_locators(text))
        if not index_path.is_file() or index_path.read_bytes() != locators:
            _atomic_write(index_path, locators)
        row.update(normalized_hash=digest, normalizer=normalizer)
        results.append(row)
    if changed:
        _save_manifest(root, entries)
    return {"sources": results}


# ------------------------------------------------------------- resolve/slice


def resolve(root: Path, text: str) -> tuple[address.Address, dict[str, Any], bool, dict | None]:
    """(address, manifest entry, superseded, current entry) for an address string."""
    try:
        addr = address.parse(text)
    except address.AddressError as exc:
        raise SourcesError(str(exc)) from exc
    entry, superseded, current = _entry_by_hash(root, addr.key, addr.hash)
    return addr, entry, superseded, current


def _entry_by_hash(
    root: Path, key: str, prefix: str
) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    entries = _entries_for(root, key)
    if not entries:
        raise SourcesError(f"no source with key {key}")
    hashes = [e["normalized_hash"] for e in entries if "normalized_hash" in e]
    try:
        full = address.resolve_prefix(prefix, hashes)
    except address.AddressError as exc:
        found = sorted({h for h in hashes if h.startswith(prefix)})
        extra = {"candidates": found} if len(found) > 1 else {}
        raise SourcesError(str(exc), **extra) from exc
    current = _current(entries)
    entry = next(e for e in reversed(entries) if e.get("normalized_hash") == full)
    return entry, _is_superseded(entry, current), current


def load_locators(root: Path, entry: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    _, text_path, index_path = _paths(root, entry)
    if not text_path.is_file() or not index_path.is_file():
        raise SourcesError(f"{entry['key']} is not indexed; run `sources index`")
    text = text_path.read_text(encoding="utf-8")
    if _sha256(text.encode("utf-8")) != entry["normalized_hash"]:
        raise SourcesError(f"normalized text of {entry['key']} does not match its manifest hash")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines, json.loads(index_path.read_text(encoding="utf-8"))


def _locator_table(index_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}
    for group in ("sections", "paragraphs", "requirements"):
        for item in index_data[group]:
            table.setdefault(item["locator"], item)
    return table


def slice_passage(root: Path, text: str, window: int = DEFAULT_WINDOW) -> dict[str, Any]:
    """The passage an address names, with *window* lines of context (paragraph, requirement)."""
    if window < 0:
        raise SourcesError("--window must not be negative")
    addr, entry, superseded, current = resolve(root, text)
    lines, index_data = load_locators(root, entry)
    item = _locator_table(index_data).get(addr.locator)
    if item is None:
        raise SourcesError(f"locator {addr.locator} not found in {addr.key}@{addr.hash[:12]}")
    start, end = item["start"], item["end"]
    if addr.kind != "sec":
        start, end = max(1, start - window), min(len(lines), end + window)
    shown_end, truncated = end, False
    if end - start + 1 > MAX_SLICE_LINES:
        shown_end, truncated = start + MAX_SLICE_LINES - 1, True
    body = "\n".join(lines[start - 1 : shown_end])
    if len(body.encode("utf-8")) > MAX_SLICE_BYTES:
        body = body.encode("utf-8")[:MAX_SLICE_BYTES].decode("utf-8", errors="ignore")
        shown_end = start + body.count("\n")
        truncated = True
    payload: dict[str, Any] = {
        "address": text,
        "key": addr.key,
        "normalized_hash": entry["normalized_hash"],
        "locator": addr.locator,
        "start": start,
        "end": shown_end,
        "truncated": truncated,
        "superseded": superseded,
        "text": body,
    }
    if superseded and current is not None:
        payload["current_raw_hash"] = current["raw_hash"]
        if "normalized_hash" in current:
            payload["current_hash"] = current["normalized_hash"]
    return payload


def diff(root: Path, key: str, old: str, new: str) -> dict[str, Any]:
    """Locators added, removed and changed (by passage text hash) between two editions."""
    tables = []
    for prefix in (old, new):
        if len(prefix) < address.MIN_HASH:
            raise SourcesError(f"hash prefix must have at least {address.MIN_HASH} characters")
        entry, _, _ = _entry_by_hash(root, key, prefix)
        _, index_data = load_locators(root, entry)
        tables.append((entry["normalized_hash"], _locator_table(index_data)))
    (old_hash, before), (new_hash, after) = tables
    return {
        "key": key,
        "old": old_hash,
        "new": new_hash,
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(
            loc
            for loc in set(before) & set(after)
            if before[loc]["text_hash"] != after[loc]["text_hash"]
        ),
    }
