"""Unit tests for the pure, vendored article core library."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import jsonschema
import yaml
from conftest import render, run


def _core(project: Path):
    sys.path.insert(0, str(project))
    try:
        importlib.invalidate_caches()
        return importlib.import_module("scripts.article")
    finally:
        sys.path.remove(str(project))


def test_package_imports_without_output_or_side_effects(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(
        project,
        "python3",
        "-c",
        "import scripts.article; print(scripts.article.CORE_VERSION)",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "1.0.0"
    assert result.stderr == ""


def test_latex_helpers_are_pure_and_single_pass(tmp_path: Path) -> None:
    core = _core(render(tmp_path=tmp_path))
    escaped = core.latex_escape("a&%$#_{}~^\\")
    assert escaped == (
        r"a\&\%\$\#\_\{\}\textasciitilde{}\textasciicircum{}\textbackslash{}"
    )
    assert core.latex_escape(r"\textbf{raw}", already_tex=True) == r"\textbf{raw}"
    assert core.count_unescaped(r"\{ \} { }", "{") == 1
    assert core.count_unescaped(r"\{ \} { }", "}") == 1

    stripped = core.strip_comments(r"100\% \citep{ok} % \citep{missing}")
    assert r"100\%" in stripped
    assert r"\citep{ok}" in stripped
    assert "missing" not in stripped


def test_diagnostics_serialize_to_the_published_schema(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    core = _core(project)
    diagnostics = core.Diagnostics()
    diagnostics.error("paper/sections/01_introduction.tex", 7, "E002", "missing key")
    diagnostics.warning("paper/refs.bib", 3, "W002", "unused key")
    payload = diagnostics.to_dict()

    assert payload["ok"] is False
    assert payload["summary"] == {"errors": 1, "warnings": 1}
    assert payload["diagnostics"][0] == {
        "path": "paper/sections/01_introduction.tex",
        "line": 7,
        "code": "E002",
        "severity": "error",
        "message": "missing key",
    }
    schema = json.loads((project / "schemas" / "diagnostics.schema.json").read_text())
    jsonschema.validate(payload, schema)


def test_validate_clean_project_and_missing_citation(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    core = _core(project)

    clean = core.validate_paper(project)
    assert clean.ok
    assert clean.errors == []
    assert any(item.code == "W001" for item in clean.warnings)

    section = project / "paper" / "sections" / "01_introduction.tex"
    section.write_text(section.read_text() + "\n\\citep{missing-key}\n")
    broken = core.validate_paper(project)
    assert not broken.ok
    assert any(
        item.code == "E002" and "missing-key" in item.message for item in broken.errors
    )


def test_metadata_generation_matches_on_disk_output(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    core = _core(project)

    metadata = core.load_metadata(project / "metadata.yaml")
    expected = core.collect_expected(project, metadata)
    assert core.compare_outputs(project, expected) == []

    citation = yaml.safe_load((project / "CITATION.cff").read_text())
    assert citation["cff-version"] == "1.2.0"
    assert citation["title"] == metadata["title"]
    zenodo = json.loads((project / ".zenodo.json").read_text())
    assert zenodo["upload_type"] == "publication"
    assert zenodo["license"] == "cc-by-4.0"
    title_block = core.gen_article_tex_title_block(metadata)
    assert title_block.startswith("% METADATA:TITLE_BLOCK:START")
    assert "\\title{" in title_block


def test_build_plans_are_data_only(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    core = _core(project)

    pdf = core.pdf_plan(project)
    assert pdf.command[0] == "latexmk"
    assert pdf.cwd == "paper"
    assert pdf.output == "paper/build/article.pdf"
    assert pdf.to_dict()["name"] == "pdf"

    docx = core.docx_plan(project, reference_docx="reference.docx")
    assert "--resource-path=paper:paper/figures:." in docx.command
    assert "--reference-doc=reference.docx" in docx.command
    assert "--citeproc" in docx.command
    assert docx.output == "manuscript.docx"


def test_status_schema_accepts_the_documented_shape(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    schema = json.loads((project / "schemas" / "status.schema.json").read_text())
    payload = {
        "schema_version": "1.0",
        "template_version": "1.4.0",
        "repo": {"root": str(project), "branch": "master", "dirty": False},
        "metadata": {"valid": True, "drift": False},
        "diagnostics": {"errors": 0, "warnings": 7},
        "tools": {"python": "3.10.12", "pandoc": None},
    }
    jsonschema.validate(payload, schema)
