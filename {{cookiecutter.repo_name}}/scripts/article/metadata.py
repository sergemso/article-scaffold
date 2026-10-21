"""Pure metadata normalization and derived-file generation.

All public functions take paths or plain data; none read ``Path.cwd()``, print,
or call ``sys.exit``. The CLI and legacy shims are responsible for I/O policy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .latex import latex_escape, replace_block

TITLE_BLOCK_START = "% METADATA:TITLE_BLOCK:START"
TITLE_BLOCK_END = "% METADATA:TITLE_BLOCK:END"
README_CITATION_START = "<!-- BIBTEX:CITATION:START -->"
README_CITATION_END = "<!-- BIBTEX:CITATION:END -->"
README_META_START = "<!-- README:META:START -->"
README_META_END = "<!-- README:META:END -->"
ABSTRACT_START = "% ABSTRACT:START"
ABSTRACT_END = "% ABSTRACT:END"
BACKMATTER_VERSION_START = "% BACKMATTER:VERSION:START"
BACKMATTER_VERSION_END = "% BACKMATTER:VERSION:END"
CHANGES_CURRENT_START = "<!-- CHANGES:CURRENT:START -->"
CHANGES_CURRENT_END = "<!-- CHANGES:CURRENT:END -->"

ZENODO_LICENSE_IDS = {
    "CC-BY-4.0": "cc-by-4.0",
    "CC-BY-SA-4.0": "cc-by-sa-4.0",
    "CC-BY-NC-4.0": "cc-by-nc-4.0",
    "CC-BY-ND-4.0": "cc-by-nd-4.0",
    "CC-BY-NC-SA-4.0": "cc-by-nc-sa-4.0",
    "CC-BY-NC-ND-4.0": "cc-by-nc-nd-4.0",
    "CC0-1.0": "cc0-1.0",
    "MIT": "mit",
    "Apache-2.0": "apache-2.0",
    "GPL-3.0": "gpl-3.0",
    "GPL-3.0-only": "gpl-3.0",
    "GPL-3.0-or-later": "gpl-3.0",
    "LGPL-3.0": "lgpl-3.0",
    "BSD-3-Clause": "bsd-3-clause",
    "BSD-2-Clause": "bsd-2-clause",
}


@dataclass(frozen=True)
class OutputDrift:
    """One generated file whose on-disk content differs from metadata."""

    path: str
    actual: str | None
    expected: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "actual": self.actual,
            "expected": self.expected,
        }


def load_metadata(path: Path) -> dict:
    """Load and normalize metadata.yaml; missing/invalid input raises."""
    if not path.is_file():
        raise FileNotFoundError(f"metadata.yaml not found at {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("metadata.yaml must contain a mapping")
    return normalize_metadata(data)


def normalize_metadata(data: dict) -> dict:
    """Add the derived keys the generators rely on, without side effects."""
    normalized = dict(data)
    raw_keywords = normalized.get("keywords", "") or ""
    if isinstance(raw_keywords, list):
        normalized["_keywords_list"] = [
            str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()
        ]
    else:
        normalized["_keywords_list"] = [
            keyword.strip()
            for keyword in str(raw_keywords).split(",")
            if keyword.strip()
        ]
    normalized["_abstract"] = normalized.get("abstract") or normalized.get("description") or ""
    normalized["_abstract_note"] = normalized.get("abstract_note") or ""
    raw_date = normalized.get("date", "")
    if isinstance(raw_date, date):
        normalized["_date_iso"] = raw_date.isoformat()
    elif raw_date:
        try:
            parsed = date.fromisoformat(str(raw_date)[:10])
            normalized["_date_iso"] = parsed.isoformat()
        except ValueError:
            normalized["_date_iso"] = str(raw_date)
    else:
        normalized["_date_iso"] = ""

    author = normalized.get("author", {})
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
    normalized["_author_family"] = family
    normalized["_author_given"] = given
    normalized["_author_full"] = full_name
    normalized["_author_orcid"] = orcid
    normalized["_author_affiliation"] = affiliation

    raw_creators = normalized.get("creators")
    creators: list[dict[str, str]] = []
    if isinstance(raw_creators, list):
        for item in raw_creators:
            if isinstance(item, dict):
                creators.append(
                    {
                        "name": str(item.get("name", "")).strip(),
                        "orcid": str(item.get("orcid", "")).strip(),
                        "affiliation": str(item.get("affiliation", "")).strip(),
                    }
                )
            elif item:
                creators.append(
                    {"name": str(item).strip(), "orcid": "", "affiliation": ""}
                )
    creators = [creator for creator in creators if creator["name"]]
    if not creators:
        creators = [
            {
                "name": full_name or "Unknown",
                "orcid": orcid,
                "affiliation": affiliation,
            }
        ]
    normalized["_creators"] = creators

    normalized["_repo_url"] = (
        f"https://github.com/{normalized.get('github_user', '')}/"
        f"{normalized.get('repo_name', '')}"
    )
    doi = normalized.get("doi", "") or ""
    normalized["_doi"] = doi
    normalized["_doi_url"] = (
        f"https://doi.org/{doi}" if doi else normalized["_repo_url"]
    )
    return normalized


def zenodo_license_id(value: object) -> str | None:
    """Map an SPDX id to Zenodo's vocabulary, or return None if unknown."""
    if not value:
        return None
    key = str(value).strip()
    if key in ZENODO_LICENSE_IDS:
        return ZENODO_LICENSE_IDS[key]
    for spdx, zenodo_id in ZENODO_LICENSE_IDS.items():
        if spdx.lower() == key.lower():
            return zenodo_id
    return None


