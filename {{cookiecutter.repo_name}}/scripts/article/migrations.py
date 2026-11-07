"""Template migrations for ``metadata.yaml``, which an upgrade never text-merges.

``metadata.yaml`` holds the author's values next to template comments, so a 3-way
merge conflicts whenever the template removes a comment beside an edited value. The
upgrade leaves the file out of the template diff and applies the migrations below
instead. A migration deletes only lines that match what an earlier template shipped,
character for character; a value the author wrote or changed is never touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Migration:
    """Edits introduced by template version ``since``."""

    since: tuple[int, ...]
    # Whole lines removed when they match exactly (without the newline).
    remove_lines: tuple[str, ...] = ()
    # Exact multi-line texts replaced by another text.
    replace: tuple[tuple[str, str], ...] = ()


_PLACEHOLDER_NOTE = (
    'abstract_note: "Replace this paragraph with a transparency note about the evidence '
    "base used in the manuscript. If the paper draws on industry data, single-source "
    "datasets, or non-peer-reviewed sources, state that here and note the limitations. "
    "If the paper uses only peer-reviewed sources and primary documents, you can delete "
    'this paragraph entirely."'
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        since=(1, 5, 0),
        remove_lines=(
            '# subtitle: ""  # optional; uncomment and fill if needed',
            _PLACEHOLDER_NOTE,
            "# Optional: Markdown printed under the current version heading in CHANGES.md.",
            "# release_notes: |",
            "#   First public version.",
            "#",
            "#   ### Contents",
            "#   - What this version contains",
            "# Markdown printed under the current version heading in CHANGES.md.",
            "# Legacy alias kept for older generated repos; the generator prefers `abstract`.",
            "# Zenodo uses the abstract as its description. Keep a separate `description`",
            "# only if you need a longer, deposit-specific text; the generator prefers",
            "# `abstract` when both are present.",
            "# Used by .zenodo.json `references`. Each entry should be a short,",
            "# human-readable citation. Optional — leave empty list for a fresh repo.",
            '#  - "Perez, C. (2002). Technological Revolutions and Financial Capital."',
            '#  - "Anthropic (2026). An update on independent evaluators."',
            "# Zenodo communities — optional. Add only verified community identifiers;",
            "# the generator never invents one.",
        ),
        replace=(
            ("#   python scripts/generate-metadata.py\n", "#   make metadata\n"),
            (
                "# Re-running generate-metadata.py is idempotent: it only overwrites\n"
                "# the metadata-derived fields, leaving your prose untouched.\n",
                "# `make pdf`, `make docx` and the CI build regenerate these files first, so\n"
                "# they never lag behind this file. Optional keys are documented in\n"
                "# docs/metadata.md and schemas/metadata.schema.json.\n"
                "#\n"
                "# Regeneration is idempotent: it only overwrites the metadata-derived\n"
                "# fields, leaving your prose untouched.\n",
            ),
            (
                "# masthead, and the Zenodo description. Edit it here, then run `make metadata`.\n",
                "# masthead, and the Zenodo description.\n",
            ),
        ),
    ),
)


def parse_version(value: object) -> tuple[int, ...]:
    """``"1.5.0"`` -> ``(1, 5, 0)``; an empty or unparseable value is ``(0,)``."""
    parts = re.findall(r"\d+", str(value or "").split("+")[0].split("-")[0])
    return tuple(int(p) for p in parts) or (0,)


def migrate_metadata(text: str, old_version: object, new_version: object) -> str:
    """Apply the migrations with ``old_version < since <= new_version`` to *text*."""
    old, new = parse_version(old_version), parse_version(new_version)
    for migration in MIGRATIONS:
        if not old < migration.since <= new:
            continue
        for before, after in migration.replace:
            text = text.replace(before, after)
        removable = set(migration.remove_lines)
        text = "".join(
            line for line in text.splitlines(keepends=True) if line.rstrip("\r\n") not in removable
        )
        text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ------------------------------------------------------------------ delivered files
#
# Files an older repo needs for the results ledger and the source store. They are
# computed read-only (``deliveries``) so the upgrade can tell whether it has work, and
# written only after the upgrade branch exists. Each one is idempotent and only adds:
# a value the author wrote in ``flow.yaml`` or ``metadata.yaml`` is never read or changed.

LEDGER_ATTRIBUTES = "docs/ledger/** linguist-generated=true"
FLOW_HINTS = (
    "# Optional token-economy settings; the defaults apply while they are absent.\n"
    "# max_calls: {small: 40, large: 60}   # advisory cap on tool calls per order\n"
    "# brief_bytes: 6000                   # byte cap of `flow next --brief`\n"
    "# group_size: 3                       # orders per group that write one file; 1 = off\n"
)
EMPTY_SOURCE_MANIFEST = '{\n  "schema_version": "1.0",\n  "sources": []\n}\n'


def deliveries(root: Path) -> dict[str, str]:
    """Path to new text for the ledger, flow-hint and source-manifest files an old repo lacks."""
    out: dict[str, str] = {}
    attributes = root / ".gitattributes"
    if attributes.is_file():
        text = attributes.read_text(encoding="utf-8")
        if "docs/ledger/" not in text:
            out[".gitattributes"] = text + ("" if text.endswith("\n") or not text else "\n") + (
                LEDGER_ATTRIBUTES + "\n"
            )
    flow = root / "flow.yaml"
    if flow.is_file():
        text = flow.read_text(encoding="utf-8")
        if not any(key in text for key in ("max_calls", "brief_bytes", "group_size")):
            out["flow.yaml"] = text + ("" if text.endswith("\n") or not text else "\n") + (
                FLOW_HINTS
            )
    sources = root / "paper" / "sources"
    if sources.is_dir() and not (sources / "manifest.json").exists():
        out["paper/sources/manifest.json"] = EMPTY_SOURCE_MANIFEST
    return out
