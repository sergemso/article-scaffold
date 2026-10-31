#!/usr/bin/env python3
"""Report the release state of every article repo an App installation can see.

    python3 scripts/track_articles.py --owner OWNER [--json] [--fail-on-drift]

An article repo is a repository of the installation that holds `companion.yaml`. For each
one it reads the version in `metadata.yaml`, the latest final `vX.Y.Z` tag and Release,
the latest successful workflow run and the companion's latest Release, then flags drift:
the article tag is newer than the companion's, or the companion is missing or private.
Read only: it never publishes. Needs `gh` authenticated through GH_TOKEN with an App
installation token for the owner (Contents, Actions and Metadata read; decision 0063).
Standard library plus PyYAML. Everything read from an article repo is untrusted input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision_companion import (  # noqa: E402
    REPO_RE,
    Completed,
    Runner,
    _is_missing,
    gh_runner,
    read_companion_repo,
    refusal,
)

__all__ = ["Completed", "Runner", "gh_runner", "track", "main"]

FINAL_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


@dataclass
class Row:
    repo: str
    companion: str = ""
    version: str = ""
    tag: str = ""
    release: str = ""
    build: str = ""
    companion_release: str = ""
    companion_private: bool = False
    drift: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "repo": self.repo,
            "companion": self.companion,
            "version": self.version,
            "tag": self.tag,
            "release": self.release,
            "build": self.build,
            "companion_release": self.companion_release,
            "companion_private": self.companion_private,
            "drift": self.drift,
            "problems": self.problems,
        }


def _key(tag: str) -> tuple[int, int, int] | None:
    m = FINAL_TAG_RE.match(tag)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def latest_final(tags: list[str]) -> str:
    keyed = [(k, t) for t in tags if (k := _key(t))]
    return max(keyed)[1] if keyed else ""


def _json(done: Completed):
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return None


def list_installation_repos(run: Runner) -> list[str]:
    done = run(
        ["api", "--paginate", "installation/repositories", "--jq", ".repositories[].full_name"],
        None,
    )
    if done.returncode != 0:
        raise RuntimeError(f"cannot list installation repositories: {done.stderr.strip()}")
    return sorted(n.strip() for n in done.stdout.splitlines() if REPO_RE.match(n.strip()))


def _version(run: Runner, repo: str) -> str:
    done = run(
        ["api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/metadata.yaml"],
        None,
    )
    if done.returncode != 0:
        return ""
    try:
        data = yaml.safe_load(done.stdout)
    except yaml.YAMLError:
        return ""
    value = data.get("version") if isinstance(data, dict) else None
    return str(value) if value is not None else ""


def _latest_release(run: Runner, repo: str) -> tuple[str, str]:
    """(tag, problem); tag is '' when the repo has no Release."""
    done = run(["api", f"repos/{repo}/releases/latest"], None)
    if _is_missing(done):
        return "", ""
    data = _json(done) if done.returncode == 0 else None
    if not isinstance(data, dict):
        return "", f"cannot read releases of {repo}: {done.stderr.strip()}"
    return str(data.get("tag_name") or ""), ""


def track_one(run: Runner, repo: str) -> Row | None:
    """The row for one repo, or None when it is not an article repo."""
    companion, problem = read_companion_repo(run, repo)
    if companion is None and not problem:
        return None
    row = Row(repo)
    if problem:
        row.problems.append(problem)
    row.version = _version(run, repo)

    refs = run(
        ["api", "--paginate", f"repos/{repo}/git/matching-refs/tags/v", "--jq", ".[].ref"], None
    )
    if refs.returncode == 0:
        row.tag = latest_final([r.strip().removeprefix("refs/tags/") for r in refs.stdout.split()])
    else:
        row.problems.append(f"cannot read tags: {refs.stderr.strip()}")
    row.release, bad = _latest_release(run, repo)
    if bad:
        row.problems.append(bad)

    runs = run(["api", f"repos/{repo}/actions/runs?status=success&per_page=1"], None)
    data = _json(runs) if runs.returncode == 0 else None
    if isinstance(data, dict) and data.get("workflow_runs"):
        latest = data["workflow_runs"][0]
        row.build = f"{latest.get('name', '')} {str(latest.get('created_at', ''))[:10]}".strip()

    if companion is None:
        return row
    why = refusal(repo, companion)
    if why:
        row.problems.append(why)
        return row
    row.companion = companion

    view = run(["api", f"repos/{companion}"], None)
    info = _json(view) if view.returncode == 0 else None
    if _is_missing(view):
        if row.tag:
            row.drift.append("companion repo does not exist")
        return row
    if not isinstance(info, dict):
        row.problems.append(f"cannot inspect companion: {view.stderr.strip()}")
        return row
    row.companion_private = bool(info.get("private")) or info.get("visibility") not in (
        None,
        "public",
    )
    if row.companion_private:
        row.drift.append("companion is not public")
    row.companion_release, bad = _latest_release(run, companion)
    if bad:
        row.problems.append(bad)
    if _key(row.tag) and (_key(row.companion_release) or (0, 0, 0)) < _key(row.tag):
        row.drift.append(
            f"article {row.tag} is newer than companion {row.companion_release or '-'}"
        )
    return row


def track(run: Runner, owner: str) -> list[Row]:
    rows = []
    for repo in list_installation_repos(run):
        if repo.split("/", 1)[0].lower() != owner.lower():
            continue
        row = track_one(run, repo)
        if row is not None:
            rows.append(row)
    return rows


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ") if text else "-"


def render_table(rows: list[Row]) -> str:
    lines = [
        "| Article repo | Version | Tag | Release | Last good run | Companion "
        "| Companion release | Drift |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        flags = "; ".join(r.drift + r.problems)
        cells = [
            f"`{r.repo}`",
            r.version,
            r.tag,
            r.release,
            r.build,
            f"`{r.companion}`" if r.companion else "",
            r.companion_release,
            flags,
        ]
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None, run: Runner = gh_runner) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--owner", required=True, help="owner whose installation repos to scan")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    parser.add_argument("--fail-on-drift", action="store_true", help="exit 1 when any row drifts")
    args = parser.parse_args(argv)

    try:
        rows = track(run, args.owner)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"owner": args.owner, "results": [r.as_dict() for r in rows]}, indent=2))
    else:
        print(render_table(rows))
    return 1 if args.fail_on_drift and any(r.drift for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
