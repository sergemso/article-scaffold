"""Pure LaTeX text helpers used by metadata generation and validation."""

from __future__ import annotations

import re

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


def _strip_comment_from_line(line: str) -> str:
    """Remove a TeX comment, respecting an odd number of preceding backslashes."""
    out: list[str] = []
    for char in line:
        if char == "%":
            backslashes = 0
            for previous in reversed(out):
                if previous == "\\":
                    backslashes += 1
                else:
                    break
            if backslashes % 2 == 0:
                break
        out.append(char)
    return "".join(out)


def strip_comments(text: str) -> str:
    """Strip comments line by line while preserving line numbers."""
    return "\n".join(_strip_comment_from_line(line) for line in text.split("\n"))


def count_unescaped(text: str, char: str) -> int:
    """Count `char` occurrences that are not escaped by a backslash."""
    count = 0
    backslashes = 0
    for current in text:
        if current == "\\":
            backslashes += 1
            continue
        if current == char and backslashes % 2 == 0:
            count += 1
        backslashes = 0
    return count


def replace_block(text: str, start_marker: str, end_marker: str, new_block: str) -> str:
    """Replace a sentinel-delimited block, treating the replacement literally."""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(
            f"Could not find marker block {start_marker}...{end_marker} in target file"
        )
    new_block_stripped = new_block.rstrip("\n")
    return pattern.sub(lambda _match: new_block_stripped, text)
