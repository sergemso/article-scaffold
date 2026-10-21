#!/usr/bin/env python3
"""Reproducible fixture analysis: CSV -> LaTeX table + PDF figure.

The default path uses only the Python standard library. Scientific Python
packages are an optional extra (see ``pyproject.toml``); they are needed only
when a user replaces this fixture with a heavier custom analysis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PAPER_DIR = ROOT / "paper"
TABLE_PATH = PAPER_DIR / "tables" / "analysis_summary.tex"
FIGURE_PATH = PAPER_DIR / "figures" / "analysis_plot.pdf"
FIGURE_TEX_PATH = PAPER_DIR / "figures" / "analysis_figure.tex"
HEAVY_MODULES = ("matplotlib", "numpy", "pandas")


class AnalysisError(RuntimeError):
    """A user-actionable pipeline failure."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_checksums() -> int:
    checksum_path = DATA_DIR / "checksums.sha256"
    if not checksum_path.is_file():
        raise AnalysisError(
            f"missing {checksum_path.relative_to(ROOT)}; restore it from git so "
            "the analysis inputs can be verified."
        )

    verified = 0
    for number, raw_line in enumerate(checksum_path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise AnalysisError(
                f"{checksum_path.relative_to(ROOT)}:{number}: expected "
                "'<sha256>  <path>'."
            )
        expected, relative = parts
        relative = relative.lstrip("*")
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected.lower()):
            raise AnalysisError(
                f"{checksum_path.relative_to(ROOT)}:{number}: invalid SHA-256 digest."
            )

        path = ROOT / relative
        if not path.is_file():
            raise AnalysisError(
                f"missing input {relative}; restore it from git before running "
                "the analysis."
            )
        actual = _sha256(path)
        if actual != expected.lower():
            raise AnalysisError(
                f"checksum mismatch for {relative}: expected {expected.lower()}, "
                f"got {actual}. If the data change is intentional, update "
                f"{checksum_path.relative_to(ROOT)} deliberately."
            )
        verified += 1

    if not verified:
        raise AnalysisError(
            f"{checksum_path.relative_to(ROOT)} contains no input checksums."
        )
    return verified