def _q(value: object) -> str:
    """A JSON/YAML string literal, safe for quotes and unicode."""
    return json.dumps(str(value), ensure_ascii=False)


def gen_citation_cff(metadata: dict) -> str:
    """Build a CFF 1.2.0 record with PyYAML, never by hand-formatting."""
    family = metadata.get("_author_family") or "Unknown"
    author: dict[str, object] = {"family-names": family}
    if metadata.get("_author_given"):
        author["given-names"] = metadata["_author_given"]
    if metadata.get("_author_orcid"):
        author["orcid"] = f"https://orcid.org/{metadata['_author_orcid']}"
    if metadata.get("_author_affiliation"):
        author["affiliation"] = metadata["_author_affiliation"]

    data: dict[str, object] = {
        "cff-version": "1.2.0",
        "message": "If you use this manuscript or its scaffold, please cite it as below.",
        "title": metadata.get("title", ""),
        "type": "software",
        "authors": [author],
    }
    if metadata.get("subtitle"):
        data["subtitle"] = metadata["subtitle"]
    if metadata.get("version"):
        data["version"] = str(metadata["version"])
    if metadata.get("_date_iso"):
        data["date-released"] = str(metadata["_date_iso"])
    if metadata.get("_abstract"):
        data["abstract"] = metadata["_abstract"]
    if metadata.get("_keywords_list"):
        data["keywords"] = list(metadata["_keywords_list"])
    if metadata.get("license"):
        data["license"] = metadata["license"]
    if metadata.get("_repo_url"):
        data["repository-code"] = metadata["_repo_url"]
        data["url"] = metadata["_repo_url"]

    identifiers: list[dict[str, str]] = []
    if metadata.get("_doi"):
        identifiers.append(
            {
                "type": "doi",
                "value": metadata["_doi"],
                "description": "Zenodo DOI",
            }
        )
        data["identifiers"] = identifiers

    preferred: dict[str, object] = {
        "type": "unpublished",
        "title": metadata.get("title", ""),
        "authors": [dict(author)],
    }
    if metadata.get("version_label") or metadata.get("target_deposit"):
        preferred["notes"] = (
            f"{metadata.get('version_label', '')}, deposited on "
            f"{metadata.get('target_deposit', '')}"
        ).strip(", ")
    if metadata.get("_date_iso"):
        try:
            preferred["year"] = int(metadata["_date_iso"][:4])
            preferred["month"] = int(metadata["_date_iso"][5:7])
        except (ValueError, IndexError):
            pass
    if identifiers:
        preferred["identifiers"] = [dict(item) for item in identifiers]
    data["preferred-citation"] = preferred

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def gen_zenodo_json(metadata: dict) -> str:
    creators = []
    for creator in metadata.get("_creators", []):
        entry = {"name": creator["name"]}
        if creator.get("orcid"):
            entry["orcid"] = creator["orcid"]
        if creator.get("affiliation"):
            entry["affiliation"] = creator["affiliation"]
        creators.append(entry)

    publication_type = str(metadata.get("publication_type", "")).strip().lower()
    if publication_type not in {"preprint", "article"}:
        manuscript_type = str(metadata.get("manuscript_type", "")).lower()
        publication_type = "article" if "article" in manuscript_type else "preprint"

    raw_communities = metadata.get("communities") or []
    if isinstance(raw_communities, str):
        raw_communities = [
            community.strip()
            for community in raw_communities.split(",")
            if community.strip()
        ]
    communities = []
    for community in raw_communities:
        identifier = (
            community.get("identifier")
            if isinstance(community, dict)
            else str(community)
        )
        if identifier:
            communities.append({"identifier": str(identifier)})

    obj: dict[str, object] = {
        "title": metadata.get("title", ""),
        "description": metadata.get("_abstract", "") or metadata.get("description", ""),
        "creators": creators,
        "keywords": list(metadata.get("_keywords_list", [])),
        "upload_type": "publication",
        "publication_type": publication_type,
        "access_right": str(metadata.get("access_right", "open") or "open"),
        "version": str(metadata.get("version", "")),
        "language": str(metadata.get("language", "en") or "en"),
        "communities": communities,
    }
    license_id = zenodo_license_id(metadata.get("license"))
    if license_id:
        obj["license"] = license_id
    if metadata.get("_doi"):
        obj["doi"] = metadata["_doi"]
    related = metadata.get("related_identifiers") or []
    if related:
        obj["related_identifiers"] = related
    references = metadata.get("references") or []
    if references:
        obj["references"] = references
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def gen_article_tex_title_block(metadata: dict) -> str:
    title_raw = metadata.get("title", "")
    title = metadata.get("title_tex") or latex_escape(title_raw)
    title_for_pdf = latex_escape(title_raw)
    subtitle = (
        latex_escape(metadata.get("subtitle", "")) if metadata.get("subtitle") else ""
    )
    author = latex_escape(metadata["_author_full"])
    affiliation = latex_escape(metadata["_author_affiliation"])
    orcid = metadata["_author_orcid"]
    version_label = metadata.get("version_label", "")
    date_iso = metadata["_date_iso"]
    out = [TITLE_BLOCK_START]
    title_inner = "\\Large \\textbf{ " + title
    if subtitle:
        title_inner += "\\\\[0.3em] \\large " + subtitle
    title_inner += " }"
    out.append("\\title{" + title_inner + "}")
    out.append("\\author{ " + author + "\\\\")
    out.append("\\small " + affiliation + "\\\\")
    out.append("\\small \\texttt{ORCID: " + orcid + "}}")
    out.append("\\date{\\small " + version_label + " — " + date_iso + "}")
    keywords = ", ".join(latex_escape(keyword) for keyword in metadata["_keywords_list"])
    subject = latex_escape(metadata.get("manuscript_type", ""))
    out.append("\\hypersetup{")
    out.append("  pdftitle={ " + title_for_pdf + " },")
    out.append("  pdfauthor={ " + author + " },")
    out.append("  pdfsubject={ " + subject + " },")
    out.append("  pdfkeywords={ " + keywords + " }")
    out.append("}")
    out.append(TITLE_BLOCK_END)
    return "\n".join(out) + "\n"


