"""Compiled brief for a flow order (decision 0081).

Deterministic and local: it reads the repo, the section index and the code index, and
makes no model call and no network call. The same repo state gives the same bytes: lists
are sorted, nothing carries a timestamp and paths are repo-relative with forward slashes.

``flow.py`` supplies the finding or gap row (it owns the stage that issued the order) and
the ledger hits (it owns the check table); this module holds the anchors, the guardrail
digest and the byte cap.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from . import code_index
from . import index as section_index
from .latex import strip_comments

BRIEF_VERSION = "1.0"
DEFAULT_BRIEF_BYTES = 6000
MIN_BRIEF_BYTES = 200
MAX_ANCHORS = 6
HASH_LEN = 12
LINE_WINDOW = 2  # context lines around a diagnostic line
GUARDRAIL_DIR = Path("docs") / "guardrails"
GUARDRAIL_LINE = 240

# The rule table: which guardrail tags apply to which order kind. A guardrail is in the
# digest when its front matter `tags` share an entry with the tags of the order's kind.
# Kinds not listed use DEFAULT_TAGS. Every kind `flow.py` issues is listed (tested).
DEFAULT_TAGS = ("orchestration",)
_MAP_TAGS = ("theses-map", "agents")
_CLAIM_TAGS = ("sources", "theses-map", "ledger", "retrieval")
_DRAFT_TAGS = ("verification",)
_RELEASE_TAGS = ("release", "orchestration", "ledger")
GUARDRAIL_RULES: dict[str, tuple[str, ...]] = {
    "state-thesis": _MAP_TAGS,
    "triage-objection": _MAP_TAGS,
    "fill-gap": _MAP_TAGS,
    "find-related": _MAP_TAGS + ("sources",),
    "red-team": _MAP_TAGS,
    "blue-team": _MAP_TAGS,
    "claim-check": _CLAIM_TAGS,
    "attest-claim": _CLAIM_TAGS,
    "reindex": _DRAFT_TAGS,
    "write-section": _DRAFT_TAGS,
    "fix-validation": _DRAFT_TAGS,
    "release-blocked": _RELEASE_TAGS,
    "verify-bibliography": _RELEASE_TAGS,
    "run-cold": _RELEASE_TAGS,
    "publish": _RELEASE_TAGS,
    "needs-human": DEFAULT_TAGS,
    "gate-failing": DEFAULT_TAGS,
}

_BACKTICK = re.compile(r"`([^`\n]+)`")
_FILE_LINES = re.compile(r"^(?P<file>[\w./-]+):(?P<start>\d+)(?:-(?P<end>\d+))?$")


# ------------------------------------------------------------------ anchors


def slice_hash(lines: list[str]) -> str:
    """12 hex characters of the slice's lines (the hash the code index stores)."""
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:HASH_LEN]


def _file_lines(path: Path, *, strip: bool = False) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if strip:
        text = strip_comments(text)
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _anchor(name: str, kind: str, file: str, start: int, end: int, lines: list[str]) -> dict:
    return {
        "name": name,
        "kind": kind,
        "file": file,
        "lines": [start, end],
        "hash": slice_hash(lines),
        "address": f"{file}:{start}-{end}@{slice_hash(lines)}",
        "text": "\n".join(lines),
    }


def _inside(root: Path, rel: str) -> Path | None:
    """The file *rel* names, only when it is a regular file inside the repo."""
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def lines_anchor(
    root: Path, rel: str, start: int, end: int, name: str | None = None
) -> dict | None:
    """An anchor on a file and line range; None when the file or the range is not there."""
    path = _inside(root, rel)
    if path is None or start < 1 or end < start:
        return None
    lines = _file_lines(path)
    if end > len(lines):
        return None
    rel = path.relative_to(root.resolve()).as_posix()
    return _anchor(name or f"{rel}:{start}-{end}", "lines", rel, start, end, lines[start - 1 : end])


def label_anchor(root: Path, label: str) -> dict | None:
    """The section or environment that holds a LaTeX label, through the section index."""
    target = root / section_index.INDEX_PATH
    if not target.is_file():
        return None
    try:
        found = json.loads(target.read_text(encoding="utf-8"))["labels"].get(label)
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if not found:
        return None
    path = _inside(root, found["file"])
    if path is None:
        return None
    start, end = found["lines"]
    lines = _file_lines(path, strip=True)
    if end > len(lines):
        return None
    return _anchor(label, "section", found["file"], start, end, lines[start - 1 : end])


def symbol_anchor(root: Path, name: str) -> dict | None:
    """One symbol from the code index; None when absent, ambiguous or changed since indexing."""
    try:
        symbol = code_index.slice_symbol(root, name)
    except (code_index.CodeIndexError, OSError, ValueError, KeyError):
        return None
    start, end = symbol["lines"]
    return {
        "name": symbol["name"],
        "kind": "symbol",
        "file": symbol["file"],
        "lines": [start, end],
        "hash": symbol["hash"],
        "address": f"{symbol['file']}:{start}-{end}@{symbol['hash']}",
        "text": symbol["text"],
    }


