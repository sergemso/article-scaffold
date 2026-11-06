"""Tier 0 checks for the ``terms`` section of the theses map (decision 0076).

Offline and deterministic: a regular-expression scan of ``paper/sections/*.tex``
against the section index. No model call and no network. Output carries term
ids, file names and line numbers, never paragraphs of the paper.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from pathlib import Path

from .diagnostics import Diagnostics
from .index import LABEL_RE, build_index, section_files
from .latex import strip_comments

DEFINITION_ENVS = ("definition",)
MATH_ENVS = (
    "equation", "align", "alignat", "gather", "multline", "flalign", "eqnarray",
    "displaymath", "math",
)
VERBATIM_ENVS = ("verbatim", "Verbatim", "lstlisting", "minted", "alltt")
QUOTE_ENVS = ("quote", "quotation")
REF_COMMANDS = "ref|eqref|autoref|cref|Cref|pageref|nameref|vref"
# Commands whose braced argument is a key or path, never prose.
KEY_ARG_RE = re.compile(
    r"\\(?:label|" + REF_COMMANDS + r"|cite[a-zA-Z]*|begin|end|input|include"
    r"|includegraphics|url|bibliography|usepackage)\*?(?:\[[^\]]*\])*\{[^}]*\}"
)
REF_RE = re.compile(r"\\(?:" + REF_COMMANDS + r")\*?\{([^}]*)\}")
COMMAND_RE = re.compile(r"\\[a-zA-Z@]+\*?")
GENERATED_RE = re.compile(r"(?ms)^% ([A-Z][A-Z_]*):START$.*?^% \1:END$")
DEF_ENV_RE = re.compile(
    r"\\begin\{(" + "|".join(DEFINITION_ENVS) + r")\*?\}(?:\[([^\]]*)\])?(.*?)\\end\{\1\*?\}",
    re.DOTALL,
)
EMPHASIS_RE = re.compile(r"\\(?:emph|textbf|textit)\{([^{}]*)\}")
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s")

CODE_USE_BEFORE = "T060"
CODE_SECOND_SITE = "T061"


@dataclass
class Report:
    """What the scan found: lint diagnostics, gaps and informational notes."""

    diagnostics: Diagnostics = field(default_factory=Diagnostics)
    gaps: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)


@dataclass
class Occurrence:
    file: str
    line: int
    start: int
    end: int
    surface: str


@dataclass
class DefinitionEnv:
    file: str
    start: int
    end: int
    title: str
    labels: list[str]
    emphasised: list[str]
    body: str


# ------------------------------------------------------------------ masking


def _blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def _mask_prose(text: str) -> str:
    """*text* with every non-prose span blanked out, keeping offsets and newlines."""
    for name in MATH_ENVS + VERBATIM_ENVS + QUOTE_ENVS:
        text = re.sub(
            rf"\\begin\{{({name})\*?\}}.*?\\end\{{\1\*?\}}", _blank, text, flags=re.DOTALL
        )
    for pattern in (
        r"(?<!\\)\$\$.*?(?<!\\)\$\$",
        r"(?<!\\)\$.*?(?<!\\)\$",
        r"\\\(.*?\\\)",
        r"\\\[.*?\\\]",
        r"\\(?:verb|lstinline)\*?(.).*?\1",
        r"\\(?:enquote|textquote|mintinline)\*?(?:\[[^\]]*\])?\{[^{}]*\}",
        r"``.*?''",
    ):
        text = re.sub(pattern, _blank, text, flags=re.DOTALL)
    text = KEY_ARG_RE.sub(_blank, text)
    return COMMAND_RE.sub(_blank, text)


def _clean_source(raw: str) -> str:
    """Comments and generated blocks removed, line numbers preserved."""
    text = GENERATED_RE.sub(_blank, raw)
    return strip_comments(text)


# ----------------------------------------------------------------- matching


def _plurals(form: str) -> list[str]:
    last = form.split()[-1] if form.split() else form
    head = form[: len(form) - len(last)]
    if re.search(r"[^aeiou]y$", last):
        return [head + last[:-1] + "ies"]
    if re.search(r"(s|x|z|ch|sh)$", last):
        return [head + last + "es"]
    return [head + last + "s"]


def _phrase(form: str) -> str:
    return r"\s+".join(re.escape(word) for word in form.replace("~", " ").split())


def term_forms(term: dict) -> list[str]:
    """Listed surface forms: the name, ``forms`` and the same for each child."""
    forms = [term["name"]] + list(term.get("forms") or [])
    for child in term.get("children") or []:
        forms += [child["name"]] + list(child.get("forms") or [])
    seen: dict[str, None] = {}
    for form in forms:
        seen.setdefault(" ".join(form.split()), None)
    return list(seen)


def _searched(term: dict, strict: bool) -> list[str]:
    """Forms the scanner looks for under the term's ``match`` rule."""
    forms = term_forms(term)
    if not strict:
        return forms
    lenient = (
        term.get("match") == "word" or bool(term.get("scope")) or term.get("kind") == "acronym"
    )
    return [form for form in forms if lenient or len(form.split()) > 1]


