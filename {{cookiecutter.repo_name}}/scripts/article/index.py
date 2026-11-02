"""Section index: where each label lives, and what each section opens with.

Lets an agent read a few lines of a long paper instead of the whole file.
Offline and deterministic: summaries are the first sentence of the first
paragraph, never a model call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .latex import strip_comments

INDEX_PATH = Path("paper") / "build" / "section-index.json"
SECTIONS_GLOB = "paper/sections/*.tex"
SUMMARY_MAX = 160
LEVELS = {
    "part": 0,
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
}
HEADING_RE = re.compile(
    r"\\(part|chapter|section|subsection|subsubsection|paragraph)"
    r"\*?\s*(?:\[[^\]]*\])?\s*\{"
)
INLINE_COMMANDS = ("emph", "textit", "textbf", "cite", "citep", "citet")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
ENV_RE = re.compile(r"\\(begin|end)\{([^}]+)\}")
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s")


def section_files(root: Path) -> list[Path]:
    return sorted(root.glob(SECTIONS_GLOB))


def _title(line: str, match: re.Match) -> str:
    depth, out = 1, []
    for char in line[match.end():]:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
    return "".join(out).strip()


def _clean(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    text = text.replace("~", " ").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def summarize(lines: list[str]) -> str:
    """First sentence of the first paragraph made of running text."""
    paragraph: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith("\\") and not paragraph:
            command = re.match(r"\\([a-zA-Z]+)", stripped)
            if command and command.group(1) not in INLINE_COMMANDS:
                continue
        paragraph.append(stripped)
    text = _clean(" ".join(paragraph))
    if not text:
        return ""
    first = SENTENCE_END_RE.split(text, maxsplit=1)[0]
    return first if len(first) <= SUMMARY_MAX else first[: SUMMARY_MAX - 3].rstrip() + "..."


def _spans(lines: list[str]) -> tuple[list[tuple[int, int, int]], list[tuple[int, int]]]:
    """Heading spans (level, start, end) and environment spans (start, end), 1-based."""
    heads: list[tuple[int, int]] = []
    envs: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for number, line in enumerate(lines, start=1):
        match = HEADING_RE.search(line)
        if match:
            heads.append((LEVELS[match.group(1)], number))
        for env in ENV_RE.finditer(line):
            if env.group(1) == "begin":
                stack.append((env.group(2), number))
            else:
                for index in range(len(stack) - 1, -1, -1):
                    if stack[index][0] == env.group(2):
                        envs.append((stack[index][1], number))
                        del stack[index:]
                        break
    spans = []
    for index, (level, start) in enumerate(heads):
        end = len(lines)
        for later_level, later_start in heads[index + 1:]:
            if later_level <= level:
                end = later_start - 1
                break
        spans.append((level, start, end))
    return spans, envs


def build_index(root: Path) -> dict:
    sections = []
    labels: dict[str, dict] = {}
    for path in section_files(root):
        relative = path.relative_to(root).as_posix()
        stripped = strip_comments(path.read_text(encoding="utf-8")).split("\n")
        if stripped and stripped[-1] == "":
            stripped.pop()
        spans, envs = _spans(stripped)
        title = ""
        for line in stripped:
            match = HEADING_RE.search(line)
            if match:
                title = _title(line, match)
                break
        sections.append(
            {
                "file": relative,
                "lines": len(stripped),
                "title": title,
                "summary": summarize(stripped),
            }
        )
        for number, line in enumerate(stripped, start=1):
            for match in LABEL_RE.finditer(line):
                inside = [e for e in envs if e[0] <= number <= e[1]]
                if inside:
                    start, end = min(inside, key=lambda e: e[1] - e[0])
                else:
                    owners = [s for s in spans if s[1] <= number <= s[2]]
                    if owners:
                        _, start, end = max(owners, key=lambda s: s[1])
                    else:
                        start = end = number
                labels.setdefault(
                    match.group(1).strip(), {"file": relative, "lines": [start, end]}
                )
    return {"version": 1, "sections": sections, "labels": dict(sorted(labels.items()))}


def write_index(root: Path) -> dict:
    index = build_index(root)
    target = root / INDEX_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def check_index(root: Path) -> list[str]:
    """Reasons the index is stale; empty when fresh."""
    target = root / INDEX_PATH
    if not target.is_file():
        return [f"{INDEX_PATH.as_posix()} is missing; run `python3 -m scripts.article index`"]
    built = target.stat().st_mtime_ns
    return [
        f"{path.relative_to(root).as_posix()} is newer than {INDEX_PATH.as_posix()}; "
        "run `python3 -m scripts.article index`"
        for path in section_files(root)
        if path.stat().st_mtime_ns > built
    ]
