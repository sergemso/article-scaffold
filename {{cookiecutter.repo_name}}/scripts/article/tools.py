"""Tool implementations for daily authoring tasks.

Each function returns a BuildPlan with the command to run.
All tools fail with actionable messages when the external tool is missing.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BuildPlan:
    """A command plus its working directory and declared output."""

    name: str
    command: tuple[str, ...]
    cwd: str
    output: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "cwd": self.cwd,
            "output": self.output,
        }


def _which_or_error(tool: str, hint: str = "") -> str:
    """Find tool on PATH or raise a helpful error."""
    path = shutil.which(tool)
    if path is None:
        msg = f"required tool '{tool}' not found in PATH"
        if hint:
            msg += f"; {hint}"
        raise FileNotFoundError(msg)
    return path


# ──────────────────────────────────────────────────────────────────────
# diff — latexdiff between two git refs
# ──────────────────────────────────────────────────────────────────────

def diff_plan(
    root: Path,
    *,
    old_ref: str = "HEAD~1",
    new_ref: str = "HEAD",
    output: str | None = None,
    dry_run: bool = False,
) -> BuildPlan:
    """Generate a diff PDF using latexdiff between two git refs."""
    if not dry_run:
        _which_or_error("latexdiff", "install latexdiff (often in texlive-extra-utils)")
    _which_or_error("git", "git is required")

    if output is None:
        output = f"diff-{old_ref.replace('/', '-')}-{new_ref.replace('/', '-')}.pdf"

    cmd = (
        "bash",
        "-c",
        (
            "set -euo pipefail; "
            "OLD_DIR=$(mktemp -d); NEW_DIR=$(mktemp -d); "
            f"git show {old_ref}:paper/article.tex > \"$OLD_DIR/article.tex\" 2>/dev/null || "
            f"git show {old_ref}:paper/article.tex > \"$OLD_DIR/article.tex\"; "
            f"git show {new_ref}:paper/article.tex > \"$NEW_DIR/article.tex\" 2>/dev/null || "
            f"git show {new_ref}:paper/article.tex > \"$NEW_DIR/article.tex\"; "
            "cd paper && latexdiff \"$OLD_DIR/article.tex\" \"$NEW_DIR/article.tex\" > diff.tex && "
            "latexmk -pdf -interaction=nonstopmode -file-line-error -halt-on-error diff.tex && "
            f"cp diff.pdf ../{output}"
        ),
    )

    return BuildPlan(
        name="diff",
        command=cmd,
        cwd=str(root),
        output=output,
    )


# ──────────────────────────────────────────────────────────────────────
# arxiv — flatten and sanitize for arXiv submission
# ──────────────────────────────────────────────────────────────────────

# Patterns for files/dirs to exclude from arXiv package
ARXIV_EXCLUDE_PATTERNS = [
    ".git",
    ".gitignore",
    ".github",
    "__pycache__",
    "*.pyc",
    ".venv",
    "venv",
    "build",
    "dist",
    "*.aux",
    "*.bbl",
    "*.blg",
    "*.log",
    "*.out",
    "*.toc",
    "*.lof",
    "*.lot",
    "*.fls",
    "*.fdb_latexmk",
    "*.synctex.gz",
    "*.pdf",
    "manuscript.docx",
    "manuscript.html",
    "manuscript.pdf",
    "paper/build",
    "paper/figures/generated",
    "paper/supplementary/build",
    "*.run.xml",
    "*.bcf",
    "scripts/githooks",
    "scripts/pre-push",
    "reference.docx",
    "CHANGES.md",
    "CITATION.cff",
    ".zenodo.json",
    "metadata.yaml",
]


def arxiv_plan(
    root: Path,
    *,
    output: str = "arxiv-submission.zip",
    dry_run: bool = False,
) -> BuildPlan:
    """Create a clean arXiv submission zip (flattened, no build artifacts)."""
    if not dry_run:
        _which_or_error("zip", "zip is required")

    exclude_args = []
    for pattern in ARXIV_EXCLUDE_PATTERNS:
        exclude_args.extend(["-x", pattern])

    cmd = (
        "zip",
        "-r",
        output,
        ".",
        *exclude_args,
    )

    return BuildPlan(
        name="arxiv",
        command=cmd,
        cwd=str(root),
        output=output,
    )


def arxiv_list(root: Path) -> list[str]:
    """List files that would be included in the arXiv package (for testing)."""
    import subprocess
    cmd = ["zip", "-r", "-", "."] + sum(
        ([ "-x", pattern ] for pattern in ARXIV_EXCLUDE_PATTERNS), []
    )
    result = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.strip().split()


# ──────────────────────────────────────────────────────────────────────
# wordcount — count words in the manuscript
# ──────────────────────────────────────────────────────────────────────

def wordcount_plan(
    root: Path,
    dry_run: bool = False,
) -> BuildPlan:
    """Count words in the manuscript using texcount."""
    if not dry_run:
        _which_or_error("texcount", "install texcount (part of TeX Live)")

    cmd = (
        "texcount",
        "-inc",
        "-brief",
        "paper/article.tex",
    )

    return BuildPlan(
        name="wordcount",
        command=cmd,
        cwd=str(root),
        output="wordcount.txt",
    )


# ──────────────────────────────────────────────────────────────────────
# spell — spell-check the manuscript
# ──────────────────────────────────────────────────────────────────────

def spell_plan(
    root: Path,
    dry_run: bool = False,
) -> BuildPlan:
    """Spell-check the manuscript using aspell."""
    if not dry_run:
        _which_or_error("aspell", "install aspell (and a dictionary, e.g. aspell-en)")

    cmd = (
        "aspell",
        "--mode=tex",
        "--lang=en",
        "--dont-backup",
        "check",
        "paper/article.tex",
    )

    return BuildPlan(
        name="spell",
        command=cmd,
        cwd=str(root / "paper"),
        output="spell-check",
    )


# ──────────────────────────────────────────────────────────────────────
# watch — live-reload PDF on changes
# ──────────────────────────────────────────────────────────────────────

def watch_plan(
    root: Path,
    dry_run: bool = False,
) -> BuildPlan:
    """Watch for changes and rebuild PDF (requires entr or inotifywait)."""
    if not dry_run:
        if shutil.which("entr"):
            pass  # entr is available
        elif shutil.which("inotifywait"):
            pass  # inotifywait is available
        else:
            raise FileNotFoundError(
                "neither 'entr' nor 'inotifywait' found; "
                "install entr (preferred) or inotify-tools"
            )

    if shutil.which("entr"):
        cmd = (
            "bash",
            "-c",
            "find paper -name '*.tex' -o -name '*.bib' | entr -c make -C paper pdf",
        )
    elif shutil.which("inotifywait"):
        cmd = (
            "bash",
            "-c",
            "while inotifywait -qre modify,create,delete paper; do make -C paper pdf; done",
        )
    else:
        # dry_run and no watcher available - just return a placeholder
        cmd = ("echo", "watcher not available")

    return BuildPlan(
        name="watch",
        command=cmd,
        cwd=str(root),
        output="live preview",
    )


# ──────────────────────────────────────────────────────────────────────
# figures — list figure files and their properties
# ──────────────────────────────────────────────────────────────────────

def figures_plan(
    root: Path,
    dry_run: bool = False,
) -> BuildPlan:
    """List all figure files with metadata (size, type, dimensions if image)."""
    if not dry_run:
        _which_or_error("file", "file command is required")
        _which_or_error("identify", "install ImageMagick (identify command) for dimensions")

    cmd = (
        "bash",
        "-c",
        (
            "cd paper/figures && "
            "for f in *; do "
            "  if [ -f \"$f\" ]; then "
            "    size=$(stat -c%s \"$f\" 2>/dev/null || stat -f%z \"$f\"); "
            "    type=$(file -b --mime-type \"$f\"); "
            "    if command -v identify >/dev/null; then "
            "      dim=$(identify -format '%wx%h' \"$f\" 2>/dev/null || echo 'N/A'); "
            "    else "
            "      dim='N/A'; "
            "    fi; "
            "    printf '%s\\t%s\\t%s\\t%s\\n' \"$f\" \"$size\" \"$type\" \"$dim\"; "
            "  fi; "
            "done"
        ),
    )

    return BuildPlan(
        name="figures",
        command=cmd,
        cwd=str(root),
        output="figures.txt",
    )


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

TOOL_PLANS = {
    "diff": diff_plan,
    "arxiv": arxiv_plan,
    "wordcount": wordcount_plan,
    "spell": spell_plan,
    "watch": watch_plan,
    "figures": figures_plan,
}