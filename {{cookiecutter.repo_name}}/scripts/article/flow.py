"""Lifecycle flow: per-stage gates computed from the repo, and the stored decisions.

Offline and deterministic. A gate reads files in the repo; it makes no network or
model call. ``flow.yaml`` stores only what the repo cannot tell: the round number,
human attestations and waivers, and the budget used (plus the bookkeeping of issued
orders). There is no stage pointer: the current stage is the earliest failing gate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import claims, core, theses
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
    def validation_errors(self) -> int:
        return self._once("validate", lambda: len(core.validate_paper(self.root).errors))

    @property
    def index_stale(self) -> list[str]:
        return self._once("index", lambda: section_index.check_index(self.root))

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


def _gate_map(f: Facts) -> dict[str, Any]:
    return _gap_gate(f, MAP_GAP_KINDS, "no thesis, objection or anchor gaps")


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
    """One of: ok, attested, needs-check, not-found, no-local-text, overstates, contradicts."""
    if f.attested(f"claim:{record['id']}"):
        return "attested"
    if record["verdict"] in ("not-found", "no-local-text"):
        return record["verdict"]
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
        run = run_check(f.root, "lint-counts")
        if run["status"] != "pass":
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
    if f.layout_script and run_check(f.root, "layout-check")["status"] != "pass":
        return _verdict(False, "the layout check fails", "python3 scripts/check_pdf_layout.py")
    if not f.attested("bibliography"):
        return _verdict(False, "no recorded bibliography verification", f"{CMD} flow attest")
    return _verdict(True, "release plan clear and bibliography attested", command)


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
    """Run a check from the fixed table: status is pass, fail or unavailable."""
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
        return {"status": "fail", "output": str(exc)[:OUTPUT_LIMIT]}
    text = " ".join((proc.stdout + proc.stderr).split())
    return {"status": "pass" if proc.returncode == 0 else "fail", "output": text[:OUTPUT_LIMIT]}


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
