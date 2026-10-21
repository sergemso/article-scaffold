"""Contract tests for the JSON-first ``python3 -m scripts.article`` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml
from conftest import render, run


def _cli(project: Path, *args: str):
    return run(project, "python3", "-m", "scripts.article", *args)


def _payload(result) -> dict:
    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout)


def _schema(project: Path, name: str) -> dict:
    return json.loads((project / "schemas" / f"{name}.schema.json").read_text())


def test_validate_json_success_matches_diagnostics_schema(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _cli(project, "validate", "--json")

    assert result.returncode == 0, result.stderr
    payload = _payload(result)
    assert payload["ok"] is True
    assert payload["summary"]["errors"] == 0
    assert any(item["code"] == "W001" for item in payload["diagnostics"])
    jsonschema.validate(payload, _schema(project, "diagnostics"))


def test_validate_json_failure_exits_1_and_keeps_schema(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    section = project / "paper" / "sections" / "01_introduction.tex"
    section.write_text(section.read_text() + "\n\\citep{missing-key}\n")

    result = _cli(project, "validate", "--json")

    assert result.returncode == 1
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["summary"]["errors"] >= 1
    assert any(
        item["code"] == "E002" and "missing-key" in item["message"]
        for item in payload["diagnostics"]
    )
    jsonschema.validate(payload, _schema(project, "diagnostics"))


def test_usage_errors_exit_2(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)

    unknown = _cli(project, "unknown-command", "--json")
    assert unknown.returncode == 2
    assert "usage error" in unknown.stderr

    bad_flag = _cli(project, "build", "pdf", "--not-a-flag", "--json")
    assert bad_flag.returncode == 2

    missing_command = _cli(project)
    assert missing_command.returncode == 2


def test_internal_error_exit_3(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    section = project / "paper" / "sections" / "01_introduction.tex"
    section.write_bytes(b"\xff\xfe")

    result = _cli(project, "validate", "--json")

    assert result.returncode == 3
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["command"] == "validate"
    assert payload["error"]


def test_metadata_check_dry_run_and_apply(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    metadata_path = project / "metadata.yaml"
    citation = project / "CITATION.cff"

    clean = _cli(project, "metadata", "--check", "--json")
    assert clean.returncode == 0
    assert _payload(clean)["drift"] == []

    metadata = yaml.safe_load(metadata_path.read_text())
    metadata["title"] = "A Changed Title"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False))
    before = citation.read_text()

    drift = _cli(project, "metadata", "--check", "--json")
    assert drift.returncode == 1
    drift_payload = _payload(drift)
    assert drift_payload["ok"] is False
    assert any(item["path"] == "CITATION.cff" for item in drift_payload["drift"])
    assert citation.read_text() == before

    dry_run = _cli(project, "metadata", "--dry-run", "--json")
    assert dry_run.returncode == 0
    dry_payload = _payload(dry_run)
    assert "CITATION.cff" in dry_payload["changed"]
    assert citation.read_text() == before

    applied = _cli(project, "metadata", "--json")
    assert applied.returncode == 0
    applied_payload = _payload(applied)
    assert "CITATION.cff" in applied_payload["changed"]
    assert yaml.safe_load(citation.read_text())["title"] == "A Changed Title"

    clean_again = _cli(project, "metadata", "--check", "--json")
    assert clean_again.returncode == 0


def test_status_json_matches_schema_and_is_read_only(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    metadata_path = project / "metadata.yaml"
    before = metadata_path.read_text()

    result = _cli(project, "status", "--json")

    assert result.returncode == 0, result.stderr
    payload = _payload(result)
    jsonschema.validate(payload, _schema(project, "status"))
    assert payload["schema_version"] == "1.0"
    assert payload["template_version"]
    assert payload["repo"]["root"] == str(project.resolve())
    assert payload["metadata"]["valid"] is True
    assert "python" in payload["tools"]
    assert metadata_path.read_text() == before


def test_build_dry_run_uses_core_plans(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)

    pdf = _cli(project, "build", "pdf", "--dry-run", "--json")
    assert pdf.returncode == 0
    pdf_payload = _payload(pdf)
    assert pdf_payload["kind"] == "pdf"
    assert pdf_payload["plan"]["command"][0] == "latexmk"
    assert pdf_payload["plan"]["cwd"] == "paper"

    docx = _cli(project, "build", "docx", "--dry-run", "--json")
    assert docx.returncode == 0
    docx_payload = _payload(docx)
    assert docx_payload["kind"] == "docx"
    assert "--resource-path=paper:paper/figures:." in docx_payload["plan"]["command"]


def test_root_option_is_explicit(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _cli(project, "--root", str(project), "validate", "--json")

    assert result.returncode == 0
    assert _payload(result)["ok"] is True


def test_release_stub_is_json_and_nonzero_until_implemented(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _cli(project, "release", "--dry-run", "--json")

    assert result.returncode in {0, 1}
    payload = _payload(result)
    assert payload["command"] == "release"
    assert "dry_run" in payload
