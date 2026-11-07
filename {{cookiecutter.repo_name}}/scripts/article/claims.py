"""Tier 1 claim checks: does a source-claim quote occur in the local source text?

Also the tier 2 verdicts (a small-model judgment of excerpt versus claim
wording), which are results in the committed ledger (``ledger.py``, decision
0079). Everything here is local and deterministic;
the CLI reports verdicts and locators, never source text, except
``excerpt``, which exists so a local judge can read the matched passage.

Source text lives under ``paper/sources/``. A node names its text with
``source:`` (a path under ``paper/sources/``); otherwise each bib key is
looked up in ``paper/sources/MANIFEST.md`` (a table row ``| key | file |`` or
a bullet ``- key: file``), then as ``paper/sources/<key>.txt``. Only ``.txt``
and ``.md`` files are read; extract PDFs to text first.

A node whose ``locator`` is a source address (``key@hash#locator``, decision 0080)
is checked against that passage of the source store only: the quote is matched in
the slice, the tier 2 ledger key is built from the slice, and a node whose hash
is no longer the current edition is reported ``stale``. ``rebase`` proposes the
address of the quote in the current edition; it never edits the map.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from . import address, ledger, sources
from .theses import load_map, structure_errors

SOURCES_DIR = sources.SOURCES_DIR
MANIFEST = sources.LEGACY_MANIFEST
LEGACY_CACHE_PATH = Path(".theses") / "claims-cache.json"
VERDICT_KIND = "claim-verdict"
VERDICT_OUTPUT = (ledger.LEDGER_DIR / VERDICT_KIND).as_posix()
PROCEDURE_VERSION = "1"  # docs/procedures/claim-check.md; a new judging rule is a new version
TIER = "2"
VERDICTS = ("supports", "overstates", "contradicts")
STATUS = {"supports": "pass", "overstates": "fail", "contradicts": "fail"}
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
    """Bib key to text file from ``MANIFEST.md``; the parser is the store's (``sources``)."""
    return {
        key: name
        for key, name in sources.legacy_entries(root).items()
        if name.lower().endswith(TEXT_SUFFIXES)
    }


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


def address_of(node: dict) -> str | None:
    """The node's locator when it is written as a source address, else None."""
    locator = node.get("locator")
    if isinstance(locator, str) and address.looks_like(locator):
        return locator.strip()
    return None


def _addressed(root: Path, text: str) -> tuple[str, dict]:
    """(source path, passage payload) for an address; only the slice is matched later."""
    addr, entry, superseded, current = sources.resolve(root, text)
    payload = sources.passage_for(root, text, addr, entry, superseded, current, cap=False)
    where = sources.store_dir(root, entry["key"], entry["raw_hash"]) / "normalized.txt"
    return where.relative_to(root).as_posix(), payload


def check_node(root: Path, node: dict) -> dict:
    """Verdict record for one source-claim node (no text)."""
    record = {"id": node["id"], "locator": node["locator"], "verdict": "no-local-text"}
    text_address = address_of(node)
    if text_address is not None:
        return _check_addressed(root, node, text_address, record)
    path = source_path(root, node)
    if path is None:
        return record
    record["source"] = path.relative_to(root).as_posix()
    span = find_quote(path.read_text(encoding="utf-8", errors="replace"), node["quote"])
    record["verdict"] = "found" if span else "not-found"
    if span:
        record["cached"] = cached_verdict(root, node["text"], excerpt_text(path, span))
    return record


def _check_addressed(root: Path, node: dict, text_address: str, record: dict) -> dict:
    try:
        source, payload = _addressed(root, text_address)
    except sources.SourcesError as exc:
        record["reason"] = str(exc)
        return record
    record["source"] = source
    passage = payload["text"]
    span = find_quote(passage, node["quote"])
    record["verdict"] = "found" if span else "not-found"
    if payload["superseded"]:
        record["stale"] = True
        if "current_hash" in payload:
            record["current_hash"] = payload["current_hash"]
    if span:
        record["cached"] = cached_verdict(root, node["text"], excerpt_in(passage, span))
    return record


def excerpt_in(text: str, span: tuple[int, int]) -> str:
    """The matched passage with a little context, cut from *text*."""
    start = max(0, span[0] - EXCERPT_CONTEXT)
    end = min(len(text), span[1] + EXCERPT_CONTEXT)
    return text[start:end]


def excerpt_text(path: Path, span: tuple[int, int]) -> str:
    """The matched passage with a little context, from the original text."""
    return excerpt_in(path.read_text(encoding="utf-8", errors="replace"), span)


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
    text_address = address_of(node)
    if text_address is not None:
        try:
            passage = _addressed(root, text_address)[1]["text"]
        except sources.SourcesError as exc:
            raise ValueError(f"{node_id!r}: {exc}") from exc
        span = find_quote(passage, node["quote"])
        if span is None:
            raise ValueError(f"quote of {node_id!r} is not found in local text")
        return excerpt_in(passage, span)
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


# ----------------------------------------------------------------- verdicts


def verdict_key(claim_text: str, excerpt: str) -> ledger.Keyed:
    """Ledger key over the claim wording, the excerpt, the procedure version and the tier."""
    return ledger.key(
        VERDICT_KIND, {"claim": claim_text, "excerpt": excerpt}, PROCEDURE_VERSION, TIER
    )


def _legacy_key(claim_text: str, excerpt: str) -> str:
    """Key of the untracked cache this ledger replaced: SHA-256 of wording plus excerpt."""
    digest = hashlib.sha256()
    digest.update(claim_text.encode("utf-8"))
    digest.update(b"\0")
    digest.update(excerpt.encode("utf-8"))
    return digest.hexdigest()


