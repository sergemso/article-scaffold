"""Contradictions and typed moves in the theses map (decision 0083): structural lint.

Structure only: references resolve, poles are anchored, move types carry their required
fields, and the move chain has no cycle. Whether a synthesis is sound is a human judgment.
No network and no matrix lookup; the principle list is a closed set of tags.
"""

from __future__ import annotations

import json
from pathlib import Path

CONTRADICTION_KINDS = ("dialectical", "technical", "physical")
MOVE_TYPES = ("negation", "negation-of-negation", "synthesis", "aufhebung", "opening")
STATUSES = ("proposed", "accepted", "retired")
AUTHORS = ("agent", "human")
CONTRADICTION_FIELDS = {
    "id", "text", "poles", "kind", "status", "author", "accepted-by",
    "improving", "worsening", "principle", "ideal-result", "resources",
}
MOVE_FIELDS = {
    "id", "type", "text", "status", "author", "accepted-by", "cites",
    "preserved", "cancelled", "lifted", "opens",
}
AUFHEBUNG_FIELDS = ("preserved", "cancelled", "lifted")
CITING_TYPES = ("negation", "negation-of-negation", "synthesis", "aufhebung")
OPENABLE = ("thesis", "hypothesis")
PRINCIPLES_FILE = Path(__file__).resolve().parents[2] / "schemas" / "triz-principles.json"


def principles() -> dict[str, dict]:
    """The shipped closed list of the 40 inventive principles, keyed by tag."""
    data = json.loads(PRINCIPLES_FILE.read_text(encoding="utf-8"))
    return {p["id"]: p for p in data["principles"]}


