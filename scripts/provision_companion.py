#!/usr/bin/env python3
"""Provision the public companion repo of one or all article repos.

    python3 scripts/provision_companion.py --repo OWNER/NAME [--dry-run] [--json]
    python3 scripts/provision_companion.py --repo all --owner OWNER

For each article repo it reads `companion.yaml` from the default branch, creates the
public companion if it is absent and re-applies its description and topics. It never
changes the visibility of an existing repo and never deletes anything. Needs `gh`
authenticated through GH_TOKEN with an App installation token for the owner
(Administration write, Contents read; decision 0062). Standard library plus PyYAML.

`companion.yaml` is author-editable, so its `repo` value is untrusted input here: it
must match the schema pattern, share the article repo's owner and differ from it.
Exit status is nonzero when any repo ends `error`, `refused` or `drift`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import yaml

ARTICLE_PREFIX = "articles."
TOPICS = ("article", "manuscript", "latex", "zenodo")
FAILING = {"error", "refused", "drift"}

REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass
class Completed:
    returncode: int
    stdout: str = ""
    stderr: str = ""


Runner = Callable[[Sequence[str], "str | None"], Completed]


def gh_runner(args: Sequence[str], stdin: str | None = None) -> Completed:
    """Run `gh`; the one place that shells out."""
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    return Completed(result.returncode, result.stdout, result.stderr)


@dataclass
class Result:
    repo: str
    status: str
    companion: str = ""
    detail: str = ""
    changes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "repo": self.repo,
            "status": self.status,
            "companion": self.companion,
            "detail": self.detail,
            "changes": self.changes,
        }


def _description(article: str) -> str:
    return f"Public companion (release snapshots) of {article}"


def _is_missing(done: Completed) -> bool:
    return done.returncode != 0 and ("404" in done.stderr or "Not Found" in done.stderr)


def list_article_repos(run: Runner, owner: str) -> list[str]:
    done = run(
        ["repo", "list", owner, "--limit", "1000", "--json", "name", "--jq", ".[].name"], None
    )
    if done.returncode != 0:
        raise RuntimeError(f"cannot list repos of {owner}: {done.stderr.strip()}")
    names = [n.strip() for n in done.stdout.splitlines() if n.strip().startswith(ARTICLE_PREFIX)]
    return sorted(f"{owner}/{n}" for n in names)


def read_companion_repo(run: Runner, article: str) -> tuple[str | None, str]:
    """(companion repo, problem). Both None/empty when companion.yaml is absent."""
    done = run(
        [
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{article}/contents/companion.yaml",
        ],
        None,
    )
    if _is_missing(done):
        return None, ""
    if done.returncode != 0:
        return None, f"cannot read companion.yaml: {done.stderr.strip()}"
    try:
        data = yaml.safe_load(done.stdout)
    except yaml.YAMLError:
        return None, "companion.yaml is not valid YAML"
    repo = data.get("repo") if isinstance(data, dict) else None
    if not isinstance(repo, str):
        return None, "companion.yaml has no string `repo`"
    return repo, ""


def refusal(article: str, companion: str) -> str:
    """Why `companion` may not be provisioned for `article`, or ''."""
    if not REPO_RE.match(companion):
        return f"companion repo {companion!r} is not OWNER/NAME"
    a_owner, a_name = article.split("/", 1)
    c_owner, c_name = companion.split("/", 1)
    if c_owner.lower() != a_owner.lower():
        return "companion owner differs from the article repo owner"
    if c_name.lower() == a_name.lower():
        return "companion must be a different repo from the article repo"
    return ""


def provision_one(run: Runner, article: str, *, dry_run: bool) -> Result:
    if not REPO_RE.match(article):
        return Result(article, "refused", detail="article repo is not OWNER/NAME")
    companion, problem = read_companion_repo(run, article)
    if problem:
        status = "error" if problem.startswith("cannot read") else "refused"
        return Result(article, status, detail=problem)
    if companion is None:
        return Result(
            article, "needs-upgrade", detail="no companion.yaml; run upgrade in the article repo"
        )
    why = refusal(article, companion)
    if why:
        return Result(article, "refused", companion, why)

    result = Result(article, "unchanged", companion)
    view = run(["api", f"repos/{companion}"], None)
    if _is_missing(view):
        exists = False
    elif view.returncode != 0:
        return Result(
            article, "error", companion, f"cannot inspect companion: {view.stderr.strip()}"
        )
    else:
        exists = True
        info = json.loads(view.stdout)
        if info.get("private") or info.get("visibility") not in (None, "public"):
            return Result(
                article, "drift", companion, "companion exists but is not public; left untouched"
            )

    description = _description(article)
    edit = ["repo", "edit", companion, "--description", description]
    for topic in TOPICS:
        edit += ["--add-topic", topic]
    edit += ["--enable-wiki=false", "--enable-projects=false"]

    if not exists:
        result.status = "created"
        result.changes.append("create public repo")
        if not dry_run:
            done = run(
                ["repo", "create", companion, "--public", f"--description={description}"], None
            )
            if done.returncode != 0:
                return Result(article, "error", companion, f"create failed: {done.stderr.strip()}")
            done = run(edit, None)
            if done.returncode != 0:
                return Result(article, "error", companion, f"edit failed: {done.stderr.strip()}")
    else:
        if info.get("description") != description:
            result.changes.append("description")
        if not set(TOPICS) <= set(info.get("topics") or []):
            result.changes.append("topics")
        if info.get("has_wiki") or info.get("has_projects"):
            result.changes.append("features")
        if result.changes:
            result.status = "updated"
            if not dry_run:
                done = run(edit, None)
                if done.returncode != 0:
                    return Result(
                        article, "error", companion, f"edit failed: {done.stderr.strip()}"
                    )

    return result


def provision(run: Runner, repo: str, owner: str, *, dry_run: bool) -> list[Result]:
    if repo == "all":
        if not owner:
            raise ValueError("--owner is required with --repo all")
        articles = list_article_repos(run, owner)
        results = []
        for article in articles:
            res = provision_one(run, article, dry_run=dry_run)
            if res.status != "needs-upgrade":
                results.append(res)
        return results
    return [provision_one(run, repo, dry_run=dry_run)]


def main(argv: list[str] | None = None, run: Runner = gh_runner) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", required=True, help="OWNER/NAME of an article repo, or `all`")
    parser.add_argument("--owner", default="", help="owner whose articles.* repos `all` covers")
    parser.add_argument("--dry-run", action="store_true", help="read only; make no changes")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args(argv)

    try:
        results = provision(run, args.repo, args.owner, dry_run=args.dry_run)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {"dry_run": args.dry_run, "results": [r.as_dict() for r in results]}, indent=2
            )
        )
    else:
        for r in results:
            line = f"{r.status:13} {r.repo}"
            if r.companion:
                line += f" -> {r.companion}"
            if r.detail:
                line += f"  ({r.detail})"
            print(line)
    return 1 if any(r.status in FAILING for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
