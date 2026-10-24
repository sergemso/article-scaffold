#!/usr/bin/env python3
"""Install the `article upgrade` command into a repo generated before it existed.

Run from the root of the generated repo (standard library only):

    python3 bootstrap-upgrader.py --template <path-or-url> [--ref REF]

It copies `scripts/article/` and `schemas/*.json` from the template at REF into the
current directory, then prints what to do next. It never touches `metadata.yaml`,
`paper/` or `analysis/`, and it refuses to overwrite an existing `scripts/article/`
unless you pass --force. Review `git diff` afterwards; nothing is committed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAYLOAD = "{{cookiecutter.repo_name}}"


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"error: git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _stored_template(repo: Path) -> str | None:
    try:
        stamp = json.loads((repo / "template.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    template = stamp.get("template")
    return template if isinstance(template, str) and template else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--template", help="template path or URL (default: template.json)")
    parser.add_argument("--ref", default="HEAD", help="branch, tag or commit (default: HEAD)")
    parser.add_argument("--repo", default=".", help="generated repo root (default: .)")
    parser.add_argument("--force", action="store_true", help="replace an existing scripts/article/")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / "metadata.yaml").is_file():
        raise SystemExit(f"error: {repo} has no metadata.yaml; run this in a generated repo")
    template = args.template or _stored_template(repo)
    if not template:
        raise SystemExit("error: no template.json to read the template from; pass --template")

    target = repo / "scripts" / "article"
    if target.exists() and not args.force:
        raise SystemExit(
            "error: scripts/article/ already exists. Use `python3 -m scripts.article upgrade`, "
            "or pass --force to replace it."
        )

    with tempfile.TemporaryDirectory(prefix="bootstrap-upgrader-") as tmp:
        checkout = Path(tmp) / "template"
        _git("clone", "--quiet", "--no-checkout", template, str(checkout))
        _git("checkout", "--quiet", args.ref, cwd=checkout)
        commit = _git("rev-parse", "HEAD", cwd=checkout)
        source = checkout / PAYLOAD
        if not (source / "scripts" / "article" / "upgrade.py").is_file():
            raise SystemExit(f"error: {args.ref} of {template} has no upgrade command")

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            source / "scripts" / "article", target, ignore=shutil.ignore_patterns("__pycache__")
        )
        schemas = repo / "schemas"
        schemas.mkdir(exist_ok=True)
        for schema in sorted((source / "schemas").glob("*.json")):
            if args.force or not (schemas / schema.name).exists():
                shutil.copy2(schema, schemas / schema.name)

    print(f"Installed scripts/article/ from {template} @ {commit[:12]}")
    print("Next:")
    print("  1. python3 -m pip install cookiecutter PyYAML")
    print("  2. git add scripts schemas && git commit -m 'chore: add the article upgrade command'")
    print("  3. python3 -m scripts.article upgrade --plan")
    if not (repo / "template.json").is_file():
        print("Note: no template.json, so --plan will refuse. Follow docs/upgrading.md")
        print("      (Three-way merge by hand) for this first upgrade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
