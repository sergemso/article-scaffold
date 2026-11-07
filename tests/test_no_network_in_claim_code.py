"""Guardrail claim-check-input-stays-local: no outbound call from the map code."""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import ROOT

LIB = ROOT / "{{cookiecutter.repo_name}}" / "scripts" / "article"
GUARDED = (
    "theses.py", "index.py", "claims.py", "flow.py", "terms.py", "address.py", "ledger.py",
    "sources.py", "code_index.py", "brief.py",
)  # fmt: skip
FORBIDDEN_MODULES = {"socket", "http", "urllib", "requests", "ssl", "ftplib", "smtplib"}
FETCHERS = {"curl", "wget"}


def _program(text: str) -> str:
    words = text.split()
    return words[0].split("/")[-1] if words else ""


def violations(source: str) -> list[str]:
    """Network-capable imports and calls found in *source*."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in FORBIDDEN_MODULES:
                found.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Call):
            func = node.func
            name = ast.unparse(func)
            if name == "os.system":
                found.append("os.system")
            elif name.split(".")[0] == "subprocess" or name == "__import__":
                strings = [
                    n.value
                    for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                ]
                if any(_program(s) in FETCHERS for s in strings):
                    found.append(f"{name} fetching over the network")
                if name == "__import__" and any(
                    s.split(".")[0] in FORBIDDEN_MODULES for s in strings
                ):
                    found.append("__import__ of a network module")
    return found


def _local_imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            names.add(node.module.split(".")[0] + ".py")
    return names


def _scan_set() -> list[Path]:
    todo, seen = list(GUARDED), set()
    while todo:
        name = todo.pop()
        if name in seen or not (LIB / name).is_file():
            continue
        seen.add(name)
        todo += sorted(_local_imports(LIB / name))
    return sorted(LIB / name for name in seen)


def test_guarded_modules_exist() -> None:
    for name in GUARDED:
        assert (LIB / name).is_file(), name


def test_claim_index_and_map_code_use_no_network() -> None:
    bad = {
        path.name: found
        for path in _scan_set()
        if (found := violations(path.read_text(encoding="utf-8")))
    }
    assert not bad, bad


def test_scan_follows_local_imports() -> None:
    names = {p.name for p in _scan_set()}
    assert {"theses.py", "index.py", "claims.py", "latex.py", "diagnostics.py"} <= names


def test_scanner_catches_deliberate_violations() -> None:
    cases = [
        "import socket",
        "import urllib.request",
        "from http.client import HTTPSConnection",
        "import requests",
        "from ssl import create_default_context",
        "import ftplib",
        "import smtplib",
        "import os\nos.system('ls')",
        "import subprocess\nsubprocess.run(['curl', 'https://example.org'])",
        "import subprocess\nsubprocess.run(['/usr/bin/wget', 'x'])",
        "__import__('socket')",
    ]
    for case in cases:
        assert violations(case), case
    clean = (
        "import json\nimport subprocess\nsubprocess.run(['git', 'status'])\n"
        "from .latex import x"
    )
    assert violations(clean) == []
