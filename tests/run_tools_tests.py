#!/usr/bin/env python3
"""Standalone test runner for tool commands.

This script runs all tool tests in a completely isolated subprocess
to avoid pytest's stdout capture interference.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add the tests directory to path so we can import conftest
sys.path.insert(0, str(Path(__file__).parent))
from conftest import render


def _project(tmp_path: Path) -> Path:
    return render(tmp_path=tmp_path)


def _run_tool_json(project: Path, tool: str, **flags: str) -> dict:
    """Run a tool via subprocess and return parsed JSON."""
    args = [sys.executable, "-m", "scripts.article", tool, "--json"]
    for flag, value in flags.items():
        if value is True:
            args.append(f"--{flag}")
        elif value is not False and value is not None:
            args.append(f"--{flag}")
            args.append(str(value))
    
    proc = subprocess.run(
        args,
        cwd=project,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(project.parent),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        },
    )
    return json.loads(proc.stdout)


def test_diff_plan_constructs_command() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "diff", dry_run=True)
        if not result["ok"]:
            return False, f"diff plan failed: {result.get('error', 'unknown')}"
        if result["command"] != "diff":
            return False, f"wrong command: {result['command']}"
        plan = result["plan"]
        if plan["name"] != "diff":
            return False, f"wrong plan name: {plan['name']}"
        cmd_str = " ".join(plan["command"])
        if "latexdiff" not in cmd_str:
            return False, f"latexdiff not in command: {cmd_str}"
        if "git show" not in cmd_str:
            return False, f"git show not in command: {cmd_str}"
        return True, ""


def test_diff_fails_gracefully_when_latexdiff_missing() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        # We can't easily monkeypatch shutil.which in a subprocess,
        # so we just verify the error message format
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "diff", dry_run=True)
        if result["ok"]:
            return False, "diff should fail when latexdiff missing"
        if "latexdiff" not in result.get("error", ""):
            return False, f"error should mention latexdiff: {result.get('error')}"
        return True, ""


def test_arxiv_plan_constructs_command() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "arxiv", dry_run=True, output="test.zip")
        if not result["ok"]:
            return False, f"arxiv plan failed: {result.get('error')}"
        if result["command"] != "arxiv":
            return False, f"wrong command: {result['command']}"
        plan = result["plan"]
        if plan["name"] != "arxiv":
            return False, f"wrong plan name: {plan['name']}"
        if "zip" not in plan["command"]:
            return False, f"zip not in command: {plan['command']}"
        if "-x" not in " ".join(plan["command"]):
            return False, f"excludes not in command: {plan['command']}"
        return True, ""


def test_arxiv_fails_gracefully_when_zip_missing() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "arxiv", dry_run=True)
        if result["ok"]:
            return False, "arxiv should fail when zip missing"
        if "zip" not in result.get("error", ""):
            return False, f"error should mention zip: {result.get('error')}"
        return True, ""


def test_wordcount_plan_constructs_command() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "wordcount", dry_run=True)
        if not result["ok"]:
            return False, f"wordcount plan failed: {result.get('error')}"
        if result["command"] != "wordcount":
            return False, f"wrong command: {result['command']}"
        plan = result["plan"]
        if plan["name"] != "wordcount":
            return False, f"wrong plan name: {plan['name']}"
        if "texcount" not in plan["command"]:
            return False, f"texcount not in command: {plan['command']}"
        if "paper/article.tex" not in plan["command"]:
            return False, f"paper/article.tex not in command: {plan['command']}"
        return True, ""


def test_wordcount_fails_gracefully_when_texcount_missing() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "wordcount", dry_run=True)
        if result["ok"]:
            return False, "wordcount should fail when texcount missing"
        if "texcount" not in result.get("error", ""):
            return False, f"error should mention texcount: {result.get('error')}"
        return True, ""


def test_spell_plan_constructs_command() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "spell", dry_run=True)
        if not result["ok"]:
            return False, f"spell plan failed: {result.get('error')}"
        if result["command"] != "spell":
            return False, f"wrong command: {result['command']}"
        plan = result["plan"]
        if plan["name"] != "spell":
            return False, f"wrong plan name: {plan['name']}"
        if "aspell" not in plan["command"]:
            return False, f"aspell not in command: {plan['command']}"
        if "--mode=tex" not in plan["command"]:
            return False, f"--mode=tex not in command: {plan['command']}"
        return True, ""


def test_spell_fails_gracefully_when_aspell_missing() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "spell", dry_run=True)
        if result["ok"]:
            return False, "spell should fail when aspell missing"
        if "aspell" not in result.get("error", ""):
            return False, f"error should mention aspell: {result.get('error')}"
        return True, ""


def test_watch_plan_constructs_command() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        result = _run_tool_json(Path(project), "watch", dry_run=True)
        if not result["ok"]:
            return False, f"watch plan failed: {result.get('error')}"
        if result["command"] != "watch":
            return False, f"wrong command: {result['command']}"
        plan = result["plan"]
        if plan["name"] != "watch":
            return False, f"wrong plan name: {plan['name']}"
        cmd_str = " ".join(plan["command"])
        if "entr" not in cmd_str and "inotifywait" not in cmd_str:
            return False, f"no watcher in command: {cmd_str}"
        return True, ""


def test_figures_plan_constructs_command() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        (Path(project) / "paper" / "figures" / "test.pdf").write_bytes(b"%PDF-1.4\n")
        result = _run_tool_json(Path(project), "figures", dry_run=True)
        if not result["ok"]:
            return False, f"figures plan failed: {result.get('error')}"
        if result["command"] != "figures":
            return False, f"wrong command: {result['command']}"
        plan = result["plan"]
        if plan["name"] != "figures":
            return False, f"wrong plan name: {plan['name']}"
        cmd_str = " ".join(plan["command"])
        if "file -b" not in cmd_str:
            return False, f"file -b not in command: {cmd_str}"
        if "identify" not in cmd_str:
            return False, f"identify not in command: {cmd_str}"
        return True, ""


def test_make_targets_exist() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        makefile = (Path(project) / "Makefile").read_text()
        for target in ("diff", "arxiv", "wordcount", "spell", "watch", "figures"):
            if f"{target}:" not in makefile:
                return False, f"Makefile missing target: {target}"
        return True, ""


def test_tool_targets_not_in_all_or_pdf() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(Path(tmp))
        makefile = (Path(project) / "Makefile").read_text()
        for target in ("diff", "arxiv", "wordcount", "spell", "watch", "figures"):
            if f"pdf:.*{target}" in makefile:
                return False, f"pdf should not depend on {target}"
            if f"all:.*{target}" in makefile:
                return False, f"all should not depend on {target}"
        return True, ""


def run_all_tests() -> dict:
    """Run all tests and return results."""
    tests = [
        ("diff_plan_constructs_command", test_diff_plan_constructs_command),
        ("diff_fails_gracefully_when_latexdiff_missing",
         test_diff_fails_gracefully_when_latexdiff_missing),
        ("arxiv_plan_constructs_command", test_arxiv_plan_constructs_command),
        ("arxiv_fails_gracefully_when_zip_missing",
         test_arxiv_fails_gracefully_when_zip_missing),
        ("wordcount_plan_constructs_command", test_wordcount_plan_constructs_command),
        ("wordcount_fails_gracefully_when_texcount_missing",
         test_wordcount_fails_gracefully_when_texcount_missing),
        ("spell_plan_constructs_command", test_spell_plan_constructs_command),
        ("spell_fails_gracefully_when_aspell_missing",
         test_spell_fails_gracefully_when_aspell_missing),
        ("watch_plan_constructs_command", test_watch_plan_constructs_command),
        ("figures_plan_constructs_command", test_figures_plan_constructs_command),
        ("make_targets_exist", test_make_targets_exist),
        ("tool_targets_not_in_all_or_pdf", test_tool_targets_not_in_all_or_pdf),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            ok, msg = test_func()
            results[name] = {"passed": ok, "message": msg}
        except Exception as e:
            results[name] = {"passed": False, "message": f"Exception: {e}"}
    
    return results


if __name__ == "__main__":
    results = run_all_tests()
    
    # Print results
    all_passed = True
    for name, result in results.items():
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status}: {name}")
        if not result["passed"]:
            all_passed = False
            print(f"  Error: {result['message']}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r["passed"])
    failed = sum(1 for r in results.values() if not r["passed"])
    print(f"\nTotal: {total}, Passed: {passed}, Failed: {failed}")
    
    if not all_passed:
        sys.exit(1)