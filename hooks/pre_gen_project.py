#!/usr/bin/env python3
# ruff: noqa: F821
"""Validate cookiecutter answers before a half-written repository is created.

Cookiecutter renders this script with the answers and runs it from the target
directory before any template files are copied.  A non-zero exit aborts the
render and removes the partial output.  Keep the diagnostics here short and
actionable: one line per invalid field, never a traceback.
"""

from __future__ import annotations

import re
import sys

TOPIC = {{ cookiecutter.topic | tojson }}
REPO_NAME = {{ cookiecutter.repo_name | tojson }}
TITLE = {{ cookiecutter.title | tojson }}
VERSION = {{ cookiecutter.version | tojson }}
ORCID = {{ cookiecutter.author_orcid | tojson }}
LICENSE = {{ cookiecutter.license | tojson }}
DOI = {{ cookiecutter.doi | tojson }}
MANUSCRIPT_KIND = {{ cookiecutter.manuscript_kind | tojson }}
CITATION_STYLE = {{ cookiecutter.citation_style | tojson }}

TOPIC_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
REPO_RE = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def _text(value: object) -> str:
    return str(value or "").strip()


def _valid_orcid(value: str) -> bool:
    if not ORCID_RE.fullmatch(value):
        return False
    compact = value.replace("-", "").upper()
    total = 0
    for digit in compact[:15]:
        total = (total + int(digit)) * 2
    result = (12 - total % 11) % 11
    expected = "X" if result == 10 else str(result)
    return compact[15] == expected


def main() -> int:
    errors: list[str] = []

    topic = _text(TOPIC)
    if not TOPIC_RE.fullmatch(topic) or len(topic) > 64:
        errors.append(
            "topic: use lowercase letters and digits separated by single "
            "hyphens or underscores (example: subject_slug)."
        )

    repo_name = _text(REPO_NAME)
    if (
        not REPO_RE.fullmatch(repo_name)
        or len(repo_name) > 100
        or repo_name.endswith(".git")
    ):
        errors.append(
            "repo_name: use a GitHub-safe name such as articles.subject_slug "
            "(letters and digits, with single . _ or - separators)."
        )

    title = _text(TITLE)
    if not title:
        errors.append("title: enter a non-empty manuscript title.")

    version = _text(VERSION)
    if not SEMVER_RE.fullmatch(version):
        errors.append("version: use semantic versioning, for example 1.0.0 or 1.0.0-rc.1.")

    license_name = _text(LICENSE)
    if license_name not in {"CC-BY-4.0", "MIT"}:
        errors.append("license: choose CC-BY-4.0 or MIT.")

    doi = _text(DOI)
    if doi and not DOI_RE.fullmatch(doi):
        errors.append(
            "doi: use a bare DOI such as 10.5281/zenodo.1234567 "
            "(do not include https://doi.org/)."
        )

    orcid = _text(ORCID)
    if orcid:
        if orcid.startswith("https://orcid.org/"):
            orcid = orcid.removeprefix("https://orcid.org/")
        if not _valid_orcid(orcid):
            errors.append(
                "author_orcid: enter a valid ORCID checksum "
                "(0000-0000-0000-0000) or leave it empty."
            )

    if _text(MANUSCRIPT_KIND) not in {"perspective", "empirical", "review"}:
        errors.append("manuscript_kind: choose perspective, empirical, or review.")

    if _text(CITATION_STYLE) not in {"numeric", "author-year"}:
        errors.append("citation_style: choose numeric or author-year.")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Fix the answers above and run cookiecutter again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
