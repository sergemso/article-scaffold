"""Theses map: loading and validation of ``theses.yaml``.

Offline and deterministic. Output carries ids and one-line text only.
"""

from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path

import yaml

from .diagnostics import Diagnostics
from .latex import strip_comments

MAP_FILE = "theses.yaml"
NODE_TYPES = ("thesis", "hypothesis", "objection", "defense", "source-claim", "argument")
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
    "conclusion",
    "inference",
    "premises",
    "steps",
    "premise-ref",
    "author",
    "target",
    "form",
    "strongest-form",
    "tradition",
    "kind",
    "counterexample",
    "severity",
    "answers",
    "move",
    "cost",
    "needs-rival-objection",
}
ARGUMENT_FIELDS = ("conclusion", "inference", "premises", "steps")
# Fields that only make sense on one node type; anywhere else they are an error.
OBJECTION_FIELDS = (
    "target",
    "form",
    "strongest-form",
    "tradition",
    "kind",
    "counterexample",
    "severity",
    "premise-ref",
)
DEFENSE_FIELDS = ("answers", "move", "cost")
TYPE_FIELDS = {
    "argument": ARGUMENT_FIELDS,
    "objection": OBJECTION_FIELDS,
    "defense": DEFENSE_FIELDS,
    "thesis": ("needs-rival-objection",),
}
AUTHORS = ("agent", "human")
FORMS = ("strongest", "standard")
TRADITIONS = ("internal", "rival", "adjacent", "none")
OBJECTION_KINDS = (
    "counterexample",
    "undercut",
    "rebuttal",
    "scope",
    "hidden-premise",
    "evidence",
)
SEVERITIES = ("fatal", "serious", "minor")
MOVES = (
    "concede-scope",
    "distinguish",
    "deny-premise",
    "accept-cost",
    "cite-evidence",
    "reformulate",
)
COSTLY_MOVES = ("accept-cost", "concede-scope")
TERM_FIELDS = {
    "id",
    "name",
    "forms",
    "kind",
    "anchor",
    "source",
    "expansion",
    "definition",
    "senses",
    "children",
    "status",
    "author",
    "accepted-by",
    "match",
    "scope",
}
TERM_KINDS = ("defined", "external", "acronym")
# The field each term kind must carry (decision 0076).
TERM_KIND_FIELD = {"defined": "anchor", "external": "source", "acronym": "expansion"}
TERM_MATCHES = ("phrase-only", "word")
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
INFERENCES = (
    "deduction",
    "modus-ponens",
    "modus-tollens",
    "disjunctive-syllogism",
    "induction",
    "abduction",
    "analogy",
    "authority",
)
# Forms whose validity is a matter of form: one premise is rarely enough.
DEDUCTIVE = ("deduction", "modus-ponens", "modus-tollens")
PREMISE_FIELDS = {"n", "text", "kind", "role", "ref", "status"}
PREMISE_KINDS = ("explicit", "implicit")
PREMISE_ROLES = ("required", "supports-conclusion")
STEP_FIELDS = {"from", "to", "rule"}
EDGE_FIELDS = {"from", "to", "type"}
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
# Tokens that mark an agent or model rather than a person.
AGENT_TOKENS = frozenset(
    {"agent", "ai", "assistant", "bot", "claude", "gpt", "llm", "model", "skill", "team"}
)


def is_agent_name(name: str) -> bool:
    """True when *name* looks like an agent role, not a person."""
    tokens = re.split(r"[^a-z0-9]+", str(name).lower())
    return any(token in AGENT_TOKENS for token in tokens)


def paper_labels(root: Path) -> set[str]:
    """All ``\\label`` names in ``paper/**/*.tex`` (comments stripped)."""
    labels: set[str] = set()
    for tex in sorted((root / "paper").rglob("*.tex")):
        content = strip_comments(tex.read_text(encoding="utf-8"))
        labels.update(m.group(1).strip() for m in LABEL_RE.finditer(content))
    return labels


