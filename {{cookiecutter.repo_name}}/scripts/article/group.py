"""Group ready orders that write the same file (decision 0081).

Pure and offline. An anchor is ``write`` when the order's outputs cover its file and
``read`` otherwise. Orders whose write anchors share a file (directly or through a chain
of orders) form one group for one agent; a shared ``read`` anchor never groups. A group has
a size cap: the first orders in the given order are offered and the rest wait for a later
call. Everything is sorted, so the same input gives the same groups.
"""

from __future__ import annotations

import hashlib
from typing import Any

DEFAULT_GROUP_SIZE = 3
MIN_GROUP_SIZE = 1  # 1 turns grouping off


def paths_overlap(a: str, b: str) -> bool:
    """Same path, or one is a directory (trailing slash) holding the other."""
    if a == b:
        return True
    return (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b))


def anchor_mode(outputs: list[str], file: str) -> str:
    """``write`` when an output (without its ``#fragment``) covers *file*, else ``read``."""
    for output in outputs:
        if paths_overlap(output.split("#", 1)[0], file):
            return "write"
    return "read"


def write_files(order: dict[str, Any]) -> set[str]:
    return {a["file"] for a in order.get("anchors", []) if a.get("mode") == "write"}


def group_id(order_ids: list[str]) -> str:
    return "g-" + hashlib.sha256("|".join(sorted(order_ids)).encode("utf-8")).hexdigest()[:12]


def plan(orders: list[dict[str, Any]], size: int) -> tuple[list[list[int]], list[int]]:
    """Indexes of the orders per group (two or more members) and the deferred indexes.

    Members keep the list order. A group over *size* keeps its first *size* members; the
    others are deferred, which is a later call's group (or single order) once these are done.
    Orders for a person or behind a gate are never grouped.
    """
    parent = list(range(len(orders)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[str, int] = {}
    for i, order in enumerate(orders):
        if order["needs_human"] or order["gated"]:
            continue
        for file in sorted(write_files(order)):
            if file in owner:
                parent[find(i)] = find(owner[file])
            else:
                owner[file] = i
    members: dict[int, list[int]] = {}
    for i in range(len(orders)):
        members.setdefault(find(i), []).append(i)
    groups: list[list[int]] = []
    deferred: list[int] = []
    for idx in sorted(members.values()):
        if len(idx) < 2:
            continue
        keep = max(size, MIN_GROUP_SIZE)
        if keep < 2:
            continue
        groups.append(idx[:keep])
        deferred += idx[keep:]
    return groups, sorted(deferred)
