"""Canonical core library for article-scaffold.

The CLI, Make targets, pre-push hook, CI, and optional MCP adapter are thin
adapters over these functions. This module intentionally has no printing,
process-exit, or current-working-directory assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from .build import BuildPlan, docx_plan, is_standalone_tex, pdf_plan, supplementary_plans
from .diagnostics import Diagnostic, Diagnostics
from .latex import count_unescaped, latex_escape, replace_block, strip_comments
from .metadata import (
    OutputDrift,
    collect_expected,
    compare_outputs,
    gen_abstract_block,
    gen_article_tex_title_block,
    gen_backmatter_version_block,
    gen_changes_current_block,
    gen_citation_cff,
    gen_readme_bibtex_block,
    gen_readme_meta_block,
    gen_zenodo_json,
    load_metadata,
    normalize_metadata,
    write_expected,
    zenodo_license_id,
)
from .release import apply_release, plan_release
from .tools import (
    TOOL_PLANS,
    arxiv_plan,
    diff_plan,
    figures_plan,
    spell_plan,
    watch_plan,
    wordcount_plan,
)
from .upgrade import UpgradeError
from .upgrade import apply as apply_upgrade
from .upgrade import finish as finish_upgrade
from .upgrade import plan as plan_upgrade
from .validate import validate_paper

CORE_VERSION = "1.0.0"


class ExitCode(IntEnum):
    """Stable process exit codes for every adapter."""

    OK = 0
    DIAGNOSTICS = 1
    USAGE = 2
    INTERNAL = 3


@dataclass(frozen=True)
class RepoPaths:
    """Canonical paths derived from an explicit repository root."""

    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / "metadata.yaml"

    @property
    def paper(self) -> Path:
        return self.root / "paper"

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    @property
    def citation(self) -> Path:
        return self.root / "CITATION.cff"

    @property
    def zenodo(self) -> Path:
        return self.root / ".zenodo.json"


__all__ = [
    "BuildPlan",
    "CORE_VERSION",
    "Diagnostic",
    "Diagnostics",
    "ExitCode",
    "OutputDrift",
    "RepoPaths",
    "TOOL_PLANS",
    "UpgradeError",
    "apply_release",
    "apply_upgrade",
    "collect_expected",
    "compare_outputs",
    "count_unescaped",
    "docx_plan",
    "gen_abstract_block",
    "gen_article_tex_title_block",
    "gen_backmatter_version_block",
    "gen_changes_current_block",
    "gen_citation_cff",
    "gen_readme_bibtex_block",
    "gen_readme_meta_block",
    "gen_zenodo_json",
    "latex_escape",
    "load_metadata",
    "normalize_metadata",
    "is_standalone_tex",
    "pdf_plan",
    "supplementary_plans",
    "finish_upgrade",
    "plan_release",
    "plan_upgrade",
    "replace_block",
    "strip_comments",
    "validate_paper",
    "write_expected",
    "zenodo_license_id",
    "arxiv_plan",
    "diff_plan",
    "figures_plan",
    "spell_plan",
    "watch_plan",
    "wordcount_plan",
]
