"""Theses map: loading and validation of ``theses.yaml``.

Offline and deterministic. Output carries ids and one-line text only.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .diagnostics import Diagnostics

MAP_FILE = "theses.yaml"
NODE_TYPES = ("thesis", "hypothesis", "objection", "defense", "source-claim")
EDGE_TYPES = ("supports", "attacks", "rebuts")
STATUSES = ("proposed", "accepted", "retired")
NODE_FIELDS = {
    "id",
    "type",
    "text",
    "status",
    "anchor",
    "bib_keys",
    "accepted-by",
    "quote",
    "locator",
    "source",
}
EDGE_FIELDS = {"from", "to", "type"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
# Tokens that mark an agent or model rather than a person.
AGENT_TOKENS = frozenset(
    {"agent", "ai", "assistant", "bot", "claude", "gpt", "llm", "model", "skill", "team"}
)


def is_agent_name(name: str) -> bool:
    """True when *name* looks like an agent role, not a person."""
    tokens = re.split(r"[^a-z0-9]+", str(name).lower())
    return any(token in AGENT_TOKENS for token in tokens)


def load_map(root: Path) -> dict | None:
    """Return the parsed map, or None when the file is absent."""
    path = root / MAP_FILE
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_map(
    data: object, labels: set[str] | None, diagnostics: Diagnostics
) -> None:
    """Check *data* against the map rules; *labels* are the paper's labels."""

    def err(code: str, message: str) -> None:
        diagnostics.error(MAP_FILE, 0, code, message)

    if not isinstance(data, dict):
        err("T001", "theses.yaml must be a mapping")
        return
    for key in sorted(set(data) - {"version", "nodes", "edges"}, key=str):
        err("T002", f"unknown top-level field {key!r}")
    if data.get("version") != 1:
        err("T003", "version must be 1")
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list):
        err("T001", "nodes must be a list")
        nodes = []
    if not isinstance(edges, list):
        err("T001", "edges must be a list")
        edges = []

    ids: set[str] = set()
    for index, node in enumerate(nodes):
        _check_node(index, node, ids, labels, err)
    for index, edge in enumerate(edges):
        _check_edge(index, edge, ids, err)


def _check_node(index, node, ids, labels, err) -> None:
    if not isinstance(node, dict):
        err("T001", f"nodes[{index}] must be a mapping")
        return
    node_id = node.get("id")
    where = f"node {node_id!r}" if isinstance(node_id, str) else f"nodes[{index}]"
    for key in sorted(set(node) - NODE_FIELDS, key=str):
        err("T002", f"{where}: unknown field {key!r}")
    if not isinstance(node_id, str) or not ID_RE.match(node_id):
        err("T004", f"{where}: id must match {ID_RE.pattern}")
    elif node_id in ids:
        err("T005", f"duplicate node id {node_id!r}")
    else:
        ids.add(node_id)
    if node.get("type") not in NODE_TYPES:
        err("T006", f"{where}: type must be one of {', '.join(NODE_TYPES)}")
    text = node.get("text")
    if not isinstance(text, str) or not text.strip() or "\n" in text.strip():
        err("T007", f"{where}: text must be a non-empty single line")
    status = node.get("status")
    if status not in STATUSES:
        err("T008", f"{where}: status must be one of {', '.join(STATUSES)}")
    anchor = node.get("anchor")
    if anchor is not None:
        if not isinstance(anchor, str) or not anchor:
            err("T009", f"{where}: anchor must be a label string or null")
        elif labels is not None and anchor not in labels:
            err("T010", f"{where}: anchor {anchor!r} is not a \\label in paper/")
    keys = node.get("bib_keys")
    if keys is not None and (
        not isinstance(keys, list)
        or not all(isinstance(k, str) and k for k in keys)
    ):
        err("T011", f"{where}: bib_keys must be a list of strings")
    by = node.get("accepted-by")
    if status == "accepted":
        if not isinstance(by, str) or not by.strip():
            err("T012", f"{where}: accepted node needs accepted-by")
    if isinstance(by, str) and is_agent_name(by):
        err("T013", f"{where}: accepted-by names an agent role, not a person")
    if node.get("type") == "source-claim":
        for field in ("quote", "locator"):
            value = node.get(field)
            if not isinstance(value, str) or not value.strip():
                err("T014", f"{where}: source-claim requires {field}")


def _check_edge(index, edge, ids, err) -> None:
    if not isinstance(edge, dict):
        err("T001", f"edges[{index}] must be a mapping")
        return
    for key in sorted(set(edge) - EDGE_FIELDS, key=str):
        err("T002", f"edges[{index}]: unknown field {key!r}")
    if edge.get("type") not in EDGE_TYPES:
        err("T015", f"edges[{index}]: type must be one of {', '.join(EDGE_TYPES)}")
    for end in ("from", "to"):
        value = edge.get(end)
        if value not in ids:
            err("T016", f"edges[{index}]: {end} {value!r} is not a node id")