def paper_bib_keys(root: Path) -> set[str] | None:
    """Keys in ``paper/refs.bib`` (comments stripped), or None when there is no file."""
    refs = root / "paper" / "refs.bib"
    if not refs.is_file():
        return None
    text = strip_comments(refs.read_text(encoding="utf-8"))
    return {m.group(1) for m in BIB_ENTRY_RE.finditer(text)}


def structure_errors(data: object) -> Diagnostics:
    """Schema and graph rules without the anchor check (gaps reports those)."""
    diagnostics = Diagnostics()
    validate_map(data, None, diagnostics)
    return diagnostics


def load_map(root: Path) -> dict | None:
    """Return the parsed map, or None when the file is absent."""
    path = root / MAP_FILE
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_map(
    data: object,
    labels: set[str] | None,
    diagnostics: Diagnostics,
    bib: set[str] | None = None,
) -> None:
    """Check *data* against the map rules.

    *labels* are the paper's labels and *bib* its bibliography keys; None skips that check.
    """

    def err(code: str, message: str) -> None:
        diagnostics.error(MAP_FILE, 0, code, message)

    def warn(code: str, message: str) -> None:
        diagnostics.warning(MAP_FILE, 0, code, message)

    if not isinstance(data, dict):
        err("T001", "theses.yaml must be a mapping")
        return
    for key in sorted(set(data) - {"version", "nodes", "edges", "terms"}, key=str):
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
    _check_arguments(nodes, err, warn)
    _check_adversarial(nodes, edges, bib, err, warn)
    _check_terms(data.get("terms"), labels, err)


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
    for owner, fields in TYPE_FIELDS.items():
        if node.get("type") != owner:
            for field in fields:
                if field in node:
                    err("T017", f"{where}: {field} belongs to {_article(owner)} node")
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


def _article(node_type: str) -> str:
    return ("an " if node_type[0] in "aeiou" else "a ") + node_type


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _premises(node: dict, where: str, err) -> list[dict]:
    """The well-formed premises of an argument; reports the malformed ones."""
    raw = node.get("premises")
    if not isinstance(raw, list) or not raw:
        err("T021", f"{where}: premises must be a non-empty list")
        return []
    good: list[dict] = []
    for position, premise in enumerate(raw, 1):
        label = f"{where} premise #{position}"
        if not isinstance(premise, dict):
            err("T021", f"{label} must be a mapping")
            continue
        for key in sorted(set(premise) - PREMISE_FIELDS, key=str):
            err("T021", f"{label}: unknown field {key!r}")
        text = premise.get("text")
        if not isinstance(text, str) or not text.strip() or "\n" in text.strip():
            err("T021", f"{label}: text must be a non-empty single line")
        if not _is_count(premise.get("n")):
            err("T021", f"{label}: n must be a positive integer")
        choices = (("kind", PREMISE_KINDS), ("role", PREMISE_ROLES), ("status", STATUSES))
        for field, allowed in choices:
            if field in premise and premise[field] not in allowed:
                err("T021", f"{label}: {field} must be one of {', '.join(allowed)}")
        good.append(premise)
    return good


