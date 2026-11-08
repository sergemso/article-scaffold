"""Tier 1 quote matching and the tier 2 verdicts (stored in the ledger)."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import render, run

SOURCE = (
    "Chapter 1\n\nThe “well-known” result is that evalu-\nation of the\n"
    "ﬁrst   contract — under load — holds.\nA second sentence follows.\n"
)


def _cli(project: Path, *args: str):
    return run(project, "python3", "-m", "scripts.article", *args)


def _node(node_id: str, quote: str, **extra: object) -> str:
    lines = [
        f"  - id: {node_id}",
        "    type: source-claim",
        "    text: The paper says the first contract holds.",
        "    status: proposed",
        f"    quote: {json.dumps(quote)}",
        "    locator: p. 3",
        "    bib_keys: [smith2020]",
    ]
    lines += [f"    {k}: {json.dumps(v)}" for k, v in extra.items()]
    return "\n".join(lines) + "\n"


def _project(tmp_path: Path, *nodes: str, source: str | None = SOURCE) -> Path:
    project = render(tmp_path=tmp_path)
    (project / "theses.yaml").write_text("version: 1\nnodes:\n" + "".join(nodes) + "edges: []\n")
    if source is not None:
        sources = project / "paper" / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        (sources / "smith2020.txt").write_text(source, encoding="utf-8")
    return project


def _check(project: Path, *args: str) -> tuple[int, dict]:
    result = _cli(project, "claims", "quote-check", *args)
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def test_exact_match(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A second sentence follows."))
    code, payload = _check(project, "c1")
    assert code == 0
    assert payload["results"] == [
        {"id": "c1", "locator": "p. 3", "verdict": "found",
         "source": "paper/sources/smith2020.txt", "cached": None}
    ]


def test_whitespace_hyphen_quote_and_ligature_differences(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        _node("c1", 'The "well known" result is that evaluation of the first contract'),
        _node("c2", "first contract - under load - holds"),
        _node("c3", 'The "well-known" result ... under load'),
    )
    code, payload = _check(project, "--all")
    assert code == 0, payload
    assert [r["verdict"] for r in payload["results"]] == ["found"] * 3


def test_changed_quote_is_not_found_and_exit_one(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A third sentence follows."))
    code, payload = _check(project, "c1")
    assert code == 1
    assert payload["ok"] is False
    assert payload["results"][0]["verdict"] == "not-found"


def test_ellipsis_segments_must_keep_order(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A second sentence ... The well-known"))
    code, payload = _check(project, "c1")
    assert code == 1 and payload["results"][0]["verdict"] == "not-found"


def test_missing_source_file_is_no_local_text(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "anything"), source=None)
    code, payload = _check(project, "--all")
    assert code == 0
    assert payload["results"][0]["verdict"] == "no-local-text"


def test_source_field_and_manifest_mapping(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A second sentence follows."), source=None)
    sources = project / "paper" / "sources"
    sources.mkdir(parents=True)
    (sources / "other.txt").write_text(SOURCE)
    (sources / "MANIFEST.md").write_text("| key | file |\n|---|---|\n| smith2020 | other.txt |\n")
    assert _check(project, "c1")[1]["results"][0]["verdict"] == "found"
    (sources / "MANIFEST.md").write_text("- smith2020: other.txt\n")
    assert _check(project, "c1")[1]["results"][0]["verdict"] == "found"
    (sources / "MANIFEST.md").write_text("")
    assert _check(project, "c1")[1]["results"][0]["verdict"] == "no-local-text"
    (project / "theses.yaml").write_text(
        "version: 1\nnodes:\n" + _node("c1", "A second sentence follows.", source="other.txt")
        + "edges: []\n"
    )
    assert _check(project, "c1")[1]["results"][0]["verdict"] == "found"


def test_source_path_cannot_escape_sources_dir(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "secret", source="../../theses.yaml"))
    assert _check(project, "c1")[1]["results"][0]["verdict"] == "no-local-text"


def test_output_has_verdicts_and_locators_only(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A second sentence follows."))
    result = _cli(project, "claims", "quote-check", "--all")
    assert "second sentence" not in result.stdout


def test_cache_hit_skips_recomputation_and_misses_on_change(tmp_path: Path) -> None:
    padded = "x " * 600 + SOURCE + "y " * 600
    project = _project(tmp_path, _node("c1", "A second sentence follows."), source=padded)
    assert _check(project, "c1")[1]["results"][0]["cached"] is None
    put = _cli(project, "claims", "cache", "c1", "--set", "overstates")
    assert json.loads(put.stdout)["verdict"] == "overstates"
    assert _check(project, "c1")[1]["results"][0]["cached"] == "overstates"
    files = [p for p in (project / "docs" / "ledger" / "claim-verdict").rglob("*.json")
             if not p.name.endswith(".prov.json")]
    assert len(files) == 1
    stored = json.loads(files[0].read_text())
    assert stored["result"] == {"verdict": "overstates"} and stored["status"] == "fail"
    assert "second sentence" not in json.dumps(stored)
    # the excerpt changes -> the key changes -> miss
    sources = project / "paper" / "sources"
    (sources / "smith2020.txt").write_text(padded.replace("x x ", "z z ", 1))
    assert _check(project, "c1")[1]["results"][0]["cached"] == "overstates"  # far-away change
    (sources / "smith2020.txt").write_text(padded.replace("under load", "under stress"))
    assert _check(project, "c1")[1]["results"][0]["cached"] is None
    # the claim wording changes -> miss
    (sources / "smith2020.txt").write_text(padded)
    text = (project / "theses.yaml").read_text().replace("first contract holds", "contract fails")
    (project / "theses.yaml").write_text(text)
    assert _check(project, "c1")[1]["results"][0]["cached"] is None


def test_record_unit_helpers_and_bad_verdict(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A second sentence follows."))
    bad = _cli(project, "claims", "cache", "c1", "--set", "maybe")
    assert bad.returncode == 2
    code = (
        "from scripts.article import claims; from pathlib import Path;"
        "r=Path('.');"
        "assert claims.cached_verdict(r,'a','b') is None;"
        "claims.record_verdict(r,'a','b','supports');"
        "assert claims.cached_verdict(r,'a','b')=='supports';"
        "assert claims.verdict_key('a','b').key!=claims.verdict_key('ab','').key"
    )
    assert run(project, "python3", "-c", code).returncode == 0


def test_excerpt_command_prints_local_passage(tmp_path: Path) -> None:
    project = _project(tmp_path, _node("c1", "A second sentence follows."))
    result = _cli(project, "claims", "excerpt", "c1")
    assert result.returncode == 0 and "A second sentence follows." in result.stdout


def test_template_gitignores_the_local_counters(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    assert ".theses/" in (project / ".gitignore").read_text().splitlines()
    assert "paper/sources/.manifest.lock" in (project / ".gitignore").read_text().splitlines()