def anchors_for(
    root: Path,
    *,
    labels: list[str] = (),  # type: ignore[assignment]
    texts: list[str] = (),  # type: ignore[assignment]
    places: list[tuple[str, int]] = (),  # type: ignore[assignment]
) -> list[dict]:
    """Anchors from three places, resolved through the indexes and deduplicated.

    - *labels*: LaTeX labels (a node's ``anchor``) resolved through the section index.
    - *texts*: free text; each backticked token that is a ``path:start-end`` range of an
      existing file, or a symbol name of the code index, becomes an anchor.
    - *places*: ``(path, line)`` of a diagnostic, anchored on the lines around it.
    """
    found: list[dict] = []
    for label in labels:
        anchor = label_anchor(root, label)
        if anchor:
            found.append(anchor)
    for text in texts:
        for token in _BACKTICK.findall(text):
            token = token.strip()
            match = _FILE_LINES.match(token)
            if match:
                start = int(match["start"])
                anchor = lines_anchor(root, match["file"], start, int(match["end"] or start))
            else:
                anchor = symbol_anchor(root, token)
            if anchor:
                found.append(anchor)
    for rel, line in places:
        path = _inside(root, rel)
        if path is None or line < 1:
            continue
        total = len(_file_lines(path))
        anchor = lines_anchor(
            root, rel, max(1, line - LINE_WINDOW), min(total, line + LINE_WINDOW)
        )
        if anchor:
            found.append(anchor)
    unique: dict[tuple, dict] = {}
    for anchor in found:
        unique.setdefault((anchor["file"], tuple(anchor["lines"]), anchor["name"]), anchor)
    ordered = sorted(unique.values(), key=lambda a: (a["file"], a["lines"][0], a["name"]))
    return ordered[:MAX_ANCHORS]


def order_anchor(anchor: dict) -> dict:
    """The anchor as an order carries it: names, places and the hash, never the text."""
    return {k: anchor[k] for k in ("name", "kind", "file", "lines", "hash", "mode") if k in anchor}


# --------------------------------------------------------------- guardrails


def _front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _first_line(text: str, fallback: str) -> str:
    body = text.split("\n## Guardrail", 1)
    if len(body) == 2:
        for line in body[1].split("\n")[1:]:
            if line.strip():
                return " ".join(line.split())[:GUARDRAIL_LINE]
    return " ".join(str(fallback).split())[:GUARDRAIL_LINE]


def guardrail_digest(root: Path, kind: str) -> list[dict]:
    """First line of each active guardrail whose tags meet the kind's tags, sorted by id.

    A repo without ``docs/guardrails/`` has an empty digest.
    """
    wanted = set(GUARDRAIL_RULES.get(kind, DEFAULT_TAGS))
    base = root / GUARDRAIL_DIR
    if not base.is_dir():
        return []
    digest = []
    for path in sorted(base.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = _front_matter(text)
        tags = meta.get("tags")
        if not isinstance(tags, list) or meta.get("status", "active") != "active":
            continue
        if wanted & {str(t) for t in tags}:
            digest.append({"id": path.stem, "line": _first_line(text, meta.get("title", ""))})
    return digest


# ------------------------------------------------------------------ compile


def _size(brief: dict) -> int:
    probe = {k: v for k, v in brief.items() if k != "bytes"}
    return len(dump(probe).encode("utf-8"))


def dump(value: Any) -> str:
    """The canonical serialization of a brief (sorted keys, no spaces, no ASCII escapes)."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def compile_brief(
    *,
    order: dict,
    row: dict,
    anchors: list[dict],
    guardrails: list[dict],
    ledger_hits: list[dict],
    verify: dict | None,
    max_calls: int | None,
    cap: int,
    notes: list[str],
) -> dict:
    """Assemble the brief and keep it within *cap* bytes.

    Over the cap, the slices are replaced by their addresses first; if it is still over,
    the guardrail lines and stored failing lines are dropped, leaving ids and keys.
    """
    brief: dict[str, Any] = {
        "version": BRIEF_VERSION,
        "order": order["id"],
        "row": row,
        "anchors": [dict(a) for a in anchors],
        "guardrails": [dict(g) for g in guardrails],
        "ledger": [dict(h) for h in ledger_hits],
        "verify": verify,
        "notes": sorted(notes),
        "degraded": [],
    }
    if max_calls is not None:
        brief["max_calls"] = max_calls
        brief["max_calls_note"] = (
            f"advisory: hand back state after about {max_calls} tool calls; "
            "the host counts, nothing here enforces it"
        )
    if _size(brief) > cap:
        for anchor in brief["anchors"]:
            anchor.pop("text", None)
        brief["degraded"].append("slices")
    if _size(brief) > cap:
        for item in brief["guardrails"]:
            item.pop("line", None)
        for hit in brief["ledger"]:
            hit.pop("failing", None)
        brief["degraded"].append("digest")
    if _size(brief) > cap:
        brief["degraded"].append("over-cap")
    brief["bytes"] = _size(brief)
    return brief