def _legacy_verdict(root: Path, claim_text: str, excerpt: str) -> str | None:
    try:
        data = json.loads((root / LEGACY_CACHE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = data.get(_legacy_key(claim_text, excerpt)) if isinstance(data, dict) else None
    verdict = entry.get("verdict") if isinstance(entry, dict) else None
    return verdict if verdict in VERDICTS else None


def _provenance(**extra: str) -> dict[str, str]:
    procedure = f"claim-check/{PROCEDURE_VERSION}"
    return {"tier": TIER, "author": "agent", "procedure": procedure, **extra}


def cached_verdict(root: Path, claim_text: str, excerpt: str) -> str | None:
    """The recorded tier 2 verdict for exactly these inputs, or None.

    A verdict found only in the old untracked cache is moved into the ledger on the
    way (its hash key cannot be converted without the texts, which are in hand here).
    A corrupt ledger entry is a miss; ``ledger verify`` reports it.
    """
    keyed = verdict_key(claim_text, excerpt)
    try:
        entry = ledger.lookup(root, keyed)
    except ledger.LedgerError:
        return None
    if entry is not None:
        verdict = (entry.get("result") or {}).get("verdict")
        return verdict if verdict in VERDICTS else None
    legacy = _legacy_verdict(root, claim_text, excerpt) if ledger.enabled() else None
    if legacy is None:
        return None
    try:
        ledger.put(
            root, keyed, STATUS[legacy], {"verdict": legacy},
            _provenance(imported=LEGACY_CACHE_PATH.as_posix()),
        )  # fmt: skip
    except ledger.LedgerError:
        return None
    return legacy


def record_verdict(root: Path, claim_text: str, excerpt: str, verdict: str) -> str:
    """Store a tier 2 verdict in the ledger and return its key; only the verdict is kept."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    if not ledger.enabled():
        raise ValueError("the ledger is switched off (ARTICLE_LEDGER=off); verdict not recorded")
    keyed = verdict_key(claim_text, excerpt)
    try:
        ledger.put(root, keyed, STATUS[verdict], {"verdict": verdict}, _provenance())
    except ledger.LedgerConflict:
        raise ValueError(
            "a different verdict is already recorded for these inputs; to re-judge, run "
            f"`ledger evict {VERDICT_KIND} {keyed.key} --reason ...` first"
        ) from None
    return keyed.key


def verdict_for_node(root: Path, node_id: str, verdict: str | None = None) -> dict:
    """Read, or with *verdict* record, the tier 2 verdict for a node's current inputs."""
    node = _one(root, node_id)
    excerpt = excerpt_for(root, node_id)
    if verdict is not None:
        key = record_verdict(root, node["text"], excerpt, verdict)
    else:
        key = verdict_key(node["text"], excerpt).key
    return {"id": node_id, "key": key, "verdict": cached_verdict(root, node["text"], excerpt)}


# ------------------------------------------------------------------- rebase


def _rebase_key(root: Path, node: dict, old: address.Address | None) -> str:
    if old is not None:
        return old.key
    for bib_key in node.get("bib_keys") or []:
        if sources.current_edition(root, bib_key) is not None:
            return bib_key
    raise ValueError(
        f"{node['id']!r} names no source in the store; run `sources add` and `sources index` first"
    )


def _innermost(items: list[dict], first: int, last: int) -> str | None:
    best = None
    for item in items:
        if item["start"] <= first and last <= item["end"]:
            if best is None or item["end"] - item["start"] < best["end"] - best["start"]:
                best = item
    return best["locator"] if best else None


def rebase(root: Path, node_id: str) -> dict:
    """Propose the address of a node's quote in the current edition; the map is not edited.

    ``status`` is ``current`` (the node already names the current edition and the quote is
    in its passage), ``proposed`` (a new address for a human to accept), ``quote-missing``
    (the quote does not survive in the current edition) or ``no-locator`` (the quote is
    there, but no section or paragraph holds it whole).
    """
    node = _one(root, node_id)
    old_text = address_of(node)
    try:
        old = address.parse(old_text) if old_text else None
    except address.AddressError as exc:
        raise ValueError(f"{node_id!r}: {exc}") from exc
    key = _rebase_key(root, node, old)
    entry = sources.current_edition(root, key)
    if entry is None or "normalized_hash" not in entry:
        raise ValueError(
            f"the current edition of {key!r} has no normalized text; run `sources index`"
        )
    try:
        lines, index_data = sources.load_locators(root, entry)
    except sources.SourcesError as exc:
        raise ValueError(str(exc)) from exc
    full = "\n".join(lines) + "\n"
    result: dict = {
        "id": node_id,
        "status": "quote-missing",
        "current_hash": entry["normalized_hash"],
    }
    if old_text:
        result["address"] = old_text
    span = find_quote(full, node["quote"])
    if span is None:
        return result
    first = full.count("\n", 0, span[0]) + 1
    last = full.count("\n", 0, max(span[0], span[1] - 1)) + 1
    groups = {
        "sec": index_data["sections"],
        "para": index_data["paragraphs"],
        "req": index_data["requirements"],
    }
    order = ["para", "sec"]
    if old is not None and old.kind == "sec":
        order = ["sec", "para"]
    elif old is not None and old.kind == "req":
        order = ["req", "para", "sec"]
    locator = next(
        (found for kind in order if (found := _innermost(groups[kind], first, last))), None
    )
    if locator is None:
        result["status"] = "no-locator"
        return result
    proposed = f"{key}@{entry['normalized_hash'][:address.MIN_HASH]}#{locator}"
    result["proposed"] = proposed
    same = (
        old is not None
        and entry["normalized_hash"].startswith(old.hash)
        and old.locator == locator
    )
    result["status"] = "current" if same else "proposed"
    return result