def _pattern(forms: list[str]) -> re.Pattern | None:
    if not forms:
        return None
    alternatives = []
    for form in sorted(forms, key=len, reverse=True):
        alternatives.append(_phrase(form))
        alternatives += [_phrase(plural) for plural in _plurals(form)]
    return re.compile(r"(?<![\w-])(?:" + "|".join(alternatives) + r")(?![\w-])", re.IGNORECASE)


# ----------------------------------------------------------------- the scan


class Scan:
    """The prose of every section file, in document order."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.index = build_index(root)
        self.files: list[str] = []
        self.source: dict[str, str] = {}
        self.prose: dict[str, str] = {}
        self.starts: dict[str, list[int]] = {}
        for path in section_files(root):
            name = path.relative_to(root).as_posix()
            text = _clean_source(path.read_text(encoding="utf-8"))
            self.files.append(name)
            self.source[name] = text
            self.prose[name] = _mask_prose(text)
            self.starts[name] = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line(self, name: str, offset: int) -> int:
        return bisect.bisect_right(self.starts[name], offset)

    def order(self, name: str, line: int) -> tuple[int, int]:
        return (self.files.index(name), line)

    def span(self, label: str) -> tuple[str, int, int] | None:
        found = self.index["labels"].get(label)
        return (found["file"], found["lines"][0], found["lines"][1]) if found else None

    def occurrences(self, term: dict, strict: bool = True) -> list[Occurrence]:
        pattern = _pattern(_searched(term, strict))
        if pattern is None:
            return []
        scope = {s.replace("\\", "/") for s in term.get("scope") or []}
        found = []
        for name in self.files:
            if strict and scope and not any(name == s or name.endswith("/" + s) for s in scope):
                continue
            for match in pattern.finditer(self.prose[name]):
                found.append(
                    Occurrence(
                        name,
                        self.line(name, match.start()),
                        match.start(),
                        match.end(),
                        " ".join(match.group(0).split()),
                    )
                )
        return found

    def sentence_refs(self, occurrence: Occurrence) -> set[str]:
        """Labels referenced in the sentence around *occurrence*."""
        text = self.source[occurrence.file]
        start = max(
            text.rfind("\n\n", 0, occurrence.start) + 2,
            *(m.end() for m in SENTENCE_END_RE.finditer(text, 0, occurrence.start)),
            0,
        )
        tail = SENTENCE_END_RE.search(text, occurrence.end)
        end = tail.start() if tail else len(text)
        refs: set[str] = set()
        for match in REF_RE.finditer(text[start:end]):
            refs.update(key.strip() for key in match.group(1).split(","))
        return refs

    def sentence_initial(self, occurrence: Occurrence) -> bool:
        before = self.prose[occurrence.file][: occurrence.start]
        stripped = before.rstrip().rstrip("[({\"'")
        raw = self.source[occurrence.file][: occurrence.start].rstrip()
        return (
            not stripped
            or stripped[-1] in ".!?"
            or "\n\n" in before[len(before.rstrip()):]
            or raw.endswith("\\item")
        )

    def definition_envs(self) -> list[DefinitionEnv]:
        found = []
        for name in self.files:
            text = self.source[name]
            for match in DEF_ENV_RE.finditer(text):
                body = match.group(3)
                found.append(
                    DefinitionEnv(
                        name,
                        self.line(name, match.start()),
                        self.line(name, match.end()),
                        (match.group(2) or "").strip(),
                        [m.group(1).strip() for m in LABEL_RE.finditer(body)],
                        [m.group(1).strip() for m in EMPHASIS_RE.finditer(body)],
                        " ".join(body.split()),
                    )
                )
        return found


def _anchors(term: dict) -> list[str]:
    anchors = [term["anchor"]] if term.get("anchor") else []
    return anchors + [s["anchor"] for s in term.get("senses") or []]


def _inside(file: str, line: int, spans: list[tuple[str, int, int]]) -> bool:
    return any(file == f and start <= line <= end for f, start, end in spans)


def _env_in(env: DefinitionEnv, spans: list[tuple[str, int, int]]) -> bool:
    return any(
        env.file == f and start <= env.start and env.end <= end for f, start, end in spans
    )


def _env_names(env: DefinitionEnv, term: dict) -> bool:
    """True when the environment's title or emphasised text is a form of *term*."""
    pattern = _pattern(term_forms(term))
    if pattern is None:
        return False
    return any(
        pattern.fullmatch(" ".join(text.split())) for text in [env.title, *env.emphasised] if text
    )


