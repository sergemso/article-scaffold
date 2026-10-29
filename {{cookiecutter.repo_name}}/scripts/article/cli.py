"""JSON-first command-line adapter over the vendored article core."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import companion, core


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


def _regenerate_metadata(root: Path, args: argparse.Namespace) -> int | None:
    """Refresh the files derived from metadata.yaml before an artifact build.

    Returns an exit code when the build must stop, otherwise None. A dry run only
    reports; it never writes.
    """
    if args.no_regenerate:
        return None
    try:
        metadata = core.load_metadata(root / "metadata.yaml")
        expected = core.collect_expected(root, metadata)
    except (FileNotFoundError, ValueError) as exc:
        if args.json:
            _emit_json({"ok": False, "command": "build", "error": str(exc)})
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return core.ExitCode.DIAGNOSTICS
    if args.dry_run:
        return None
    changed = core.write_expected(expected)
    if changed and not args.json:
        for path in changed:
            print(f"regenerated {path.relative_to(root)} from metadata.yaml", file=sys.stderr)
    return None


def _build(args: argparse.Namespace) -> int:
    root = _root(args)
    stop = _regenerate_metadata(root, args)
    if stop is not None:
        return stop
    if args.kind == "supp":
        return _build_supplementary(root, args)
    if args.kind == "pdf":
        plan = core.pdf_plan(root)
    else:
        reference = root / "reference.docx"
        plan = core.docx_plan(
            root,
            reference_docx="reference.docx" if reference.is_file() else None,
            citation_style=args.citation_style,
        )
    return _run_plan(root, args, plan, kind=args.kind)


def _run_plan(
    root: Path, args: argparse.Namespace, plan: core.BuildPlan, *, kind: str
) -> int:
    payload: dict[str, Any] = {
        "ok": True,
        "command": "build",
        "kind": kind,
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
    if result.returncode == 0 and plan.publish_to:
        try:
            shutil.copyfile(root / plan.output, root / plan.publish_to)
            payload["published_to"] = plan.publish_to
        except OSError as exc:
            payload.update({"ok": False, "error": f"could not copy {plan.output}: {exc.strerror}"})
    if args.json:
        _emit_json(payload)
    else:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if payload.get("error"):
            print(f"ERROR: {payload['error']}", file=sys.stderr)
    return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS


def _build_supplementary(root: Path, args: argparse.Namespace) -> int:
    plans = core.supplementary_plans(root)
    if not plans:
        if args.json:
            _emit_json({"ok": True, "command": "build", "kind": "supp", "plans": []})
        else:
            print("No standalone supplementary .tex found, skipping supplementary PDFs")
        return core.ExitCode.OK
    code = core.ExitCode.OK
    for plan in plans:
        result = _run_plan(root, args, plan, kind="supp")
        if result != core.ExitCode.OK:
            code = result
    return code


def _companion(args: argparse.Namespace) -> int:
    root = _root(args)
    payload: dict[str, Any] = {"ok": True, "command": "companion"}
    try:
        if args.gate:
            payload.update(mode="gate", **companion.gate(root, args.gate))
        else:
            config = companion.read_config(root)
            if config is None:
                raise companion.CompanionError(
                    f"{companion.CONFIG_NAME} not found; run `upgrade` to add it"
                )
            if args.build:
                payload["mode"] = "build"
                payload.update(
                    companion.build(root, config, Path(args.build), args.artifacts)
                )
            else:
                payload["mode"] = "plan"
                payload.update(companion.plan(root, config))
    except (FileNotFoundError, ValueError) as exc:
        payload.update(ok=False, error=str(exc))
        if args.json:
            _emit_json(payload)
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return core.ExitCode.DIAGNOSTICS

    if args.json:
        _emit_json(payload)
    elif payload["mode"] == "gate":
        verdict = "allowed" if payload["allowed"] else "not allowed"
        print(f"release {payload['tag']}: {verdict}")
        for reason in payload["reasons"]:
            print(f"  {reason}")
    else:
        print(f"companion: {payload['repo']} ({payload['branch']})")
        print(f"{len(payload['files'])} files, tree {payload['tree_sha256']}")
        for path in payload["excluded"]:
            print(f"  denied: {path}")
        if payload["mode"] == "plan":
            for item in payload["files"]:
                print(f"  {item['path']}")
    return core.ExitCode.OK


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


def _upgrade(args: argparse.Namespace) -> int:
    """Plan, apply or finish an upgrade to a newer template commit."""
    root = _root(args)
    mode = "apply" if args.apply else "finish" if args.finish else "plan"
    if args.commit and mode != "apply":
        print("usage error: --commit only goes with --apply", file=sys.stderr)
        return core.ExitCode.USAGE
    if args.regenerate and mode != "finish":
        print("usage error: --regenerate only goes with --finish", file=sys.stderr)
        return core.ExitCode.USAGE
    try:
        if mode == "apply":
            payload = core.apply_upgrade(root, args.to, commit=args.commit)
        elif mode == "finish":
            payload = core.finish_upgrade(root, regenerate=args.regenerate)
        else:
            payload = core.plan_upgrade(root, args.to)
    except core.UpgradeError as exc:
        payload = {
            "ok": False,
            "command": "upgrade",
            "error": {"code": exc.code, "message": exc.message},
        }
    payload["mode"] = mode

    if args.json:
        _emit_json(payload)
    else:
        _print_upgrade(payload)
    return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS


def _print_upgrade(payload: dict[str, Any]) -> None:
    if "error" in payload:
        error = payload["error"]
        print(f"ERROR [{error['code']}]: {error['message']}", file=sys.stderr)
        return
    for refusal in payload.get("refusals", []):
        print(f"REFUSED [{refusal['code']}]: {refusal['message']}", file=sys.stderr)
    info = payload.get("plan")
    if info:
        print(f"template: {info['template']}")
        print(f"from {info['old'] or '(unknown)'} to {info['new'] or '(unknown)'}")
        if info["up_to_date"]:
            print("already up to date")
    elif payload.get("up_to_date"):
        print("already up to date")
    elif payload.get("no_changes"):
        print("the template has a newer commit, but it changes none of this repository's files")
    if payload.get("finished"):
        print(f"upgrade finished on {payload['branch']}; review `git diff --cached` and commit")
    elif payload["mode"] == "apply" and payload.get("branch"):
        print(f"branch: {payload['branch']}")
        for key in ("applied", "conflicted"):
            for path in payload[key]:
                print(f"  {key}: {path}")
        for item in payload["skipped"]:
            print(f"  skipped: {item['path']} ({item['reason']})")
        if payload["conflicted"]:
            print("resolve the conflicts, `git add` them, then run `upgrade --finish`")
        else:
            print("run `upgrade --finish` to regenerate derived files and bump the stamp")


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

    build = subparsers.add_parser("build", help="build PDF, DOCX or supplementary PDFs")
    _add_common(build)
    build.add_argument("kind", choices=["pdf", "docx", "supp"])
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
    build.add_argument(
        "--no-regenerate",
        action="store_true",
        help="do not refresh the files derived from metadata.yaml before building",
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

    companion_cmd = subparsers.add_parser(
        "companion", help="plan or build the public companion snapshot"
    )
    _add_common(companion_cmd)
    cmode = companion_cmd.add_mutually_exclusive_group()
    cmode.add_argument(
        "--plan", action="store_true", help="show what would be published (default)"
    )
    cmode.add_argument(
        "--build", metavar="DIR", help="write the snapshot to DIR (empty or absent)"
    )
    cmode.add_argument(
        "--gate", metavar="TAG", help="say whether TAG may produce a public Release"
    )
    companion_cmd.add_argument(
        "--artifacts",
        metavar="DIR",
        help="with --build: directory holding manuscript.pdf, manuscript.docx and supp/",
    )
    companion_cmd.set_defaults(func=_companion)

    upgrade = subparsers.add_parser(
        "upgrade", help="plan or apply an upgrade to a newer template commit"
    )
    _add_common(upgrade)
    mode = upgrade.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="show the upgrade plan (default)")
    mode.add_argument(
        "--apply",
        action="store_true",
        help="apply it on a new branch; conflicts are left to you",
    )
    mode.add_argument(
        "--finish",
        action="store_true",
        help="after resolving conflicts: check, regenerate derived files, re-stamp",
    )
    upgrade.add_argument(
        "--commit",
        action="store_true",
        help="with --apply: also commit the result (for CI), conflict markers included",
    )
    upgrade.add_argument(
        "--regenerate",
        action="store_true",
        help="with --finish: overwrite derived files that differ from metadata.yaml",
    )
    upgrade.add_argument(
        "--to", metavar="REF", help="template branch, tag or commit (default: its HEAD)"
    )
    upgrade.set_defaults(func=_upgrade)

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