def _line(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value.strip()


def _section(data: dict, key: str, err) -> list:
    raw = data.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        err("T001", f"{key} must be a list")
        return []
    return raw


def uses_section(data: object) -> bool:
    """True when the map declares a contradiction or a move (the stage is otherwise off)."""
    return isinstance(data, dict) and bool(data.get("contradictions") or data.get("moves"))


def check(data: dict, err) -> None:
    """Lint the ``contradictions`` and ``moves`` sections of *data*; *err(code, message)*."""
    raw_nodes = [n for n in data.get("nodes") or [] if isinstance(n, dict)]
    node_types = {n.get("id"): n.get("type") for n in raw_nodes}
    contradictions = _section(data, "contradictions", err)
    moves = _section(data, "moves", err)
    ids: set[str] = set()
    c_ids = _check_contradictions(contradictions, node_types, ids, err)
    by_id = _check_moves(moves, node_types, c_ids, ids, err)
    _check_cycles(by_id, err)


def _identify(item: dict, label: str, index: int, ids: set, node_types: dict, err) -> str:
    item_id = item.get("id")
    where = f"{label} {item_id!r}" if isinstance(item_id, str) else f"{label}s[{index}]"
    if not isinstance(item_id, str) or not item_id:
        err("T070", f"{where}: id must be a non-empty string")
    elif item_id in ids or item_id in node_types:
        err("T071", f"duplicate id {item_id!r} (ids are shared by nodes, contradictions and moves)")
    else:
        ids.add(item_id)
    return where


def _common(item: dict, where: str, err) -> None:
    if item.get("status") not in STATUSES:
        err("T072", f"{where}: status must be one of {', '.join(STATUSES)}")
    if item.get("author") not in AUTHORS:
        err("T072", f"{where}: author must be one of {', '.join(AUTHORS)}")
    if "text" in item and not _line(item["text"]):
        err("T007", f"{where}: text must be a non-empty single line")
    by = item.get("accepted-by")
    if item.get("status") == "accepted" and (not isinstance(by, str) or not by.strip()):
        err("T012", f"{where}: accepted item needs accepted-by")
    if isinstance(by, str):
        from .theses import is_agent_name

        if is_agent_name(by):
            err("T013", f"{where}: accepted-by names an agent role, not a person")


def _check_contradictions(items: list, node_types: dict, ids: set, err) -> set[str]:
    known = principles()
    found: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            err("T001", f"contradictions[{index}] must be a mapping")
            continue
        where = _identify(item, "contradiction", index, ids, node_types, err)
        if isinstance(item.get("id"), str):
            found.add(item["id"])
        for key in sorted(set(item) - CONTRADICTION_FIELDS, key=str):
            err("T002", f"{where}: unknown field {key!r}")
        _common(item, where, err)
        _check_poles(item.get("poles"), where, node_types, err)
        kind = item.get("kind")
        if kind not in CONTRADICTION_KINDS:
            err("T073", f"{where}: kind must be one of {', '.join(CONTRADICTION_KINDS)}")
        for field in ("improving", "worsening"):
            if kind == "technical" and not _line(item.get(field)):
                err("T074", f"{where}: a technical contradiction needs {field}")
            elif kind != "technical" and field in item:
                err("T075", f"{where}: {field} belongs to a technical contradiction")
        if "principle" in item:
            if kind == "dialectical":
                err("T076", f"{where}: principle belongs to a technical or physical contradiction")
            if item["principle"] not in known:
                err("T077", f"{where}: principle {item['principle']!r} is not a listed tag")
        if "ideal-result" in item and not _line(item["ideal-result"]):
            err("T007", f"{where}: ideal-result must be a non-empty single line")
        resources = item.get("resources")
        if resources is not None and (
            not isinstance(resources, list) or not all(_line(r) for r in resources)
        ):
            err("T078", f"{where}: resources must be a list of single lines")
    return found


def _check_poles(poles: object, where: str, node_types: dict, err) -> None:
    if not isinstance(poles, list) or len(poles) != 2:
        err("T079", f"{where}: poles must be a list of exactly two")
        return
    for number, pole in enumerate(poles, start=1):
        if not isinstance(pole, dict):
            err("T079", f"{where}: pole {number} must be a mapping")
            continue
        for key in sorted(set(pole) - {"text", "claim", "niche"}, key=str):
            err("T002", f"{where}: pole {number}: unknown field {key!r}")
        if not _line(pole.get("text")):
            err("T080", f"{where}: pole {number} needs a one-line text")
        has_claim, has_niche = "claim" in pole, "niche" in pole
        if has_claim == has_niche:
            err("T081", f"{where}: pole {number} must be anchored to exactly one of claim or niche")
        elif has_claim:
            if node_types.get(pole["claim"]) != "source-claim":
                err("T082", f"{where}: pole {number}: {pole['claim']!r} is not a source-claim node")
        elif not _line(pole["niche"]):
            err("T081", f"{where}: pole {number}: niche must be a non-empty single line")


def _check_moves(items: list, node_types: dict, c_ids: set, ids: set, err) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            by_id.setdefault(item["id"], item)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            err("T001", f"moves[{index}] must be a mapping")
            continue
        where = _identify(item, "move", index, ids, node_types, err)
        for key in sorted(set(item) - MOVE_FIELDS, key=str):
            err("T002", f"{where}: unknown field {key!r}")
        _common(item, where, err)
        kind = item.get("type")
        if kind not in MOVE_TYPES:
            err("T083", f"{where}: type must be one of {', '.join(MOVE_TYPES)}")
            continue
        cites = _check_cites(item, where, c_ids, by_id, err)
        if kind in CITING_TYPES and not cites:
            err("T084", f"{where}: a {kind} must cite at least one contradiction or move")
        elif kind in ("synthesis", "aufhebung") and len(cites) < 2:
            err("T085", f"{where}: a {kind} must cite at least two contradictions or moves")
        if kind == "negation-of-negation" and cites and not any(
            by_id.get(c, {}).get("type") == "negation" for c in cites
        ):
            err("T086", f"{where}: a negation-of-negation must cite a prior negation")
        for field in AUFHEBUNG_FIELDS:
            if kind == "aufhebung" and not _line(item.get(field)):
                err("T087", f"{where}: an aufhebung must record {field}")
            elif kind != "aufhebung" and field in item:
                err("T088", f"{where}: {field} belongs to an aufhebung move")
        if kind == "opening":
            target = item.get("opens")
            if target is None:
                err("T089", f"{where}: an opening must name the node it opens")
            elif node_types.get(target) not in OPENABLE:
                err("T090", f"{where}: opens {target!r}, which is not a thesis or hypothesis node")
        elif "opens" in item:
            err("T091", f"{where}: opens belongs to an opening move")
    return by_id


def _check_cites(item: dict, where: str, c_ids: set, moves: dict, err) -> list[str]:
    cites = item.get("cites")
    if cites is None:
        return []
    if not isinstance(cites, list) or not all(isinstance(c, str) for c in cites):
        err("T092", f"{where}: cites must be a list of ids")
        return []
    if len(set(cites)) != len(cites):
        err("T092", f"{where}: cites lists an id twice")
    for cited in cites:
        if cited not in c_ids and cited not in moves:
            err("T093", f"{where}: cites {cited!r}, which is not a contradiction or move id")
    return cites


def _check_cycles(moves: dict[str, dict], err) -> None:
    """A move may cite earlier moves; following citations must never come back."""
    graph = {
        mid: [c for c in (m.get("cites") or []) if isinstance(c, str) and c in moves]
        for mid, m in moves.items()
    }
    state: dict[str, int] = {}
    reported: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        state[node] = 1
        for nxt in graph[node]:
            if state.get(nxt) == 1:
                loop = trail[trail.index(nxt):] + [nxt]
                if min(loop) not in reported:
                    reported.add(min(loop))
                    err("T094", "cycle in the move chain: " + " -> ".join(loop))
            elif nxt not in state:
                visit(nxt, trail + [nxt])
        state[node] = 2

    for mid in graph:
        if mid not in state:
            visit(mid, [mid])


def development(data: dict) -> list[dict]:
    """The chain of moves in dependency order (derived, never stored).

    A move comes after every move it cites; ties keep file order. Moves caught in a cycle
    are left out (lint reports the cycle). Each entry carries id, type, text, status,
    cites and opens (None unless an opening).
    """
    by_id: dict[str, dict] = {}
    for move in data.get("moves") or []:
        if isinstance(move, dict) and isinstance(move.get("id"), str):
            by_id.setdefault(move["id"], move)
    deps = {
        mid: [c for c in (m.get("cites") or []) if isinstance(c, str) and c in by_id]
        for mid, m in by_id.items()
    }
    order: list[str] = []
    placed: set[str] = set()
    progress = True
    while progress:
        progress = False
        for mid in by_id:
            if mid not in placed and all(d in placed for d in deps[mid]):
                order.append(mid)
                placed.add(mid)
                progress = True
    return [
        {
            "id": mid,
            "type": by_id[mid].get("type"),
            "text": by_id[mid].get("text"),
            "status": by_id[mid].get("status"),
            "cites": list(by_id[mid].get("cites") or []),
            "opens": by_id[mid].get("opens"),
        }
        for mid in order
    ]


# ------------------------------------------------------------------ gaps, view

GAP_KINDS = ("contradiction-unmoved", "move-without-opening", "thesis-untraced")
UNTRACED_FIELD = "untraced-reason"


def _live(items: object) -> list[dict]:
    return [
        i for i in items or []
        if isinstance(i, dict) and isinstance(i.get("id"), str) and i.get("status") != "retired"
    ]


def _label(item: dict) -> str:
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    poles = [p.get("text", "") for p in item.get("poles") or [] if isinstance(p, dict)]
    return " / ".join(p for p in poles if isinstance(p, str)) or item["id"]


def _cited_by(moves: list[dict]) -> dict[str, list[str]]:
    cited: dict[str, list[str]] = {}
    for move in moves:
        for target in move.get("cites") or []:
            if isinstance(target, str):
                cited.setdefault(target, []).append(move["id"])
    return cited


def _opened_by(moves: list[dict]) -> dict[str, list[str]]:
    opened: dict[str, list[str]] = {}
    for move in moves:
        if move.get("type") == "opening" and isinstance(move.get("opens"), str):
            opened.setdefault(move["opens"], []).append(move["id"])
    return opened


def gaps(data: dict, kinds=GAP_KINDS) -> list[dict]:
    """Dialectic gaps of a valid map; empty unless the map uses the section (decision 0083).

    ``contradiction-unmoved``: a live contradiction no live move cites.
    ``move-without-opening``: a live move no live move cites that is not an opening (the
    chain ends without opening a thesis or question).
    ``thesis-untraced``: a live thesis no live opening opens and with no ``untraced-reason``.
    Sorted by kind then id.
    """
    if not uses_section(data):
        return []
    moves = _live(data.get("moves"))
    cited = _cited_by(moves)
    opened = _opened_by(moves)
    found: list[dict] = []
    if "contradiction-unmoved" in kinds:
        for item in _live(data.get("contradictions")):
            if item["id"] not in cited:
                found.append(
                    {"kind": "contradiction-unmoved", "id": item["id"], "text": _label(item)}
                )
    if "move-without-opening" in kinds:
        for move in moves:
            if move.get("type") != "opening" and move["id"] not in cited:
                found.append(
                    {"kind": "move-without-opening", "id": move["id"], "text": _label(move)}
                )
    if "thesis-untraced" in kinds:
        for node in _live(data.get("nodes")):
            if (
                node.get("type") == "thesis"
                and node["id"] not in opened
                and not _line(node.get(UNTRACED_FIELD))
            ):
                found.append({"kind": "thesis-untraced", "id": node["id"], "text": _label(node)})
    return sorted(found, key=lambda g: (g["kind"], g["id"]))


def view(data: dict) -> dict:
    """The read-only dialectic view: contradictions, the derived move chain, theses, gaps.

    Deterministic: contradictions and theses keep file order, moves follow ``development``.
    """
    moves = _live(data.get("moves"))
    cited = _cited_by(moves)
    opened = _opened_by(moves)
    return {
        "used": uses_section(data),
        "contradictions": [
            {
                "id": c["id"],
                "kind": c.get("kind"),
                "status": c.get("status"),
                "text": _label(c),
                "poles": [
                    {k: p[k] for k in ("text", "claim", "niche") if k in p}
                    for p in c.get("poles") or []
                    if isinstance(p, dict)
                ],
                "moved-by": sorted(cited.get(c["id"], [])),
            }
            for c in data.get("contradictions") or []
            if isinstance(c, dict) and isinstance(c.get("id"), str)
        ],
        "moves": development(data),
        "theses": [
            {
                "id": n["id"],
                "status": n.get("status"),
                "opened-by": sorted(opened.get(n["id"], [])),
                "untraced-reason": n.get(UNTRACED_FIELD),
            }
            for n in data.get("nodes") or []
            if isinstance(n, dict) and n.get("type") == "thesis" and isinstance(n.get("id"), str)
        ],
        "gaps": gaps(data),
    }


def format_text(report: dict) -> str:
    """Plain-text rendering of :func:`view` (one line per item)."""
    if not report["used"]:
        return "No contradictions or moves declared; the dialectic stage is off."
    lines = ["Contradictions:"]
    for c in report["contradictions"]:
        moved = ", ".join(c["moved-by"]) or "unmoved"
        lines.append(f"  {c['id']} [{c['kind']}, {c['status']}] {c['text']} -> {moved}")
    lines.append("Moves:")
    for m in report["moves"]:
        tail = f" opens {m['opens']}" if m["opens"] else ""
        cites = f" cites {', '.join(m['cites'])}" if m["cites"] else ""
        lines.append(f"  {m['id']} [{m['type']}, {m['status']}]{cites}{tail}: {m['text']}")
    lines.append("Gaps:")
    lines += [f"  {g['kind']} {g['id']}: {g['text']}" for g in report["gaps"]] or ["  none"]
    return "\n".join(lines)
