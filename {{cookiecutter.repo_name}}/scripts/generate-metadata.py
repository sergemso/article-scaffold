#!/usr/bin/env python3
"""
generate-metadata.py — regenerate derived metadata from metadata.yaml.

Reads  metadata.yaml  and writes:
  - CITATION.cff
  - .zenodo.json
  - paper/article.tex    (METADATA:TITLE_BLOCK block)
  - paper/sections/00_abstract.tex (ABSTRACT block)
  - paper/sections/08_backmatter.tex (BACKMATTER:VERSION block)
  - README.md            (README:META and BIBTEX:CITATION blocks)
  - CHANGES.md           (CHANGES:CURRENT block)

Idempotent: re-running with the same metadata.yaml produces byte-identical
output. Lines outside the sentinel-marked blocks are preserved, so manual
edits to README.md or article.tex prose survive a regeneration.

Usage:
    python scripts/generate-metadata.py
    python scripts/generate-metadata.py --check   # exit 1 on drift, write nothing
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    print(
        "ERROR: PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = REPO_ROOT / "metadata.yaml"
CITATION_PATH = REPO_ROOT / "CITATION.cff"
ZENODO_PATH = REPO_ROOT / ".zenodo.json"
ARTICLE_TEX_PATH = REPO_ROOT / "paper" / "article.tex"
README_PATH = REPO_ROOT / "README.md"

TITLE_BLOCK_START = "% METADATA:TITLE_BLOCK:START"
TITLE_BLOCK_END = "% METADATA:TITLE_BLOCK:END"
README_CITATION_START = "<!-- BIBTEX:CITATION:START -->"
README_CITATION_END = "<!-- BIBTEX:CITATION:END -->"
README_META_START = "<!-- README:META:START -->"
README_META_END = "<!-- README:META:END -->"
ABSTRACT_PATH = REPO_ROOT / "paper" / "sections" / "00_abstract.tex"
ABSTRACT_START = "% ABSTRACT:START"
ABSTRACT_END = "% ABSTRACT:END"
BACKMATTER_PATH = REPO_ROOT / "paper" / "sections" / "08_backmatter.tex"
BACKMATTER_VERSION_START = "% BACKMATTER:VERSION:START"
BACKMATTER_VERSION_END = "% BACKMATTER:VERSION:END"
CHANGES_PATH = REPO_ROOT / "CHANGES.md"
CHANGES_CURRENT_START = "<!-- CHANGES:CURRENT:START -->"
CHANGES_CURRENT_END = "<!-- CHANGES:CURRENT:END -->"


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def load_metadata() -> dict:
    if not METADATA_PATH.is_file():
        print(f"ERROR: metadata.yaml not found at {METADATA_PATH}", file=sys.stderr)
        sys.exit(1)
    with METADATA_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Normalise: accept either a comma-separated string or a YAML list.
    raw_keywords = data.get("keywords", "") or ""
    if isinstance(raw_keywords, list):
        data["_keywords_list"] = [str(k).strip() for k in raw_keywords if str(k).strip()]
    else:
        data["_keywords_list"] = [
            k.strip() for k in str(raw_keywords).split(",") if k.strip()
        ]
    data["_abstract"] = data.get("abstract") or data.get("description") or ""
    data["_abstract_note"] = data.get("abstract_note") or ""
    raw_date = data.get("date", "")
    if isinstance(raw_date, date):
        data["_date_iso"] = raw_date.isoformat()
    elif raw_date:
        try:
            d = date.fromisoformat(str(raw_date)[:10])
            data["_date_iso"] = d.isoformat()
        except ValueError:
            data["_date_iso"] = str(raw_date)
    else:
        data["_date_iso"] = ""
    # Author name parsing
    author = data.get("author", {})
    if isinstance(author, dict):
        full_name = author.get("name", "")
        orcid = author.get("orcid", "")
        affiliation = author.get("affiliation", "")
    else:
        full_name, orcid, affiliation = str(author), "", ""
    parts = full_name.split()
    if len(parts) >= 2:
        family, given = parts[-1], " ".join(parts[:-1])
    else:
        family, given = full_name, ""
    data["_author_family"] = family
    data["_author_given"] = given
    data["_author_full"] = full_name
    data["_author_orcid"] = orcid
    data["_author_affiliation"] = affiliation
    # Repo URL
    data["_repo_url"] = (
        f"https://github.com/{data.get('github_user','')}/{data.get('repo_name','')}"
    )
    # DOI URL
    doi = data.get("doi", "") or ""
    data["_doi"] = doi
    data["_doi_url"] = f"https://doi.org/{doi}" if doi else data["_repo_url"]
    return data


LATEX_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(text: str, already_tex: bool = False) -> str:
    """Escape free text for LaTeX in a single pass.

    A single pass is essential: replacing backslashes first and then braces
    would turn ``\\`` into ``\\textbackslash{}``. Unicode is preserved; the
    generated document is UTF-8 and the active TeX engine decides which
    characters it can typeset. Pass ``already_tex=True`` for a raw-LaTeX
    override such as ``title_tex``; it is returned unchanged.
    """
    if not text:
        return ""
    if already_tex:
        return text
    return "".join(LATEX_ESCAPE_MAP.get(ch, ch) for ch in text)


# ─────────────────────────────────────────────────────────────
# Generators
# ─────────────────────────────────────────────────────────────


def _q(value: object) -> str:
    """A JSON/YAML string literal, safe for quotes and unicode."""
    return json.dumps(str(value), ensure_ascii=False)


def gen_citation_cff(m: dict) -> str:
    """Build a CFF 1.2.0 record with PyYAML, never by hand-formatting."""
    family = m.get("_author_family") or "Unknown"
    author: dict[str, object] = {"family-names": family}
    if m.get("_author_given"):
        author["given-names"] = m["_author_given"]
    if m.get("_author_orcid"):
        author["orcid"] = f"https://orcid.org/{m['_author_orcid']}"
    if m.get("_author_affiliation"):
        author["affiliation"] = m["_author_affiliation"]

    data: dict[str, object] = {
        "cff-version": "1.2.0",
        "message": "If you use this manuscript or its scaffold, please cite it as below.",
        "title": m.get("title", ""),
        "type": "software",
        "authors": [author],
    }
    if m.get("subtitle"):
        data["subtitle"] = m["subtitle"]
    if m.get("version"):
        data["version"] = str(m["version"])
    if m.get("_date_iso"):
        data["date-released"] = str(m["_date_iso"])
    if m.get("_abstract"):
        data["abstract"] = m["_abstract"]
    if m.get("_keywords_list"):
        data["keywords"] = list(m["_keywords_list"])
    if m.get("license"):
        data["license"] = m["license"]
    if m.get("_repo_url"):
        data["repository-code"] = m["_repo_url"]
        data["url"] = m["_repo_url"]

    identifiers: list[dict[str, str]] = []
    if m.get("_doi"):
        identifiers.append(
            {
                "type": "doi",
                "value": m["_doi"],
                "description": "Zenodo DOI",
            }
        )
        data["identifiers"] = identifiers

    preferred: dict[str, object] = {
        "type": "unpublished",
        "title": m.get("title", ""),
        "authors": [dict(author)],
    }
    if m.get("version_label") or m.get("target_deposit"):
        preferred["notes"] = (
            f"{m.get('version_label', '')}, deposited on "
            f"{m.get('target_deposit', '')}"
        ).strip(", ")
    if m.get("_date_iso"):
        try:
            preferred["year"] = int(m["_date_iso"][:4])
            preferred["month"] = int(m["_date_iso"][5:7])
        except (ValueError, IndexError):
            pass
    if identifiers:
        preferred["identifiers"] = [dict(item) for item in identifiers]
    data["preferred-citation"] = preferred

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def gen_zenodo_json(m: dict) -> str:
    obj = {
        "title": m.get("title", ""),
        "description": m.get("_abstract", "") or m.get("description", ""),
        "creators": [
            {
                "name": m["_author_full"],
                "orcid": m["_author_orcid"],
                "affiliation": m["_author_affiliation"],
            }
        ],
        "keywords": m["_keywords_list"],
        "license": m.get("license", ""),
        "upload_type": "publication",
        "publication_type": "preprint",
        "access_right": "open",
        "version": m.get("version", ""),
        "language": "en",
        "communities": [{"identifier": c} for c in m.get("communities", []) or []],
        "related_identifiers": [],
        "references": m.get("references", []) or [],
    }
    if m.get("_doi"):
        obj["doi"] = m["_doi"]
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def gen_article_tex_title_block(m: dict) -> str:
    title_raw = m.get("title", "")
    # title_tex is an explicit raw-LaTeX escape hatch for the visible title.
    # PDF metadata still uses the escaped plain title.
    title = m.get("title_tex") or latex_escape(title_raw)
    title_for_pdf = latex_escape(title_raw)
    subtitle = latex_escape(m.get("subtitle", "")) if m.get("subtitle") else ""
    author = latex_escape(m["_author_full"])
    affiliation = latex_escape(m["_author_affiliation"])
    orcid = m["_author_orcid"]
    vlabel = m.get("version_label", "")
    date_iso = m["_date_iso"]
    out = [TITLE_BLOCK_START]
    # Title with optional inline subtitle. The leading/trailing spaces inside
    # \textbf{} and \title{} match the cookiecutter template's format so
    # `make metadata` is a no-op on first run.
    title_inner = f"\\Large \\textbf{{ {title}"
    if subtitle:
        title_inner += f"\\\\[0.3em] \\large {subtitle}"
    title_inner += " }"
    out.append(f"\\title{{{title_inner}}}")
    out.append(f"\\author{{ {author}\\\\")
    out.append(f"\\small {affiliation}\\\\")
    out.append(f"\\small \\texttt{{ORCID: {orcid}}}}}")
    out.append(f"\\date{{\\small {vlabel} — {date_iso}}}")
    keywords = ", ".join(latex_escape(k) for k in m["_keywords_list"])
    subject = latex_escape(m.get("manuscript_type", ""))
    out.append(r"\hypersetup{")
    out.append(f"  pdftitle={{ {title_for_pdf} }},")
    out.append(f"  pdfauthor={{ {author} }},")
    out.append(f"  pdfsubject={{ {subject} }},")
    out.append(f"  pdfkeywords={{ {keywords} }}")
    out.append("}")
    out.append(TITLE_BLOCK_END)
    return "\n".join(out) + "\n"


def gen_readme_bibtex_block(m: dict) -> str:
    topic = m.get("repo_name", "").replace("articles.", "").replace(".", "_")
    vlabel_norm = re.sub(r"[^A-Za-z0-9]", "_", m.get("version_label", ""))
    key = f"{topic}_{vlabel_norm}"
    author = m["_author_full"]
    title = m.get("title", "")
    year = m["_date_iso"][:4] if m["_date_iso"] else ""
    vlabel = m.get("version_label", "")
    deposit = m.get("target_deposit", "")
    license_ = m.get("license", "")
    lines = [
        README_CITATION_START,
        "<!-- Regenerated by `python scripts/generate-metadata.py` from metadata.yaml.",
        "     Edit metadata.yaml, not this block. -->",
        "```bibtex",
        f"@misc{{ {key},",
        f"  author       = {{ {author} }},",
        f"  title        = {{ {title} }},",
        f"  year         = {{ {year} }},",
        f"  note         = {{ {vlabel} }},",
        f"  howpublished = {{ {deposit} }},",
    ]
    if m.get("_doi"):
        lines.append(f"  doi          = {{ {m['_doi']} }},")
        lines.append(f"  url          = {{ {m['_doi_url']} }},")
    else:
        lines.append(f"  url          = {{ {m['_repo_url']} }},")
    lines.append(f"  license      = {{ {license_} }}")
    lines.append("}")
    lines.append("```")
    lines.append(README_CITATION_END)
    return "\n".join(lines) + "\n"


def gen_readme_meta_block(m: dict) -> str:
    lines = [README_META_START, f"# {m.get('title', '')}"]
    if m.get("subtitle"):
        lines.append(f"## {m['subtitle']}")
    lines.extend(
        [
            "",
            f"**Manuscript type:** {m.get('manuscript_type', '')}",
            f"**Version:** {m.get('version_label', '')} ({m['_date_iso']})",
            f"**License:** {m.get('license', '')}",
            f"**Target deposit:** {m.get('target_deposit', '')} (preprint)",
        ]
    )
    if m.get("_doi"):
        lines.append(f"**DOI:** {m['_doi']}")
    lines.extend(["", "## Abstract", "", m["_abstract"], README_META_END])
    return "\n".join(lines) + "\n"


def gen_abstract_block(m: dict) -> str:
    abstract = latex_escape(m["_abstract"])
    note = latex_escape(m["_abstract_note"])
    keywords = ", ".join(latex_escape(k) for k in m["_keywords_list"])
    lines = [
        ABSTRACT_START,
        r"\begin{abstract}",
        r"\noindent",
        abstract,
        r"\end{abstract}",
        "",
        r"\bigskip",
        r"\noindent\textbf{A note on evidence.} " + note,
        "",
        r"\medskip",
        r"\noindent\textbf{Keywords:} " + keywords + ".",
        ABSTRACT_END,
    ]
    return "\n".join(lines) + "\n"


def gen_backmatter_version_block(m: dict) -> str:
    lines = [
        BACKMATTER_VERSION_START,
        r"\section*{Version Statement}",
        "",
        f"This is version~{latex_escape(m.get('version', ''))} of the manuscript, dated",
        f"{latex_escape(m['_date_iso'])}, prepared for {latex_escape(m.get('target_deposit', ''))}",
        "deposit as a preprint.",
        BACKMATTER_VERSION_END,
    ]
    return "\n".join(lines) + "\n"


def gen_changes_current_block(m: dict) -> str:
    lines = [
        CHANGES_CURRENT_START,
        f"## {m.get('version_label', '')} - {m['_date_iso']} (current)",
        CHANGES_CURRENT_END,
    ]
    return "\n".join(lines) + "\n"


def write_if_changed(path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


# ─────────────────────────────────────────────────────────────
# Block replacement
# ─────────────────────────────────────────────────────────────


def replace_block(text: str, start_marker: str, end_marker: str, new_block: str) -> str:
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(
            f"Could not find marker block {start_marker}...{end_marker} in target file"
        )
    # Use a lambda replacement so backslashes in new_block (e.g. \Large in
    # LaTeX) are treated as literals, not as regex group references.
    new_block_stripped = new_block.rstrip("\n")
    return pattern.sub(lambda m: new_block_stripped, text)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────


def _read_required(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(
            f"required file is missing: {path.relative_to(REPO_ROOT)}"
        )
    return path.read_text(encoding="utf-8")


def collect_expected(m: dict) -> dict[Path, str]:
    """Return the exact content each generated file should have."""
    outputs: dict[Path, str] = {
        CITATION_PATH: gen_citation_cff(m),
        ZENODO_PATH: gen_zenodo_json(m),
    }

    outputs[ARTICLE_TEX_PATH] = replace_block(
        _read_required(ARTICLE_TEX_PATH),
        TITLE_BLOCK_START,
        TITLE_BLOCK_END,
        gen_article_tex_title_block(m),
    )
    outputs[ABSTRACT_PATH] = replace_block(
        _read_required(ABSTRACT_PATH),
        ABSTRACT_START,
        ABSTRACT_END,
        gen_abstract_block(m),
    )
    outputs[BACKMATTER_PATH] = replace_block(
        _read_required(BACKMATTER_PATH),
        BACKMATTER_VERSION_START,
        BACKMATTER_VERSION_END,
        gen_backmatter_version_block(m),
    )
    outputs[CHANGES_PATH] = replace_block(
        _read_required(CHANGES_PATH),
        CHANGES_CURRENT_START,
        CHANGES_CURRENT_END,
        gen_changes_current_block(m),
    )

    readme = _read_required(README_PATH)
    readme = replace_block(
        readme, README_META_START, README_META_END, gen_readme_meta_block(m)
    )
    readme = replace_block(
        readme,
        README_CITATION_START,
        README_CITATION_END,
        gen_readme_bibtex_block(m),
    )
    outputs[README_PATH] = readme
    return outputs


def check_outputs(expected: dict[Path, str]) -> int:
    """Compare expected content with disk; print unified diffs; return 0/1."""
    drift = False
    for path, expected_text in expected.items():
        rel = path.relative_to(REPO_ROOT)
        if not path.is_file():
            print(f"ERROR: missing {rel}", file=sys.stderr)
            drift = True
            continue
        actual = path.read_text(encoding="utf-8")
        if actual == expected_text:
            continue
        drift = True
        print(f"drift: {rel}", file=sys.stderr)
        diff = difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected_text.splitlines(keepends=True),
            fromfile=f"{rel} (on disk)",
            tofile=f"{rel} (expected from metadata.yaml)",
        )
        sys.stderr.writelines(diff)
    if drift:
        print(
            "\nmetadata-check: generated files are out of date; run `make metadata`.",
            file=sys.stderr,
        )
        return 1
    print("metadata-check: generated files are up to date.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate derived metadata from metadata.yaml."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated files with disk and exit 1 on drift; write nothing",
    )
    args = parser.parse_args(argv)

    m = load_metadata()
    try:
        expected = collect_expected(m)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        return check_outputs(expected)

    for path, text in expected.items():
        if write_if_changed(path, text):
            print(f"  updated {path.relative_to(REPO_ROOT)}")

    print("\nDone. Review with `git diff` before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
