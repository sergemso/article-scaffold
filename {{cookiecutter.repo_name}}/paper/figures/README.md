# `paper/figures/`

Source artwork for the manuscript. Files here are **tracked** by git (they are
not ignored). The preamble's `\graphicspath{ {figures/} }` lets you include
them in `paper/sections/*.tex` by basename only:

```latex
\includegraphics[width=0.8\textwidth]{example_figure.pdf}
```

## Conventions

- **Vector first.** Prefer PDF or SVG-derived PDF for line art; PNG only for
  raster screenshots. PDFs render cleanly at any zoom level in the final
  manuscript.
- **Self-contained names.** `figure1.pdf` is acceptable but `cost_per_token.pdf`
  is better: the filename should survive a renumbering of the figure list.
- **Captions in LaTeX, not in the figure.** The figure file should contain
  only the visual; the caption lives in the `\caption{...}` command in the
  section file so that the caption text is searchable.
- **Generation scripts live in `paper/figures/scripts/`** if your figures are
  produced by code. Commit both the script and the rendered PDF so that the
  PDF is reproducible without re-running the script.

## Placeholder

Delete the example below once you add a real figure. The `\includegraphics`
example in `paper/sections/02_methods.tex` references `example_figure.pdf` —
either drop a PDF by that name in this directory or update the example.
