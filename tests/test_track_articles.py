"""Article tracker: read only, flags drift, treats article content as untrusted."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "track_articles", ROOT / "scripts" / "track_articles.py"
)
ta = importlib.util.module_from_spec(spec)
sys.modules["track_articles"] = ta
spec.loader.exec_module(ta)

ORG = "org"
ART = "org/articles.a"
COMP = "org/articles.a.public"


class FakeGh:
    def __init__(self, repos: dict[str, dict]) -> None:
        """repos: full name -> {files, tags, release, runs, info}."""
        self.repos = repos
        self.calls: list[list[str]] = []

    def __call__(self, args, stdin=None):
        args = list(args)
        self.calls.append(args)
        if args[:3] == ["api", "--paginate", "installation/repositories"]:
            return ta.Completed(0, "\n".join(self.repos))
        target = next(a for a in args if a.startswith("repos/"))
        _, owner, name, *rest = target.split("/", 3)
        repo = self.repos.get(f"{owner}/{name}")
        path = rest[0] if rest else ""
        if repo is None:
            return ta.Completed(1, "", "gh: Not Found (HTTP 404)")
        if path.startswith("contents/"):
            text = repo.get("files", {}).get(path.removeprefix("contents/"))
            return ta.Completed(0, text) if text is not None else ta.Completed(1, "", "Not Found")
        if path.startswith("git/matching-refs"):
            return ta.Completed(0, "\n".join(f"refs/tags/{t}" for t in repo.get("tags", [])))
        if path == "releases/latest":
            if repo.get("release"):
                return ta.Completed(0, json.dumps({"tag_name": repo["release"]}))
            return ta.Completed(1, "", "gh: Not Found (HTTP 404)")
        if path.startswith("actions/runs"):
            return ta.Completed(0, json.dumps({"workflow_runs": repo.get("runs", [])}))
        return ta.Completed(0, json.dumps(repo.get("info", {"private": False})))


def article(tags=("v0.1.0",), release="v0.1.0", version="0.1.0", companion=COMP) -> dict:
    return {
        "files": {
            "companion.yaml": yaml.safe_dump({"repo": companion}),
            "metadata.yaml": yaml.safe_dump({"version": version}),
        },
        "tags": list(tags),
        "release": release,
        "runs": [{"name": "Build", "created_at": "2026-10-30T10:00:00Z"}],
    }


def test_in_sync_article_has_no_drift() -> None:
    gh = FakeGh({ART: article(), COMP: {"release": "v0.1.0", "info": {"private": False}}})
    (row,) = ta.track(gh, ORG)
    assert (row.version, row.tag, row.release, row.companion_release) == (
        "0.1.0",
        "v0.1.0",
        "v0.1.0",
        "v0.1.0",
    )
    assert row.build == "Build 2026-10-30"
    assert row.drift == [] and row.problems == []


def test_newest_final_tag_wins_and_prereleases_are_ignored() -> None:
    assert ta.latest_final(["v0.9.0", "v0.10.0", "v1.0.0-rc1", "vnext"]) == "v0.10.0"


def test_newer_article_tag_is_drift() -> None:
    gh = FakeGh({ART: article(tags=["v0.1.0", "v0.2.0"]), COMP: {"release": "v0.1.0", "info": {}}})
    (row,) = ta.track(gh, ORG)
    assert row.drift == ["article v0.2.0 is newer than companion v0.1.0"]


def test_private_companion_is_drift() -> None:
    gh = FakeGh({ART: article(), COMP: {"release": "v0.1.0", "info": {"private": True}}})
    (row,) = ta.track(gh, ORG)
    assert "companion is not public" in row.drift


def test_missing_companion_is_drift_only_once_a_tag_exists() -> None:
    (tagged,) = ta.track(FakeGh({ART: article()}), ORG)
    assert tagged.drift == ["companion repo does not exist"]
    (untagged,) = ta.track(FakeGh({ART: article(tags=(), release="")}), ORG)
    assert untagged.drift == []


def test_repos_without_companion_yaml_and_other_owners_are_skipped() -> None:
    gh = FakeGh(
        {
            "org/plain": {"files": {}},
            "other/articles.b": article(companion="other/articles.b.public"),
            ART: article(),
            COMP: {"release": "v0.1.0"},
        }
    )
    assert [r.repo for r in ta.track(gh, ORG)] == [ART]


def test_hostile_companion_value_is_refused_not_followed() -> None:
    gh = FakeGh({ART: article(companion="evil/steal")})
    (row,) = ta.track(gh, ORG)
    assert row.companion == "" and row.problems
    assert not any("evil" in " ".join(c) for c in gh.calls)


def test_json_and_table_output(capsys) -> None:
    gh = FakeGh({ART: article(), COMP: {"release": "v0.1.0"}})
    assert ta.main(["--owner", ORG, "--json"], run=gh) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["repo"] == ART
    assert ta.main(["--owner", ORG], run=gh) == 0
    assert f"`{ART}`" in capsys.readouterr().out


def test_fail_on_drift_sets_exit_status() -> None:
    gh = FakeGh({ART: article()})
    assert ta.main(["--owner", ORG], run=gh) == 0
    assert ta.main(["--owner", ORG, "--fail-on-drift"], run=gh) == 1


def test_script_only_issues_get_requests() -> None:
    gh = FakeGh({ART: article(), COMP: {"release": "v0.1.0"}})
    ta.track(gh, ORG)
    for call in gh.calls:
        assert call[0] == "api"
        assert "-X" not in call and "--method" not in call and "-f" not in call


def test_workflow_is_read_only_and_never_publishes() -> None:
    text = (ROOT / ".github/workflows/track-articles.yml").read_text()
    doc = yaml.safe_load(text)
    assert "schedule" in doc["on"] and "workflow_dispatch" in doc["on"]
    for scope in [doc.get("permissions", {})] + [
        j.get("permissions", {}) for j in doc["jobs"].values()
    ]:
        assert not any(v == "write" for v in scope.values())
    uses = [s for j in doc["jobs"].values() for s in j["steps"] if "app-token" in s.get("uses", "")]
    assert uses
    for step in uses:
        with_ = step["with"]
        assert "owner" in with_
        assert not any(v == "write" for k, v in with_.items() if k.startswith("permission-"))
    assert "gh release" not in text and "-X" not in text and "git push" not in text
