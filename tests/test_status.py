"""Schema and behavior tests for ``article status``."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml
from conftest import commit_all, render, run


def _status(project: Path):
    result = run(project, "python3", "-m", "scripts.article", "status", "--json")
    assert result.stdout.strip(), result.stderr
    return result, json.loads(result.stdout)


def _schema(project: Path) -> dict:
    return json.loads((project / "schemas" / "status.schema.json").read_text())


def _rewrite_metadata(project: Path, **changes: object) -> None:
    path = project / "metadata.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def test_fresh_repository_status_is_schema_valid(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result, payload = _status(project)

    assert result.returncode == 0, result.stderr
    jsonschema.validate(payload, _schema(project))
    assert payload["schema_version"] == "1.0"
    assert payload["template_version"] == "1.5.1"
    assert payload["repo"]["root"] == str(project.resolve())
    assert payload["repo"]["branch"] in {"master", "main"}
    assert payload["repo"]["dirty"] is True
    assert payload["metadata"] == {"valid": True, "drift": False}
    assert payload["diagnostics"]["errors"] == 0
    assert payload["diagnostics"]["warnings"] > 0
    assert payload["tools"]["python"]
    assert "pandoc" in payload["tools"]
    assert "latexmk" in payload["tools"]


def test_status_is_read_only_after_commit(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    commit_all(project)
    before = run(project, "git", "status", "--porcelain")
    assert before.stdout == ""

    result, payload = _status(project)

    assert result.returncode == 0, result.stderr
    assert payload["repo"]["dirty"] is False
    assert payload["repo"]["branch"] in {"master", "main"}
    after = run(project, "git", "status", "--porcelain")
    assert after.stdout == ""


def test_metadata_drift_is_reported_without_failing_status(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _rewrite_metadata(project, title="A Drifted Title")

    result, payload = _status(project)

    assert result.returncode == 0, result.stderr
    jsonschema.validate(payload, _schema(project))
    assert payload["metadata"]["valid"] is True
    assert payload["metadata"]["drift"] is True


def test_invalid_metadata_is_reported_and_status_stays_usable(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "metadata.yaml").write_text("title: [unterminated\n")

    result, payload = _status(project)

    assert result.returncode == 0, result.stderr
    jsonschema.validate(payload, _schema(project))
    assert payload["metadata"]["valid"] is False
    assert payload["metadata"]["drift"] is True


def test_template_version_can_be_overridden_by_metadata(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _rewrite_metadata(project, template_version="9.9.9")

    _, payload = _status(project)

    assert payload["template_version"] == "9.9.9"
    jsonschema.validate(payload, _schema(project))


def test_human_status_output_mentions_the_same_fields(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(project, "python3", "-m", "scripts.article", "status")

    assert result.returncode == 0, result.stderr
    for label in ("root:", "template:", "branch:", "dirty:", "metadata valid:"):
        assert label in result.stdout
