"""JSON-first command-line adapter over the vendored article core."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import core


class UsageError(Exception):
    """Raised instead of argparse's direct process exit."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised via CLI
        raise UsageError(message)


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _validate(args: argparse.Namespace) -> int:
    diagnostics = core.validate_paper(_root(args))
    if args.json:
        _emit_json(diagnostics.to_dict())
    else:
        if diagnostics.items:
            print(diagnostics.format_text(), file=sys.stderr)
        if diagnostics.ok:
            print("All validation checks passed.")
        else:
            print(
                f"ERROR: {len(diagnostics.errors)} validation error(s).",
                file=sys.stderr,
            )
    return core.ExitCode.OK if diagnostics.ok else core.ExitCode.DIAGNOSTICS


def _metadata(args: argparse.Namespace) -> int:
    root = _root(args)
    try:
        metadata = core.load_metadata(root / "metadata.yaml")
        expected = core.collect_expected(root, metadata)
    except (FileNotFoundError, ValueError) as exc:
        payload = {"ok": False, "command": "metadata", "error": str(exc)}
        if args.json:
            _emit_json(payload)
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return core.ExitCode.DIAGNOSTICS

    drift = core.compare_outputs(root, expected)
    if args.check:
        payload = {
            "ok": not drift,
            "command": "metadata",
            "check": True,
            "drift": [item.to_dict() for item in drift],
        }
        if args.json:
            _emit_json(payload)
        elif drift:
            for item in drift:
                print(f"drift: {item.path}", file=sys.stderr)
        else:
            print("metadata-check: generated files are up to date.")
        return core.ExitCode.OK if not drift else core.ExitCode.DIAGNOSTICS

    if args.dry_run:
        payload = {
            "ok": True,
            "command": "metadata",
            "dry_run": True,
            "changed": [item.path for item in drift],
        }
        if args.json:
            _emit_json(payload)
        else:
            for item in drift:
                print(f"would update {item.path}")
        return core.ExitCode.OK

    changed = core.write_expected(expected)
    payload = {
        "ok": True,
        "command": "metadata",
        "dry_run": False,
        "changed": [str(path.relative_to(root)) for path in changed],
    }
    if args.json:
        _emit_json(payload)
    else:
        for path in changed:
            print(f"updated {path.relative_to(root)}")
        print("Done. Review with `git diff` before committing.")
    return core.ExitCode.OK