def _env_summary(env: DefinitionEnv) -> str:
    text = env.title or re.sub(r"\\[a-zA-Z]+\*?|[{}]", "", env.body)
    text = " ".join(text.split())
    return text if len(text) <= 80 else text[:77].rstrip() + "..."


def check(root: Path, data: dict) -> Report:
    """Run the tier 0 term checks on a map that already passes ``theses lint``."""
    report = Report()
    terms = [t for t in data.get("terms") or [] if t.get("status") != "retired"]
    if not terms:
        return report
    scan = Scan(root)
    warn, error = report.diagnostics.warning, report.diagnostics.error
    spans: dict[str, list[tuple[str, int, int]]] = {}
    for term in terms:
        spans[term["id"]] = [s for s in map(scan.span, _anchors(term)) if s]
    registered = [s for found in spans.values() for s in found]
    envs = scan.definition_envs()

    for term in terms:
        defining = spans[term["id"]]
        _use_before_definition(term, defining, scan, report, warn, error)
        _drift(term, defining, scan, report)
        _orphan(term, defining, scan, report)

    for env in envs:
        if _env_in(env, registered):
            continue
        owner = next(
            (t for t in terms if t.get("kind") == "defined" and _env_names(env, t)), None
        )
        if owner is not None:
            warn(
                env.file,
                env.start,
                CODE_SECOND_SITE,
                f"term {owner['id']!r} is defined again here; its anchor is "
                f"{owner.get('anchor')!r}",
            )
        else:
            label = env.labels[0] if env.labels else f"{env.file}:{env.start}"
            report.gaps.append(
                {"kind": "term-unregistered", "id": label, "text": _env_summary(env)}
            )
    report.gaps.sort(key=lambda g: (g["kind"], g["id"]))
    return report


def _use_before_definition(term, defining, scan, report, warn, error) -> None:
    if term.get("kind") != "defined" or not defining:
        return
    first = min(scan.order(f, start) for f, start, _ in defining)
    anchors = set(_anchors(term))
    early = [
        o
        for o in scan.occurrences(term)
        if scan.order(o.file, o.line) < first and not (scan.sentence_refs(o) & anchors)
    ]
    if not early:
        return
    emit = error if term.get("status") == "accepted" else warn
    place = f"{early[0].file}:{early[0].line}"
    emit(
        early[0].file,
        early[0].line,
        CODE_USE_BEFORE,
        f"term {term['id']!r} is used before its definition at {place}"
        + (f" and {len(early) - 1} more place(s)" if len(early) > 1 else ""),
    )


def _drift(term, defining, scan, report) -> None:
    listed = set(term_forms(term))
    drift: dict[str, Occurrence] = {}
    for occurrence in scan.occurrences(term):
        surface = occurrence.surface
        if surface in listed or _inside(occurrence.file, occurrence.line, defining):
            continue
        if scan.sentence_initial(occurrence) and surface[:1].lower() + surface[1:] in listed:
            continue
        drift.setdefault(surface, occurrence)
    if drift:
        first = min(drift.values(), key=lambda o: scan.order(o.file, o.line))
        report.notes.append(
            {
                "kind": "term-drift",
                "id": term["id"],
                "text": "surface forms not listed: "
                + ", ".join(repr(s) for s in sorted(drift))
                + f"; first at {first.file}:{first.line}",
            }
        )


def _orphan(term, defining, scan, report) -> None:
    uses = [
        o
        for o in scan.occurrences(term, strict=False)
        if not _inside(o.file, o.line, defining)
    ]
    if not uses:
        report.notes.append(
            {
                "kind": "term-orphan",
                "id": term["id"],
                "text": f"{term['name']} is never used outside its definition",
            }
        )
