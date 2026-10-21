"""Multi-author metadata must agree across LaTeX, CFF, Zenodo, and README."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
import yaml
from conftest import render, run

AUTHORS = {
    "Ada Lovelace": {
        "orcid": "0000-0002-1825-0097",
        "given": "Ada",
        "family": "Lovelace",
    },
    "Grace Hopper": {
        "orcid": "0000-0002-1694-233X",
        "given": "Grace",
        "family": "Hopper",
    },
    "Plato": {"orcid": "", "given": "", "family": "Plato"},
}


def _multi_author_metadata() -> dict:
    return {
        "metadata_schema": 2,
        "title": "Three Authors, One Model",
        "abstract": "A fixture with three authors and two affiliations.",
        "authors": [
            {
                "name": "Ada Lovelace",
                "orcid": "0000-0002-1825-0097",
                "affiliations": ["afi"],
                "corresponding": True,
                "email": "ada@example.org",
            },
            {
                "given": "Grace",
                "family": "Hopper",
                "orcid": "0000-0002-1694-233X",
                "affiliations": ["afi", "lab"],
            },
            {"name": "Plato"},
        ],
        "affiliations": {
            "afi": {
                "name": "Analytical Engine Institute",
                "ror": "https://ror.org/02mhbdp94",
            },
            "lab": {"name": "Computing Lab"},
        },
        "version": "1.0.0",
        "version_label": "v1 preprint",
        "date": "2026-01-02",
        "license": "CC-BY-4.0",
        "license_code": "MIT",
        "target_deposit": "Zenodo",
        "github_user": "test-user",
        "repo_name": "articles.three_authors",
        "repo_url": "https://github.com/test-user/articles.three_authors",
        "keywords": "authors, metadata",
        "description": "A fixture with three authors and two affiliations.",
        "references": [],
        "communities": [],
    }


def _expected_cff_name(author: dict) -> str:
    given = author.get("given-names", "")
    family = author.get("family-names", "")
    return " ".join(part for part in (given, family) if part)


def _title_block(project: Path) -> str:
    text = (project / "paper" / "article.tex").read_text()
    match = re.search(
        r"% METADATA:TITLE_BLOCK:START(.*?)% METADATA:TITLE_BLOCK:END",
        text,
        re.DOTALL,
    )
    assert match, "title block sentinels are missing"
    return match.group(1)


def test_three_authors_agree_across_all_outputs(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    metadata_path = project / "metadata.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_multi_author_metadata(), sort_keys=False, allow_unicode=True)
    )

    result = run(project, "make", "metadata")
    assert result.returncode == 0, result.stderr + result.stdout

    names = set(AUTHORS)

    cff = yaml.safe_load((project / "CITATION.cff").read_text())
    cff_names = {_expected_cff_name(author) for author in cff["authors"]}
    assert cff_names == names
    assert len(cff["preferred-citation"]["authors"]) == 3
    assert cff["authors"][0]["orcid"] == "https://orcid.org/0000-0002-1825-0097"
    assert cff["authors"][1]["affiliation"] == (
        "Analytical Engine Institute; Computing Lab"
    )
    assert "orcid" not in cff["authors"][2]

    zenodo = json.loads((project / ".zenodo.json").read_text())
    assert {creator["name"] for creator in zenodo["creators"]} == names
    assert zenodo["creators"][0]["orcid"] == "0000-0002-1825-0097"

    readme = (project / "README.md").read_text()
    assert "**Authors:**" in readme
    for name in names:
        assert name in readme
    assert "https://orcid.org/0000-0002-1825-0097" in readme
    assert "https://ror.org/02mhbdp94" in readme
    assert "**Corresponding author(s):** Ada Lovelace" in readme
    assert "mailto:ada@example.org" in readme

    block = _title_block(project)
    for name in names:
        assert name in block
    assert block.count(r"\and") == 2
    assert "https://orcid.org/0000-0002-1825-0097" in block
    assert "https://ror.org/02mhbdp94" in block
    assert r"\thanks{Corresponding author:" in block
    assert "mailto:ada@example.org" in block


def test_three_author_pdf_builds_when_latexmk_is_available(tmp_path: Path) -> None:
    if shutil.which("latexmk") is None:
        pytest.skip("latexmk is not installed")

    project = render(tmp_path=tmp_path)
    metadata_path = project / "metadata.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_multi_author_metadata(), sort_keys=False, allow_unicode=True)
    )
    result = run(project, "make", "pdf")
    assert result.returncode == 0, result.stderr + result.stdout
    assert (project / "paper" / "article.pdf").is_file()
