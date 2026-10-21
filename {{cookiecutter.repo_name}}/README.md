<!-- README:META:START -->
# {{ cookiecutter.title }}
{%- if cookiecutter.subtitle %}
## {{ cookiecutter.subtitle }}
{%- endif %}

**Manuscript type:** {{ cookiecutter.manuscript_type }}
**Version:** {{ cookiecutter.version_label }} ({{ cookiecutter.date }})
**License:** {{ cookiecutter.license }}
**Code license:** MIT
**Target deposit:** {{ cookiecutter.target_deposit }} (preprint)
{%- if cookiecutter.doi %}
**DOI:** {{ cookiecutter.doi }}
{%- endif %}

## Abstract

{{ cookiecutter.abstract }}
<!-- README:META:END -->

---

## Repository Structure

```
{{ cookiecutter.repo_name }}/
├── README.md
├── LICENSE                    # {{ cookiecutter.license }} paper license
{%- if cookiecutter.license == "CC-BY-4.0" %}
├── LICENSE-CODE               # MIT code license
{%- endif %}
├── CITATION.cff               # Citation metadata (regenerated from metadata.yaml)
├── .zenodo.json               # Zenodo deposit metadata (regenerated from metadata.yaml)
├── metadata.yaml              # Single source of truth for metadata
├── .gitignore
├── Makefile                   # Build automation (pdf / docx / validate / metadata / clean / analysis)
├── CHANGES.md                 # Version history (v1 → v2 → ...)
├── .github/
│   └── workflows/
│       ├── build-artifacts.yml    # Builds PDF + DOCX on push to paper/**
│       ├── release.yml           # Builds + publishes on v* tags
│       └── validate-latex.yml    # Lint: \input resolves, \cite keys exist, braces balanced
├── paper/
│   ├── article.tex            # Main LaTeX document
│   ├── refs.bib               # BibTeX bibliography
│   ├── Makefile               # Direct paper/ build
│   ├── .latexmkrc             # latexmk config: outdir=build, reproducible
│   ├── sections/
│   │   ├── 00_abstract.tex
│   │   ├── 01_introduction.tex
│   │   ├── 02_methods.tex          # optional; uncomment \input in article.tex
│   │   ├── 03_results.tex          # optional
│   │   ├── 04_discussion.tex       # optional
│   │   ├── 05_conclusion.tex
│   │   ├── 08_backmatter.tex       # COI / Data / AI-use / Version statements
│   │   └── 09_references.tex
│   ├── figures/               # Tracked; referenced via \includegraphics
│   └── tables/                # Generated tables from make analysis
├── data/
│   ├── raw/observations.csv   # fixture data for empirical analysis
│   └── checksums.sha256       # input checksums for reproducibility
├── analysis/
│   ├── analyze.py             # stdlib-only pipeline: CSV → table + figure
│   ├── pyproject.toml         # optional heavy deps (pandas, matplotlib, numpy)
│   └── uv.lock                # lockfile for optional deps
└── scripts/
    ├── article/               # Vendored core library + JSON-first CLI
    │   ├── cli.py             # python3 -m scripts.article
    │   ├── validate.py        # shared validation logic
    │   └── metadata.py        # shared metadata generation
    ├── generate-metadata.py   # Deprecated shim; delegates to scripts.article
    ├── validate-paper.py      # Deprecated shim; delegates to scripts.article
    └── pre-push               # Hook source; `make hooks` installs it
```

## Build Instructions

### Prerequisites
- **LaTeX distribution** with `pdflatex` and `bibtex` (TeX Live, MiKTeX, or MacTeX) — for PDF
- **Pandoc 3.x** — for DOCX
- **Python 3.10+** — for `make metadata` and `make validate`

### Build the PDF (canonical output)
```bash
make pdf        # runs latexmk: pdflatex → bibtex → pdflatex → pdflatex
```
Output: `paper/article.pdf`

### Build the DOCX (derived artifact)
```bash
make docx
```
Output: `manuscript.docx` (in the repository root). The DOCX is regenerated
by CI on every push that touches `paper/**`; you do not need to commit it.

### Validate locally
```bash
make validate   # runs the same checks as .github/workflows/validate-latex.yml
```
The pre-push hook (installed automatically by the scaffold) runs
`python3 -m scripts.article validate` before each push. It lives in
`scripts/githooks/pre-push` and is enabled through `core.hooksPath`. After
cloning an existing repository, run:

```bash
make hooks      # install/reinstall the pre-push hook; safe to rerun
```

### JSON-first CLI

Every Make target above is also available through the vendored CLI. Use
`--json` for CI, hooks, editors, or an optional MCP adapter:

```bash
python3 -m scripts.article validate --json
python3 -m scripts.article metadata --check --json
python3 -m scripts.article status --json
python3 -m scripts.article build pdf --dry-run --json
```

Exit codes are stable: `0` success, `1` diagnostics/failure, `2` usage error,
and `3` internal error. `scripts/validate-paper.py` and
`scripts/generate-metadata.py` remain as deprecated shims for older
repositories and still accept their historical flags.

### Regenerate derived metadata
After editing `metadata.yaml` (e.g. to bump the version or add a DOI):
```bash
make metadata
```
This updates `CITATION.cff`, `.zenodo.json`, the title/author/date block in
`paper/article.tex`, and the citation block below.

### Clean
```bash
make clean      # removes LaTeX build artifacts + manuscript.docx + manuscript.pdf
```

## Citation

<!-- BIBTEX:CITATION:START -->
<!-- Regenerated by `python scripts/generate-metadata.py` from metadata.yaml.
     Edit metadata.yaml, not this block. -->
```bibtex
@misc{ {{ cookiecutter.topic }}_{{ cookiecutter.version_label | replace(' ', '_') | replace('.', '') }},
  author       = { {{ cookiecutter.author_name }} },
  title        = { {{ cookiecutter.title }} },
  year         = { {{ cookiecutter.date[:4] }} },
  note         = { {{ cookiecutter.version_label }} },
  howpublished = { {{ cookiecutter.target_deposit }} },
{%- if cookiecutter.doi %}
  doi          = { {{ cookiecutter.doi }} },
  url          = { https://doi.org/{{ cookiecutter.doi }} },
{%- else %}
  url          = { https://github.com/{{ cookiecutter.github_user }}/{{ cookiecutter.repo_name }} },
{%- endif %}
  license      = { {{ cookiecutter.license }} }
}
```
<!-- BIBTEX:CITATION:END -->

## License

- Manuscript: [{{ cookiecutter.license }}](LICENSE)
{%- if cookiecutter.license == "CC-BY-4.0" %}
- Code: [MIT](LICENSE-CODE)
{%- endif %}

## Conflicts of Interest

See `paper/sections/08_backmatter.tex` for the full COI, Data Availability,
Use of AI Assistance, and Version statements.
