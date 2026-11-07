"""Lifecycle flow: per-stage gates computed from the repo, and the stored decisions.

Offline and deterministic. A gate reads files in the repo; it makes no network or
model call. ``flow.yaml`` stores only what the repo cannot tell: the round number,
human attestations and waivers, and the budget used (plus the bookkeeping of issued
orders). There is no stage pointer: the current stage is the earliest failing gate.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

import yaml

from . import brief as order_brief
from . import claims, companion, core, group, ledger, theses
from . import index as section_index

STATE_FILE = "flow.yaml"
STATUS_SCHEMA_VERSION = "1.0"
STAGES = (
    "frame",
    "map",
    "discover",
    "draft",
    "verify-sources",
    "adversarial",
    "revise",
    "release-gate",
    "publish",
)
TIERS = ("script", "small", "large")
DEFAULT_WEIGHTS = {"script": 0, "small": 1, "large": 5}
DEFAULT_BUDGET_LIMIT = 20
DEFAULT_RETRY_CAP = 3
DEFAULT_MAX_CALLS = {"small": 40, "large": 60}  # advisory; tune from the cost measurement
STATE_FIELDS = {
    "version",
    "round",
    "weights",
    "budget",
    "retry_cap",
    "attestations",
    "waivers",
    "orders",
    "reviews",
    "closed",
    "brief_bytes",
    "max_calls",
    "group_size",
}
HEADER = (
    "# Flow state: decisions the repo cannot derive (round, attestations, waivers, budget).\n"
    "# Schema: schemas/flow.schema.json. Gates are computed from the repo on every\n"
    "# `flow status`; there is no stage pointer here. Attestations and waivers are\n"
    "# recorded by a person in a terminal (`flow attest`, `flow waive`).\n"
)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAP_GAP_KINDS = ("thesis-unsupported", "objection-undefended", "anchor-missing")


class FlowError(Exception):
    """A flow command is refused or flow.yaml is unusable."""


# --------------------------------------------------------------------- state


def default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "round": 0,
        "weights": dict(DEFAULT_WEIGHTS),
        "budget": {"limit": DEFAULT_BUDGET_LIMIT, "used": 0},
        "retry_cap": DEFAULT_RETRY_CAP,
        "attestations": [],
        "waivers": [],
        "orders": {},
        "reviews": [],
    }


def _is_date(value: object) -> bool:
    if isinstance(value, date):
        return True
    if not isinstance(value, str) or not ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _as_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _nonneg_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def state_errors(data: object) -> list[str]:
    """Rule violations of a parsed flow.yaml (empty when valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["flow.yaml must be a mapping"]
    for key in sorted(set(data) - STATE_FIELDS, key=str):
        errors.append(f"unknown top-level field {key!r}")
    if data.get("version") != 1:
        errors.append("version must be 1")
    if not _nonneg_int(data.get("round")):
        errors.append("round must be a non-negative integer")
    weights = data.get("weights")
    if not isinstance(weights, dict) or set(weights) != set(TIERS):
        errors.append(f"weights must give exactly {', '.join(TIERS)}")
    elif not all(_nonneg_int(v) for v in weights.values()):
        errors.append("weights must be non-negative integers")
    budget = data.get("budget")
    if (
        not isinstance(budget, dict)
        or set(budget) != {"limit", "used"}
        or not all(_nonneg_int(v) for v in budget.values())
    ):
        errors.append("budget must be {limit, used} of non-negative integers")
    if not _nonneg_int(data.get("retry_cap")):
        errors.append("retry_cap must be a non-negative integer")
    errors += _list_errors(data.get("attestations"), "attestations", ("name", "by", "at", "why"))
    errors += _list_errors(
        data.get("waivers"), "waivers", ("stage", "by", "at", "why", "expires")
    )
    for item in data.get("waivers") or []:
        if isinstance(item, dict) and item.get("stage") not in STAGES:
            errors.append(f"waiver stage {item.get('stage')!r} is not a stage")
    if not isinstance(data.get("orders"), dict):
        errors.append("orders must be a mapping")
    if not isinstance(data.get("reviews"), list):
        errors.append("reviews must be a list")
    if "brief_bytes" in data and not (
        _nonneg_int(data["brief_bytes"]) and data["brief_bytes"] >= order_brief.MIN_BRIEF_BYTES
    ):
        errors.append(f"brief_bytes must be an integer of at least {order_brief.MIN_BRIEF_BYTES}")
    if "max_calls" in data:
        calls = data["max_calls"]
        if not isinstance(calls, dict) or not set(calls) <= {"small", "large"}:
            errors.append("max_calls must be a mapping with only small and large")
        elif not all(_nonneg_int(v) and v >= 1 for v in calls.values()):
            errors.append("max_calls values must be positive integers")
    if "group_size" in data and not (
        _nonneg_int(data["group_size"]) and data["group_size"] >= group.MIN_GROUP_SIZE
    ):
        errors.append("group_size must be a positive integer (1 turns grouping off)")
    closed = data.get("closed", [])
    if not isinstance(closed, list) or not all(
        isinstance(c, dict) and set(c) == {"round", "at"} and _nonneg_int(c["round"])
        and _is_date(c["at"])
        for c in closed
    ):
        errors.append("closed must be a list of {round, at}")
    return errors


def _list_errors(items: object, name: str, fields: tuple[str, ...]) -> list[str]:
    if not isinstance(items, list):
        return [f"{name} must be a list"]
    errors = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != set(fields):
            errors.append(f"{name}[{index}] must have exactly {', '.join(fields)}")
            continue
        for field in fields:
            value = item[field]
            if field in ("at", "expires"):
                if not _is_date(value):
                    errors.append(f"{name}[{index}].{field} must be a YYYY-MM-DD date")
            elif not isinstance(value, str) or not value.strip() or "\n" in value:
                errors.append(f"{name}[{index}].{field} must be a non-empty single line")
        if isinstance(item.get("by"), str) and theses.is_agent_name(item["by"]):
            errors.append(f"{name}[{index}].by names an agent role, not a person")
    return errors


def load_state(root: Path) -> dict[str, Any]:
    """The stored state; defaults when flow.yaml is absent. Raises FlowError if invalid."""
    path = root / STATE_FILE
    if not path.is_file():
        return default_state()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FlowError(f"flow.yaml is not valid YAML: {exc}") from exc
    errors = state_errors(data)
    if errors:
        raise FlowError("flow.yaml is invalid: " + "; ".join(errors))
    return data


def save_state(root: Path, state: dict[str, Any]) -> None:
    errors = state_errors(state)
    if errors:
        raise FlowError("refusing to write an invalid flow.yaml: " + "; ".join(errors))
    body = yaml.safe_dump(state, sort_keys=False, allow_unicode=True, default_flow_style=False)
    (root / STATE_FILE).write_text(HEADER + body, encoding="utf-8")


# --------------------------------------------------------------------- facts


class Facts:
    """Lazily computed, memoised views of the repo that gates and orders share."""

    def __init__(self, root: Path, state: dict[str, Any]) -> None:
        self.root = root
        self.state = state
        self._memo: dict[str, Any] = {}

    def _once(self, key: str, make):
        if key not in self._memo:
            self._memo[key] = make()
        return self._memo[key]

    @property
    def map(self) -> tuple[dict | None, str | None]:
        """(map, problem): the parsed map when it validates, else a one-line problem."""

        def make():
            try:
                data = theses.load_map(self.root)
            except yaml.YAMLError:
                return None, "theses.yaml is not valid YAML"
            if data is None:
                return None, "theses.yaml not found"
            if not theses.structure_errors(data).ok:
                return None, "theses.yaml does not validate"
            return data, None

        return self._once("map", make)

    @property
    def gaps(self) -> list[dict]:
        def make():
            data, _ = self.map
            if data is None:
                return []
            return theses.gaps(data, theses.paper_labels(self.root), theses.GAP_KINDS)

        return self._once("gaps", make)

    def gap_ids(self, *kinds: str) -> list[dict]:
        return [g for g in self.gaps if g["kind"] in kinds]

    @property
    def nodes(self) -> dict[str, dict]:
        data, _ = self.map
        return {n["id"]: n for n in (data or {}).get("nodes") or []}

    @property
    def claim_records(self) -> list[dict]:
        def make():
            if self.map[0] is None:
                return []
            return claims.quote_check(self.root)

        return self._once("claims", make)

    @property
    def validation_diagnostics(self) -> list:
        return self._once("validate", lambda: list(core.validate_paper(self.root).errors))

    @property
    def validation_errors(self) -> int:
        return len(self.validation_diagnostics)

    @property
    def index_stale(self) -> list[str]:
        return self._once("index", lambda: section_index.check_index(self.root))

    def check(self, name: str) -> dict[str, Any]:
        return self._once(f"check:{name}", lambda: run_check(self.root, name))

    def attested(self, name: str) -> bool:
        return any(a["name"] == name for a in self.state["attestations"])

    @property
    def counts_script(self) -> bool:
        return (self.root / "scripts" / "lint-counts.py").is_file()

    @property
    def layout_script(self) -> bool:
        return (self.root / "scripts" / "check_pdf_layout.py").is_file()


# ---------------------------------------------------------------------- gates

CMD = "python3 -m scripts.article"


def _verdict(ok: bool, reason: str, command: str) -> dict[str, Any]:
    return {"ok": ok, "reason": reason, "command": command}


def _gate_frame(f: Facts) -> dict[str, Any]:
    command = f"{CMD} theses lint"
    data, problem = f.map
    if data is None:
        return _verdict(False, f"{problem}", command)
    if not any(n["type"] == "thesis" and n["status"] == "accepted" for n in f.nodes.values()):
        return _verdict(False, "no thesis node is accepted by a person", f"{CMD} theses accept")
    return _verdict(True, "an accepted thesis exists", command)


def _gap_gate(f: Facts, kinds: tuple[str, ...], ok_reason: str) -> dict[str, Any]:
    command = f"{CMD} theses gaps " + " ".join(f"--kind {k}" for k in kinds)
    data, problem = f.map
    if data is None:
        return _verdict(False, f"{problem}", f"{CMD} theses lint")
    found = f.gap_ids(*kinds)
    if found:
        ids = ", ".join(sorted({g["id"] for g in found})[:5])
        kind_names = ", ".join(sorted({g["kind"] for g in found}))
        return _verdict(False, f"gaps remain ({kind_names}): {ids}", command)
    return _verdict(True, ok_reason, command)


def untriaged(f: Facts) -> list[str]:
    """Review-item objections that still have no anchor (set by triage)."""
    return sorted(
        n["id"]
        for n in f.nodes.values()
        if n["type"] == "objection" and n["status"] == "proposed"
        and n.get("source") and not n.get("anchor")
    )


def _gate_map(f: Facts) -> dict[str, Any]:
    result = _gap_gate(f, MAP_GAP_KINDS, "no thesis, objection or anchor gaps")
    pending = untriaged(f)
    if result["ok"] and pending:
        return _verdict(
            False, f"review items not triaged (no anchor): {', '.join(pending[:5])}",
            f"{CMD} theses slice {pending[0]}",
        )
    return result


def _gate_discover(f: Facts) -> dict[str, Any]:
    return _gap_gate(f, ("single-source",), "no single-source gaps")


def _validate_and_index(f: Facts, command: str, ok_reason: str) -> dict[str, Any]:
    if f.validation_errors:
        return _verdict(False, f"{f.validation_errors} validation error(s)", f"{CMD} validate")
    stale = f.index_stale
    if stale:
        return _verdict(False, stale[0], f"{CMD} index --check")
    return _verdict(True, ok_reason, command)


def _gate_draft(f: Facts) -> dict[str, Any]:
    return _validate_and_index(f, f"{CMD} validate", "validation passes and the index is current")


def source_claim_state(f: Facts, record: dict) -> str:
    """One of: ok, attested, needs-check, not-found, no-local-text, stale, overstates, contradicts.

    ``stale``: the node's source address names a superseded edition (``claims rebase``).
    """
    if f.attested(f"claim:{record['id']}"):
        return "attested"
    if record["verdict"] in ("not-found", "no-local-text"):
        return record["verdict"]
    if record.get("stale"):
        return "stale"  # the pinned edition was superseded; `claims rebase` proposes an address
    cached = record.get("cached")
    if cached == "supports":
        return "ok"
    return cached if cached in ("overstates", "contradicts") else "needs-check"


def _gate_verify(f: Facts) -> dict[str, Any]:
    command = f"{CMD} claims quote-check --all"
    data, problem = f.map
    if data is None:
        return _verdict(False, f"{problem}", f"{CMD} theses lint")
    bad = [(r["id"], source_claim_state(f, r)) for r in f.claim_records]
    bad = [(i, s) for i, s in bad if s not in ("ok", "attested")]
    if bad:
        ids = ", ".join(f"{i} ({s})" for i, s in bad[:5])
        return _verdict(False, f"source claims not verified: {ids}", command)
    return _verdict(True, "every source claim is verified or attested", command)


def _gate_adversarial(f: Facts) -> dict[str, Any]:
    return _gap_gate(
        f, ("thesis-unattacked", "objection-undefended"), "every thesis is attacked and defended"
    )


def _gate_revise(f: Facts) -> dict[str, Any]:
    result = _validate_and_index(f, f"{CMD} validate", "validation passes and the index is current")
    if result["ok"] and f.counts_script:
        if f.check("lint-counts")["status"] != "pass":
            return _verdict(False, "the counts lint fails", "python3 scripts/lint-counts.py")
    return result


def _gate_release(f: Facts) -> dict[str, Any]:
    command = f"{CMD} release --dry-run"
    if f.validation_errors:
        return _verdict(False, f"{f.validation_errors} validation error(s)", f"{CMD} validate")
    from . import release

    plan = release.plan_release(f.root)
    checks = (plan.get("plan") or {}).get("checks") or {}
    if not plan.get("ok") or not checks.get("has_version") or not checks.get("tag_absent"):
        why = plan.get("error") or "the release plan has a blocking item"
        return _verdict(False, why, command)
    if f.layout_script and f.check("layout-check")["status"] != "pass":
        return _verdict(False, "the layout check fails", "python3 scripts/check_pdf_layout.py")
    if not f.attested("bibliography"):
        return _verdict(False, "no recorded bibliography verification", f"{CMD} flow attest")
    if not cold_run_recorded(f.root):
        return _verdict(
            False, "no cold run matches the current inputs", f"{CMD} check --cold"
        )
    verdict = _verdict(
        True, "release plan clear, bibliography attested, cold run current", command
    )
    verdict["relied_on"] = relied_on(f.root)
    return verdict


def _gate_publish(f: Facts) -> dict[str, Any]:
    return _verdict(
        False, "publishing is a human step; read the release plan", f"{CMD} release --dry-run"
    )


GATES = {
    "frame": _gate_frame,
    "map": _gate_map,
    "discover": _gate_discover,
    "draft": _gate_draft,
    "verify-sources": _gate_verify,
    "adversarial": _gate_adversarial,
    "revise": _gate_revise,
    "release-gate": _gate_release,
    "publish": _gate_publish,
}


# ------------------------------------------------------------- named checks

# Every entry is a fixed argument vector. "article" expands to the vendored CLI and
# "python" to this interpreter; nothing else is ever taken from an order, a file
# or a caller (guardrail flow-checks-are-named-not-supplied).
CHECKS: dict[str, tuple[str, ...]] = {
    "theses-lint": ("article", "theses", "lint"),
    "theses-gaps": ("article", "theses", "gaps"),
    "index-check": ("article", "index", "--check"),
    "claims-quote-check": ("article", "claims", "quote-check", "--all"),
    "make-validate": ("article", "validate"),
    "release-plan": ("article", "release", "--dry-run"),
    "layout-check": ("python", "scripts/check_pdf_layout.py", "paper/article.pdf"),
    "lint-counts": ("python", "scripts/lint-counts.py"),
}
# Checks that need a script the repo may not ship; absent means "unavailable", never pass.
CHECK_SCRIPTS = {
    "layout-check": "scripts/check_pdf_layout.py",
    "lint-counts": "scripts/lint-counts.py",
}
OUTPUT_LIMIT = 400


def argv_for(name: str) -> list[str]:
    parts = CHECKS[name]
    head = {"article": [sys.executable, "-m", "scripts.article"], "python": [sys.executable]}
    return head[parts[0]] + list(parts[1:])


def run_check(root: Path, name: str) -> dict[str, Any]:
    """Run a check from the fixed table: status is pass, fail, unavailable or error.

    A timeout or a process that cannot start is an ``error``, never a ``fail``: it says
    nothing about the paper, so it must not be stored or counted as a verdict.
    """
    if name not in CHECKS:
        raise FlowError(f"unknown check name {name!r}")
    script = CHECK_SCRIPTS.get(name)
    if script is not None and not (root / script).is_file():
        return {"status": "unavailable", "output": f"{script} is not in this repo"}
    try:
        proc = subprocess.run(
            argv_for(name), cwd=root, capture_output=True, text=True, timeout=300, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "output": str(exc)[:OUTPUT_LIMIT]}
    text = " ".join((proc.stdout + proc.stderr).split())
    return {
        "status": "pass" if proc.returncode == 0 else "fail",
        "output": text[:OUTPUT_LIMIT],
        "lines": (proc.stdout + proc.stderr).splitlines(),
    }


# ---------------------------------------------------------- ledgered checks

_ARTICLE_INPUTS = (
    "scripts/article/*.py", "schemas/*.json", "theses.yaml", "metadata.yaml",
    "paper/**/*.tex", "paper/**/*.bib", "paper/sources/**/*",
)  # fmt: skip


class CheckSpec(NamedTuple):
    """What a named check reads. ``inputs`` are repo-relative globs; ``tools`` are declared
    version strings, never found by running a tool. A check that is not ``deterministic``
    is never stored."""

    inputs: tuple[str, ...]
    version: str = "1"
    tools: dict[str, str] = {}
    deterministic: bool = True


# Over-inclusive on purpose: an extra input costs a miss, a missing one serves a wrong hit.
CHECK_SPECS: dict[str, CheckSpec] = {
    "theses-lint": CheckSpec(_ARTICLE_INPUTS),
    "theses-gaps": CheckSpec(_ARTICLE_INPUTS),
    "index-check": CheckSpec(_ARTICLE_INPUTS),
    "claims-quote-check": CheckSpec(_ARTICLE_INPUTS),
    "make-validate": CheckSpec(
        _ARTICLE_INPUTS + ("scripts/validate-paper.py", "paper/figures/**/*")
    ),
    "release-plan": CheckSpec(_ARTICLE_INPUTS, deterministic=False),  # reads git state
    "layout-check": CheckSpec(("scripts/check_pdf_layout.py", "paper/article.pdf")),
    "lint-counts": CheckSpec(("scripts/lint-counts.py", "paper/**/*.tex", "data/**/*")),
}
CHECK_TIER = "script"
FAILING_LINES = 5
FAILING_WIDTH = 200
_LABELLED_SECRET = re.compile(rb"(?i)\b(password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*\S+")


def redact(line: str) -> str:
    """Mask the secret patterns the commit guardrail uses (`companion.SECRET_PATTERNS`)."""
    raw = line.encode("utf-8", "replace")
    for pattern in (*companion.SECRET_PATTERNS, _LABELLED_SECRET):
        raw = pattern.sub(b"[redacted]", raw)
    return raw.decode("utf-8", "replace")


def failing_lines(lines: list[str]) -> list[str]:
    """The first few non-empty output lines, redacted and cut to a fixed width."""
    kept = [" ".join(line.split()) for line in lines if line.strip()]
    return [redact(line)[:FAILING_WIDTH] for line in kept[:FAILING_LINES]]


def _expand(root: Path, patterns: tuple[str, ...]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and not path.is_symlink():
                found[path.relative_to(root).as_posix()] = path
    return found


def check_keyed(root: Path, name: str) -> ledger.Keyed | None:
    """The ledger key of a named check, or None when none of its inputs exists."""
    if name not in CHECKS:
        raise FlowError(f"unknown check name {name!r}")
    found = _expand(root, CHECK_SPECS[name].inputs)
    spec = CHECK_SPECS[name]
    if not found:
        return None
    return ledger.key(
        "check-outcome", found, f"{name}@{spec.version}", CHECK_TIER, spec.tools
    )


def check_read(root: Path, name: str) -> dict[str, Any]:
    """A pure read: ``hit`` with the stored verdict, ``stale`` (an older entry of this check
    exists for other inputs), ``miss`` or ``uncacheable``. Nothing runs and nothing is written."""
    if name not in CHECKS:
        raise FlowError(f"unknown check name {name!r}")
    base = {"ok": True, "command": "check", "name": name}
    if not CHECK_SPECS[name].deterministic:
        return {**base, "state": "uncacheable"}
    keyed = check_keyed(root, name)
    if keyed is None:
        return {**base, "state": "miss", "reason": "no input file exists"}
    entry = ledger.lookup(root, keyed)
    if entry is not None:
        return {
            **base, "state": "hit", "verdict": entry["status"], "key": keyed.key,
            "failing": entry.get("result", {}).get("failing", []),
        }
    nearest = ledger.explain(root, keyed, f"{name}@")
    if nearest["nearest"] is None:
        return {**base, "state": "miss", "key": keyed.key}
    return {**base, "state": "stale", "key": keyed.key, "changed": nearest["changed"],
            "added": nearest["added"], "removed": nearest["removed"]}  # fmt: skip


def check_record(root: Path, name: str) -> dict[str, Any]:
    """Run a check from the fixed table and store a pass or fail.

    The key is computed first, so an unchanged input is a hit and nothing runs. An
    ``error`` or ``unavailable`` outcome and a non-deterministic check are never stored.
    """
    if name not in CHECKS:
        raise FlowError(f"unknown check name {name!r}")
    base = {"command": "check record", "name": name}
    spec = CHECK_SPECS[name]
    keyed = check_keyed(root, name) if spec.deterministic else None
    if keyed is not None:
        entry = ledger.lookup(root, keyed)
        if entry is not None:
            return {
                **base, "ok": entry["status"] == "pass", "state": "hit", "stored": False,
                "verdict": entry["status"],
                "failing": entry.get("result", {}).get("failing", []),
            }
    ran = run_check(root, name)
    status = ran["status"]
    if status not in ("pass", "fail"):
        return {**base, "ok": False, "state": status, "stored": False,
                "failing": failing_lines([ran["output"]])}  # fmt: skip
    failing = failing_lines(ran.get("lines", [])) if status == "fail" else []
    stored = False
    if keyed is not None:
        try:
            stored = ledger.put(
                root, keyed, status, {"check": name, "failing": failing},
                {"author": "script"},
            ) == "created"
        except ledger.LedgerConflict as exc:
            raise FlowError(str(exc)) from exc
    return {**base, "ok": status == "pass", "state": "ran", "stored": stored,
            "verdict": status, "failing": failing}  # fmt: skip


# ----------------------------------------------------------------- cold run

COLD_KIND = "cold-run"
COLD_TIER = "cold"
RELIED_ON_CAP = 50


def cold_keyed(root: Path) -> ledger.Keyed | None:
    """Key over the inputs of every deterministic table check and their versions.

    Any change to a file a check reads makes the key differ, so a cold run never carries
    over to changed inputs and there is no time window.
    """
    found: dict[str, Path] = {}
    versions = []
    for name in sorted(CHECKS):
        spec = CHECK_SPECS[name]
        if not spec.deterministic:
            continue
        versions.append(f"{name}@{spec.version}")
        found.update(_expand(root, spec.inputs))
    if not found:
        return None
    return ledger.key(COLD_KIND, found, "cold-run@1;" + ";".join(versions), COLD_TIER)


def cold_run_recorded(root: Path) -> bool:
    """True when a passing cold-run record matches the current inputs. A pure file read.

    It uses ``ledger.get`` and not ``lookup``, so ``ARTICLE_LEDGER=off`` cannot satisfy it
    and only ``cold_run`` can write the record.
    """
    keyed = cold_keyed(root)
    if keyed is None:
        return False
    entry = ledger.get(root, COLD_KIND, keyed.key)
    return entry is not None and entry["status"] == "pass"


def relied_on(root: Path) -> dict[str, Any]:
    """Tier 2 verdicts a gate rests on, with provenance: no cold run can re-judge them."""
    digests = ledger.keys(root, "claim-verdict")
    entries = []
    for digest in digests[:RELIED_ON_CAP]:
        prov = (ledger.provenance(root, "claim-verdict", digest) or [{}])[0]
        item = {"key": digest[:12], "author": str(prov.get("author", "unknown"))}
        if "recorded" in prov:
            item["recorded"] = str(prov["recorded"])
        entries.append(item)
    return {"count": len(digests), "entries": entries}


def cold_run(root: Path) -> dict[str, Any]:
    """Run every deterministic table check ignoring lookups, then compare with the ledger.

    A stored outcome that differs from the cold one is evicted (logged) and replaced, and
    the run fails: the ledger had served a wrong answer. Only a clean run writes the
    ``cold-run`` record the release gate reads. It is run by CI or the parent session,
    never from ``next_order``.
    """
    if not ledger.enabled():
        error = "the ledger is switched off; a cold run could not be recorded"
        return {"ok": False, "command": "check --cold", "error": error}
    outcomes: dict[str, str] = {}
    differences: list[dict[str, str]] = []
    problems: list[str] = []
    for name in sorted(CHECKS):
        if not CHECK_SPECS[name].deterministic:
            outcomes[name] = "skipped"
            continue
        ran = run_check(root, name)
        status = ran["status"]
        outcomes[name] = status
        if status not in ("pass", "fail"):
            if status == "error":
                problems.append(f"{name}: {ran['output']}")
            continue
        failing = failing_lines(ran.get("lines", [])) if status == "fail" else []
        keyed = check_keyed(root, name)
        if keyed is None:
            continue
        stored = ledger.get(root, "check-outcome", keyed.key)
        result = {"check": name, "failing": failing}
        if stored is not None and (stored["status"], stored.get("result")) != (status, result):
            ledger.evict(
                root, "check-outcome", keyed.key,
                f"cold run differs: ledger said {stored['status']}, cold run says {status}",
            )
            differences.append({"check": name, "ledger": stored["status"], "cold": status})
            stored = None
        if stored is None:
            ledger.put(root, keyed, status, result, {"author": "script", "cold": True})
    failed = sorted(n for n, s in outcomes.items() if s == "fail")
    ok = not (differences or problems or failed)
    recorded = False
    keyed = cold_keyed(root)
    if ok and keyed is not None:
        ledger.put(root, keyed, "pass", {"checks": outcomes}, {"author": "script"})
        recorded = True
    return {"ok": ok, "command": "check --cold", "recorded": recorded, "checks": outcomes,
            "differences": differences, "failed": failed, "errors": problems}  # fmt: skip


# -------------------------------------------------------------------- status


def active_waiver(state: dict[str, Any], stage: str, today: date) -> dict | None:
    for waiver in state["waivers"]:
        if waiver["stage"] == stage and _as_date(waiver["expires"]) >= today:
            return waiver
    return None


def evaluate(facts: Facts, today: date) -> list[dict[str, Any]]:
    """Per-stage results: stage, status (pass|fail|waived|human), reason, command."""
    results = []
    for stage in STAGES:
        verdict = GATES[stage](facts)
        if stage == "publish":
            results.append(
                {"stage": stage, "status": "human", "reason": verdict["reason"],
                 "command": verdict["command"]}
            )
            continue
        status = "pass" if verdict["ok"] else "fail"
        reason = verdict["reason"]
        entry = {"stage": stage, "status": status, "reason": reason, "command": verdict["command"]}
        if "relied_on" in verdict:
            entry["relied_on"] = verdict["relied_on"]
        waiver = None if verdict["ok"] else active_waiver(facts.state, stage, today)
        if waiver is not None:
            entry["status"] = "waived"
            entry["reason"] = (
                f"waived by {waiver['by']} until {_as_date(waiver['expires']).isoformat()} "
                f"({waiver['why']}); gate says: {reason}"
            )
        results.append(entry)
    return results


def current_stage(results: list[dict[str, Any]]) -> str | None:
    """The earliest failing gate; the human publish step when every gate before it passes."""
    for entry in results:
        if entry["status"] in ("fail", "human"):
            return entry["stage"]
    return None


def status(root: Path, today: date | None = None) -> dict[str, Any]:
    state = load_state(root)
    facts = Facts(root, state)
    results = evaluate(facts, today or date.today())
    budget = state["budget"]
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "ok": not any(r["status"] == "fail" for r in results),
        "command": "flow status",
        "round": state["round"],
        "current_stage": current_stage(results),
        "budget": {"limit": budget["limit"], "used": budget["used"]},
        "stages": results,
    }


# -------------------------------------------------------------------- orders

ORDER_SCHEMA_VERSION = "1.0"
MAX_NODES = 20
PROCEDURES = Path("docs") / "procedures"


def procedure(name: str) -> str:
    return (PROCEDURES / f"{name}.md").as_posix()


def order_id(stage: str, kind: str, nodes: list[str], check: str | None) -> str:
    """Stable id: stage, kind, check and sorted node ids, hashed."""
    text = "|".join([stage, kind, check or "", *sorted(nodes)])
    return "o-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def make_order(
    stage: str,
    kind: str,
    *,
    nodes: list[str] | None = None,
    outputs: list[str] | None = None,
    tier: str = "small",
    proc: str | None = None,
    check: str | None = None,
    gated: bool = False,
    needs_human: bool = False,
    confirm: str | None = None,
    reason: str,
) -> dict[str, Any]:
    """An order carries ids, paths and names only; never manuscript or source text."""
    ids = sorted(nodes or [])[:MAX_NODES]
    return {
        "id": order_id(stage, kind, ids, check),
        "stage": stage,
        "kind": kind,
        "nodes": ids,
        "outputs": list(outputs or []),
        "tier": tier,
        "procedure": proc,
        "check": check,
        "gated": gated,
        "retries": 0,
        "needs_human": needs_human,
        "confirm": confirm,
        "reason": reason,
    }


