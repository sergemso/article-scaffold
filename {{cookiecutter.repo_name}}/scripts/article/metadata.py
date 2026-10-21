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

from .diagnostics import Diagnostics
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


ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
ROR_RE = re.compile(r"^https://ror\.org/[0-9a-z]{9}$")

# Metadata diagnostics use the same stable record shape as the validator.
METADATA_PATH = "metadata.yaml"
E_METADATA_AUTHORS = "E020"
E_METADATA_ORCID = "E021"
E_METADATA_AFFILIATION = "E022"
E_METADATA_CORRESPONDING = "E023"
E_METADATA_UNKNOWN_AFFILIATION = "E024"
E_METADATA_ROR = "E025"
E_METADATA_SHAPE = "E026"
E_METADATA_SCHEMA = "E027"
W_METADATA_LEGACY_AUTHOR = "W020"


def valid_orcid(value: object) -> bool:
    """Return True for a bare ORCID with a valid ISO 7064 checksum."""
    text = str(value or "").strip()
    if text.startswith("https://orcid.org/"):
        text = text[len("https://orcid.org/") :]
    if not ORCID_RE.fullmatch(text):
        return False
    compact = text.replace("-", "").upper()
    total = 0
    for digit in compact[:15]:
        total = (total + int(digit)) * 2
    result = (12 - total % 11) % 11
    expected = "X" if result == 10 else str(result)
    return compact[15] == expected


def valid_ror(value: object) -> bool:
    """Return True for the canonical https://ror.org/identifier shape."""
    return bool(ROR_RE.fullmatch(str(value or "").strip()))


is_valid_orcid = valid_orcid
is_valid_ror = valid_ror


