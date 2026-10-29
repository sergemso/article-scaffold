"""article companion: snapshot, deny patterns, leak scan and release gate."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import render, run


def _companion(project: Path, *args: str):
    result = run(project, "python3", "-m", "scripts.article", "companion", "--json", *args)
    payload = json.loads(result.stdout)
    jsonschema.validate(
        payload,
        json.loads((project / "schemas" / "companion-result.schema.json").read_text()),
    )
    return result, payload


def _artifacts(tmp_path: Path) -> Path:
    art = tmp_path / "artifacts"
    (art / "supp").mkdir(parents=True)
    (art / "manuscript.pdf").write_bytes(b"%PDF-1.5 dummy")
    (art / "manuscript.docx").write_bytes(b"PK dummy")
    (art / "supp" / "s1.pdf").write_bytes(b"%PDF-1.5 supp")
    return art


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    return render(tmp_path=tmp_path)


def _paths(payload: dict) -> list[str]:
    return [item["path"] for item in payload["files"]]


def test_plan_lists_allowlist_and_is_read_only(project: Path) -> None:
    def tree() -> list[str]:
        return sorted(
            p.as_posix()
            for p in project.rglob("*")
            if ".git/" not in p.as_posix() and "__pycache__" not in p.as_posix()
        )

    before = tree()
    result, payload = _companion(project)

    assert result.returncode == 0, result.stderr
    assert payload["mode"] == "plan"
    paths = _paths(payload)
    assert "CITATION.cff" in paths and ".zenodo.json" in paths
    assert any(p.startswith("paper/") for p in paths)
    assert not any(p.startswith((".github/", "scripts/", "docs/", ".git/")) for p in paths)
    assert before == tree()


def test_build_copies_allowlist_and_artifacts(project: Path, tmp_path: Path) -> None:
    snap = tmp_path / "snap"
    result, payload = _companion(
        project, "--build", str(snap), "--artifacts", str(_artifacts(tmp_path))
    )

    assert result.returncode == 0, result.stderr
    paths = _paths(payload)
    assert "manuscript.pdf" in paths and "manuscript.docx" in paths
    assert "supp/s1.pdf" in paths
    assert (snap / "manuscript.pdf").read_bytes() == b"%PDF-1.5 dummy"
    assert any(p.startswith("paper/") for p in paths)
    assert not any(p.startswith((".github/", "scripts/", "docs/")) for p in paths)
    on_disk = sorted(
        p.relative_to(snap).as_posix() for p in snap.rglob("*") if p.is_file()
    )
    assert on_disk == paths


def test_snapshot_metadata_names_only_the_companion(project: Path, tmp_path: Path) -> None:
    assert "test-user/articles.test_topic\"" in (project / "metadata.yaml").read_text()
    snap = tmp_path / "snap"
    result, _ = _companion(project, "--build", str(snap))

    assert result.returncode == 0
    text = (snap / "metadata.yaml").read_text()
    assert "test-user/articles.test_topic.public" in text
    assert "test-user/articles.test_topic\"" not in text
    assert (project / "metadata.yaml").read_text() != text


def test_deny_beats_allow(project: Path, tmp_path: Path) -> None:
    (project / "data").mkdir(exist_ok=True)
    (project / "data" / "keep.csv").write_text("a,b\n")
    (project / "data" / "private.key").write_text("not a secret, just denied\n")
    (project / "analysis" / "__pycache__").mkdir(parents=True, exist_ok=True)
    (project / "analysis" / "__pycache__" / "x.pyc").write_bytes(b"x")
    _, payload = _companion(project)

    paths = _paths(payload)
    assert "data/keep.csv" in paths
    assert "data/private.key" not in paths
    assert "data/private.key" in payload["excluded"]
    assert "analysis/__pycache__/x.pyc" not in paths


def test_planted_env_file_is_never_copied(project: Path, tmp_path: Path) -> None:
    (project / "data").mkdir(exist_ok=True)
    (project / "data" / ".env").write_text("SECRET=1\n")
    snap = tmp_path / "snap"
    result, payload = _companion(project, "--build", str(snap))

    assert result.returncode == 0, result.stderr
    assert "data/.env" not in _paths(payload)
    assert not (snap / "data" / ".env").exists()


# Assembled at runtime so this file holds no literal that looks like a secret.
PLANTED_SECRETS = [
    "token " + "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123456789",
    "github" + "_pat_" + "11ABCDEFG0abcdefghijklmnop",
    "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
    "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "xo" + "xb-" + "1234-abcd",
]


@pytest.mark.parametrize("planted", PLANTED_SECRETS)
def test_planted_secret_fails_the_build(project: Path, tmp_path: Path, planted: str) -> None:
    (project / "paper" / "sections" / "leak.tex").write_text(planted + "\n")
    snap = tmp_path / "snap"
    result, payload = _companion(project, "--build", str(snap))

    assert result.returncode == 1
    assert payload["ok"] is False
    assert "leak.tex" in payload["error"]
    assert not snap.exists()


def test_private_url_fails_but_companion_url_passes(project: Path, tmp_path: Path) -> None:
    leak = project / "paper" / "sections" / "leak.tex"
    leak.write_text("see https://github.com/test-user/articles.test_topic for more\n")
    result, payload = _companion(project, "--build", str(tmp_path / "bad"))
    assert result.returncode == 1
    assert "private repository" in payload["error"]

    leak.write_text("see https://github.com/test-user/articles.test_topic.public ok\n")
    result, payload = _companion(project, "--build", str(tmp_path / "good"))
    assert result.returncode == 0, payload


def test_custom_companion_suffix_is_honoured(project: Path, tmp_path: Path) -> None:
    path = project / "companion.yaml"
    data = yaml.safe_load(path.read_text())
    data["repo"] = "test-user/articles.test_topic-archive"
    path.write_text(yaml.safe_dump(data))
    assert run(project, "make", "metadata").returncode == 0
    leak = project / "paper" / "sections" / "leak.tex"
    leak.write_text("github.com/test-user/articles.test_topic-archive\n")
    result, _ = _companion(project, "--build", str(tmp_path / "ok"))
    assert result.returncode == 0

    leak.write_text("github.com/test-user/articles.test_topic.public\n")
    result, _ = _companion(project, "--build", str(tmp_path / "bad"))
    assert result.returncode == 1


def test_build_refuses_non_empty_output(project: Path, tmp_path: Path) -> None:
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "x").write_text("x")
    result, payload = _companion(project, "--build", str(snap))
    assert result.returncode == 1
    assert (snap / "x").read_text() == "x"
    assert "empty" in payload["error"]


def test_build_needs_manuscript_pdf_in_artifacts(project: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result, payload = _companion(
        project, "--build", str(tmp_path / "snap"), "--artifacts", str(empty)
    )
    assert result.returncode == 1
    assert "manuscript.pdf" in payload["error"]


@pytest.mark.parametrize(
    ("tag", "allowed"),
    [("v1.0.0", True), ("v1.0.1", False), ("v1.0.0-rc.1", False), ("1.0.0", False)],
)
def test_gate(project: Path, tag: str, allowed: bool) -> None:
    result, payload = _companion(project, "--gate", tag)

    assert result.returncode == 0
    assert payload["mode"] == "gate"
    assert payload["allowed"] is allowed
    assert bool(payload["reasons"]) is not allowed


def test_tree_hash_is_deterministic(project: Path, tmp_path: Path) -> None:
    art = _artifacts(tmp_path)
    _, first = _companion(project, "--build", str(tmp_path / "a"), "--artifacts", str(art))
    _, second = _companion(project, "--build", str(tmp_path / "b"), "--artifacts", str(art))
    assert first["tree_sha256"] == second["tree_sha256"]
    assert first["files"] == second["files"]

    (project / "paper" / "sections" / "extra.tex").write_text("changed\n")
    _, third = _companion(project, "--build", str(tmp_path / "c"), "--artifacts", str(art))
    assert third["tree_sha256"] != first["tree_sha256"]


def test_missing_config_is_an_error(project: Path) -> None:
    (project / "companion.yaml").unlink()
    result, payload = _companion(project)
    assert result.returncode == 1
    assert "upgrade" in payload["error"]


def test_help_lists_companion(project: Path) -> None:
    result = run(project, "python3", "-m", "scripts.article", "--help")
    assert "companion" in result.stdout
