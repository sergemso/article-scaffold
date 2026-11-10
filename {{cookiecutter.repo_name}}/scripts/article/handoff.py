"""Handoff result of an agent that reached its call cap (decision 0081).

Pure and offline. A handoff names the order, the anchors done and still remaining, the files
touched, the ledger keys written and the verify outcome. It carries no model or host name
and no manuscript text: every field is an id, a path, a hash or a fixed word. It is stored
in the order's entry in ``flow.yaml`` and read back when the brief is rebuilt, so a fresh
agent resumes without rediscovery. Everything is sorted, so the same handoff always gives
the same bytes.

An optional ``evidence`` list holds one short line per done item: the command run and its
result, or ``not-run``. Lines are single-line text capped in length and count, and a line
that names a model or a vendor is refused, so a handoff stays host-neutral.
"""

from __future__ import annotations

import re
from typing import Any

VERSION = "1.0"
FIELDS = ("version", "order", "done", "remaining", "files", "ledger_keys", "verify")
OPTIONAL = ("evidence",)
OUTCOMES = ("pass", "fail", "not-run")
MAX_ITEMS = 50
ORDER_RE = re.compile(r"^o-[0-9a-f]{12}$")
KEY_RE = re.compile(r"^[0-9a-f]{64}$")
CHECK_RE = re.compile(r"^[a-z][a-z-]*$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/#@+=-]*$")
MAX_NAME = 200
MAX_EVIDENCE = 200
# Names of models and vendors; a handoff line must not carry one (guardrail
# article-tooling-is-host-neutral). Control characters, newlines included, are refused too.
VENDOR_RE = re.compile(
    r"\b(claude|anthropic|gpt|openai|opus|sonnet|haiku|gemini|llama)\b", re.IGNORECASE
)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _anchor_errors(items: object, name: str) -> list[str]:
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        return [f"{name} must be a list of at most {MAX_ITEMS} anchors"]
    errors = []
    for item in items:
        ok = (
            isinstance(item, dict)
            and set(item) == {"name", "file"}
            and isinstance(item["name"], str)
            and len(item["name"]) <= MAX_NAME
            and bool(NAME_RE.match(item["name"]))
            and _file_ok(item["file"])
        )
        if not ok:
            errors.append(
                f"{name} entries must be {{name, file}}: a name of at most {MAX_NAME} characters "
                "with no spaces (an id as `flow next` printed it, not text) and a relative path"
            )
            break
    return errors


def _evidence_errors(items: object) -> list[str]:
    ok = (
        isinstance(items, list)
        and len(items) <= MAX_ITEMS
        and all(
            isinstance(i, str)
            and 0 < len(i) <= MAX_EVIDENCE
            and not CONTROL_RE.search(i)
            and not VENDOR_RE.search(i)
            for i in items
        )
    )
    if ok:
        return []
    return [
        f"evidence must be a list of at most {MAX_ITEMS} single-line strings of at most "
        f"{MAX_EVIDENCE} characters, with no model or vendor name"
    ]


def _file_ok(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    return ".." not in value.split("/")


def errors(data: object) -> list[str]:
    """Rule violations of a handoff document (empty when valid)."""
    if not isinstance(data, dict):
        return ["handoff must be a mapping"]
    unknown = set(data) - set(FIELDS) - set(OPTIONAL)
    found = [f"unknown field {k!r}" for k in sorted(unknown, key=str)]
    found += [f"missing field {k!r}" for k in FIELDS if k not in data]
    if data.get("version") != VERSION:
        found.append(f"version must be {VERSION!r}")
    if not (isinstance(data.get("order"), str) and ORDER_RE.match(data["order"])):
        found.append("order must be an order id (o- and 12 hex characters)")
    found += _anchor_errors(data.get("done", []), "done")
    found += _anchor_errors(data.get("remaining", []), "remaining")
    files = data.get("files", [])
    if not (isinstance(files, list) and len(files) <= MAX_ITEMS and all(map(_file_ok, files))):
        found.append("files must be a list of relative paths inside the repository")
    keys = data.get("ledger_keys", [])
    if not (
        isinstance(keys, list) and len(keys) <= MAX_ITEMS
        and all(isinstance(k, str) and KEY_RE.match(k) for k in keys)
    ):
        found.append("ledger_keys must be a list of 64-hex ledger keys")
    if "evidence" in data:
        found += _evidence_errors(data["evidence"])
    verify = data.get("verify")
    if not (
        isinstance(verify, dict)
        and set(verify) == {"check", "outcome"}
        and verify["outcome"] in OUTCOMES
        and (verify["check"] is None
             or (isinstance(verify["check"], str) and CHECK_RE.match(verify["check"])))
    ):
        found.append("verify must be {check, outcome} with outcome pass, fail or not-run")
    if not found:
        shared = _ids(data["done"]) & _ids(data["remaining"])
        if shared:
            names = ", ".join(sorted(shared))
            found.append(f"an anchor cannot be both done and remaining: {names}")
    return found


def _ids(anchors: list[dict]) -> set[str]:
    return {f"{a['file']}::{a['name']}" for a in anchors}


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    """The handoff with sorted, deduplicated lists; call only after ``errors`` is empty."""
    def anchors(items: list[dict]) -> list[dict]:
        unique = {(a["file"], a["name"]) for a in items}
        return [{"name": n, "file": f} for f, n in sorted(unique)]

    record = {
        "version": VERSION,
        "order": data["order"],
        "done": anchors(data["done"]),
        "remaining": anchors(data["remaining"]),
        "files": sorted(set(data["files"])),
        "ledger_keys": sorted(set(data["ledger_keys"])),
        "verify": {"check": data["verify"]["check"], "outcome": data["verify"]["outcome"]},
    }
    if data.get("evidence"):
        record["evidence"] = sorted(set(data["evidence"]))
    return record


def done_ids(handoff: dict[str, Any] | None) -> set[tuple[str, str]]:
    """``(file, name)`` of every anchor a handoff reports as done."""
    if not isinstance(handoff, dict):
        return set()
    done = handoff.get("done")
    if not isinstance(done, list):
        return set()
    return {
        (a["file"], a["name"])
        for a in done
        if isinstance(a, dict) and isinstance(a.get("file"), str) and isinstance(a.get("name"), str)
    }
