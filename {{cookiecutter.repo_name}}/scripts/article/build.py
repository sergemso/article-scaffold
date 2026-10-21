"""Side-effect-free build plans consumed by the CLI and Make targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildPlan:
    """A command plus its working directory and declared output."""

    name: str
    command: tuple[str, ...]
    cwd: str
    output: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": list(self.command),
            "cwd": self.cwd,
            "output": self.output,
        }


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