def _check_argument(node: dict, nodes: dict[str, dict], err, warn) -> None:
    where = f"node {node['id']!r}"
    for field in ("conclusion", "inference", "premises"):
        if field not in node:
            err("T018", f"{where}: argument requires {field}")
    conclusion = nodes.get(node.get("conclusion"))
    if "conclusion" in node:
        if conclusion is None:
            err("T019", f"{where}: conclusion {node['conclusion']!r} is not a node id")
        elif conclusion.get("type") not in ("thesis", "hypothesis"):
            err("T019", f"{where}: conclusion must be a thesis or hypothesis node")
    inference = node.get("inference")
    if "inference" in node and inference not in INFERENCES:
        err("T020", f"{where}: inference must be one of {', '.join(INFERENCES)}")
    if "premises" not in node:
        return
    premises = _premises(node, where, err)
    numbers = [p["n"] for p in premises if _is_count(p.get("n"))]
    if numbers != list(range(1, len(numbers) + 1)):
        err("T022", f"{where}: premise numbers must be unique and consecutive from 1")
    for premise in premises:
        ref = premise.get("ref")
        if ref is not None and nodes.get(ref, {}).get("type") != "source-claim":
            err("T024", f"{where}: premise ref {ref!r} is not a source-claim node")
    steps = node.get("steps")
    if steps is not None:
        _check_steps(steps, set(numbers), where, err)
    if inference in DEDUCTIVE and len(premises) == 1:
        warn("T026", f"{where}: a {inference} argument with one premise probably hides one")
    if node.get("status") != "accepted":
        return
    for premise in premises:
        if premise.get("kind") == "implicit" and premise.get("status") != "accepted":
            err("T025", f"{where}: implicit premise {premise.get('n')} is not accepted yet")
    stale = conclusion is not None and conclusion.get("status") == "retired"
    for premise in premises:
        if premise.get("role", "required") != "required":
            continue
        if premise.get("status") == "retired":
            stale = True
        elif nodes.get(premise.get("ref"), {}).get("status") == "retired":
            stale = True
    if stale:
        warn("T027", f"{where}: accepted, but its conclusion or a required premise is retired")


def _check_steps(steps: object, numbers: set[int], where: str, err) -> None:
    if not isinstance(steps, list):
        err("T023", f"{where}: steps must be a list")
        return
    for position, step in enumerate(steps, 1):
        label = f"{where} step #{position}"
        if not isinstance(step, dict):
            err("T023", f"{label} must be a mapping")
            continue
        for key in sorted(set(step) - STEP_FIELDS, key=str):
            err("T023", f"{label}: unknown field {key!r}")
        sources = step.get("from")
        if not isinstance(sources, list) or not sources or not all(_is_count(n) for n in sources):
            err("T023", f"{label}: from must be a list of premise numbers")
        else:
            for n in sources:
                if n not in numbers:
                    err("T023", f"{label}: from names premise {n}, which does not exist")
        if not isinstance(step.get("to"), str) or not step["to"].strip():
            err("T023", f"{label}: to must be a non-empty string")
        if step.get("rule") not in INFERENCES:
            err("T023", f"{label}: rule must be one of {', '.join(INFERENCES)}")


def _check_arguments(raw_nodes: list, err, warn) -> None:
    """Rules that need every node known: arguments and premise-refs."""
    nodes = {
        n["id"]: n
        for n in raw_nodes
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }
    for node in nodes.values():
        if node.get("type") == "argument":
            _check_argument(node, nodes, err, warn)
    for node in nodes.values():
        ref = node.get("premise-ref")
        if ref is None or node.get("type") != "objection":
            continue
        where = f"node {node['id']!r}"
        target = nodes.get(ref.get("argument")) if isinstance(ref, dict) else None
        if not isinstance(ref, dict) or set(ref) != {"argument", "n"}:
            err("T028", f"{where}: premise-ref must be {{argument, n}}")
        elif target is None or target.get("type") != "argument":
            err("T028", f"{where}: premise-ref {ref['argument']!r} is not an argument node")
        elif ref["n"] not in {
            p.get("n") for p in target.get("premises") or [] if isinstance(p, dict)
        }:
            err("T028", f"{where}: premise-ref names premise {ref['n']!r}, which does not exist")


def _lookup(nodes: dict[str, dict], key: object) -> dict | None:
    """The node with id *key*, or None (also for an unhashable or non-string *key*)."""
    return nodes.get(key) if isinstance(key, str) else None


