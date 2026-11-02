"""Shared helpers for the flow tests: a rendered project copied per test."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from conftest import run

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
