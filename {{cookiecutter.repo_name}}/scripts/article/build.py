"""Side-effect-free build plans consumed by the CLI and Make targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_DOCUMENTCLASS_RE = re.compile(r"^[^%\n]*\\documentclass\b", re.MULTILINE)


@dataclass(frozen=True)
class BuildPlan:
    """A command plus its working directory and declared output."""

    name: str
    command: tuple[str, ...]
    cwd: str
    output: str
    # Where a successful build also copies *output*, so the CLI and ``make pdf`` agree.
    publish_to: str | None = None

    def to_dict(self) -> dict[str, object]:
        plan: dict[str, object] = {
            "name": self.name,
            "command": list(self.command),
            "cwd": self.cwd,
            "output": self.output,
        }
        if self.publish_to:
            plan["publish_to"] = self.publish_to
        return plan


def pdf_plan(root: Path | None = None) -> BuildPlan:
    """Plan the canonical PDF build; *root* is accepted for future use."""
    del root
    return BuildPlan(
        name="pdf",
        command=(
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-file-line-error",
            "-halt-on-error",
            "article.tex",
        ),
        cwd="paper",
        output="paper/build/article.pdf",
        publish_to="paper/article.pdf",
    )


def docx_plan(
    root: Path | None = None,
    *,
    pandoc: str = "pandoc",
    reference_docx: str | None = None,
    citeproc: bool = True,
    citation_style: str | None = None,
) -> BuildPlan:
    """Plan a DOCX build with the same resource path as ``make docx``."""
    del root
    command = [
        pandoc,
        "--output=manuscript.docx",
        "--from=latex",
        "--to=docx",
    ]
    if citeproc:
        command.extend(["--citeproc", "--bibliography=paper/refs.bib"])
    if citation_style:
        command.append(f"--metadata=citation-style={citation_style}")
    command.extend(
        [
            "--resource-path=paper:paper/figures:.",
        ]
    )
    if reference_docx:
        command.append(f"--reference-doc={reference_docx}")
    command.append("paper/article.tex")
    return BuildPlan(
        name="docx",
        command=tuple(command),
        cwd=".",
        output="manuscript.docx",
    )


def is_standalone_tex(path: Path) -> bool:
    """True when *path* is a compilable document, not an ``\\input`` fragment."""
    try:
        return bool(_DOCUMENTCLASS_RE.search(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError):
        return False


def supplementary_plans(root: Path | None = None) -> list[BuildPlan]:
    """Plan one PDF build per standalone supplementary document.

    Discovers ``paper/supplementary.tex`` (legacy single-file layout) and every
    top-level ``paper/supplementary/*.tex`` that has a ``\\documentclass``.
    Fragments without one are skipped. Returns ``[]`` without a *root*.
    """
    if root is None:
        return []
    paper = root / "paper"
    plans: list[BuildPlan] = []
    legacy = paper / "supplementary.tex"
    if legacy.is_file() and is_standalone_tex(legacy):
        plans.append(_supp_plan("supplementary", "paper", "paper/build", "paper"))
    supp_dir = paper / "supplementary"
    if supp_dir.is_dir():
        for tex in sorted(supp_dir.glob("*.tex")):
            if is_standalone_tex(tex):
                plans.append(
                    _supp_plan(
                        tex.stem,
                        "paper/supplementary",
                        "paper/supplementary/build",
                        "paper/supplementary",
                    )
                )
    return plans


def _supp_plan(stem: str, cwd: str, build_dir: str, publish_dir: str) -> BuildPlan:
    return BuildPlan(
        name=f"supp:{stem}",
        command=(
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-file-line-error",
            "-halt-on-error",
            "-outdir=build",
            f"{stem}.tex",
        ),
        cwd=cwd,
        output=f"{build_dir}/{stem}.pdf",
        publish_to=f"{publish_dir}/{stem}.pdf",
    )