def gen_readme_bibtex_block(metadata: dict) -> str:
    topic = metadata.get("repo_name", "").replace("articles.", "").replace(".", "_")
    version_label = re.sub(
        r"[^A-Za-z0-9]", "_", metadata.get("version_label", "")
    )
    key = f"{topic}_{version_label}"
    author = metadata["_author_full"]
    title = metadata.get("title", "")
    year = metadata["_date_iso"][:4] if metadata["_date_iso"] else ""
    version_label_raw = metadata.get("version_label", "")
    deposit = metadata.get("target_deposit", "")
    license_value = metadata.get("license", "")
    lines = [
        README_CITATION_START,
        "<!-- Regenerated by `python scripts/generate-metadata.py` from metadata.yaml.",
        "     Edit metadata.yaml, not this block. -->",
        "```bibtex",
        "@misc{ " + key + ",",
        "  author       = { " + author + " },",
        "  title        = { " + title + " },",
        "  year         = { " + year + " },",
        "  note         = { " + version_label_raw + " },",
        "  howpublished = { " + deposit + " },",
    ]
    if metadata.get("_doi"):
        lines.append("  doi          = { " + metadata["_doi"] + " },")
        lines.append("  url          = { " + metadata["_doi_url"] + " },")
    else:
        lines.append("  url          = { " + metadata["_repo_url"] + " },")
    lines.append("  license      = { " + license_value + " }")
    lines.append("}")
    lines.append("```")
    lines.append(README_CITATION_END)
    return "\n".join(lines) + "\n"


