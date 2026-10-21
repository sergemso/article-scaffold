"""Release plan/apply and DOI handling tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import render, run


def _project(tmp_path: Path, **overrides: str) -> Path:
    return render(tmp_path=tmp_path, **overrides)


def _release_json(project: Path, **flags: str) -> dict:
    args = ["python3", "-m", "scripts.article", "release", "--json"]
    for flag, value in flags.items():
        cli_flag = flag.replace("_", "-")
        if value is True:
            args.append(f"--{cli_flag}")
        elif value is not False and value is not None:
            args.append(f"--{cli_flag}")
            args.append(str(value))
    result = run(project, *args)
    return json.loads(result.stdout)


def _release_text(project: Path, **flags: str) -> subprocess.CompletedProcess:
    args = ["python3", "-m", "scripts.article", "release"]
    for flag, value in flags.items():
        cli_flag = flag.replace("_", "-")
        if value is True:
            args.append(f"--{cli_flag}")
        elif value is not False and value is not None:
            args.append(f"--{cli_flag}")
            args.append(str(value))
    return run(project, *args)


def test_release_plan_is_read_only_and_schema_valid(tmp_path: Path) -> None:
    project = _project(tmp_path)
    result = _release_json(project, dry_run=True)
    assert result["ok"] is True
    assert result["command"] == "release"
    assert result["dry_run"] is True
    assert "plan" in result
    plan = result["plan"]
    assert plan["version"] == "1.0.0"
    assert plan["tag"] == "v1.0.0"
    assert isinstance(plan["artifact_list"], list)
    assert isinstance(plan["checks"], dict)
    assert isinstance(plan["dry_run_diff"], list)


def test_release_plan_includes_all_checks(tmp_path: Path) -> None:
    project = _project(tmp_path)
    result = _release_json(project, dry_run=True)
    plan = result["plan"]
    checks = plan["checks"]
    required = {"git_clean", "tag_absent", "has_version", "has_artifacts"}
    assert required.issubset(checks.keys())


def test_release_plan_shows_doi_when_present(tmp_path: Path) -> None:
    project = _project(tmp_path, doi="10.5281/zenodo.1234567")
    result = _release_json(project, dry_run=True)
    plan = result["plan"]
    assert plan["doi"] == "10.5281/zenodo.1234567"


def test_release_plan_fails_on_invalid_version(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # Corrupt version
    (project / "metadata.yaml").write_text("version: not-a-version\n")
    result = _release_json(project, dry_run=True)
    assert result["ok"] is False
    assert "error" in result


def test_release_apply_fails_without_yes_flag(tmp_path: Path) -> None:
    project = _project(tmp_path)
    result = _release_json(project, apply=True)
    assert result["ok"] is False
    assert "error" in result
    assert "yes" in result["error"].lower()


def test_release_apply_fails_on_dirty_tree(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # Make a change
    (project / "paper" / "sections" / "00_abstract.tex").write_text("Changed.\n")
    result = _release_json(project, apply=True, yes=True)
    assert result["ok"] is False
    assert "error" in result
    assert "uncommitted" in result["error"].lower() or "dirty" in result["error"].lower()


def test_release_apply_fails_on_existing_tag(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run(project, "git", "add", "-A", check=True)
    run(project, "git", "commit", "-qm", "initial", check=True)
    run(project, "git", "tag", "v1.0.0", check=True)
    result = _release_json(project, apply=True, yes=True)
    assert result["ok"] is False
    assert "error" in result
    assert "tag" in result["error"].lower()


def test_release_apply_succeeds_on_clean_tree(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run(project, "git", "add", "-A", check=True)
    run(project, "git", "commit", "-qm", "initial", check=True)
    # Build PDF artifact (DOCX may fail if pandoc < 2.11)
    run(project, "make", "pdf", check=True)

    result = _release_json(project, apply=True, yes=True)
    assert result["ok"] is True, result.get("error")
    assert result["version"] == "1.0.0"
    assert result["tag"] == "v1.0.0"
    assert "paper/article.pdf" in result["artifacts"]
    # Verify tag was created
    tags = run(project, "git", "tag", "-l", "v1.0.0", check=True).stdout.strip()
    assert tags == "v1.0.0"


def test_release_plan_text_output_is_human_readable(tmp_path: Path) -> None:
    project = _project(tmp_path)
    result = _release_text(project, dry_run=True)
    assert result.returncode == 0
    output = result.stdout
    assert "version: 1.0.0" in output
    assert "tag: v1.0.0" in output
    assert "checks:" in output
    assert "PASS" in output or "FAIL" in output


def test_release_apply_updates_metadata_doi_and_regenerates(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run(project, "git", "add", "-A", check=True)
    run(project, "git", "commit", "-qm", "initial", check=True)
    run(project, "make", "pdf", check=True)

    # Add DOI to metadata.yaml and commit it
    import yaml
    metadata = yaml.safe_load((project / "metadata.yaml").read_text())
    metadata["doi"] = "10.5281/zenodo.9999999"
    (project / "metadata.yaml").write_text(yaml.safe_dump(metadata, sort_keys=False))
    run(project, "git", "add", "metadata.yaml", check=True)
    run(project, "git", "commit", "-qm", "Add DOI", check=True)

    # Apply release (should regenerate with new DOI)
    result = _release_json(project, apply=True, yes=True)
    assert result["ok"] is True, result.get("error")

    # Verify DOI propagated to CITATION.cff
    cff = yaml.safe_load((project / "CITATION.cff").read_text())
    # DOI appears in identifiers and preferred-citation.identifiers
    identifiers = cff.get("identifiers", [])
    doi_found = any(item.get("value") == "10.5281/zenodo.9999999" for item in identifiers)
    assert doi_found, f"DOI not found in CITATION.cff identifiers: {identifiers}"
    preferred = cff.get("preferred-citation", {})
    pref_ids = preferred.get("identifiers", [])
    doi_found_pref = any(item.get("value") == "10.5281/zenodo.9999999" for item in pref_ids)
    assert doi_found_pref, f"DOI not found in preferred-citation.identifiers: {pref_ids}"
    # Also check Zenodo JSON
    zenodo = json.loads((project / ".zenodo.json").read_text())
    assert zenodo.get("doi") == "10.5281/zenodo.9999999"


def test_release_text_output_shows_error_cleanly(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "metadata.yaml").write_text("version: invalid\n")
    result = _release_text(project, dry_run=True)
    assert result.returncode == 1  # DIAGNOSTICS error for invalid semver
    assert "ERROR:" in result.stderr or "error" in result.stdout.lower()
    assert "invalid version format" in (result.stdout + result.stderr)


def test_release_cli_help_includes_apply_and_yes(tmp_path: Path) -> None:
    project = _project(tmp_path)
    result = run(project, "python3", "-m", "scripts.article", "release", "--help")
    assert result.returncode == 0
    assert "--apply" in result.stdout
    assert "--yes" in result.stdout
    assert "--dry-run" in result.stdout