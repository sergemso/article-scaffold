# `paper/tables/`

Generated and hand-authored tables for empirical manuscripts. Files here are
tracked by git, so a table can be regenerated from `analysis/` and reviewed as a
normal source diff. The preamble's `\graphicspath` includes `tables/` for
empirical projects, so a table saved as a PDF can be included by basename:

```latex
\includegraphics[width=\textwidth]{cost_table.pdf}
```

Prefer a LaTeX `table`/`tabular` environment when the table is small and the
numbers are stable. Use a generated PDF or a `\input` fragment from this
directory when the table is produced by `make analysis`; keep the analysis
script and its lockfile in the repository so the table is reproducible.

The perspective and review manuscript kinds do not load this directory by
default. `make pdf` never runs analysis; use `make analysis` explicitly before
building an empirical manuscript.
