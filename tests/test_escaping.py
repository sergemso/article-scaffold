"""Structured metadata must survive hostile free text.

The template's YAML, JSON and CFF outputs are consumed by tools, so a quote,
ampersand, percent sign, underscore, or unicode character in a title must not
change the document structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from conftest import SPECIAL_ABSTRACT, SPECIAL_TITLE, render

HOSTILE_SUBTITLE = 'A "sub" title with 50% & more'
HOSTILE_KEYWORDS = 'quotes, "100%", #hashtag, ünïcode'


def test_metadata_yaml_parses(tmp_path: Path) -> None:
    project = render(
        tmp_path=tmp_path,
        title=SPECIAL_TITLE,
        subtitle=HOSTILE_SUBTITLE,
        abstract=SPECIAL_ABSTRACT,
        keywords=HOSTILE_KEYWORDS,
    )
    metadata = yaml.safe_load((project / "metadata.yaml").read_text())
    assert metadata["title"] == SPECIAL_TITLE
    assert metadata["subtitle"] == HOSTILE_SUBTITLE
    assert metadata["abstract"] == SPECIAL_ABSTRACT
    assert metadata["keywords"] == HOSTILE_KEYWORDS


def test_zenodo_json_parses(tmp_path: Path) -> None:
    project = render(
        tmp_path=tmp_path,
        title=SPECIAL_TITLE,
        abstract=SPECIAL_ABSTRACT,
        keywords=HOSTILE_KEYWORDS,
    )
    data = json.loads((project / ".zenodo.json").read_text())
    assert data["title"] == SPECIAL_TITLE
    assert data["description"] == SPECIAL_ABSTRACT
    assert data["keywords"] == [kw.strip() for kw in HOSTILE_KEYWORDS.split(",")]


def test_citation_cff_parses(tmp_path: Path) -> None:
    project = render(
        tmp_path=tmp_path,
        title=SPECIAL_TITLE,
        subtitle=HOSTILE_SUBTITLE,
        abstract=SPECIAL_ABSTRACT,
    )
    cff = yaml.safe_load((project / "CITATION.cff").read_text())
    assert cff["title"] == SPECIAL_TITLE
    assert cff["subtitle"] == HOSTILE_SUBTITLE
    assert cff["authors"][0]["family-names"] == "Lovelace"