def _one_line(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value.strip()


def _check_objection(node, nodes, bib, err) -> None:
    where = f"node {node['id']!r}"
    extra = [f for f in OBJECTION_FIELDS if f != "premise-ref" and f in node]
    if extra and "target" not in node and "premise-ref" not in node:
        err("T030", f"{where}: an objection with {extra[0]} needs a target")
    if "target" in node and _lookup(nodes, node["target"]) is None:
        err("T030", f"{where}: target {node['target']!r} is not a node id")
    ref = node.get("premise-ref")
    if "target" in node and isinstance(ref, dict) and ref.get("argument") != node["target"]:
        err("T038", f"{where}: premise-ref names a different argument than target")
    for field, allowed in (
        ("form", FORMS),
        ("tradition", TRADITIONS),
        ("kind", OBJECTION_KINDS),
        ("severity", SEVERITIES),
    ):
        if field in node and node[field] not in allowed:
            err("T029", f"{where}: {field} must be one of {', '.join(allowed)}")
    strongest = node.get("strongest-form")
    if node.get("form") == "strongest" and not isinstance(strongest, dict):
        err("T031", f"{where}: a strongest objection needs strongest-form source and restated")
    if "strongest-form" in node:
        _check_strongest_form(strongest, where, nodes, bib, err)
    example = node.get("counterexample")
    if node.get("kind") == "counterexample" and not isinstance(example, dict):
        err("T033", f"{where}: a counterexample needs counterexample case and why-it-bites")
    if "counterexample" in node:
        if not isinstance(example, dict) or set(example) - {"case", "why-it-bites"}:
            err("T029", f"{where}: counterexample must be {{case, why-it-bites}}")
        else:
            for field in ("case", "why-it-bites"):
                if not _one_line(example.get(field)):
                    err("T033", f"{where}: counterexample needs {field}")


def _check_strongest_form(strongest, where, nodes, bib, err) -> None:
    if not isinstance(strongest, dict) or set(strongest) - {"source", "restated"}:
        err("T029", f"{where}: strongest-form must be {{source, restated}}")
        return
    for field in ("source", "restated"):
        if not _one_line(strongest.get(field)):
            err("T031", f"{where}: strongest-form needs {field}")
    source = strongest.get("source")
    if not _one_line(source):
        return
    if source in nodes:
        if nodes[source].get("type") != "source-claim":
            err("T032", f"{where}: strongest-form source {source!r} is not a source-claim")
    elif bib is not None and source not in bib:
        err("T032", f"{where}: strongest-form source {source!r} is not a node id or bib key")


def _check_defense(node, nodes, supporters, err) -> None:
    where = f"node {node['id']!r}"
    if "answers" in node:
        target = _lookup(nodes, node["answers"])
        if target is None or target.get("type") != "objection":
            err("T034", f"{where}: answers {node['answers']!r} is not an objection node")
    if "move" in node and node["move"] not in MOVES:
        err("T029", f"{where}: move must be one of {', '.join(MOVES)}")
    if "cost" in node and not _one_line(node["cost"]):
        err("T029", f"{where}: cost must be a non-empty single line")
    if node.get("move") in COSTLY_MOVES and "cost" not in node:
        err("T035", f"{where}: move {node['move']} needs a cost")
    if node.get("move") == "cite-evidence":
        if not any(nodes.get(s, {}).get("type") == "source-claim" for s in supporters):
            err("T036", f"{where}: cite-evidence needs a source-claim node that supports it")


def _check_adversarial(raw_nodes: list, raw_edges: list, bib, err, warn) -> None:
    """Objection and defense rules that need every node known (decision 0074)."""
    nodes = {
        n["id"]: n
        for n in raw_nodes
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }
    supporters: dict[str, list[str]] = {}
    for edge in raw_edges:
        if isinstance(edge, dict) and edge.get("type") == "supports":
            supporters.setdefault(edge.get("to"), []).append(edge.get("from"))
    seen: dict[tuple, str] = {}
    for node in nodes.values():
        if "author" in node and node["author"] not in AUTHORS:
            err("T029", f"node {node['id']!r}: author must be one of {', '.join(AUTHORS)}")
        if "needs-rival-objection" in node and not isinstance(node["needs-rival-objection"], bool):
            err("T029", f"node {node['id']!r}: needs-rival-objection must be true or false")
        if node.get("type") == "objection":
            _check_objection(node, nodes, bib, err)
            ref = node.get("premise-ref")
            ref = ref if isinstance(ref, dict) else {}
            target = node.get("target") or ref.get("argument")
            kind = node.get("kind")
            if (
                isinstance(target, str)
                and isinstance(kind, str)
                and node.get("status") != "retired"
            ):
                n = ref.get("n")
                key = (target, kind, n if isinstance(n, int) else None)
                if key in seen:
                    warn("T037", f"node {node['id']!r}: duplicates objection {seen[key]!r}")
                else:
                    seen[key] = node["id"]
        elif node.get("type") == "defense":
            _check_defense(node, nodes, supporters.get(node["id"], []), err)


# ---------------------------------------------------------------------- terms


def _text_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _check_terms(raw: object, labels, err) -> None:
    """Structure of the ``terms`` section (decision 0076); the scan is in ``terms.py``."""
    if raw is None:
        return
    if not isinstance(raw, list):
        err("T001", "terms must be a list")
        return
    seen: set[str] = set()
    for index, term in enumerate(raw):
        if not isinstance(term, dict):
            err("T001", f"terms[{index}] must be a mapping")
            continue
        term_id = term.get("id")
        where = f"term {term_id!r}" if isinstance(term_id, str) else f"terms[{index}]"
        for key in sorted(set(term) - TERM_FIELDS, key=str):
            err("T002", f"{where}: unknown field {key!r}")
        if not isinstance(term_id, str) or not ID_RE.match(term_id):
            err("T004", f"{where}: id must match {ID_RE.pattern}")
        elif term_id in seen:
            err("T039", f"duplicate term id {term_id!r}")
        else:
            seen.add(term_id)
        if not _one_line(term.get("name")):
            err("T040", f"{where}: name must be a non-empty single line")
        kind = term.get("kind")
        if kind not in TERM_KINDS:
            err("T041", f"{where}: kind must be one of {', '.join(TERM_KINDS)}")
        else:
            needed = TERM_KIND_FIELD[kind]
            if not _one_line(term.get(needed)):
                err("T042", f"{where}: kind {kind} requires {needed}")
        for field in ("forms", "scope"):
            if field in term and not _text_list(term[field]):
                err("T043", f"{where}: {field} must be a list of non-empty strings")
        if term.get("status") not in STATUSES:
            err("T008", f"{where}: status must be one of {', '.join(STATUSES)}")
        if "author" in term and term["author"] not in AUTHORS:
            err("T044", f"{where}: author must be one of {', '.join(AUTHORS)}")
        if "match" in term and term["match"] not in TERM_MATCHES:
            err("T045", f"{where}: match must be one of {', '.join(TERM_MATCHES)}")
        by = term.get("accepted-by")
        if term.get("status") == "accepted" and not (isinstance(by, str) and by.strip()):
            err("T012", f"{where}: accepted term needs accepted-by")
        if isinstance(by, str) and is_agent_name(by):
            err("T013", f"{where}: accepted-by names an agent role, not a person")
        anchors = [("anchor", term.get("anchor"))]
        senses = term.get("senses", [])
        if not isinstance(senses, list):
            err("T046", f"{where}: senses must be a list")
            senses = []
        for number, sense in enumerate(senses, start=1):
            if not isinstance(sense, dict) or not _one_line(sense.get("anchor")):
                err("T046", f"{where}: senses[{number}] needs an anchor")
                continue
            for key in sorted(set(sense) - {"anchor", "definition"}, key=str):
                err("T002", f"{where}: senses[{number}]: unknown field {key!r}")
            anchors.append((f"senses[{number}] anchor", sense["anchor"]))
        for field, value in anchors:
            if (
                isinstance(value, str)
                and value
                and labels is not None
                and value not in labels
            ):
                err("T047", f"{where}: {field} {value!r} is not a \\label in paper/")
        _check_term_children(term.get("children"), where, err)


def _check_term_children(children: object, where: str, err) -> None:
    if children is None:
        return
    if not isinstance(children, list):
        err("T048", f"{where}: children must be a list")
        return
    seen: set[str] = set()
    for child in children:
        if not isinstance(child, dict):
            err("T048", f"{where}: each child must be a mapping")
            continue
        child_id = child.get("id")
        for key in sorted(set(child) - {"id", "name", "forms", "definition"}, key=str):
            err("T002", f"{where}: child {child_id!r}: unknown field {key!r}")
        if not isinstance(child_id, str) or not ID_RE.match(child_id):
            err("T048", f"{where}: child id must match {ID_RE.pattern}")
        elif child_id in seen:
            err("T039", f"{where}: duplicate child id {child_id!r}")
        else:
            seen.add(child_id)
        if not _one_line(child.get("name")):
            err("T048", f"{where}: child {child_id!r} needs a one-line name")
        if "forms" in child and not _text_list(child["forms"]):
            err("T043", f"{where}: child {child_id!r}: forms must be a list of strings")


# ---------------------------------------------------------------- lint, gaps

DEFAULT_GAP_KINDS = (
    "thesis-unsupported",
    "objection-undefended",
    "objection-fatal-undefended",
    "single-source",
    "anchor-missing",
    "defense-no-answers",
    "defense-no-anchor",
    "thesis-no-rival",
    "term-unregistered",
)
GAP_KINDS = DEFAULT_GAP_KINDS + ("thesis-unattacked",)


def lint(root: Path) -> Diagnostics:
    """Schema plus graph rules for the map in *root*."""
    diagnostics = Diagnostics()
    path = root / MAP_FILE
    if not path.is_file():
        diagnostics.error(MAP_FILE, 0, "T000", "theses.yaml not found")
        return diagnostics
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        diagnostics.error(MAP_FILE, 0, "T001", f"invalid YAML: {exc}")
        return diagnostics
    validate_map(data, paper_labels(root), diagnostics, paper_bib_keys(root))
    return diagnostics


def _nodes(data: dict) -> dict[str, dict]:
    return {n["id"]: n for n in data.get("nodes") or []}


def _incoming(data: dict, target: str, edge_type: str, nodes: dict) -> list[dict]:
    found = []
    for edge in data.get("edges") or []:
        if edge["to"] == target and edge["type"] == edge_type:
            source = nodes.get(edge["from"])
            if source is not None:
                found.append(source)
    return found


def _brief(node: dict) -> dict:
    return {"id": node["id"], "type": node["type"], "status": node["status"], "text": node["text"]}


def gaps(data: dict, labels: set[str] | None, kinds=DEFAULT_GAP_KINDS) -> list[dict]:
    """Gaps in a valid map, sorted by kind then id. Ids and one-line text only."""
    nodes = _nodes(data)
    found: list[dict] = []

    def add(kind: str, node: dict) -> None:
        if kind in kinds:
            found.append({"kind": kind, "id": node["id"], "text": node["text"]})

    for node in nodes.values():
        if node["status"] == "retired":
            continue
        kind = node["type"]
        if kind == "thesis":
            support = [
                s
                for s in _incoming(data, node["id"], "supports", nodes)
                if s["status"] != "retired"
            ]
            if not support:
                add("thesis-unsupported", node)
            attackers = _incoming(data, node["id"], "attacks", nodes)
            if not any(
                a["type"] == "objection" and a["status"] in ("accepted", "retired")
                for a in attackers
            ):
                add("thesis-unattacked", node)
        if kind in ("thesis", "hypothesis"):
            sources = set()
            for s in _incoming(data, node["id"], "supports", nodes):
                if s["type"] == "source-claim" and s["status"] != "retired":
                    keys = s.get("bib_keys") or [s.get("source") or s["id"]]
                    sources.update(keys)
            if len(sources) == 1:
                add("single-source", node)
        if kind == "thesis" and node["status"] == "accepted" and node.get("needs-rival-objection"):
            attackers = {a["id"] for a in _incoming(data, node["id"], "attacks", nodes)}
            rivals = [
                o
                for o in nodes.values()
                if o["type"] == "objection"
                and o["status"] != "retired"
                and o.get("tradition") == "rival"
                and (o.get("target") == node["id"] or o["id"] in attackers)
            ]
            if not rivals:
                add("thesis-no-rival", node)
        if kind == "objection":
            defenses = [
                d
                for d in _incoming(data, node["id"], "rebuts", nodes)
                if d["type"] == "defense" and d["status"] != "retired"
            ] + [
                d
                for d in nodes.values()
                if d["type"] == "defense"
                and d["status"] != "retired"
                and d.get("answers") == node["id"]
            ]
            if not defenses:
                add(
                    "objection-fatal-undefended"
                    if node.get("severity") == "fatal"
                    else "objection-undefended",
                    node,
                )
        if kind == "defense":
            used = "move" in node or "cost" in node
            if used and "answers" not in node:
                add("defense-no-answers", node)
            if (used or "answers" in node) and not node.get("anchor"):
                add("defense-no-anchor", node)
        anchor = node.get("anchor")
        if anchor and labels is not None and anchor not in labels:
            add("anchor-missing", node)
    # A fatal objection with no answer comes first, then kind and id.
    return sorted(
        found,
        key=lambda g: (g["kind"] != "objection-fatal-undefended", g["kind"], g["id"]),
    )


# --------------------------------------------------------------------- slice


def slice_map(data: dict, node_id: str, depth: int = 1) -> dict:
    """Node plus neighbourhood within *depth* edges (either direction)."""
    nodes = _nodes(data)
    if node_id not in nodes:
        raise KeyError(f"no node {node_id!r}")
    edges = data.get("edges") or []
    reach = {node_id: 0}
    queue = deque([node_id])
    while queue:
        current = queue.popleft()
        if reach[current] >= depth:
            continue
        for edge in edges:
            for a, b in ((edge["from"], edge["to"]), (edge["to"], edge["from"])):
                if a == current and b not in reach and b in nodes:
                    reach[b] = reach[current] + 1
                    queue.append(b)
    return {
        "root": node_id,
        "depth": depth,
        "nodes": [_brief(nodes[i]) for i in sorted(reach)],
        "edges": sorted(
            (
                {"from": e["from"], "to": e["to"], "type": e["type"]}
                for e in edges
                if e["from"] in reach and e["to"] in reach
            ),
            key=lambda e: (e["from"], e["to"], e["type"]),
        ),
    }


# -------------------------------------------------------------------- accept


class AcceptError(Exception):
    """The requested promotion is refused."""


def accept_text(text: str, node_id: str, by: str) -> tuple[str, bool]:
    """Return (new text, changed) with *node_id* accepted by *by*.

    Edits only that node's lines, so comments and ordering elsewhere survive.
    """
    by = by.strip()
    if not by or "\n" in by:
        raise AcceptError("--by needs a one-line name")
    if is_agent_name(by):
        raise AcceptError(f"{by!r} names an agent role; only a person accepts")
    root = yaml.compose(text)
    mapping = None
    for key, value in root.value:
        if key.value == "nodes":
            for item in value.value:
                fields = {k.value: v for k, v in item.value}
                if "id" in fields and fields["id"].value == node_id:
                    mapping = item
    if mapping is None:
        raise AcceptError(f"no node {node_id!r}")
    if mapping.flow_style:
        raise AcceptError(f"node {node_id!r} is in flow style; edit it by hand")
    fields = {k.value: v for k, v in mapping.value}
    if "status" not in fields:
        raise AcceptError(f"node {node_id!r} has no status; run `theses lint`")
    status = fields["status"].value
    if status == "retired":
        raise AcceptError(f"node {node_id!r} is retired")
    current = fields["accepted-by"].value if "accepted-by" in fields else None
    if status == "accepted" and current == by:
        return text, False
    if status == "accepted" and current:
        raise AcceptError(f"node {node_id!r} is already accepted by {current!r}")

    edits: list[tuple[int, int, str]] = []
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    quoted = json.dumps(by, ensure_ascii=False)
    status_node = fields["status"]
    edits.append((status_node.start_mark.index, status_node.end_mark.index, "accepted"))
    if "accepted-by" in fields:
        by_node = fields["accepted-by"]
        edits.append((by_node.start_mark.index, by_node.end_mark.index, quoted))
    else:
        last = mapping.value[-1][1]
        stop = len(text[: last.end_mark.index].rstrip())
        end_line = text.count("\n", 0, stop)
        indent = " " * mapping.value[0][0].start_mark.column
        at = starts[end_line + 1] if end_line + 1 < len(starts) else len(text)
        prefix = "" if at == 0 or text[at - 1] == "\n" else "\n"
        edits.append((at, at, f"{prefix}{indent}accepted-by: {quoted}\n"))
    for start, stop, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[stop:]
    return text, True


def accept(root: Path, node_id: str, by: str) -> bool:
    """Promote *node_id*; returns False when nothing changed."""
    path = root / MAP_FILE
    if not path.is_file():
        raise AcceptError("theses.yaml not found")
    old = path.read_text(encoding="utf-8")
    new, changed = accept_text(old, node_id, by)
    if not changed:
        return False
    check = Diagnostics()
    validate_map(yaml.safe_load(new), None, check)
    if not check.ok:
        raise AcceptError("the result would not validate; fix `theses lint` first")
    path.write_text(new, encoding="utf-8")
    return True


# ----------------------------------------------------------------- add nodes


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def append_nodes_text(text: str, new_nodes: list[dict]) -> str:
    """Return *text* with *new_nodes* appended after the last node.

    Only inserts lines: existing nodes, comments and ordering stay byte for byte, so two
    branches that edit different nodes still merge. Values are written as quoted scalars.
    """
    if not new_nodes:
        return text
    root = yaml.compose(text)
    value = None
    for key, item in root.value:
        if key.value == "nodes":
            value = item
    if value is None:
        raise AcceptError("theses.yaml has no nodes list")
    key_indent = 0
    for key, item in root.value:
        if item is value:
            key_indent = key.start_mark.column
    indent = " " * (key_indent + 2)
    block = ""
    for node in new_nodes:
        first = True
        for field, field_value in node.items():
            lead = f"{indent}- " if first else f"{indent}  "
            block += f"{lead}{field}: {_quote(str(field_value))}\n"
            first = False
    if value.flow_style:
        if value.value:
            raise AcceptError("nodes is in flow style; edit the file by hand")
        head = text[: value.start_mark.index].rstrip(" ")
        tail = text[value.end_mark.index :]
        return head + "\n" + block + tail.lstrip(" ").lstrip("\n")
    last = value.value[-1]
    stop = len(text[: last.end_mark.index].rstrip())
    at = text.find("\n", stop)
    at = len(text) if at < 0 else at + 1
    prefix = "" if at == 0 or text[at - 1] == "\n" else "\n"
    return text[:at] + prefix + block + text[at:]


def add_nodes(root: Path, new_nodes: list[dict]) -> None:
    """Append nodes to theses.yaml; refuses a result that would not validate."""
    path = root / MAP_FILE
    if not path.is_file():
        raise AcceptError("theses.yaml not found")
    new = append_nodes_text(path.read_text(encoding="utf-8"), new_nodes)
    check = Diagnostics()
    validate_map(yaml.safe_load(new), None, check)
    if not check.ok:
        raise AcceptError("the result would not validate; fix `theses lint` first")
    path.write_text(new, encoding="utf-8")
