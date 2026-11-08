"""JSON-first command-line adapter over the vendored article core."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import claims, code_index, companion, core, flow, ledger, sources, terms, theses
from . import index as section_index


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


def _index(args: argparse.Namespace) -> int:
    root = _root(args)
    if getattr(args, "index_action", None) == "slice":
        try:
            result = code_index.slice_symbol(root, args.name, args.file)
        except code_index.CodeIndexError as exc:
            _emit_json({"ok": False, "command": "index slice", "error": str(exc), **exc.extra})
            return core.ExitCode.DIAGNOSTICS
        _emit_json({"ok": True, "command": "index slice", **result})
        return core.ExitCode.OK
    if args.check:
        stale = section_index.check_index(root) + code_index.check_index(root)
        if args.json:
            _emit_json({"ok": not stale, "command": "index", "check": True, "stale": stale})
        else:
            for reason in stale:
                print(f"ERROR: {reason}", file=sys.stderr)
            if not stale:
                print("Section index is current.")
        return core.ExitCode.DIAGNOSTICS if stale else core.ExitCode.OK
    index = section_index.write_index(root)
    code = code_index.write_index(root)
    payload = {
        "ok": True,
        "command": "index",
        "path": section_index.INDEX_PATH.as_posix(),
        "sections": len(index["sections"]),
        "labels": len(index["labels"]),
    }
    broken = []
    if code is not None:
        payload["code_path"] = code_index.INDEX_PATH.as_posix()
        payload["code_files"] = len(code["files"])
        payload["symbols"] = len(code["symbols"])
        broken = [f for f in code["files"] if f["status"] != "ok"]
        payload["unparsed"] = [
            {"file": f["file"], "status": f["status"], "error": f.get("error", "")} for f in broken
        ]
    if args.json:
        _emit_json(payload)
    else:
        print(
            f"Wrote {payload['path']} "
            f"({payload['sections']} sections, {payload['labels']} labels)."
        )
        if code is not None:
            print(
                f"Wrote {payload['code_path']} "
                f"({payload['code_files']} files, {payload['symbols']} symbols)."
            )
            for f in broken:
                print(f"WARNING: {f['file']} not indexed: {f['status']}", file=sys.stderr)
    return core.ExitCode.OK


def _ledger_keyed(args: argparse.Namespace, root: Path) -> ledger.Keyed:
    """Key from ``--input name=PATH`` (file content) and ``--text name=VALUE`` (literal)."""
    values: dict[str, Any] = {}
    for item in args.input or []:
        name, sep, path = item.partition("=")
        if not sep or not name:
            raise ledger.LedgerError(f"--input wants name=PATH, got {item!r}")
        values[name] = (root / path).resolve()
    for item in args.text or []:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise ledger.LedgerError(f"--text wants name=VALUE, got {item!r}")
        values[name] = value
    tools = {}
    for item in args.tool or []:
        name, sep, version = item.partition("=")
        if not sep or not name:
            raise ledger.LedgerError(f"--tool wants name=VERSION, got {item!r}")
        tools[name] = version
    if not args.version or not args.tier:
        raise ledger.LedgerError("give --version and --tier")
    return ledger.key(args.kind, values, args.version, args.tier, tools)


def _ledger(args: argparse.Namespace) -> int:
    root = _root(args)
    action = args.ledger_action
    command = f"ledger {action}"
    try:
        if action in ("get", "explain"):
            if getattr(args, "no_ledger", False):
                os.environ["ARTICLE_LEDGER"] = "off"
            if action == "get" and args.key:
                entry = ledger.get(root, args.kind, args.key)
                digest = args.key
            else:
                keyed = _ledger_keyed(args, root)
                digest = keyed.key
                entry = ledger.lookup(root, keyed) if action == "get" else None
            payload: dict[str, Any] = {"ok": True, "command": command, "key": digest}
            if action == "get":
                payload["hit"] = entry is not None
                if entry is not None:
                    payload["entry"] = entry
                    payload["provenance"] = ledger.provenance(root, args.kind, digest)
                payload["bypassed"] = not ledger.enabled()
                _emit_json(payload)
                return core.ExitCode.OK if entry is not None else core.ExitCode.DIAGNOSTICS
            _emit_json({**payload, **ledger.explain(root, keyed)})
            return core.ExitCode.OK
        if action == "verify":
            problems = ledger.verify(root)
            _emit_json({"ok": not problems, "command": command, "problems": problems})
            return core.ExitCode.DIAGNOSTICS if problems else core.ExitCode.OK
        if action == "evict":
            ledger.evict(root, args.kind, args.key, args.reason)
            _emit_json({"ok": True, "command": command, "key": args.key, "evicted": True})
            return core.ExitCode.OK
        if action == "gc":
            _emit_json({"ok": True, "command": command, **ledger.gc(root, args.apply)})
            return core.ExitCode.OK
        _emit_json({"ok": True, "command": command, "stats": ledger.stats(root, args.reset)})
        return core.ExitCode.OK
    except ledger.LedgerError as exc:
        _emit_json({"ok": False, "command": command, "error": str(exc)})
        return core.ExitCode.DIAGNOSTICS


def _sources(args: argparse.Namespace) -> int:
    root = _root(args)
    action = args.sources_action
    command = f"sources {action}"
    try:
        if action == "add":
            result = sources.add(
                root,
                Path(args.file),
                origin=args.origin,
                edition=args.edition,
                key=args.key,
                terms=args.terms,
                retrieved=args.retrieved,
                media_type=args.media_type,
            )
        elif action == "index":
            result = sources.index(root, args.key, args.force)
        elif action == "slice":
            result = sources.slice_passage(root, args.address, args.window)
        elif action == "diff":
            result = sources.diff(root, args.key, args.old, args.new)
        elif action == "find":
            result = sources.find(root, " ".join(args.query), args.key, args.limit)
        else:
            result = sources.list_sources(root)
    except sources.SourcesError as exc:
        _emit_json({"ok": False, "command": command, "error": str(exc), **exc.extra})
        return core.ExitCode.DIAGNOSTICS
    unreadable = action == "index" and any(r["status"] == "unreadable" for r in result["sources"])
    _emit_json({"ok": True, "command": command, **result})
    return core.ExitCode.DIAGNOSTICS if unreadable else core.ExitCode.OK


def _claims(args: argparse.Namespace) -> int:
    root = _root(args)
    action = args.claims_action
    try:
        if action == "quote-check":
            if args.id is None and not args.all:
                raise ValueError("give a node id or --all")
            results = claims.quote_check(root, None if args.all else args.id)
            bad = [r["id"] for r in results if r["verdict"] == "not-found" or r.get("stale")]
            _emit_json({"ok": not bad, "command": "claims quote-check", "results": results})
            return core.ExitCode.DIAGNOSTICS if bad else core.ExitCode.OK
        if action == "excerpt":
            print(claims.excerpt_for(root, args.id))
            return core.ExitCode.OK
        if action == "rebase":
            proposal = claims.rebase(root, args.id)
            good = proposal["status"] in ("current", "proposed")
            _emit_json({"ok": good, "command": "claims rebase", **proposal})
            return core.ExitCode.OK if good else core.ExitCode.DIAGNOSTICS
        entry = claims.verdict_for_node(root, args.id, args.set)
        _emit_json({"ok": True, "command": f"claims {action}", **entry})
        return core.ExitCode.OK
    except ValueError as exc:
        _emit_json({"ok": False, "command": f"claims {action}", "error": str(exc)})
        return core.ExitCode.DIAGNOSTICS


def _theses(args: argparse.Namespace) -> int:
    root = _root(args)
    action = args.theses_action
    if action == "lint":
        diagnostics = theses.lint(root)
        if diagnostics.ok:
            data = theses.load_map(root)
            diagnostics.extend(terms.check(root, data).diagnostics)
        if args.json:
            _emit_json(diagnostics.to_dict())
        else:
            if diagnostics.items:
                print(diagnostics.format_text(), file=sys.stderr)
            if diagnostics.ok:
                print("Theses map is valid.")
        return core.ExitCode.OK if diagnostics.ok else core.ExitCode.DIAGNOSTICS
    try:
        if action == "accept":
            changed = theses.accept(root, args.id, args.by)
            _emit_json(
                {"ok": True, "command": "theses accept", "id": args.id, "changed": changed}
            )
            return core.ExitCode.OK
        data = theses.load_map(root)
        if data is None:
            raise theses.AcceptError("theses.yaml not found")
        if not theses.structure_errors(data).ok:
            raise theses.AcceptError("theses.yaml does not validate; run `theses lint`")
        if action == "slice":
            _emit_json(theses.slice_map(data, args.id, args.depth))
            return core.ExitCode.OK
        if action == "terms":
            report = terms.check(root, data)
            _emit_json(
                {
                    "ok": report.diagnostics.ok and not report.gaps,
                    "command": "theses terms",
                    "diagnostics": report.diagnostics.to_dict()["diagnostics"],
                    "gaps": report.gaps,
                    "notes": report.notes,
                }
            )
            return core.ExitCode.OK if report.diagnostics.ok else core.ExitCode.DIAGNOSTICS
        kinds = tuple(args.kind) if args.kind else theses.DEFAULT_GAP_KINDS
        found = theses.gaps(data, theses.paper_labels(root), kinds)
        if "term-unregistered" in kinds:
            found += terms.check(root, data).gaps
        _emit_json({"ok": not found, "command": "theses gaps", "gaps": found})
        return core.ExitCode.DIAGNOSTICS if found else core.ExitCode.OK
    except (theses.AcceptError, KeyError) as exc:
        message = exc.args[0] if exc.args else str(exc)
        _emit_json({"ok": False, "command": f"theses {action}", "error": message})
        return core.ExitCode.DIAGNOSTICS


def _confirm_in_terminal(action: str) -> bool:
    """True only when a person types `yes` at an interactive terminal."""
    if not sys.stdin.isatty():
        return False
    print(f"flow {action}: type 'yes' to record this as yourself: ", end="", file=sys.stderr)
    return sys.stdin.readline().strip() == "yes"


def _flow(args: argparse.Namespace) -> int:
    root = _root(args)
    action = args.flow_action
    try:
        if action == "status":
            payload = flow.status(root)
            if args.json:
                _emit_json(payload)
            else:
                for entry in payload["stages"]:
                    print(f"{entry['stage']:<15} {entry['status']:<7} {entry['reason']}")
                    if entry["status"] == "fail":
                        print(f"{'':<15} run: {entry['command']}")
                print(f"current stage: {payload['current_stage']}")
            return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS
        if action == "next":
            if args.open:
                _emit_json(flow.open_orders(root, with_brief=args.brief))
            else:
                _emit_json(flow.next_order(root, with_brief=args.brief))
            return core.ExitCode.OK
        if action == "done":
            payload = flow.done(root, args.order_id)
            _emit_json(payload)
            return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS
        if action == "handoff":
            try:
                raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text("utf-8")
            except OSError as exc:
                raise flow.FlowError(f"cannot read the handoff file: {exc}") from exc
            try:
                data = json.loads(raw)
            except ValueError as exc:
                raise flow.FlowError(f"handoff is not valid JSON: {exc}") from exc
            _emit_json(flow.handoff(root, args.order_id, data))
            return core.ExitCode.OK
        if action == "round":
            if args.round_action == "open":
                payload = flow.round_open(root, args.review)
            else:
                payload = flow.round_close(root)
            _emit_json(payload)
            return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS
        confirmed = _confirm_in_terminal(action)
        if action == "attest":
            payload = flow.attest(root, args.name, args.by, args.why, confirmed=confirmed)
        else:
            payload = flow.waive(
                root, args.stage, args.by, args.why, args.expires, confirmed=confirmed
            )
        _emit_json(payload)
        return core.ExitCode.OK
    except flow.FlowError as exc:
        _emit_json({"ok": False, "command": f"flow {action}", "error": str(exc)})
        return core.ExitCode.DIAGNOSTICS
    raise AssertionError(action)  # pragma: no cover


def _check(args: argparse.Namespace) -> int:
    root = _root(args)
    words = args.words
    if args.cold:
        if words:
            print("usage error: check --cold takes no name", file=sys.stderr)
            return core.ExitCode.USAGE
        try:
            payload = flow.cold_run(root)
        except (flow.FlowError, ledger.LedgerError) as exc:
            _emit_json({"ok": False, "command": "check --cold", "error": str(exc)})
            return core.ExitCode.DIAGNOSTICS
        _emit_json(payload)
        return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS
    record = len(words) == 2 and words[0] == "record"
    if not record and len(words) != 1:  # also covers no name at all
        print("usage error: check takes a name, or `record` and a name", file=sys.stderr)
        return core.ExitCode.USAGE
    name = words[-1]
    command = "check record" if record else "check"
    try:
        payload = flow.check_record(root, name) if record else flow.check_read(root, name)
    except (flow.FlowError, ledger.LedgerError) as exc:
        _emit_json({"ok": False, "command": command, "error": str(exc)})
        return core.ExitCode.DIAGNOSTICS
    _emit_json(payload)
    if record:
        return core.ExitCode.OK if payload["ok"] else core.ExitCode.DIAGNOSTICS
    hit_pass = payload["state"] == "hit" and payload["verdict"] == "pass"
    return core.ExitCode.OK if hit_pass else core.ExitCode.DIAGNOSTICS


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
    for notice in payload.get("notices", []):
        print(f"NOTICE [{notice['code']}]: {notice['message']}", file=sys.stderr)
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

    index_cmd = subparsers.add_parser(
        "index",
        help="write the section index and the code index (paper/build/); `index slice NAME`",
    )
    _add_common(index_cmd)
    index_cmd.add_argument(
        "--check",
        action="store_true",
        help="fail when the index is missing or older than a section; write nothing",
    )
    index_cmd.set_defaults(func=_index)
    index_sub = index_cmd.add_subparsers(dest="index_action")
    i_slice = index_sub.add_parser("slice", help="print one code symbol's lines (JSON)")
    i_slice.add_argument("name", help="qualified symbol name, e.g. Class.method or Type::method")
    i_slice.add_argument("--file", help="only symbols in this file (resolves an ambiguous name)")
    _add_common(i_slice)
    i_slice.set_defaults(func=_index, check=False)

    claims_cmd = subparsers.add_parser(
        "claims", help="check source-claim quotes against local source text"
    )
    claims_sub = claims_cmd.add_subparsers(dest="claims_action", required=True)
    c_check = claims_sub.add_parser(
        "quote-check", help="tier 1: is the quote in the local text? (exit 1 on not-found)"
    )
    _add_common(c_check)
    c_check.add_argument("id", nargs="?")
    c_check.add_argument("--all", action="store_true", help="check every active source-claim")
    c_excerpt = claims_sub.add_parser(
        "excerpt", help="print the matched passage for a local tier-2 judge"
    )
    _add_common(c_excerpt)
    c_excerpt.add_argument("id")
    c_cache = claims_sub.add_parser("cache", help="read or set the tier-2 verdict of a node")
    _add_common(c_cache)
    c_cache.add_argument("id")
    c_cache.add_argument("--set", choices=claims.VERDICTS, help="record a verdict")
    c_record = claims_sub.add_parser(
        "record", help="record the tier-2 verdict of a node in the ledger (same as cache --set)"
    )
    _add_common(c_record)
    c_record.add_argument("id")
    c_record.add_argument("--set", choices=claims.VERDICTS, required=True, help="the verdict")
    c_rebase = claims_sub.add_parser(
        "rebase",
        help="propose the address of a node's quote in the current edition (the map is not edited)",
    )
    _add_common(c_rebase)
    c_rebase.add_argument("id")
    for sub in (c_check, c_excerpt, c_cache, c_record, c_rebase):
        sub.set_defaults(func=_claims)

    ledger_cmd = subparsers.add_parser(
        "ledger", help="read, verify and maintain the committed results ledger"
    )
    ledger_sub = ledger_cmd.add_subparsers(dest="ledger_action", required=True)
    l_get = ledger_sub.add_parser("get", help="look a result up (exit 1 on a miss)")
    l_explain = ledger_sub.add_parser("explain", help="why a lookup misses: the nearest entry")
    for sub in (l_get, l_explain):
        _add_common(sub)
        sub.add_argument("kind", choices=sorted(ledger.KINDS))
        sub.add_argument("--input", action="append", metavar="NAME=PATH", help="a file input")
        sub.add_argument("--text", action="append", metavar="NAME=VALUE", help="a literal input")
        sub.add_argument("--version", help="procedure or check version")
        sub.add_argument("--tier", help="tier of the result")
        sub.add_argument("--tool", action="append", metavar="NAME=VERSION", help="declared tool")
        sub.add_argument("--no-ledger", action="store_true", help="bypass the lookup")
    l_get.add_argument("--key", help="read this exact key instead of computing one")
    l_verify = ledger_sub.add_parser(
        "verify", help="recompute every stored key (exit 1 on a problem)"
    )
    l_evict = ledger_sub.add_parser("evict", help="remove one entry; the only delete, logged")
    l_evict.add_argument("kind", choices=sorted(ledger.KINDS))
    l_evict.add_argument("key")
    l_evict.add_argument("--reason", required=True)
    l_gc = ledger_sub.add_parser("gc", help="report entries whose input files are gone or whose claim left the map")
    l_gc.add_argument("--apply", action="store_true", help="evict and log them")
    l_stats = ledger_sub.add_parser("stats", help="local hit and miss counters, no content")
    l_stats.add_argument("--reset", action="store_true")
    for sub in (l_verify, l_evict, l_gc, l_stats):
        _add_common(sub)
    for sub in (l_get, l_explain, l_verify, l_evict, l_gc, l_stats):
        sub.set_defaults(func=_ledger)

    sources_cmd = subparsers.add_parser(
        "sources", help="add, normalize, index and slice third-party sources (offline)"
    )
    sources_sub = sources_cmd.add_subparsers(dest="sources_action", required=True)
    s_add = sources_sub.add_parser("add", help="copy a file into paper/sources/ and record it")
    s_add.add_argument("file")
    s_add.add_argument("--origin", required=True, help="where the file came from (URL or note)")
    s_add.add_argument("--edition", required=True, help="edition key, e.g. a draft revision")
    s_add.add_argument("--key", help="source key (default: from MANIFEST.md or the file name)")
    s_add.add_argument("--terms", help="a note on the source's terms of use")
    s_add.add_argument("--retrieved", help="retrieval time, UTC ISO 8601 (default: now)")
    s_add.add_argument("--media-type", help="override the media type guessed from the suffix")
    s_index = sources_sub.add_parser(
        "index", help="normalize text and build the locator index (exit 1 if one is unreadable)"
    )
    s_index.add_argument("key", nargs="?", help="only this source")
    s_index.add_argument("--force", action="store_true", help="regenerate normalized text")
    s_slice = sources_sub.add_parser("slice", help="print the passage an address names")
    s_slice.add_argument("address", help="source-key@hash#locator")
    s_slice.add_argument("--window", type=int, default=sources.DEFAULT_WINDOW, help="context lines")
    s_diff = sources_sub.add_parser("diff", help="locators added, removed and changed")
    s_diff.add_argument("key")
    s_diff.add_argument("old", help="old normalized hash (prefix)")
    s_diff.add_argument("new", help="new normalized hash (prefix)")
    s_find = sources_sub.add_parser(
        "find", help="keyword and phrase search; prints addresses with one-line context"
    )
    s_find.add_argument("query", nargs="+", help="terms that must all occur in a passage")
    s_find.add_argument("--key", help="only this source")
    s_find.add_argument("--limit", type=int, default=sources.DEFAULT_FIND_LIMIT)
    s_list = sources_sub.add_parser("list", help="stored sources and MANIFEST.md rows not imported")
    for sub in (s_add, s_index, s_slice, s_diff, s_find, s_list):
        _add_common(sub)
        sub.set_defaults(func=_sources)

    theses_cmd = subparsers.add_parser(
        "theses", help="lint, inspect and promote nodes of the theses map"
    )
    theses_sub = theses_cmd.add_subparsers(dest="theses_action", required=True)
    t_lint = theses_sub.add_parser("lint", help="schema and graph rules")
    _add_common(t_lint)
    t_gaps = theses_sub.add_parser(
        "gaps", help="list gaps (exit 1 when any): ids and one-line text only"
    )
    _add_common(t_gaps)
    t_gaps.add_argument(
        "--kind",
        action="append",
        choices=theses.GAP_KINDS,
        help="gap kind to report (repeatable; default: all but thesis-unattacked)",
    )
    t_slice = theses_sub.add_parser("slice", help="a node and its neighbourhood")
    _add_common(t_slice)
    t_slice.add_argument("id")
    t_slice.add_argument("--depth", type=int, default=1, help="edges to follow (default 1)")
    t_accept = theses_sub.add_parser("accept", help="promote a proposed node (people only)")
    _add_common(t_accept)
    t_accept.add_argument("id")
    t_accept.add_argument("--by", required=True, help="name of the accepting person")
    t_terms = theses_sub.add_parser(
        "terms", help="tier 0 term checks, including the informational notes"
    )
    _add_common(t_terms)
    for sub in (t_lint, t_gaps, t_terms, t_slice, t_accept):
        sub.set_defaults(func=_theses, command="theses")

    check_cmd = subparsers.add_parser(
        "check",
        help="read a named check's stored result, or `check record NAME` to run and store it",
    )
    _add_common(check_cmd)
    check_cmd.add_argument("words", nargs="*", metavar="[record] NAME")
    check_cmd.add_argument(
        "--cold", action="store_true",
        help="run every deterministic check ignoring lookups and record the cold run",
    )
    check_cmd.set_defaults(func=_check, command="check")

    flow_cmd = subparsers.add_parser(
        "flow", help="lifecycle gates, work orders and review rounds"
    )
    flow_sub = flow_cmd.add_subparsers(dest="flow_action", required=True)
    f_status = flow_sub.add_parser("status", help="per-stage gate results from the repo")
    _add_common(f_status)
    f_next = flow_sub.add_parser("next", help="print the first open work order as JSON")
    _add_common(f_next)
    f_next.add_argument(
        "--open", action="store_true",
        help="list every open order of the current stage with parallel_safe marks",
    )
    f_next.add_argument(
        "--brief", action="store_true",
        help="add the compiled brief (finding row, anchor slices, guardrail digest, ledger "
        "hits, verify command) to each order",
    )
    f_done = flow_sub.add_parser(
        "done", help="close an issued order by running its named check (takes the id only)"
    )
    _add_common(f_done)
    f_done.add_argument("order_id")
    f_handoff = flow_sub.add_parser(
        "handoff", help="record the state an agent hands back at its call cap"
    )
    _add_common(f_handoff)
    f_handoff.add_argument("order_id")
    f_handoff.add_argument(
        "--file", required=True, help="handoff JSON (schemas/flow-handoff.schema.json); - is stdin"
    )
    f_attest = flow_sub.add_parser("attest", help="record a human attestation (terminal only)")
    _add_common(f_attest)
    f_attest.add_argument("name", help="for example bibliography or claim:<node id>")
    f_attest.add_argument("--by", required=True, help="name of the person")
    f_attest.add_argument("--why", required=True, help="one-line reason or evidence")
    f_waive = flow_sub.add_parser("waive", help="waive a failing gate until a date (terminal only)")
    _add_common(f_waive)
    f_waive.add_argument("stage", choices=flow.STAGES)
    f_waive.add_argument("--by", required=True, help="name of the person")
    f_waive.add_argument("--why", required=True, help="one-line reason")
    f_waive.add_argument("--expires", required=True, help="YYYY-MM-DD")
    f_round = flow_sub.add_parser("round", help="open a review round from a file, or close it")
    round_sub = f_round.add_subparsers(dest="round_action", required=True)
    r_open = round_sub.add_parser("open", help="one proposed objection node per review item")
    _add_common(r_open)
    r_open.add_argument("--review", required=True, help="local review file in this repository")
    r_close = round_sub.add_parser("close", help="record the round once the gates pass")
    _add_common(r_close)
    for sub in (f_status, f_next, f_done, f_handoff, f_attest, f_waive, r_open, r_close):
        sub.set_defaults(func=_flow, command="flow")

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