def _text(value: object) -> str:
    return str(value or "").strip()


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a legacy display name into given names and a family name."""
    parts = full_name.split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    if parts:
        # Mononyms are valid: keep the single token as the family name.
        return "", parts[0]
    return "", ""


def _normalize_affiliations(raw: object, diagnostics: Diagnostics) -> dict[str, dict]:
    """Normalize an id->mapping map (or a list with explicit ids)."""
    affiliations: dict[str, dict] = {}
    names: dict[str, str] = {}

    if raw is None:
        return affiliations
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        items = []
        for item in raw:
            if not isinstance(item, dict) or not _text(item.get("id")):
                diagnostics.error(
                    METADATA_PATH,
                    0,
                    E_METADATA_SHAPE,
                    "each affiliations list entry must be a mapping with an id",
                )
                continue
            items.append((_text(item["id"]), item))
    else:
        diagnostics.error(
            METADATA_PATH,
            0,
            E_METADATA_SHAPE,
            "affiliations must be an id->mapping map or a list with ids",
        )
        return affiliations

    for key, raw_affiliation in items:
        affiliation_id = _text(key)
        if not affiliation_id:
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_SHAPE,
                "affiliation ids must be non-empty",
            )
            continue
        if affiliation_id in affiliations:
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_AFFILIATION,
                f"duplicate affiliation id: {affiliation_id}",
            )
            continue
        if isinstance(raw_affiliation, str):
            raw_affiliation = {"name": raw_affiliation}
        if not isinstance(raw_affiliation, dict):
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_SHAPE,
                f"affiliation {affiliation_id} must be a mapping or a name",
            )
            continue
        name = _text(raw_affiliation.get("name"))
        if not name:
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_SHAPE,
                f"affiliation {affiliation_id} is missing a name",
            )
        if name and name in names:
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_AFFILIATION,
                f"duplicate affiliation name: {name}",
            )
        elif name:
            names[name] = affiliation_id
        ror = _text(raw_affiliation.get("ror"))
        if ror and not valid_ror(ror):
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_ROR,
                f"affiliation {affiliation_id} has an invalid ROR: {ror}",
            )
        affiliations[affiliation_id] = {
            "id": affiliation_id,
            "name": name,
            "ror": ror,
        }
    return affiliations


def _normalize_author(
    raw: object,
    *,
    affiliations: dict[str, dict],
    diagnostics: Diagnostics,
    legacy: bool = False,
) -> dict:
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        diagnostics.error(
            METADATA_PATH,
            0,
            E_METADATA_SHAPE,
            "each author must be a mapping or a name",
        )
        raw = {}

    name = _text(raw.get("name"))
    given = _text(raw.get("given"))
    family = _text(raw.get("family"))
    if not name:
        name = " ".join(part for part in (given, family) if part)
    if name and not given and not family:
        given, family = _split_name(name)

    orcid = _text(raw.get("orcid"))
    if orcid.startswith("https://orcid.org/"):
        orcid = orcid[len("https://orcid.org/") :]
    if orcid and not valid_orcid(orcid):
        diagnostics.error(
            METADATA_PATH,
            0,
            E_METADATA_ORCID,
            f"author {name or '<unnamed>'} has an invalid ORCID: {orcid}",
        )

    author_ror = _text(raw.get("ror"))
    if author_ror and not valid_ror(author_ror):
        diagnostics.error(
            METADATA_PATH,
            0,
            E_METADATA_ROR,
            f"author {name or '<unnamed>'} has an invalid ROR: {author_ror}",
        )

    raw_affiliations = raw.get("affiliations")
    legacy_affiliation = raw_affiliations is None
    if legacy_affiliation:
        raw_affiliations = raw.get("affiliation")
    if isinstance(raw_affiliations, str):
        raw_affiliations = [
            part.strip() for part in raw_affiliations.split(",") if part.strip()
        ]
    if not isinstance(raw_affiliations, list):
        if raw_affiliations:
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_SHAPE,
                f"author {name or '<unnamed>'} affiliations must be a list",
            )
        raw_affiliations = []

    affiliation_ids: list[str] = []
    for item in raw_affiliations:
        if isinstance(item, dict):
            item = item.get("id") or item.get("name")
        affiliation_id = _text(item)
        if not affiliation_id:
            continue
        if affiliation_id not in affiliations:
            if legacy_affiliation:
                # v1 stored a free-text affiliation on the author. Give it a
                # synthetic id so the normalized model is still uniform.
                synthetic = f"aff{len(affiliations) + 1}"
                while synthetic in affiliations:
                    synthetic = f"aff{len(affiliations) + 2}"
                affiliations[synthetic] = {
                    "id": synthetic,
                    "name": affiliation_id,
                    "ror": "",
                }
                affiliation_id = synthetic
            else:
                diagnostics.error(
                    METADATA_PATH,
                    0,
                    E_METADATA_UNKNOWN_AFFILIATION,
                    f"author {name or '<unnamed>'} references unknown "
                    f"affiliation id: {affiliation_id}",
                )
                continue
        if affiliation_id in affiliation_ids:
            diagnostics.error(
                METADATA_PATH,
                0,
                E_METADATA_AFFILIATION,
                f"author {name or '<unnamed>'} repeats affiliation {affiliation_id}",
            )
            continue
        affiliation_ids.append(affiliation_id)

    affiliation_names = [
        affiliations[affiliation_id]["name"]
        for affiliation_id in affiliation_ids
        if affiliation_id in affiliations
    ]
    return {
        "name": name,
        "given": given,
        "family": family,
        "orcid": orcid,
        "email": _text(raw.get("email")),
        "affiliations": affiliation_ids,
        "affiliation_names": affiliation_names,
        "corresponding": bool(raw.get("corresponding", legacy)),
        "ror": author_ror,
    }


def _metadata_schema(data: dict, diagnostics: Diagnostics) -> int:
    raw = data.get("metadata_schema")
    if raw is None:
        return 2 if "authors" in data or "affiliations" in data else 1
    if raw in (1, 2, "1", "2"):
        return int(raw)
    diagnostics.error(
        METADATA_PATH,
        0,
        E_METADATA_SCHEMA,
        f"metadata_schema must be 1 or 2, got: {raw}",
    )
    return 2 if "authors" in data else 1


def _normalize_authors(
    data: dict,
    *,
    schema: int,
    affiliations: dict[str, dict],
    diagnostics: Diagnostics,
) -> list[dict]:
    raw_authors = data.get("authors")
    authors: list[dict] = []
    legacy = False

    if isinstance(raw_authors, list) and raw_authors:
        for item in raw_authors:
            authors.append(
                _normalize_author(item, affiliations=affiliations, diagnostics=diagnostics)
            )
    elif "author" in data:
        legacy = True
        authors.append(
            _normalize_author(
                data["author"],
                affiliations=affiliations,
                diagnostics=diagnostics,
                legacy=True,
            )
        )
    elif any(
        key in data
        for key in ("author_name", "author_orcid", "author_affiliation")
    ):
        legacy = True
        authors.append(
            _normalize_author(
                {
                    "name": data.get("author_name"),
                    "orcid": data.get("author_orcid"),
                    "affiliation": data.get("author_affiliation"),
                },
                affiliations=affiliations,
                diagnostics=diagnostics,
                legacy=True,
            )
        )

    if not authors:
        diagnostics.error(
            METADATA_PATH,
            0,
            E_METADATA_AUTHORS,
            "metadata must define authors: (schema 2) or the legacy author: mapping",
        )
        return authors

    if legacy:
        diagnostics.warning(
            METADATA_PATH,
            0,
            W_METADATA_LEGACY_AUTHOR,
            "legacy author fields are deprecated; use authors: and affiliations: "
            "with metadata_schema: 2",
        )

    if schema >= 2 and not any(author["corresponding"] for author in authors):
        diagnostics.error(
            METADATA_PATH,
            0,
            E_METADATA_CORRESPONDING,
            "at least one author must be marked corresponding: true",
        )
    return authors


def _normalize_creators(
    data: dict, authors: list[dict]
) -> list[dict[str, str]]:
    raw_creators = data.get("creators")
    creators: list[dict[str, str]] = []
    if isinstance(raw_creators, list):
        for item in raw_creators:
            if isinstance(item, dict):
                creators.append(
                    {
                        "name": _text(item.get("name")),
                        "orcid": _text(item.get("orcid")),
                        "affiliation": _text(item.get("affiliation")),
                    }
                )
            elif item:
                creators.append(
                    {"name": _text(item), "orcid": "", "affiliation": ""}
                )
    creators = [creator for creator in creators if creator["name"]]
    if creators:
        return creators

    for author in authors:
        creator = {"name": author["name"] or "Unknown", "orcid": author["orcid"]}
        if author["affiliation_names"]:
            creator["affiliation"] = "; ".join(author["affiliation_names"])
        creators.append(creator)
    if not creators:
        creators = [{"name": "Unknown", "orcid": "", "affiliation": ""}]
    return creators


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
    """Add the derived keys the generators rely on, without side effects.

    Both the v2 ``authors``/``affiliations`` model and the legacy ``author``
    mapping are accepted. Semantic problems are recorded under
    ``_metadata_diagnostics`` rather than raised, so the CLI and pre-generation
    checks can present every issue at once.
    """
    normalized = dict(data)
    diagnostics = Diagnostics()
    schema = _metadata_schema(normalized, diagnostics)
    affiliations = _normalize_affiliations(normalized.get("affiliations"), diagnostics)
    authors = _normalize_authors(
        normalized,
        schema=schema,
        affiliations=affiliations,
        diagnostics=diagnostics,
    )

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
    normalized["_abstract"] = (
        normalized.get("abstract") or normalized.get("description") or ""
    )
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

    first = authors[0] if authors else {
        "name": "Unknown",
        "given": "",
        "family": "Unknown",
        "orcid": "",
        "affiliations": [],
        "affiliation_names": [],
    }
    normalized["_metadata_schema"] = schema
    normalized["_affiliations"] = affiliations
    normalized["_authors"] = authors
    normalized["_author_full"] = first["name"] or "Unknown"
    normalized["_author_family"] = first["family"] or first["name"] or "Unknown"
    normalized["_author_given"] = first["given"]
    normalized["_author_orcid"] = first["orcid"]
    normalized["_author_affiliation"] = (
        first["affiliation_names"][0] if first["affiliation_names"] else ""
    )
    normalized["_creators"] = _normalize_creators(normalized, authors)
    normalized["_metadata_diagnostics"] = [
        item.to_dict() for item in diagnostics.items
    ]
    normalized["_metadata_warnings"] = [
        item.to_dict() for item in diagnostics.warnings
    ]
    normalized["_metadata_ok"] = diagnostics.ok

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


def validate_metadata(data: dict) -> Diagnostics:
    """Return actionable diagnostics for a metadata mapping."""
    normalized = normalize_metadata(data)
    diagnostics = Diagnostics()
    for item in normalized.get("_metadata_diagnostics", []):
        diagnostics.add(
            item["path"],
            item["line"],
            item["code"],
            item["message"],
            severity=item["severity"],
        )
    return diagnostics


metadata_diagnostics = validate_metadata


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
