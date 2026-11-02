"""Tier 1 claim checks: does a source-claim quote occur in the local source text?

Also the check cache that tier 2 (a small-model judgment of excerpt versus
claim wording) reads and writes. Everything here is local and deterministic;
the CLI reports verdicts and locators, never source text, except
``excerpt``, which exists so a local judge can read the matched passage.

Source text lives under ``paper/sources/``. A node names its text with
``source:`` (a path under ``paper/sources/``); otherwise each bib key is
looked up in ``paper/sources/MANIFEST.md`` (a table row ``| key | file |`` or
a bullet ``- key: file``), then as ``paper/sources/<key>.txt``. Only ``.txt``
and ``.md`` files are read; extract PDFs to text first.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .theses import load_map, structure_errors

SOURCES_DIR = Path("paper") / "sources"
MANIFEST = "MANIFEST.md"
CACHE_PATH = Path(".theses") / "claims-cache.json"
VERDICTS = ("supports", "overstates", "contradicts")
TEXT_SUFFIXES = (".txt", ".md")
EXCERPT_CONTEXT = 200
ELLIPSIS_RE = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\.\.\.|…")
_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "«": '"', "»": '"',
}  # fmt: skip
_DROPPED = {"­", "-", "‐", "‑", "‒", "–", "—", "−"}


def normalise(text: str) -> tuple[str, list[int]]:
    """Fold *text* for matching; return it with the original index of each char.

    Whitespace, hyphens and dashes are dropped (so line-break hyphenation and
    dash styles do not matter), ligatures are expanded and quotes unified.
    """
    out: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        if char in _DROPPED or char.isspace():
            continue
        for part in unicodedata.normalize("NFKC", _QUOTES.get(char, char)):
            if part.isspace() or part in _DROPPED:
                continue
            out.append(_QUOTES.get(part, part))
            origin.append(index)
    return "".join(out), origin


def _segments(quote: str) -> list[str]:
    parts = [normalise(part)[0] for part in ELLIPSIS_RE.split(quote)]
    return [part for part in parts if part]


def find_quote(source: str, quote: str) -> tuple[int, int] | None:
    """Original-text span covering *quote* (segments split at ellipses, in order)."""
    folded, origin = normalise(source)
    first = last = None
    cursor = 0
    for segment in _segments(quote):
        at = folded.find(segment, cursor)
        if at < 0:
            return None
        if first is None:
            first = origin[at]
        last = origin[at + len(segment) - 1] + 1
        cursor = at + len(segment)
    if first is None:
        return None
    return first, last


def _manifest_map(root: Path) -> dict[str, str]:
    path = root / SOURCES_DIR / MANIFEST
    mapping: dict[str, str] = {}
    if not path.is_file():
        return mapping
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and len(cells) >= 2:
            key, name = cells[0], cells[1]
        else:
            bullet = re.match(r"\s*[-*]\s+`?([^`:\s]+)`?\s*:\s*`?([^`\s]+)`?", line)
            if not bullet:
                continue
            key, name = bullet.group(1), bullet.group(2)
        if name.lower().endswith(TEXT_SUFFIXES):
            mapping.setdefault(key, name)
    return mapping


def source_path(root: Path, node: dict) -> Path | None:
    """Local text file for *node*, or None when there is none."""
    base = (root / SOURCES_DIR).resolve()
    names: list[str] = []
    if node.get("source"):
        names.append(node["source"])
    else:
        manifest = _manifest_map(root)
        for key in node.get("bib_keys") or []:
            names.append(manifest.get(key, f"{key}.txt"))
    for name in names:
        candidate = (root / SOURCES_DIR / name).resolve()
        if (
            candidate.is_file()
            and candidate.is_relative_to(base)
            and candidate.suffix.lower() in TEXT_SUFFIXES
        ):
            return candidate
    return None


def check_node(root: Path, node: dict) -> dict:
    """Verdict record for one source-claim node (no text)."""
    record = {"id": node["id"], "locator": node["locator"], "verdict": "no-local-text"}
    path = source_path(root, node)
    if path is None:
        return record
    record["source"] = path.relative_to(root).as_posix()
    span = find_quote(path.read_text(encoding="utf-8", errors="replace"), node["quote"])
    record["verdict"] = "found" if span else "not-found"
    if span:
        record["cached"] = cached_verdict(root, node["text"], excerpt_text(path, span))
    return record


def excerpt_text(path: Path, span: tuple[int, int]) -> str:
    """The matched passage with a little context, from the original text."""
    text = path.read_text(encoding="utf-8", errors="replace")
    start = max(0, span[0] - EXCERPT_CONTEXT)
    end = min(len(text), span[1] + EXCERPT_CONTEXT)
    return text[start:end]


def source_claims(root: Path) -> list[dict]:
    data = load_map(root)
    if data is None or not structure_errors(data).ok:
        raise ValueError("theses.yaml is missing or invalid; run `theses lint`")
    return [
        n
        for n in data.get("nodes") or []
        if n["type"] == "source-claim" and n["status"] != "retired"
    ]


def quote_check(root: Path, node_id: str | None = None) -> list[dict]:
    nodes = source_claims(root)
    if node_id is not None:
        nodes = [n for n in nodes if n["id"] == node_id]
        if not nodes:
            raise ValueError(f"no active source-claim node {node_id!r}")
    return [check_node(root, n) for n in sorted(nodes, key=lambda n: n["id"])]


def excerpt_for(root: Path, node_id: str) -> str:
    """Excerpt for tier 2; raises when the quote is not found locally."""
    node = _one(root, node_id)
    path = source_path(root, node)
    span = None
    if path is not None:
        text = path.read_text(encoding="utf-8", errors="replace")
        span = find_quote(text, node["quote"])
    if path is None or span is None:
        raise ValueError(f"quote of {node_id!r} is not found in local text")
    return excerpt_text(path, span)


def _one(root: Path, node_id: str) -> dict:
    for node in source_claims(root):
        if node["id"] == node_id:
            return node
    raise ValueError(f"no active source-claim node {node_id!r}")


# ------------------------------------------------------------------- cache


def cache_key(claim_text: str, excerpt: str) -> str:
    """SHA-256 of claim wording plus excerpt."""
    digest = hashlib.sha256()
    digest.update(claim_text.encode("utf-8"))
    digest.update(b"\0")
    digest.update(excerpt.encode("utf-8"))
    return digest.hexdigest()


def _read_cache(root: Path) -> dict:
    path = root / CACHE_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def cached_verdict(root: Path, claim_text: str, excerpt: str) -> str | None:
    entry = _read_cache(root).get(cache_key(claim_text, excerpt))
    return entry.get("verdict") if isinstance(entry, dict) else None


def cache_put(root: Path, claim_text: str, excerpt: str, verdict: str) -> str:
    """Store a tier-2 verdict under the hash; only the hash and verdict are kept."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    key = cache_key(claim_text, excerpt)
    data = _read_cache(root)
    data[key] = {"verdict": verdict}
    path = root / CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return key


def cache_for_node(root: Path, node_id: str, verdict: str | None = None) -> dict:
    """Read, or with *verdict* write, the cache entry for a node's current inputs."""
    node = _one(root, node_id)
    excerpt = excerpt_for(root, node_id)
    if verdict is not None:
        key = cache_put(root, node["text"], excerpt, verdict)
    else:
        key = cache_key(node["text"], excerpt)
    return {"id": node_id, "key": key, "verdict": cached_verdict(root, node["text"], excerpt)}
