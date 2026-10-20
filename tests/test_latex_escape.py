"""Table-driven tests for the single-pass LaTeX escaper."""

from __future__ import annotations

import importlib.util

import pytest
from conftest import ROOT

SCRIPT = ROOT / "{{cookiecutter.repo_name}}" / "scripts" / "generate-metadata.py"
_spec = importlib.util.spec_from_file_location("generate_metadata", SCRIPT)
assert _spec and _spec.loader
generate_metadata = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_metadata)
latex_escape = generate_metadata.latex_escape


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("plain text", "plain text"),
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
        ("a & b % c", r"a \& b \% c"),
        ("\\&", r"\textbackslash{}\&"),
        ("— ünïcode", "— ünïcode"),
    ],
)
def test_every_special_character(raw: str, expected: str) -> None:
    assert latex_escape(raw) == expected


def test_backslash_is_not_double_escaped() -> None:
    escaped = latex_escape("\\")
    assert escaped == r"\textbackslash{}"
    assert r"\textbackslash\{\}" not in escaped


def test_already_tex_is_a_passthrough() -> None:
    raw = r"$\alpha$ \& \textbf{Bold}"
    assert latex_escape(raw, already_tex=True) == raw


def test_escaped_text_can_be_marked_already_tex() -> None:
    escaped = latex_escape("A & B % C")
    assert latex_escape(escaped, already_tex=True) == escaped


def test_title_tex_override_is_raw_but_pdf_title_is_plain() -> None:
    metadata = {
        "title": "Plain & Simple",
        "title_tex": r"$\alpha$ \& \textbf{Bold}",
        "subtitle": "",
        "_author_full": "Ada Lovelace",
        "_author_affiliation": "Analytical Engine Institute",
        "_author_orcid": "0000-0002-1825-0097",
        "_keywords_list": ["alpha & beta"],
        "_date_iso": "2026-01-02",
        "version_label": "v1 preprint",
        "manuscript_type": "Perspective / Review Essay",
    }
    block = generate_metadata.gen_article_tex_title_block(metadata)
    assert r"$\alpha$ \& \textbf{Bold}" in block
    assert r"pdftitle={ Plain \& Simple }" in block
    assert r"pdfkeywords={ alpha \& beta }" in block
