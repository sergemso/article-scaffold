"""Results ledger (decision 0079): committed, append-only, keyed by a hash of every input.

One file per result at ``docs/ledger/<kind>/<key[:2]>/<key>.json``. An entry holds the
input hashes and the result and no timestamp, so two worktrees that compute the same
result write the same bytes. Provenance goes in ``<key>.<hash>.prov.json`` files whose
names differ per writer, so they never collide in a merge.

Only ``pass`` and ``fail`` are stored. An error or an unavailable check is not a result.
Nothing here opens a network connection or runs a command.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

KEY_VERSION = 1
SCHEMA_VERSION = "1.0"
LEDGER_DIR = Path("docs") / "ledger"
EVICTIONS = LEDGER_DIR / "evictions.jsonl"
STATS_PATH = Path(".theses") / "ledger-stats.json"
STATUSES = ("pass", "fail")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ENTRY_FILE = re.compile(r"^[0-9a-f]{64}\.json$")


class LedgerError(ValueError):
    """A key, entry or request the ledger refuses."""


class LedgerConflict(LedgerError):
    """A different result is already stored for this key."""


class Kind(NamedTuple):
    """A kind declares its inputs in one place (guardrail ledger-keys-cover-every-input).

    ``open_inputs`` kinds take any non-empty set of names; ``paths`` says the names are
    repo-relative file paths, so a rename is a miss and ``gc`` can compare them with disk.
    """

    name: str
    inputs: tuple[str, ...] = ()
    open_inputs: bool = False
    paths: bool = False


KINDS: dict[str, Kind] = {
    kind.name: kind
    for kind in (
        Kind("claim-verdict", inputs=("claim", "excerpt")),
        Kind("check-outcome", open_inputs=True, paths=True),
    )
}


class Keyed(NamedTuple):
    key: str
    kind: str
    version: str
    tier: str
    tools: dict[str, str]
    inputs: dict[str, str]


# ---------------------------------------------------------------------- keys


def enabled() -> bool:
    """``ARTICLE_LEDGER=off`` bypasses lookups and writes (debugging switch)."""
    return os.environ.get("ARTICLE_LEDGER", "").strip().lower() != "off"


def hash_input(value: str | bytes | Path) -> str:
    """SHA-256 of content with CRLF read as LF. A Path is read; never its mtime or name."""
    if isinstance(value, Path):
        try:
            data = value.read_bytes()
        except OSError as exc:
            raise LedgerError(f"cannot read input {value}: {exc.strerror or exc}") from exc
    elif isinstance(value, str):
        data = value.encode("utf-8")
    else:
        data = value
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _digest(
    kind: str, version: str, tier: str, tools: Mapping[str, str], hashes: Mapping[str, str]
) -> str:
    payload = {
        "key_version": KEY_VERSION,
        "kind": kind,
        "version": version,
        "tier": tier,
        "tools": dict(tools),
        "inputs": dict(hashes),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def key(
    kind: str,
    inputs: Mapping[str, str | bytes | Path],
    version: str,
    tier: str,
    tools: Mapping[str, str] | None = None,
) -> Keyed:
    """Key over every declared input, the procedure version, the tier and the tool versions.

    ``tools`` are declared strings; this never runs a tool to find out its version.
    """
    if kind not in KINDS:
        raise LedgerError(f"unregistered ledger kind {kind!r}")
    spec = KINDS[kind]
    if not isinstance(version, str) or not version:
        raise LedgerError("version must be a non-empty string")
    if not isinstance(tier, str) or not tier:
        raise LedgerError("tier must be a non-empty string")
    tools = dict(tools or {})
    if not all(isinstance(k, str) and isinstance(v, str) and v for k, v in tools.items()):
        raise LedgerError("tools must map names to non-empty version strings")
    if spec.open_inputs:
        if not inputs:
            raise LedgerError(f"kind {kind} needs at least one input")
    else:
        missing = sorted(set(spec.inputs) - set(inputs))
        extra = sorted(set(inputs) - set(spec.inputs))
        if missing or extra:
            parts = [f"missing input {n}" for n in missing] + [
                f"undeclared input {n}" for n in extra
            ]
            raise LedgerError(f"kind {kind}: " + "; ".join(parts))
    hashes = {name: hash_input(value) for name, value in sorted(inputs.items())}
    return Keyed(_digest(kind, version, tier, tools, hashes), kind, version, tier, tools, hashes)


# ------------------------------------------------------------------- storage


def _entry_path(root: Path, kind: str, digest: str) -> Path:
    if kind not in KINDS:
        raise LedgerError(f"unregistered ledger kind {kind!r}")
    if not _HEX64.match(digest):
        raise LedgerError("a key is 64 lowercase hex characters")
    return root / LEDGER_DIR / kind / digest[:2] / f"{digest}.json"


def _dump(entry: dict[str, Any]) -> str:
    return json.dumps(entry, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _check_entry(entry: Any, kind: str | None = None, digest: str | None = None) -> None:
    """Structure, then the recomputed key: a hand-edited or foreign entry is refused."""
    if not isinstance(entry, dict):
        raise LedgerError("entry is not an object")
    wanted = {
        "schema_version", "kind", "key", "key_version", "version", "tier", "tools", "inputs",
        "status", "result",
    }  # fmt: skip
    if set(entry) - wanted or not (wanted - {"result"}) <= set(entry):
        raise LedgerError("entry fields do not match the schema")
    if entry["schema_version"] != SCHEMA_VERSION:
        raise LedgerError("unknown entry schema_version")
    if entry["key_version"] != KEY_VERSION:
        raise LedgerError(f"key_version {entry['key_version']!r} is not {KEY_VERSION}")
    if entry["status"] not in STATUSES:
        raise LedgerError(f"status must be one of {', '.join(STATUSES)}")
    if "result" in entry and not isinstance(entry["result"], dict):
        raise LedgerError("result must be an object")
    inputs, tools = entry["inputs"], entry["tools"]
    if not isinstance(inputs, dict) or not inputs:
        raise LedgerError("inputs must be a non-empty object")
    if not all(isinstance(h, str) and _HEX64.match(h) for h in inputs.values()):
        raise LedgerError("input hashes must be 64 hex characters")
    if not isinstance(tools, dict) or not all(isinstance(v, str) and v for v in tools.values()):
        raise LedgerError("tools must map names to version strings")
    if not all(isinstance(entry[f], str) and entry[f] for f in ("version", "tier", "kind")):
        raise LedgerError("version, tier and kind must be non-empty strings")
    if entry["kind"] not in KINDS:
        raise LedgerError(f"unregistered ledger kind {entry['kind']!r}")
    if _digest(entry["kind"], entry["version"], entry["tier"], tools, inputs) != entry["key"]:
        raise LedgerError("stored key does not match the entry's inputs")
    if kind is not None and entry["kind"] != kind:
        raise LedgerError("entry kind does not match its location")
    if digest is not None and entry["key"] != digest:
        raise LedgerError("entry key does not match its file name")


def get(root: Path, kind: str, digest: str) -> dict[str, Any] | None:
    """The stored entry, or None. A corrupt entry raises; it is never served."""
    path = _entry_path(root, kind, digest)
    if not path.is_file():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"{path.name}: unreadable entry ({exc})") from exc
    _check_entry(entry, kind, digest)
    return entry


def provenance(root: Path, kind: str, digest: str) -> list[dict[str, Any]]:
    path = _entry_path(root, kind, digest)
    found = []
    for item in sorted(path.parent.glob(f"{digest}.*.prov.json")):
        try:
            found.append(json.loads(item.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return found


def _entry_for(keyed: Keyed, status: str, result: dict[str, Any] | None) -> dict[str, Any]:
    if status not in STATUSES:
        raise LedgerError(f"status must be one of {', '.join(STATUSES)}; an error is not stored")
    if result is not None and not isinstance(result, dict):
        raise LedgerError("result must be an object")
    entry: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": keyed.kind,
        "key": keyed.key,
        "key_version": KEY_VERSION,
        "version": keyed.version,
        "tier": keyed.tier,
        "tools": dict(keyed.tools),
        "inputs": dict(keyed.inputs),
        "status": status,
    }
    if result is not None:
        entry["result"] = result
    return entry


def put(
    root: Path,
    keyed: Keyed,
    status: str,
    result: dict[str, Any] | None = None,
    provenance_info: Mapping[str, Any] | None = None,
) -> str:
    """Store a result: ``created``, ``exists`` (same result, no-op) or ``skipped`` (switch off).

    A different result for an existing key raises LedgerConflict. The write is atomic and
    never overwrites: two writers of the same entry leave one valid file. Only commands
    that run a check or record a verdict call this; there is no CLI verb for it.
    """
    entry = _entry_for(keyed, status, result)
    if not enabled():
        _bump(root, "bypassed")
        return "skipped"
    path = _entry_path(root, keyed.kind, keyed.key)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _dump(entry)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        try:
            os.link(tmp, path)
        except FileExistsError:
            existing = get(root, keyed.kind, keyed.key)
            if existing == entry:
                return "exists"
            _bump(root, "conflicts")
            raise LedgerConflict(
                f"{keyed.kind} {keyed.key[:12]}: a different result is already stored"
            ) from None
        except OSError:  # filesystem without hard links: exclusive create instead
            try:
                with open(path, "x", encoding="utf-8") as handle:
                    handle.write(data)
            except FileExistsError:
                if get(root, keyed.kind, keyed.key) == entry:
                    return "exists"
                _bump(root, "conflicts")
                raise LedgerConflict(
                    f"{keyed.kind} {keyed.key[:12]}: a different result is already stored"
                ) from None
    finally:
        tmp.unlink(missing_ok=True)
    _write_provenance(path, keyed.key, provenance_info)
    return "created"


def _write_provenance(entry_path: Path, digest: str, extra: Mapping[str, Any] | None) -> None:
    info = {
        "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "platform": sys.platform,
        **(extra or {}),
    }
    text = json.dumps(info, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    tag = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    (entry_path.parent / f"{digest}.{tag}.prov.json").write_text(text, encoding="utf-8")


def _entry_files(root: Path, kind: str | None = None) -> list[Path]:
    base = root / LEDGER_DIR
    if not base.is_dir():
        return []
    kinds = [base / kind] if kind else [p for p in sorted(base.iterdir()) if p.is_dir()]
    found = []
    for kind_dir in kinds:
        if kind_dir.is_dir():
            found.extend(f for f in sorted(kind_dir.glob("*/*.json")) if _ENTRY_FILE.match(f.name))
    return found


# -------------------------------------------------------------- lookups, stats


def _read_stats(root: Path) -> dict[str, int]:
    try:
        data = json.loads((root / STATS_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, int)} if isinstance(data, dict) else {}


def _bump(root: Path, name: str) -> None:
    """Counters only (hits, misses, conflicts, bypassed); never content. Local, untracked."""
    stats = _read_stats(root)
    stats[name] = stats.get(name, 0) + 1
    try:
        path = root / STATS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass


def stats(root: Path, reset: bool = False) -> dict[str, int]:
    found = _read_stats(root)
    if reset:
        try:
            (root / STATS_PATH).unlink(missing_ok=True)
        except OSError:
            pass
    return {name: found.get(name, 0) for name in ("hits", "misses", "conflicts", "bypassed")}


def lookup(root: Path, keyed: Keyed) -> dict[str, Any] | None:
    """``get`` that counts a hit or a miss. With the switch off it is always a miss."""
    if not enabled():
        _bump(root, "bypassed")
        return None
    entry = get(root, keyed.kind, keyed.key)
    _bump(root, "hits" if entry is not None else "misses")
    return entry


# ---------------------------------------------------- verify, explain, evict, gc


def verify(root: Path) -> list[str]:
    """Problems in stored entries: unreadable, misplaced, or a key that does not recompute."""
    problems = []
    base = root / LEDGER_DIR
    for path in _entry_files(root):
        rel = path.relative_to(root).as_posix()
        kind, shard = path.parent.parent.name, path.parent.name
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            _check_entry(entry, kind if kind in KINDS else None, path.stem)
        except (OSError, json.JSONDecodeError, LedgerError) as exc:
            problems.append(f"{rel}: {exc}")
            continue
        if kind not in KINDS:
            problems.append(f"{rel}: unregistered ledger kind {kind!r}")
        elif shard != path.stem[:2]:
            problems.append(f"{rel}: stored under the wrong shard directory")
    if base.is_dir():
        for stray in sorted(base.glob("*/*/.tmp-*")):
            problems.append(f"{stray.relative_to(root).as_posix()}: leftover temporary file")
    return problems


def explain(root: Path, keyed: Keyed, version_prefix: str | None = None) -> dict[str, Any]:
    """Why a lookup missed: the nearest stored entry of the kind and what differs from it.

    ``version_prefix`` limits the comparison to entries whose version starts with it, so one
    named check is not compared with another.
    """
    best: tuple[int, str, dict[str, Any]] | None = None
    for path in _entry_files(root, keyed.kind):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            _check_entry(entry, keyed.kind, path.stem)
        except (OSError, json.JSONDecodeError, LedgerError):
            continue
        if version_prefix is not None and not entry["version"].startswith(version_prefix):
            continue
        stored = entry["inputs"]
        changed = sorted(n for n in keyed.inputs if n in stored and stored[n] != keyed.inputs[n])
        added = sorted(set(keyed.inputs) - set(stored))
        removed = sorted(set(stored) - set(keyed.inputs))
        other = [
            name
            for name, now in (
                ("version", keyed.version),
                ("tier", keyed.tier),
                ("tools", keyed.tools),
            )
            if entry[name] != now
        ]
        distance = len(changed) + len(added) + len(removed) + len(other)
        report = {
            "nearest": entry["key"], "changed": changed, "added": added, "removed": removed,
            "other": other,
        }  # fmt: skip
        if best is None or (distance, entry["key"]) < (best[0], best[1]):
            best = (distance, entry["key"], report)
    if best is None:
        return {"nearest": None, "changed": [], "added": [], "removed": [], "other": []}
    return best[2]


def evict(root: Path, kind: str, digest: str, reason: str) -> None:
    """The only delete. It is logged to ``docs/ledger/evictions.jsonl``."""
    if not reason.strip():
        raise LedgerError("eviction needs a reason")
    path = _entry_path(root, kind, digest)
    if not path.is_file():
        raise LedgerError(f"no {kind} entry {digest[:12]}")
    for item in [path, *path.parent.glob(f"{digest}.*.prov.json")]:
        item.unlink(missing_ok=True)
    line = {
        "kind": kind,
        "key": digest,
        "reason": reason.strip(),
        "evicted": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    log = root / EVICTIONS
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")


def gc(root: Path, apply: bool = False) -> dict[str, Any]:
    """Entries of path-input kinds whose files no longer hash to the stored values.

    Label-input kinds (a claim wording) cannot be compared with disk and are not touched.
    An entry may still be valid on another branch; ``apply`` evicts and logs each one.
    """
    orphans = []
    for kind in (k for k in KINDS.values() if k.paths):
        for path in _entry_files(root, kind.name):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                _check_entry(entry, kind.name, path.stem)
            except (OSError, json.JSONDecodeError, LedgerError):
                continue
            for name, stored in entry["inputs"].items():
                target = root / name
                try:
                    current = hash_input(target) if target.is_file() else None
                except LedgerError:
                    current = None
                if current != stored:
                    reason = "input missing" if current is None else "input changed"
                    orphans.append(
                        {"kind": kind.name, "key": entry["key"], "reason": f"{reason}: {name}"}
                    )
                    break
    if apply:
        for item in orphans:
            evict(root, item["kind"], item["key"], f"gc: {item['reason']}")
    return {"orphans": orphans, "applied": apply}