def _load_observations() -> dict[str, list[float]]:
    path = DATA_DIR / "raw" / "observations.csv"
    if not path.is_file():
        raise AnalysisError(
            f"missing input {path.relative_to(ROOT)}; restore it from git before "
            "running the analysis."
        )

    observations: dict[str, list[float]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if "group" not in fields or "value" not in fields:
            raise AnalysisError(
                f"{path.relative_to(ROOT)}: expected columns 'group,value'."
            )
        for line_number, row in enumerate(reader, 2):
            group = (row.get("group") or "").strip()
            raw_value = (row.get("value") or "").strip()
            if not group:
                raise AnalysisError(
                    f"{path.relative_to(ROOT)}:{line_number}: empty group."
                )
            try:
                value = float(raw_value)
            except ValueError as exc:
                raise AnalysisError(
                    f"{path.relative_to(ROOT)}:{line_number}: value {raw_value!r} "
                    "is not a number."
                ) from exc
            if not math.isfinite(value):
                raise AnalysisError(
                    f"{path.relative_to(ROOT)}:{line_number}: value must be finite."
                )
            observations.setdefault(group, []).append(value)

    if not observations:
        raise AnalysisError(
            f"{path.relative_to(ROOT)} contains no observations."
        )
    return observations


def _summaries(observations: dict[str, list[float]]) -> list[tuple[str, int, float]]:
    return [
        (group, len(values), sum(values) / len(values))
        for group, values in sorted(observations.items())
    ]


def _latex_escape(value: str) -> str:
    escaped = value.replace("\\", r"\textbackslash{}")
    for char, replacement in (
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        escaped = escaped.replace(char, replacement)
    return escaped


def _render_table(rows: list[tuple[str, int, float]]) -> str:
    body = "\n".join(
        f"{_latex_escape(group)} & {count} & {mean:.2f} \\\\"
        for group, count, mean in rows
    )
    return (
        "% Generated by analysis/analyze.py from data/raw/observations.csv.\n"
        "% Do not edit by hand; run `make analysis` instead.\n"
        "\\begin{table}[H]\n"
        "  \\centering\n"
        "  \\small\n"
        "  \\caption{Mean observed value by group in the fixture dataset.}\n"
        "  \\label{tab:analysis_summary}\n"
        "  \\begin{tabular}{lrr}\n"
        "    \\toprule\n"
        "    Group & N & Mean \\\\\n"
        "    \\midrule\n"
        f"{body}\n"
        "    \\bottomrule\n"
        "  \\end{tabular}\n"
        "\\end{table}\n"
    )


def _render_figure_fragment() -> str:
    return (
        "% Generated by analysis/analyze.py from data/raw/observations.csv.\n"
        "% Do not edit by hand; run `make analysis` instead.\n"
        "\\begin{figure}[H]\n"
        "  \\centering\n"
        "  \\includegraphics[width=0.75\\textwidth]{analysis_plot.pdf}\n"
        "  \\caption{Mean outcome by group in the fixture analysis. Replace the\n"
        "    fixture with your own data and analysis; regenerate with\n"
        "    \\texttt{make analysis}.}\n"
        "  \\label{fig:analysis_plot}\n"
        "\\end{figure}\n"
    )


def _pdf_escape(value: str) -> str:
    text = str(value).encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_figure(rows: list[tuple[str, int, float]]) -> bytes:
    page_width, page_height = 420, 260
    left, bottom, plot_width, plot_height = 55, 55, 320, 145
    max_value = max(mean for _, _, mean in rows)
    scale = plot_height / max_value if max_value > 0 else 0.0
    slot = plot_width / len(rows)
    bar_width = min(64.0, slot * 0.55)
    colors = ("0.20 0.47 0.75", "0.85 0.45 0.20", "0.25 0.60 0.35", "0.55 0.35 0.70")

    commands = [
        "0.98 0.98 0.98 rg",
        f"0 0 {page_width} {page_height} re f",
        "0.20 0.20 0.20 RG",
        "0.8 w",
        f"{left} {bottom} m {left} {bottom + plot_height} l S",
        f"{left} {bottom} m {left + plot_width} {bottom} l S",
        "BT /F1 12 Tf 55 232 Td (Mean value by group) Tj ET",
    ]

    for index, (group, _count, mean) in enumerate(rows):
        x = left + slot * index + (slot - bar_width) / 2
        height = max(0.0, mean * scale)
        commands.append(f"{colors[index % len(colors)]} rg")
        commands.append(f"{x:.2f} {bottom:.2f} {bar_width:.2f} {height:.2f} re f")
        label_x = max(left, x - 12)
        commands.append(
            f"BT /F1 9 Tf {label_x:.2f} 38 Td ({_pdf_escape(group)}) Tj ET"
        )
        commands.append(
            f"BT /F1 9 Tf {x:.2f} {bottom + height + 5:.2f} Td "
            f"({_pdf_escape(f'{mean:.2f}')}) Tj ET"
        )

    commands.append(
        f"BT /F1 8 Tf {left} {bottom + plot_height + 8} Td "
        f"({_pdf_escape(f'Maximum {max_value:.2f}')}) Tj ET"
    )
    content = ("\n".join(commands) + "\n").encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {page_width} {page_height}] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"\nendstream"
        ),
    ]

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            "trailer\n<< /Size 6 /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _check_heavy_environment() -> None:
    missing = [name for name in HEAVY_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        raise AnalysisError(
            "heavy analysis dependencies are not installed ("
            + ", ".join(missing)
            + "). Run `uv sync --extra heavy` in analysis/ or use the "
            "standard-library pipeline without --heavy."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify checksums and parse the data without writing outputs",
    )
    parser.add_argument(
        "--heavy",
        action="store_true",
        help="require the optional scientific Python extra",
    )
    args = parser.parse_args(argv)

    try:
        if args.heavy:
            _check_heavy_environment()
        verified = _verify_checksums()
        observations = _load_observations()
        rows = _summaries(observations)
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.check:
        count = sum(len(values) for values in observations.values())
        print(f"OK: {verified} input checksum(s) verified; {count} observations.")
        return 0

    try:
        TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TABLE_PATH.write_text(_render_table(rows), encoding="utf-8")
        FIGURE_PATH.write_bytes(_render_figure(rows))
        FIGURE_TEX_PATH.write_text(_render_figure_fragment(), encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: could not write analysis outputs: {exc}", file=sys.stderr)
        return 2

    for path in (TABLE_PATH, FIGURE_PATH, FIGURE_TEX_PATH):
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
