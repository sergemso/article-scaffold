# `analysis/`

The empirical data-to-table/figure pipeline. It is intentionally independent of
the PDF build:

```bash
make analysis        # verify checksums, then regenerate fixtures
make analysis-check  # verify checksums and parse the data without writing
make pdf             # never invokes analysis
```

Default outputs:

```text
paper/tables/analysis_summary.tex
paper/figures/analysis_plot.pdf
```

The default pipeline uses only the Python standard library. That keeps a clean
checkout buildable with the same Python 3.10+ requirement as the rest of the
template. `uv.lock` records the optional scientific extras for users who replace
the fixture with a heavier analysis; they are opt-in:

```bash
cd analysis
uv sync --extra heavy
```

or, without uv:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[heavy]'
```

If the data file is missing, has a checksum mismatch, or the optional heavy
environment is requested but unavailable, the script stops with an actionable
error instead of writing partial outputs.

## Replacing the fixture

1. Put inputs under `data/raw/` and update `data/checksums.sha256`.
2. Edit `analyze.py` to read your inputs and write a LaTeX table plus a figure.
3. Keep the output paths stable so `paper/sections/03_results.tex` can include
   them conditionally, and test with `make analysis && make pdf`.