def _map_problem_order(stage: str, f: Facts) -> dict[str, Any]:
    _, problem = f.map
    if problem == "theses.yaml not found":
        return make_order(
            stage, "state-thesis", tier="script", needs_human=True, reason=problem
        )
    return make_order(
        stage, "fix-validation", outputs=["theses.yaml"], check="theses-lint",
        reason=f"{problem}; run theses lint",
    )


def _by_node(gaps: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for gap in gaps:
        grouped.setdefault(gap["id"], []).append(gap["kind"])
    return grouped


def _node_output(node_id: str) -> list[str]:
    return [f"{theses.MAP_FILE}#{node_id}"]


def orders_for(stage: str, f: Facts) -> list[dict[str, Any]]:
    """Open orders for *stage*, in a stable order (the first is the one to issue)."""
    if stage == "publish":
        return [
            make_order(
                stage, "publish", tier="script", needs_human=True,
                reason="deposit and tag are irreversible; read the release plan and decide",
            )
        ]
    needs_map = stage in ("frame", "map", "discover", "verify-sources", "adversarial")
    if needs_map and f.map[0] is None:
        return [_map_problem_order(stage, f)]
    out: list[dict[str, Any]] = []
    if stage == "frame":
        out.append(
            make_order(
                stage, "state-thesis", tier="script", needs_human=True,
                reason="no thesis is accepted; add one and run theses accept",
            )
        )
    elif stage == "map":
        for node_id in untriaged(f):
            out.append(
                make_order(
                    stage, "triage-objection", nodes=[node_id], outputs=_node_output(node_id),
                    check="theses-lint",
                    reason=f"set anchor, severity and the stage to reopen for {node_id}",
                )
            )
        for node_id, kinds in sorted(_by_node(f.gap_ids(*MAP_GAP_KINDS)).items()):
            defence = "objection-undefended" in kinds or "thesis-unsupported" in kinds
            out.append(
                make_order(
                    stage, "fill-gap", nodes=[node_id], outputs=_node_output(node_id),
                    proc=procedure("blue-team") if defence else None, check="theses-lint",
                    reason=f"gap {', '.join(sorted(kinds))} on {node_id}",
                )
            )
    elif stage == "discover":
        for node_id in sorted(_by_node(f.gap_ids("single-source"))):
            out.append(
                make_order(
                    stage, "find-related", nodes=[node_id], outputs=_node_output(node_id),
                    check="theses-lint", reason=f"{node_id} rests on a single source",
                )
            )
    elif stage in ("draft", "revise"):
        out += _draft_orders(stage, f)
    elif stage == "verify-sources":
        out += _verify_orders(stage, f)
    elif stage == "adversarial":
        for gap in f.gap_ids("thesis-unattacked"):
            out.append(
                make_order(
                    stage, "red-team", nodes=[gap["id"]], outputs=_node_output(gap["id"]),
                    proc=procedure("red-team"), check="theses-lint",
                    reason=f"thesis {gap['id']} has no accepted objection",
                )
            )
        for gap in f.gap_ids("objection-undefended"):
            out.append(
                make_order(
                    stage, "blue-team", nodes=[gap["id"]], outputs=_node_output(gap["id"]),
                    proc=procedure("blue-team"), check="theses-lint",
                    reason=f"objection {gap['id']} has no defense",
                )
            )
    elif stage == "release-gate":
        out += _release_orders(stage, f)
    return out


def _draft_orders(stage: str, f: Facts) -> list[dict[str, Any]]:
    out = []
    if f.index_stale:
        out.append(
            make_order(
                stage, "reindex", tier="script", outputs=[section_index.INDEX_PATH.as_posix()],
                check="index-check", reason="the section index is missing or stale",
            )
        )
    if f.validation_errors:
        kind, tier = ("write-section", "large") if stage == "draft" else ("fix-validation", "small")
        out.append(
            make_order(
                stage, kind, outputs=["paper/"], tier=tier, check="make-validate",
                reason=f"{f.validation_errors} validation error(s); run validate",
            )
        )
    if stage == "revise" and f.counts_script and f.check("lint-counts")["status"] != "pass":
        out.append(
            make_order(
                stage, "fix-validation", outputs=["paper/"], check="lint-counts",
                reason="the counts lint fails",
            )
        )
    return out


def _verify_orders(stage: str, f: Facts) -> list[dict[str, Any]]:
    out = []
    for record in f.claim_records:
        state = source_claim_state(f, record)
        if state == "needs-check":
            out.append(
                make_order(
                    stage, "claim-check", nodes=[record["id"]],
                    outputs=[claims.VERDICT_OUTPUT], proc=procedure("claim-check"),
                    check="claims-quote-check",
                    reason=f"{record['id']} has no fresh cached verdict",
                )
            )
        elif state not in ("ok", "attested"):
            out.append(
                make_order(
                    stage, "attest-claim", nodes=[record["id"]], tier="script",
                    needs_human=True, reason=f"{record['id']}: {state}",
                )
            )
    return out


def _release_orders(stage: str, f: Facts) -> list[dict[str, Any]]:
    out = []
    if f.validation_errors:
        out.append(
            make_order(
                stage, "fix-validation", outputs=["paper/"], check="make-validate",
                reason=f"{f.validation_errors} validation error(s); run validate",
            )
        )
    elif not _release_plan_clear(f):
        out.append(
            make_order(
                stage, "release-blocked", tier="script", needs_human=True,
                reason="the release plan has a blocking item; run release --dry-run",
            )
        )
    elif f.layout_script and f.check("layout-check")["status"] != "pass":
        out.append(
            make_order(
                stage, "fix-validation", outputs=["paper/"], check="layout-check",
                reason="the layout check fails",
            )
        )
    elif not f.attested("bibliography"):
        out.append(
            make_order(
                stage, "verify-bibliography", tier="script", check="release-plan", gated=True,
                confirm="bibliography",
                reason="bibliography verification needs a confirmation in the owner's terminal",
            )
        )
    elif not cold_run_recorded(f.root):
        out.append(
            make_order(
                stage, "run-cold", tier="script", gated=True, confirm="cold-run",
                outputs=["docs/ledger/cold-run"],
                reason=(
                    "no cold run matches the current inputs; CI or a person runs "
                    f"`{CMD} check --cold`, then records `flow attest cold-run`"
                ),
            )
        )
    return out


def _release_plan_clear(f: Facts) -> bool:
    from . import release

    plan = release.plan_release(f.root)
    checks = (plan.get("plan") or {}).get("checks") or {}
    return bool(plan.get("ok") and checks.get("has_version") and checks.get("tag_absent"))


def _record(state: dict[str, Any], order: dict[str, Any]) -> dict[str, Any] | None:
    entry = state["orders"].get(order["id"])
    if isinstance(entry, dict) and entry.get("done"):
        return None  # the condition arose again after a pass: treat as new
    return entry if isinstance(entry, dict) else None


def next_order(
    root: Path, today: date | None = None, with_brief: bool = False
) -> dict[str, Any]:
    """The first open order for the earliest failing gate; re-issuing is idempotent."""
    state = load_state(root)
    facts = Facts(root, state)
    results = evaluate(facts, today or date.today())
    stage = current_stage(results)
    if stage is None:
        return {"ok": True, "command": "flow next", "order": None, "reason": "every gate passes"}
    candidates = orders_for(stage, facts)
    if not candidates:
        entry = next(r for r in results if r["stage"] == stage)
        candidates = [
            make_order(
                stage, "gate-failing", tier="script", needs_human=True,
                reason=f"{entry['reason']}; run {entry['command']}",
            )
        ]
    ready = _ready(candidates, state)
    for item in ready:
        decorate(item, facts)
    groups, _ = group.plan(ready, group_size(state))
    members = next((g for g in groups if g[0] == 0), None)
    if members is None:
        order = ready[0]
        if not order["needs_human"]:
            _remember(root, state, order)
        decorate(order, facts, with_brief)
        return {"ok": True, "command": "flow next", "order": order}
    batch = [ready[i] for i in members]
    for item in batch:
        _remember(root, state, item)
    unit = group_unit(batch, facts, with_brief)
    for item in batch:
        item["group"] = unit["id"]
    return {
        "ok": True, "command": "flow next", "order": batch[0], "group": unit, "orders": batch,
    }


def _ready(candidates: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    """Candidates with their retry count and the retry or budget limits applied."""
    ready = []
    for order in candidates:
        entry = _record(state, order)
        order["retries"] = int(entry.get("retries", 0)) if entry else 0
        ready.append(_apply_limits(order, entry, state))
    return ready


def group_size(state: dict[str, Any]) -> int:
    return int(state.get("group_size", group.DEFAULT_GROUP_SIZE))


def _apply_limits(order: dict[str, Any], entry: dict | None, state: dict[str, Any]):
    """Past the retry cap or a spent budget, replace the order with a needs-human one."""
    if order["needs_human"]:
        return order
    over_cap = order["retries"] >= state["retry_cap"]
    weight = state["weights"][order["tier"]]
    spent = weight > 0 and state["budget"]["used"] >= state["budget"]["limit"]
    if not (over_cap or spent):
        return order
    why = (
        f"retry cap {state['retry_cap']} reached" if over_cap
        else f"round budget spent ({state['budget']['used']}/{state['budget']['limit']} units)"
    )
    human = make_order(
        order["stage"], "needs-human", nodes=order["nodes"], tier="script", needs_human=True,
        reason=f"{why} for {order['kind']} {order['id']}",
    )
    human["retries"] = order["retries"]
    human["evidence"] = {
        "order": order["id"],
        "check": order["check"],
        "output": (entry or {}).get("last_output", ""),
    }
    return human


def _remember(root: Path, state: dict[str, Any], order: dict[str, Any]) -> None:
    """Record the issued order so `flow done` can close it; unchanged state is not rewritten."""
    old = state["orders"].get(order["id"])
    entry = {
        "kind": order["kind"],
        "stage": order["stage"],
        "tier": order["tier"],
        "check": order["check"],
        "nodes": order["nodes"],
        "gated": order["gated"],
        "confirm": order["confirm"],
        "retries": order["retries"],
        "done": False,
    }
    if isinstance(old, dict) and old.get("last_output"):
        entry["last_output"] = old["last_output"]
    if old != entry:
        state["orders"][order["id"]] = entry
        save_state(root, state)


# ------------------------------------------------------------- brief, call cap

# Where the finding or gap row of a brief comes from, per order kind. The row is read from
# the stage that issued the order, never from a model. Kinds not listed use the gate row.
ROW_SOURCES = {
    "fill-gap": "theses gaps",
    "find-related": "theses gaps",
    "red-team": "theses gaps",
    "blue-team": "theses gaps",
    "triage-objection": "theses.yaml node",
    "claim-check": "claims quote-check",
    "attest-claim": "claims quote-check",
    "write-section": "validate",
    "fix-validation": "validate",  # only where the order's check is make-validate
}
# The gap kinds each gap-driven order answers; the row lists only those.
ROW_GAP_KINDS = {
    "fill-gap": MAP_GAP_KINDS,
    "find-related": ("single-source",),
    "red-team": ("thesis-unattacked",),
    "blue-team": ("objection-undefended",),
}
GATE_ROW_SOURCE = "flow status"
ROW_TEXT = 300
ROW_ERRORS = 5
MAX_BRIEF_NODES = 5


def _row_source(order: dict[str, Any]) -> str:
    source = ROW_SOURCES.get(order["kind"], GATE_ROW_SOURCE)
    if source == "validate" and order["check"] != "make-validate":
        return GATE_ROW_SOURCE
    return source


def _short(value: object) -> object:
    return value[:ROW_TEXT] if isinstance(value, str) else value


def _relative(root: Path, path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path
    return candidate.as_posix()


def finding_row(order: dict[str, Any], f: Facts) -> dict[str, Any]:
    """The finding or gap row that raised the order, labelled with its source."""
    source = _row_source(order)
    nodes = order["nodes"][:MAX_BRIEF_NODES]
    row: dict[str, Any] = {"source": source}
    if source == "theses gaps":
        row["gaps"] = sorted(
            (
                {"kind": g["kind"], "id": g["id"], "text": _short(g["text"])}
                for g in f.gaps
                if g["id"] in nodes and g["kind"] in ROW_GAP_KINDS[order["kind"]]
            ),
            key=lambda g: (g["id"], g["kind"]),
        )
    elif source in ("theses.yaml node", "claims quote-check"):
        row["nodes"] = [
            {k: _short(f.nodes[n][k]) for k in ("id", "type", "status", "text") if k in f.nodes[n]}
            for n in nodes
            if n in f.nodes
        ]
        if source == "claims quote-check":
            row["records"] = sorted(
                (
                    {k: _short(v) for k, v in r.items() if isinstance(v, (str, bool, int))}
                    for r in f.claim_records
                    if r["id"] in nodes
                ),
                key=lambda r: r["id"],
            )
    elif source == "validate":
        diagnostics = f.validation_diagnostics
        row["count"] = len(diagnostics)
        row["errors"] = [
            {
                "path": _relative(f.root, str(d.path)),
                "line": d.line,
                "code": d.code,
                "message": _short(d.message),
            }
            for d in diagnostics[:ROW_ERRORS]
        ]
    else:
        row["reason"] = order["reason"]
    return row


def _order_anchors(order: dict[str, Any], f: Facts, row: dict[str, Any]) -> list[dict]:
    nodes = [f.nodes[n] for n in order["nodes"] if n in f.nodes]
    places = [(e["path"], e["line"]) for e in row.get("errors", []) if e["line"] > 0]
    return order_brief.anchors_for(
        f.root,
        labels=[n["anchor"] for n in nodes if isinstance(n.get("anchor"), str)],
        texts=[n["text"] for n in nodes],
        places=places,
    )


def _ledger_hits(order: dict[str, Any], f: Facts) -> list[dict[str, Any]]:
    """Ledger entries already valid for the order's inputs (read only, nothing counted)."""
    hits: list[dict[str, Any]] = []
    if not ledger.enabled():
        return hits
    name = order["check"]
    spec = CHECK_SPECS.get(name) if name else None
    if spec is not None and spec.deterministic:
        keyed = check_keyed(f.root, name)
        entry = _safe_get(f.root, keyed)
        if entry is not None:
            hits.append(
                {
                    "kind": "check-outcome", "name": name, "key": keyed.key,
                    "status": entry["status"],
                    "failing": (entry.get("result") or {}).get("failing", []),
                }
            )  # fmt: skip
    if order["kind"] in ("claim-check", "attest-claim"):
        for node_id in order["nodes"][:MAX_BRIEF_NODES]:
            try:
                excerpt = claims.excerpt_for(f.root, node_id)
            except (ValueError, OSError):
                continue
            keyed = claims.verdict_key(f.nodes[node_id]["text"], excerpt)
            entry = _safe_get(f.root, keyed)
            if entry is not None:
                hits.append(
                    {
                        "kind": claims.VERDICT_KIND, "name": node_id, "key": keyed.key,
                        "status": entry["status"],
                        "verdict": (entry.get("result") or {}).get("verdict"),
                    }
                )  # fmt: skip
    return sorted(hits, key=lambda h: (h["kind"], h["name"]))


def _safe_get(root: Path, keyed: ledger.Keyed | None) -> dict[str, Any] | None:
    if keyed is None:
        return None
    try:
        return ledger.get(root, keyed.kind, keyed.key)
    except ledger.LedgerError:
        return None  # a corrupt entry is never served; `ledger verify` reports it


def max_calls_for(order: dict[str, Any], state: dict[str, Any]) -> int | None:
    """The advisory call cap for an order's tier: ``flow.yaml`` ``max_calls`` over the defaults.

    Script orders and orders for a person carry none. The host counts calls; the CLI never
    enforces this.
    """
    if order["needs_human"] or order["tier"] not in DEFAULT_MAX_CALLS:
        return None
    table = {**DEFAULT_MAX_CALLS, **(state.get("max_calls") or {})}
    return int(table[order["tier"]])


def _anchored(order: dict[str, Any], f: Facts) -> tuple[dict[str, Any], list[dict]]:
    """The finding row and the anchors of an order, each anchor marked ``write`` or ``read``.

    An anchor is a write anchor when the order's outputs cover its file (see ``group``).
    """
    row = finding_row(order, f)
    anchors = _order_anchors(order, f, row)
    for anchor in anchors:
        anchor["mode"] = group.anchor_mode(order["outputs"], anchor["file"])
    return row, anchors


def _verify_for(order: dict[str, Any]) -> dict[str, str] | None:
    name = order["check"]
    return {"check": name, "command": f"{CMD} check record {name}"} if name else None


def _brief_cap(f: Facts) -> int:
    return int(f.state.get("brief_bytes", order_brief.DEFAULT_BRIEF_BYTES))


def _index_notes(f: Facts) -> list[str]:
    if (f.root / section_index.INDEX_PATH).is_file():
        return []
    return ["the section index is missing; section anchors are not resolved"]


def decorate(order: dict[str, Any], f: Facts, with_brief: bool = False) -> None:
    """Add the optional ``anchors`` and ``max_calls``; with *with_brief*, the compiled brief.

    Nothing here is stored in ``flow.yaml``. A brief is rebuilt from the repo on each call.
    """
    row, anchors = _anchored(order, f)
    order.pop("anchors", None)
    if anchors:
        order["anchors"] = [order_brief.order_anchor(a) for a in anchors]
    calls = max_calls_for(order, f.state)
    if calls is not None:
        order["max_calls"] = calls
    if not with_brief:
        return
    order["brief"] = order_brief.compile_brief(
        order=order,
        row=row,
        anchors=anchors,
        guardrails=order_brief.guardrail_digest(f.root, order["kind"]),
        ledger_hits=_ledger_hits(order, f),
        verify=_verify_for(order),
        max_calls=calls,
        cap=_brief_cap(f),
        notes=_index_notes(f),
    )


def group_unit(batch: list[dict[str, Any]], f: Facts, with_brief: bool) -> dict[str, Any]:
    """One unit for one agent: the member ids, the shared files, a combined cap and brief.

    The members keep their own fields but carry no brief of their own.
    """
    ids = [o["id"] for o in batch]
    gid = group.group_id(ids)
    counts: dict[str, int] = {}
    for order in batch:
        for file in group.write_files(order):
            counts[file] = counts.get(file, 0) + 1
    unit: dict[str, Any] = {
        "id": gid,
        "orders": ids,
        "files": sorted(file for file, n in counts.items() if n > 1),
    }
    calls = [o["max_calls"] for o in batch if "max_calls" in o]
    if calls:
        unit["max_calls"] = sum(calls)
    seen: dict[tuple, dict] = {}
    parts = [_anchored(o, f) for o in batch]
    for _, anchors in parts:
        for a in anchors:
            seen.setdefault((a["file"], tuple(a["lines"]), a["name"]), a)
    merged = [seen[k] for k in sorted(seen)]
    unit["anchors"] = [order_brief.order_anchor(a) for a in merged]
    if not with_brief:
        return unit
    guardrails: dict[str, dict] = {}
    hits: dict[tuple, dict] = {}
    verifies: dict[str, dict] = {}
    for order in batch:
        for item in order_brief.guardrail_digest(f.root, order["kind"]):
            guardrails.setdefault(item["id"], item)
        for hit in _ledger_hits(order, f):
            hits.setdefault((hit["kind"], hit["name"]), hit)
        verify = _verify_for(order)
        if verify:
            verifies.setdefault(verify["command"], verify)
    commands = sorted(verifies)
    notes = _index_notes(f)
    notes += [f"also verify: {c}" for c in commands[1:]]
    notes.append(f"{len(batch)} orders share {', '.join(unit['files']) or 'files'}")
    row = dict(parts[0][0])
    row["members"] = [{"order": o["id"], "row": p[0]} for o, p in zip(batch, parts, strict=True)]
    unit["brief"] = order_brief.compile_brief(
        order={"id": gid},
        row=row,
        anchors=merged,
        guardrails=[guardrails[k] for k in sorted(guardrails)],
        ledger_hits=[hits[k] for k in sorted(hits)],
        verify=verifies[commands[0]] if commands else None,
        max_calls=unit.get("max_calls"),
        cap=_brief_cap(f),
        notes=notes,
    )
    return unit


# ---------------------------------------------------------------- done, attest

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9:._-]*$")


def _fail(root: Path, state: dict[str, Any], order_id: str, output: str) -> dict[str, Any]:
    entry = state["orders"][order_id]
    entry["retries"] = int(entry.get("retries", 0)) + 1
    entry["last_output"] = output[:OUTPUT_LIMIT]
    save_state(root, state)
    return {
        "ok": False,
        "command": "flow done",
        "id": order_id,
        "retries": entry["retries"],
        "retry_cap": state["retry_cap"],
        "output": entry["last_output"],
    }


def done(root: Path, order_id: str, today: date | None = None) -> dict[str, Any]:
    """Close an issued order: run its named check, then confirm the condition is gone.

    Takes the order id and nothing else. A pass is recorded once; closing again is a
    no-op, so a crash between `next` and `done` never double counts.
    """
    state = load_state(root)
    entry = state["orders"].get(order_id)
    if not isinstance(entry, dict):
        raise FlowError(f"unknown order {order_id!r}; run `flow next`")
    if entry.get("done"):
        return {"ok": True, "command": "flow done", "id": order_id, "charged": 0, "already": True}
    check = entry.get("check")
    if check is not None and check not in CHECKS:
        raise FlowError(f"order {order_id!r} names an unknown check {check!r}; refusing")
    confirmed = any(a["name"] == entry.get("confirm") for a in state["attestations"])
    if entry.get("gated") and not confirmed:
        raise FlowError(
            f"order {order_id!r} is gated: it closes only after a person records "
            f"`flow attest {entry.get('confirm')}` in a terminal"
        )
    if check is not None:
        ran = check_record(root, check)
        if not ran["ok"]:
            detail = "; ".join(ran["failing"]) or ran["state"]
            outcome = ran.get("verdict", ran["state"])
            return _fail(root, state, order_id, f"check {check}: {outcome}: {detail}")
    facts = Facts(root, state)
    if order_id in {o["id"] for o in orders_for(entry["stage"], facts)}:
        return _fail(root, state, order_id, "the condition behind this order still holds")
    tier = entry.get("tier", "small")
    weight = state["weights"].get(tier, 0)
    state["budget"]["used"] += weight
    state["orders"][order_id] = {
        "kind": entry.get("kind"), "stage": entry.get("stage"), "tier": tier,
        "check": check, "retries": 0, "done": True,
    }
    save_state(root, state)
    return {"ok": True, "command": "flow done", "id": order_id, "charged": weight}


def _require_person(by: str, why: str, confirmed: bool) -> None:
    if not confirmed:
        raise FlowError("a person must record this in a terminal; no confirmation was given")
    if not by.strip() or "\n" in by or theses.is_agent_name(by):
        raise FlowError("--by needs the one-line name of a person, not an agent role")
    if not why.strip() or "\n" in why:
        raise FlowError("--why needs a one-line reason")


def attest(
    root: Path, name: str, by: str, why: str, *, confirmed: bool, today: date | None = None
) -> dict[str, Any]:
    """Record a human attestation (for example `bibliography` or `claim:<node id>`)."""
    _require_person(by, why, confirmed)
    if not NAME_RE.match(name):
        raise FlowError(f"attestation name must match {NAME_RE.pattern}")
    state = load_state(root)
    state["attestations"] = [a for a in state["attestations"] if a["name"] != name]
    state["attestations"].append(
        {
            "name": name, "by": by.strip(), "at": (today or date.today()).isoformat(),
            "why": why.strip(),
        }
    )
    save_state(root, state)
    return {"ok": True, "command": "flow attest", "name": name}


def waive(
    root: Path, stage: str, by: str, why: str, expires: str, *, confirmed: bool,
    today: date | None = None,
) -> dict[str, Any]:
    """Record a waiver that turns a failing gate into `waived` until *expires*."""
    _require_person(by, why, confirmed)
    if stage not in STAGES:
        raise FlowError(f"{stage!r} is not a stage")
    if not _is_date(expires):
        raise FlowError("--expires must be a YYYY-MM-DD date")
    now = today or date.today()
    if _as_date(expires) < now:
        raise FlowError("--expires is in the past")
    state = load_state(root)
    state["waivers"] = [w for w in state["waivers"] if w["stage"] != stage]
    state["waivers"].append(
        {"stage": stage, "by": by.strip(), "at": now.isoformat(), "why": why.strip(),
         "expires": str(expires)}
    )
    save_state(root, state)
    return {"ok": True, "command": "flow waive", "stage": stage, "expires": str(expires)}


# --------------------------------------------------------------- review round

ITEM_RE = re.compile(r"^\s{0,3}(\d+)[.)]\s+(.*)$")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
ITEM_LIMIT = 240


def split_review(text: str) -> list[tuple[int, str]]:
    """Items of a review as (line number, one-line text), by a deterministic rule.

    A numbered list wins; otherwise each heading is an item. A numbered item continues
    over the following non-blank, non-item lines. Item text is data: it is stored as a
    node's one-line text and never placed in an order.
    """
    lines = text.splitlines()
    numbered = [i for i, line in enumerate(lines) if ITEM_RE.match(line)]
    items: list[tuple[int, str]] = []
    if numbered:
        for i in numbered:
            parts = [ITEM_RE.match(lines[i]).group(2)]
            for follow in lines[i + 1 :]:
                if not follow.strip() or ITEM_RE.match(follow) or HEADING_RE.match(follow):
                    break
                parts.append(follow)
            items.append((i + 1, " ".join(" ".join(parts).split())))
    else:
        for i, line in enumerate(lines):
            match = HEADING_RE.match(line)
            if match and match.group(1).strip():
                items.append((i + 1, " ".join(match.group(1).split())))
    return [(n, t[:ITEM_LIMIT]) for n, t in items if t]


def _review_path(root: Path, review: str) -> tuple[Path, str]:
    path = (root / review).resolve() if not Path(review).is_absolute() else Path(review).resolve()
    base = root.resolve()
    if not path.is_file() or not path.is_relative_to(base):
        raise FlowError("the review must be a file inside this repository")
    return path, path.relative_to(base).as_posix()


def round_open(root: Path, review: str, today: date | None = None) -> dict[str, Any]:
    """Start a round from a local review file: one proposed objection per item."""
    path, rel = _review_path(root, review)
    text = path.read_text(encoding="utf-8", errors="replace")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    state = load_state(root)
    for seen in state["reviews"]:
        if seen.get("file") == rel and seen.get("sha256") == digest:
            return {"ok": True, "command": "flow round open", "round": state["round"],
                    "created": [], "unchanged": True}
    items = split_review(text)
    if not items:
        raise FlowError("no items found: use a numbered list or headings")
    data = theses.load_map(root)
    if data is None or not theses.structure_errors(data).ok:
        raise FlowError("theses.yaml is missing or invalid; run `theses lint`")
    known = {n["id"] for n in data.get("nodes") or []}
    fresh: list[dict[str, str]] = []
    for line, item in items:
        node_id = "rv-" + hashlib.sha256(item.encode("utf-8")).hexdigest()[:8]
        if node_id in known or any(n["id"] == node_id for n in fresh):
            continue
        fresh.append({
            "id": node_id, "type": "objection", "text": item, "status": "proposed",
            "source": rel, "locator": f"line {line}",
        })
    try:
        theses.add_nodes(root, fresh)
    except theses.AcceptError as exc:
        raise FlowError(str(exc)) from exc
    state["round"] += 1
    state["budget"]["used"] = 0
    state["orders"] = {}
    state["reviews"].append({"file": rel, "sha256": digest, "round": state["round"]})
    save_state(root, state)
    return {"ok": True, "command": "flow round open", "round": state["round"],
            "created": [n["id"] for n in fresh], "unchanged": False}


def round_close(root: Path, today: date | None = None) -> dict[str, Any]:
    """Record the round as closed once every gate before publish passes or is waived."""
    now = today or date.today()
    state = load_state(root)
    results = evaluate(Facts(root, state), now)
    failing = [r["stage"] for r in results if r["status"] == "fail"]
    if failing:
        return {"ok": False, "command": "flow round close", "round": state["round"],
                "failing": failing}
    closed = state.setdefault("closed", [])
    if not any(c["round"] == state["round"] for c in closed):
        closed.append({"round": state["round"], "at": now.isoformat()})
        save_state(root, state)
    return {"ok": True, "command": "flow round close", "round": state["round"], "failing": []}


# ------------------------------------------------------------ parallel orders


_paths_overlap = group.paths_overlap


def mark_parallel(orders: list[dict[str, Any]]) -> None:
    """Set `parallel_safe` on each order: true only if its nodes and outputs are disjoint
    from every other order in the list and a person is not needed.

    Map writes touch only the named nodes (see `theses.accept_text`), so orders on
    different nodes edit different lines of `theses.yaml` and merge cleanly.
    """
    for order in orders:
        safe = not order["needs_human"] and not order["gated"]
        for other in orders:
            if other is order:
                continue
            if set(order["nodes"]) & set(other["nodes"]) or any(
                _paths_overlap(x, y) for x in order["outputs"] for y in other["outputs"]
            ):
                safe = False
        order["parallel_safe"] = safe


def open_orders(
    root: Path, today: date | None = None, with_brief: bool = False
) -> dict[str, Any]:
    """Every open order of the current stage, with `parallel_safe` marks.

    Hosts run one working copy per concurrent order and merge the branches.
    """
    state = load_state(root)
    facts = Facts(root, state)
    results = evaluate(facts, today or date.today())
    stage = current_stage(results)
    if stage is None:
        return {"ok": True, "command": "flow next", "orders": []}
    ready = _ready(orders_for(stage, facts), state)
    for order in ready:
        decorate(order, facts)
    plans, deferred = group.plan(ready, group_size(state))
    grouped = {i for g in plans for i in g}
    offered = [(i, o) for i, o in enumerate(ready) if i not in deferred]
    for _, order in offered:
        if not order["needs_human"]:
            _remember(root, state, order)
    units = []
    for g in plans:
        batch = [ready[i] for i in g]
        unit = group_unit(batch, facts, with_brief)
        for order in batch:
            order["group"] = unit["id"]
        units.append(unit)
    orders = [o for _, o in offered]
    if with_brief:
        for i, order in offered:
            if i not in grouped:
                decorate(order, facts, True)
    mark_parallel(orders)
    for order in orders:
        if "group" in order:
            order["parallel_safe"] = False
    payload: dict[str, Any] = {"ok": True, "command": "flow next", "orders": orders}
    if units:
        payload["groups"] = units
    if deferred:
        payload["deferred"] = [ready[i]["id"] for i in deferred]
    return payload
