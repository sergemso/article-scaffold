"""Companion provisioning: idempotent, owner-bound, and the token never leaks."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "provision_companion", ROOT / "scripts" / "provision_companion.py"
)
pc = importlib.util.module_from_spec(spec)
sys.modules["provision_companion"] = pc
spec.loader.exec_module(pc)

TOKEN = "github_pat_SECRETVALUE123"  # go-getter:allow-secret (fake test value)
ART = "me/articles.topic"
COMP = "me/articles.topic.public"


class FakeGh:
    def __init__(self, files: dict[str, str], repos: dict[str, dict] | None = None) -> None:
        self.files = files  # article repo -> companion.yaml text
        self.repos = repos if repos is not None else {}
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, args, stdin=None):
        args = list(args)
        self.calls.append((args, stdin))
        if args[:2] == ["repo", "list"]:
            names = ["articles.topic", "articles.other", "unrelated", "articles.bare"]
            return pc.Completed(0, "\n".join(names))
        if args[0] == "api" and "contents/companion.yaml" in args[-1]:
            repo = args[-1].split("/")[1] + "/" + args[-1].split("/")[2]
            if repo in self.files:
                return pc.Completed(0, self.files[repo])
            return pc.Completed(1, "", "gh: Not Found (HTTP 404)")
        if args[0] == "api":
            repo = args[1].removeprefix("repos/")
            if repo in self.repos:
                return pc.Completed(0, json.dumps(self.repos[repo]))
            return pc.Completed(1, "", "gh: Not Found (HTTP 404)")
        if args[:2] == ["repo", "create"]:
            self.repos[args[2]] = {
                "private": False,
                "description": "",
                "topics": [],
                "has_wiki": True,
                "has_projects": True,
            }
            return pc.Completed(0)
        if args[:2] == ["repo", "edit"]:
            repo = self.repos[args[2]]
            repo["description"] = args[args.index("--description") + 1]
            repo["topics"] = [args[i + 1] for i, a in enumerate(args) if a == "--add-topic"]
            repo["has_wiki"] = repo["has_projects"] = False
            return pc.Completed(0)
        if args[:2] == ["secret", "set"]:
            return pc.Completed(0)
        raise AssertionError(f"unexpected gh call {args}")

    def writes(self) -> list[list[str]]:
        return [
            a
            for a, _ in self.calls
            if a[:2] in (["repo", "create"], ["repo", "edit"], ["secret", "set"])
        ]


def _yaml(repo: str) -> str:
    return yaml.safe_dump(
        {"version": 1, "repo": repo, "branch": "main", "include": ["a"], "exclude": []}
    )


def _run(fake, *argv, monkeypatch, capsys):
    monkeypatch.setenv("COMPANION_PAT", TOKEN)
    code = pc.main(["--json", *argv], run=fake)
    return code, json.loads(capsys.readouterr().out)["results"]


def test_creates_when_absent_then_rerun_is_unchanged(monkeypatch, capsys) -> None:
    fake = FakeGh({ART: _yaml(COMP)})
    code, res = _run(fake, "--repo", ART, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0 and res[0]["status"] == "created" and res[0]["secret"] == "refreshed"
    assert fake.repos[COMP]["description"] == pc._description(ART)
    code, res = _run(fake, "--repo", ART, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0 and res[0]["status"] == "unchanged"
    assert not any(a[:2] == ["repo", "create"] for a, _ in fake.calls[-4:])


def test_existing_public_companion_gets_description_and_topics(monkeypatch, capsys) -> None:
    repos = {
        COMP: {
            "private": False,
            "description": "old",
            "topics": [],
            "has_wiki": False,
            "has_projects": False,
        }
    }
    fake = FakeGh({ART: _yaml(COMP)}, repos)
    code, res = _run(fake, "--repo", ART, monkeypatch=monkeypatch, capsys=capsys)
    assert res[0]["status"] == "updated" and code == 0
    assert set(fake.repos[COMP]["topics"]) == set(pc.TOPICS)


def test_private_companion_is_drift_and_untouched(monkeypatch, capsys) -> None:
    repos = {COMP: {"private": True, "visibility": "private"}}
    fake = FakeGh({ART: _yaml(COMP)}, repos)
    code, res = _run(fake, "--repo", ART, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 1 and res[0]["status"] == "drift"
    assert fake.writes() == []


@pytest.mark.parametrize(
    "companion",
    [
        "other/articles.topic.public",
        "me/articles.topic",
        "me/../x",
        "-me/x",
        "no-slash",
        "me/a b",
        "me/x/y",
    ],
)
def test_foreign_owner_and_malformed_names_are_refused(companion, monkeypatch, capsys) -> None:
    fake = FakeGh({ART: _yaml(companion)})
    code, res = _run(fake, "--repo", ART, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 1 and res[0]["status"] == "refused"
    assert fake.writes() == []


def test_missing_companion_yaml_needs_upgrade(monkeypatch, capsys) -> None:
    fake = FakeGh({})
    code, res = _run(fake, "--repo", ART, monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0 and res[0]["status"] == "needs-upgrade"
    assert fake.writes() == []


def test_dry_run_makes_no_write_calls(monkeypatch, capsys) -> None:
    fake = FakeGh({ART: _yaml(COMP)})
    monkeypatch.delenv("COMPANION_PAT", raising=False)
    code = pc.main(["--json", "--repo", ART, "--dry-run"], run=fake)
    res = json.loads(capsys.readouterr().out)["results"]
    assert code == 0 and res[0]["status"] == "created"
    assert fake.writes() == [] and COMP not in fake.repos


def test_empty_token_fails_unless_dry_run(monkeypatch, capsys) -> None:
    monkeypatch.setenv("COMPANION_PAT", "")
    fake = FakeGh({ART: _yaml(COMP)})
    assert pc.main(["--repo", ART], run=fake) == 2
    assert "COMPANION_PAT" in capsys.readouterr().err
    assert fake.calls == []


def test_token_goes_only_to_stdin_of_secret_set(monkeypatch, capsys) -> None:
    fake = FakeGh({ART: _yaml(COMP)})
    monkeypatch.setenv("COMPANION_PAT", TOKEN)
    pc.main(["--repo", ART, "--json"], run=fake)
    out = capsys.readouterr()
    assert TOKEN not in out.out + out.err
    for args, stdin in fake.calls:
        assert all(TOKEN not in a for a in args)
        if stdin is not None:
            assert args[:3] == ["secret", "set", "COMPANION_TOKEN"] and stdin == TOKEN
        assert "GH_PAT" not in " ".join(args)


def test_all_filters_to_articles_with_companion_yaml(monkeypatch, capsys) -> None:
    other = "me/articles.other"
    fake = FakeGh({ART: _yaml(COMP), other: _yaml("me/articles.other.public")})
    code, res = _run(fake, "--repo", "all", "--owner", "me", monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0
    assert [r["repo"] for r in res] == [
        other,
        ART,
    ]  # sorted; articles.bare lacks the file, unrelated skipped
    assert not any("unrelated" in " ".join(a) for a, _ in fake.calls)


def test_all_requires_owner(monkeypatch, capsys) -> None:
    monkeypatch.setenv("COMPANION_PAT", TOKEN)
    assert pc.main(["--repo", "all"], run=FakeGh({})) == 2


def test_workflow_triggers_and_secret_handling() -> None:
    text = (ROOT / ".github/workflows/provision-companion.yml").read_text()
    doc = yaml.safe_load(text)
    assert {"workflow_dispatch", "workflow_call"} <= set(doc["on"])
    assert doc["on"]["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True
    assert doc["on"]["workflow_call"]["secrets"]["GH_PAT"]["required"] is False
    assert doc["on"]["workflow_call"]["secrets"]["COMPANION_PAT"]["required"] is False
    assert "zenodo.org/account/settings/github" in text and "upgrade" in text
    assert "gh secret set" not in text  # the script owns secret setting
    assert "secrets.GH_PAT" in text and "secrets.COMPANION_PAT" in text
    script = (ROOT / "scripts/provision_companion.py").read_text()
    assert "GH_PAT" not in script.replace("GH_PAT`", "").replace("with GH_PAT.", "")