def _git_state(root: Path) -> tuple[str | None, bool]:
    git = shutil.which("git")
    if git is None:
        return None, False
    branch = subprocess.run(
        [git, "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        [git, "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return (
        branch.stdout.strip() if branch.returncode == 0 else None,
        bool(status.stdout.strip()) if status.returncode == 0 else False,
    )


def _basic_status(root: Path) -> dict[str, Any]:
    branch, dirty = _git_state(root)
    try:
        metadata = core.load_metadata(root / "metadata.yaml")
        valid = True
        drift = bool(core.compare_outputs(root, core.collect_expected(root, metadata)))
    except (FileNotFoundError, ValueError):
        valid = False
        drift = True
    diagnostics = core.validate_paper(root)
    tools = {
        "python": sys.version.split()[0],
        "pandoc": shutil.which("pandoc"),
        "latexmk": shutil.which("latexmk"),
        "git": shutil.which("git"),
    }
    return {
        "schema_version": "1.0",
        "template_version": core.CORE_VERSION,
        "repo": {"root": str(root), "branch": branch, "dirty": dirty},
        "metadata": {"valid": valid, "drift": drift},
        "diagnostics": {
            "errors": len(diagnostics.errors),
            "warnings": len(diagnostics.warnings),
        },
        "tools": tools,
    }


def _status(args: argparse.Namespace) -> int:
    root = _root(args)
    try:
        from .status import build_status  # type: ignore[attr-defined]
    except ImportError:
        payload = _basic_status(root)
    else:
        payload = build_status(root)
    if args.json:
        _emit_json(payload)
    else:
        print(f"root: {payload['repo']['root']}")
        print(f"template: {payload['template_version']}")
        print(f"branch: {payload['repo']['branch']}")
        print(f"dirty: {payload['repo']['dirty']}")
        print(f"metadata valid: {payload['metadata']['valid']}")
        print(f"metadata drift: {payload['metadata']['drift']}")
        print(f"diagnostics: {payload['diagnostics']}")
    return core.ExitCode.OK


def _build(args: argparse.Namespace) -> int:
    root = _root(args)
    if args.kind == "pdf":
        plan = core.pdf_plan(root)
    else:
        reference = root / "reference.docx"
        plan = core.docx_plan(
            root,
            reference_docx="reference.docx" if reference.is_file() else None,
            citation_style=args.citation_style,
        )
    payload: dict[str, Any] = {
        "ok": True,
        "command": "build",
        "kind": args.kind,
        "plan": plan.to_dict(),
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        if args.json:
            _emit_json(payload)
        else:
            print(" ".join(plan.command))
        return core.ExitCode.OK

    executable = shutil.which(plan.command[0])
    if executable is None:
        payload.update(
            {
                "ok": False,
                "error": f"required build tool not found: {plan.command[0]}",
            }
        )
        if args.json:
            _emit_json(payload)
        else:
            print(f"ERROR: {payload['error']}", file=sys.stderr)
        return core.ExitCode.DIAGNOSTICS

    result = subprocess.run(
        list(plan.command),
        cwd=root / plan.cwd,
        capture_output=True,
        text=True,
    )
    payload.update(
        {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if args.json:
        _emit_json(payload)
    else:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    return core.ExitCode.OK if result.returncode == 0 else core.ExitCode.DIAGNOSTICS


def _release(args: argparse.Namespace) -> int:
    root = _root(args)

    if args.apply:
        if not args.yes:
            payload = {
                "ok": False,
                "command": "release",
                "error": "release apply requires explicit --yes flag",
                "dry_run": False,
            }
            if args.json:
                _emit_json(payload)
            else:
                print("ERROR: release apply requires explicit --yes flag", file=sys.stderr)
            return core.ExitCode.USAGE

        result = core.apply_release(root, yes=True)
        payload = {"ok": result["ok"], "command": "release", "apply": True}
        if not result["ok"]:
            payload["error"] = result.get("error", "unknown error")
        else:
            payload.update({k: v for k, v in result.items() if k != "ok"})
        if args.json:
            _emit_json(payload)
        else:
            if not result["ok"]:
                print(f"ERROR: {result.get('error', 'unknown error')}", file=sys.stderr)
            else:
                print(result.get("message", "Release applied successfully"))
        return core.ExitCode.OK if result["ok"] else core.ExitCode.DIAGNOSTICS

    # Plan mode (default)
    plan = core.plan_release(_root(args))

    payload = {"ok": plan.get("ok", False), "command": "release", "dry_run": args.dry_run}
    if "plan" in plan:
        payload["plan"] = plan["plan"]
    elif "error" in plan:
        payload["error"] = plan["error"]

    if args.json:
        _emit_json(payload)
    else:
        if not plan.get("ok", False):
            print(f"ERROR: {plan.get('error', 'unknown error')}", file=sys.stderr)
        else:
            p = plan["plan"]
            print(f"version: {p['version']}")
            print(f"tag: {p['tag']}")
            if p.get("doi"):
                print(f"DOI: {p['doi']}")
            print(f"artifacts: {', '.join(p['artifact_list']) or '(none)'}")
            print("checks:")
            for check, passed in p["checks"].items():
                status = "PASS" if passed else "FAIL"
                print(f"  {check}: {status}")
            if p.get("dry_run_diff"):
                print("dry-run diff:")
                for item in p["dry_run_diff"]:
                    print(f"  {item}")
    return core.ExitCode.OK if plan.get("ok", False) else core.ExitCode.DIAGNOSTICS


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def _tool_plan(args: argparse.Namespace, tool_name: str) -> int:
    """Dispatch to a tool plan from core."""
    root = _root(args)
    try:
        plan_func = core.TOOL_PLANS[tool_name]
    except KeyError:
        payload = {"ok": False, "command": tool_name, "error": f"unknown tool: {tool_name}"}
        if args.json:
            _emit_json(payload)
        else:
            print(f"ERROR: unknown tool: {tool_name}", file=sys.stderr)
        return core.ExitCode.USAGE

    try:
        plan = plan_func(_root(args), dry_run=args.dry_run)
    except Exception as exc:
        payload = {"ok": False, "command": tool_name, "error": f"plan construction failed: {exc}"}
        if args.json:
            _emit_json(payload)
        else:
            print(f"ERROR: {payload['error']}", file=sys.stderr)
        return core.ExitCode.DIAGNOSTICS

    payload: dict[str, Any] = {
        "ok": True,
        "command": tool_name,
        "plan": plan.to_dict(),
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        if args.json:
            _emit_json(payload)
        else:
            print(" ".join(plan.command))
        return core.ExitCode.OK

    executable = shutil.which(plan.command[0])
    if executable is None:
        payload.update(
            {
                "ok": False,
                "error": f"required tool not found: {plan.command[0]}",
            }
        )
        if args.json:
            _emit_json(payload)
        else:
            print(f"ERROR: {payload['error']}", file=sys.stderr)
        return core.ExitCode.DIAGNOSTICS

    result = subprocess.run(
        list(plan.command),
        cwd=root / plan.cwd,
        capture_output=True,
        text=True,
    )
    payload.update(
        {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if args.json:
        _emit_json(payload)
    else:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    return core.ExitCode.OK if result.returncode == 0 else core.ExitCode.DIAGNOSTICS


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python3 -m scripts.article",
        description="Validate, inspect, and build a scaffolded article repository.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repository root (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate paper sources")
    _add_common(validate)
    validate.set_defaults(func=_validate)

    metadata = subparsers.add_parser(
        "metadata", help="regenerate derived metadata from metadata.yaml"
    )
    _add_common(metadata)
    metadata.add_argument(
        "--check",
        action="store_true",
        help="compare generated files with disk; write nothing",
    )
    metadata.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change; write nothing",
    )
    metadata.set_defaults(func=_metadata)

    status = subparsers.add_parser("status", help="report repository status")
    _add_common(status)
    status.set_defaults(func=_status)

    build = subparsers.add_parser("build", help="build PDF or DOCX")
    _add_common(build)
    build.add_argument("kind", choices=["pdf", "docx"])
    build.add_argument(
        "--dry-run",
        action="store_true",
        help="print the command without running it",
    )
    build.add_argument(
        "--citation-style",
        choices=["numeric", "author-year"],
        default=None,
        help="override the metadata citation style for DOCX",
    )
    build.set_defaults(func=_build)

    release = subparsers.add_parser("release", help="plan or apply a release")
    _add_common(release)
    release.add_argument(
        "--dry-run",
        action="store_true",
        help="show the release plan without applying it",
    )
    release.add_argument(
        "--apply",
        action="store_true",
        help="apply the release (requires --yes)",
    )
    release.add_argument(
        "--yes",
        action="store_true",
        help="confirm release application (required with --apply)",
    )
    release.set_defaults(func=_release)

    # Tool subcommands
    diff = subparsers.add_parser("diff", help="generate latexdiff between two refs")
    _add_common(diff)
    diff.add_argument("--old-ref", default="HEAD~1", help="old git ref (default: HEAD~1)")
    diff.add_argument("--new-ref", default="HEAD", help="new git ref (default: HEAD)")
    diff.add_argument("--output", help="output PDF filename")
    diff.add_argument("--dry-run", action="store_true", help="print command without running")
    diff.set_defaults(func=lambda a: _tool_plan(a, "diff"))

    arxiv = subparsers.add_parser("arxiv", help="create arXiv submission zip")
    _add_common(arxiv)
    arxiv.add_argument("--output", default="arxiv-submission.zip", help="output zip filename")
    arxiv.add_argument("--dry-run", action="store_true", help="print command without running")
    arxiv.set_defaults(func=lambda a: _tool_plan(a, "arxiv"))

    wordcount = subparsers.add_parser("wordcount", help="count words with texcount")
    _add_common(wordcount)
    wordcount.add_argument("--dry-run", action="store_true", help="print command without running")
    wordcount.set_defaults(func=lambda a: _tool_plan(a, "wordcount"))

    spell = subparsers.add_parser("spell", help="spell-check with aspell")
    _add_common(spell)
    spell.add_argument("--dry-run", action="store_true", help="print command without running")
    spell.set_defaults(func=lambda a: _tool_plan(a, "spell"))

    watch = subparsers.add_parser("watch", help="live-reload PDF on changes")
    _add_common(watch)
    watch.add_argument("--dry-run", action="store_true", help="print command without running")
    watch.set_defaults(func=lambda a: _tool_plan(a, "watch"))

    figures = subparsers.add_parser("figures", help="list figure files with metadata")
    _add_common(figures)
    figures.add_argument("--dry-run", action="store_true", help="print command without running")
    figures.set_defaults(func=lambda a: _tool_plan(a, "figures"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return core.ExitCode.USAGE
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - the CLI boundary maps failures to 3
        if getattr(args, "json", False):
            _emit_json({"ok": False, "command": args.command, "error": str(exc)})
        else:
            print(f"internal error: {exc}", file=sys.stderr)
        return core.ExitCode.INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
