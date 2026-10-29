"""companion.yaml: rendered default, schema and the config reader."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from conftest import render, run


def _companion(project: Path):
    path = project / "scripts" / "article" / "companion.py"
    spec = importlib.util.spec_from_file_location("companion_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _schema(project: Path) -> dict:
    return json.loads((project / "schemas" / "companion.schema.json").read_text())


def test_default_companion_yaml_is_schema_valid(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    data = yaml.safe_load((project / "companion.yaml").read_text())

    jsonschema.validate(data, _schema(project))
    assert data["repo"] == "test-user/articles.test_topic.public"
    assert data["branch"] == "main"
    assert ".github/**" in data["exclude"]
    assert _companion(project).read_config(project) == data


def test_rendered_repo_still_validates(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(project, "make", "validate")
    assert result.returncode == 0, result.stdout + result.stderr


def test_absent_file_returns_none(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "companion.yaml").unlink()
    assert _companion(project).read_config(project) is None


@pytest.mark.parametrize(
    "change",
    [
        {"repo": "no-slash"},
        {"repo": "owner/"},
        {"branch": ""},
        {"include": []},
        {"exclude": "nope"},
        {"version": 2},
        {"extra": 1},
    ],
)
def test_invalid_config_raises(tmp_path: Path, change: dict) -> None:
    project = render(tmp_path=tmp_path)
    path = project / "companion.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(change)
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ValueError, match="companion.yaml"):
        _companion(project).read_config(project)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, _schema(project))


def test_missing_key_and_bad_yaml_raise(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    path = project / "companion.yaml"
    module = _companion(project)
    path.write_text("version: 1\n")
    with pytest.raises(ValueError, match="missing"):
        module.read_config(project)
    path.write_text("a: [unclosed\n")
    with pytest.raises(ValueError, match="invalid YAML"):
        module.read_config(project)
