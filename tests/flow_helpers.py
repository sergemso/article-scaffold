"""Shared helpers for the flow tests: a rendered project copied per test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from conftest import ROOT, run

sys.path.insert(0, str(ROOT / "{{cookiecutter.repo_name}}"))

THESIS_MAP = """\
version: 1
nodes:
  - id: t1
    type: thesis
    text: Main claim.
    status: accepted
    accepted-by: Ada Lovelace
edges: []
"""


CLEAN_MAP = (
    "version: 1\nnodes:\n"
    "  - {id: t1, type: thesis, text: T., status: accepted, accepted-by: Ada}\n"
    "  - {id: o1, type: objection, text: O., status: accepted, accepted-by: Ada}\n"
    "  - {id: d1, type: defense, text: D., status: proposed}\n"
    "edges:\n  - {from: d1, to: t1, type: supports}\n"
    "  - {from: o1, to: t1, type: attacks}\n  - {from: d1, to: o1, type: rebuts}\n"
)


def cli(project: Path, *args: str):
    return run(project, "python3", "-m", "scripts.article", *args)


def jcli(project: Path, *args: str) -> dict:
    result = cli(project, *args)
    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout)


def stages(payload: dict) -> dict[str, dict]:
    return {s["stage"]: s for s in payload["stages"]}


def set_state(project: Path, **changes) -> None:
    path = project / "flow.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def write_map(project: Path, text: str) -> None:
    (project / "theses.yaml").write_text(text)


def record_cold_run(project: Path) -> None:
    """Write the cold-run record for the project's current inputs (what `check --cold` does
    after a clean run), without running every check."""
    from scripts.article import flow, ledger

    ledger.put(project, flow.cold_keyed(project), "pass", {"checks": {}})