def gen_readme_meta_block(metadata: dict) -> str:
    lines = [README_META_START, f"# {metadata.get('title', '')}"]
    if metadata.get("subtitle"):
        lines.append(f"## {metadata['subtitle']}")
    lines.extend(
        [
            "",
            f"**Manuscript type:** {metadata.get('manuscript_type', '')}",
            f"**Version:** {metadata.get('version_label', '')} ({metadata['_date_iso']})",
            f"**License:** {metadata.get('license', '')}",
            "**Code license:** MIT",
            f"**Target deposit:** {metadata.get('target_deposit', '')} (preprint)",
        ]
    )
    if metadata.get("_doi"):
        lines.append(f"**DOI:** {metadata['_doi']}")
    lines.extend(["", "## Abstract", "", metadata["_abstract"], README_META_END])
    return "\n".join(lines) + "\n"


def gen_abstract_block(metadata: dict) -> str:
    abstract = latex_escape(metadata["_abstract"])
    note = latex_escape(metadata["_abstract_note"])
    keywords = ", ".join(
        latex_escape(keyword) for keyword in metadata["_keywords_list"]
    )
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


def gen_backmatter_version_block(metadata: dict) -> str:
    lines = [
        BACKMATTER_VERSION_START,
        r"\section*{Version Statement}",
        "",
        "This is version~"
        + latex_escape(metadata.get("version", ""))
        + " of the manuscript, dated",
        latex_escape(metadata["_date_iso"])
        + ", prepared for "
        + latex_escape(metadata.get("target_deposit", "")),
        "deposit as a preprint.",
        BACKMATTER_VERSION_END,
    ]
    return "\n".join(lines) + "\n"


def gen_changes_current_block(metadata: dict) -> str:
    lines = [
        CHANGES_CURRENT_START,
        f"## {metadata.get('version_label', '')} - {metadata['_date_iso']} (current)",
        CHANGES_CURRENT_END,
    ]
    return "\n".join(lines) + "\n"


def _read_required(root: Path, path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"required file is missing: {path.relative_to(root)}")
    return path.read_text(encoding="utf-8")


def collect_expected(root: Path, metadata: dict) -> dict[Path, str]:
    """Return the exact content each generated file should have."""
    citation_path = root / "CITATION.cff"
    zenodo_path = root / ".zenodo.json"
    article_path = root / "paper" / "article.tex"
    abstract_path = root / "paper" / "sections" / "00_abstract.tex"
    backmatter_path = root / "paper" / "sections" / "08_backmatter.tex"
    changes_path = root / "CHANGES.md"
    readme_path = root / "README.md"

    outputs: dict[Path, str] = {
        citation_path: gen_citation_cff(metadata),
        zenodo_path: gen_zenodo_json(metadata),
    }
    outputs[article_path] = replace_block(
        _read_required(root, article_path),
        TITLE_BLOCK_START,
        TITLE_BLOCK_END,
        gen_article_tex_title_block(metadata),
    )
    outputs[abstract_path] = replace_block(
        _read_required(root, abstract_path),
        ABSTRACT_START,
        ABSTRACT_END,
        gen_abstract_block(metadata),
    )
    outputs[backmatter_path] = replace_block(
        _read_required(root, backmatter_path),
        BACKMATTER_VERSION_START,
        BACKMATTER_VERSION_END,
        gen_backmatter_version_block(metadata),
    )
    outputs[changes_path] = replace_block(
        _read_required(root, changes_path),
        CHANGES_CURRENT_START,
        CHANGES_CURRENT_END,
        gen_changes_current_block(metadata),
    )

    readme = _read_required(root, readme_path)
    readme = replace_block(
        readme, README_META_START, README_META_END, gen_readme_meta_block(metadata)
    )
    readme = replace_block(
        readme,
        README_CITATION_START,
        README_CITATION_END,
        gen_readme_bibtex_block(metadata),
    )
    outputs[readme_path] = readme
    return outputs


def compare_outputs(root: Path, expected: dict[Path, str]) -> list[OutputDrift]:
    """Return drift records without writing or printing."""
    drift: list[OutputDrift] = []
    for path, expected_text in expected.items():
        actual = path.read_text(encoding="utf-8") if path.is_file() else None
        if actual != expected_text:
            drift.append(
                OutputDrift(
                    path=str(path.relative_to(root)),
                    actual=actual,
                    expected=expected_text,
                )
            )
    return drift


def write_expected(expected: dict[Path, str]) -> list[Path]:
    """Write only changed outputs; return the paths that changed."""
    changed: list[Path] = []
    for path, text in expected.items():
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        path.write_text(text, encoding="utf-8")
        changed.append(path)
    return changed
