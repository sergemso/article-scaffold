# article-scaffold

A [Cookiecutter](https://github.com/cookiecutter/cookiecutter) template that
scaffolds a new LaTeX article repository following the canonical structure
extracted from a real article repository.

> **Design rationale:** see [`canonical-pattern.md`](./canonical-pattern.md)
> for the full analysis of the source repo's structure, the issues fixed in
> this template, and the rationale for each design choice. This README is the
> *how-to-use* doc; `canonical-pattern.md` is the *why-it's-structured-this-way*
> doc.

> **Agent workflow:** see [`AGENTS.md`](./AGENTS.md). The original hardening queue is
> archived in `docs/plans/archive/t-queue/`.

## Two ways to bootstrap a new article repo

**Option A — Locally with `cookiecutter`:**

```bash
# One-time install
pip install cookiecutter

# Scaffold a new article repo
cookiecutter /path/to/article-scaffold
```

You get interactive prompts for title / author / version / etc. The rendered
repo lands in `./articles.<topic>/`. The cookiecutter `post_gen_project.py`
hook automatically initialises git on the chosen default branch, makes the
scripts executable, installs the pre-push hook, and fills in today's date.

**Option B — Remotely with the `bootstrap-article.yml` workflow:**

If you push this template to GitHub, the
`.github/workflows/bootstrap-article.yml` workflow lets you bootstrap a new
article repo from the GitHub UI (or via `gh workflow run`) without cloning
locally. The workflow:

1. Renders the template with the parameters you supply as workflow inputs.
2. Runs `make validate` on the rendered repo (fails the workflow if the
   template is broken).
3. Creates a new GitHub repo under `${{ github.actor }}` (or a custom owner
   you specify) with the chosen visibility (default **private**).
4. Pushes the initial commit, which triggers the new repo's own
   `build-artifacts.yml` to build PDF + DOCX.

To use it, add a `GH_PAT` secret to the scaffold repo
(Settings → Secrets and variables → Actions → New repository secret).
The PAT needs the `repo` scope (classic) or `Administration: write`
(fine-grained) on the target owner. Then:

```bash
gh workflow run bootstrap-article.yml \
  -f topic=ai_governance \
  -f title="From AI Scaling to AI Governance" \
  -f subtitle="Technological Revolutions and the Political Economy of Deployment" \
  -f author_name="Your Name" \
  -f author_orcid="" \
  -f version="3.0.0" \
  -f version_label="v3 preprint" \
  -f license="CC-BY-4.0" \
  -f target_deposit="Zenodo" \
  -f keywords="AI governance,regulatory capture,Carlota Perez,embedded evaluators"
```

The workflow's job summary prints a clickable link to the new repo and a
next-steps checklist. See the workflow file for the full input list.

### Public companion repos

New article repos are private, but Zenodo only archives public repos. Each article repo
therefore has a public companion that receives an allowlisted snapshot on every final
release tag. The bootstrap workflow creates it by calling `provision-companion.yml`
(input `create_companion`, default true), which needs the `COMPANION_PAT` secret next to
`GH_PAT`. Existing repos adopt it by upgrading, then running the provisioning workflow.
Switching the companion on in Zenodo stays manual. See [docs/companion.md](docs/companion.md).

## Optional user configuration

You can set personal defaults so you don't have to re-enter them every time.
Create a config file at `~/.config/article-scaffold/config.yaml`:

```yaml
github_user: "your-github-user"
author_name: "Your Name"
author_orcid: "0000-0000-0000-0000"
author_affiliation: "Your Affiliation"
keywords: "your, keywords"
target_deposit: "Zenodo"
```

Or set the `ARTICLE_SCAFFOLD_CONFIG` environment variable to point to a
different file. The config is read by the `pre_gen_project.py` hook and
applied to `metadata.yaml` by `post_gen_project.py`. **The config file is
never copied into the generated repository.**

## Quick start (local cookiecutter)

```bash
# One-time install
pip install cookiecutter

# Scaffold a new article repo
cookiecutter /path/to/article-scaffold

# Or, from this directory:
cookiecutter .
```

Cookiecutter will prompt for:

| Prompt             | Default                              | Notes                                            |
| ------------------ | ------------------------------------ | ------------------------------------------------ |
| `topic`            | `subject_slug`                      | Short slug; becomes the suffix of `repo_name`.   |
| `repo_name`        | `articles.<topic>`                   | Conforms to the existing repo naming pattern.    |
| `github_user`      | `your-github-user`                   | Used in repo URL and README badge.               |
| `title`            | `Untitled Manuscript`                | Full manuscript title.                           |
| `subtitle`         | *(empty)*                            | Optional subtitle.                                |
| `manuscript_type`  | `Perspective / Review Essay`         | Free-text label in README.                        |
| `author_name`      | `Your Name`                         | Full name; family/given split is auto-derived.   |
| `author_orcid`     | *(empty)*                           | Optional ORCID, no URL prefix.                   |
| `author_affiliation` | `Your Affiliation`           | Free-text affiliation.                           |
| `version`          | `1.0.0`                              | Semver-ish; goes in CITATION.cff + .zenodo.json. |
| `version_label`    | `v1 preprint`                        | Human label; shown in article.tex \date{}.       |
| `date`             | `YYYY-MM-DD`                         | Filled with today's date by post_gen hook.       |
| `license`          | `CC-BY-4.0`                          | SPDX-style.                                       |
| `target_deposit`   | `Zenodo`                             | Free-text; appears in README + backmatter.       |
| `doi`              | *(empty)*                            | Leave empty pre-deposit; fill after deposit.     |
| `default_branch`   | `main`                               | Git default branch (`main` or `master`).         |
| `keywords`         | `your, keywords`                     | Comma-separated.                                 |
| `abstract`         | *(placeholder text)*                 | Full abstract; goes in 00_abstract.tex + README. |

After the prompts, cookiecutter creates a new directory named after
`repo_name`, runs the `post_gen_project.py` hook (which initialises git,
installs the pre-push hook, fills in the date, applies user config, and
prints next steps), and exits.

## What you get

The scaffolded repo has this shape (after cookiecutter rendering):

```
articles.<topic>/
├── README.md                  # abstract + build instructions + bibtex citation
├── LICENSE                    # CC-BY-4.0 (or chosen license)
├── CITATION.cff               # citation metadata (derived from metadata.yaml)
├── .zenodo.json               # Zenodo deposit metadata (derived from metadata.yaml)
├── metadata.yaml              # SINGLE SOURCE OF TRUTH for metadata
├── .gitignore
├── Makefile                   # pdf / docx / validate / metadata / clean / analysis
├── CHANGES.md                 # version history template
├── .github/
│   └── workflows/
│       ├── build-artifacts.yml    # build PDF + DOCX on push to paper/**
│       ├── release.yml           # build + publish on v* tags
│       └── validate-latex.yml    # lint: \input resolves, \cite keys, braces
├── paper/
│   ├── article.tex            # main LaTeX doc; title block is metadata-driven
│   ├── refs.bib               # BibTeX (placeholder entries)
│   ├── Makefile               # direct paper/ build
│   ├── .latexmkrc             # latexmk config: outdir=build, reproducible
│   ├── sections/
│   │   ├── 00_abstract.tex
│   │   ├── 01_introduction.tex
│   │   ├── 02_methods.tex           # optional; uncomment \input in article.tex
│   │   ├── 03_results.tex          # optional
│   │   ├── 04_discussion.tex       # optional
│   │   ├── 05_conclusion.tex
│   │   ├── 08_backmatter.tex       # COI / Data / AI-use / Version statements
│   │   └── 09_references.tex
│   ├── figures/               # tracked; referenced via \includegraphics
│   ├── tables/                # generated tables from make analysis
│   └── supplementary/          # tracked; standalone *.tex here build to their own PDFs (make supp-pdf)
├── data/
│   ├── raw/observations.csv   # fixture data for empirical analysis
│   └── checksums.sha256       # input checksums for reproducibility
├── analysis/
│   ├── analyze.py             # stdlib-only pipeline: CSV → table + figure
│   ├── pyproject.toml         # optional heavy deps (pandas, matplotlib, numpy)
│   └── uv.lock                # lockfile for optional deps
└── scripts/
    ├── article/               # vendored core library + JSON-first CLI
    │   ├── cli.py             # python3 -m scripts.article
    │   ├── validate.py        # shared validation logic
    │   ├── metadata.py        # shared metadata generation
    │   └── ...
    ├── generate-metadata.py   # deprecated shim; delegates to scripts.article
    ├── validate-paper.py      # deprecated shim; delegates to scripts.article
    └── pre-push               # hook source; `make hooks` installs it
```

## Design rationale

This template extracts and codifies the canonical structure of a real
article repository. See `canonical-pattern.md` (sibling
file) for the full analysis of that structure and the rationale for each
choice.

Highlights:
- **Single source of truth for metadata.** `metadata.yaml` → CITATION.cff,
  .zenodo.json, README citation block, article.tex title block. Change
  one file, not four.
- **Section decomposition.** Each section is a `NN_name.tex` file; the
  numbered prefix keeps ordering stable across renames. Methods/results/
  discussion are scaffolded but commented out — uncomment what you need.
- **CI separation.** Three workflows: validate (lint), build (continuous),
  release (tag-driven). The validate workflow mirrors `make validate`
  locally so the pre-push hook catches the same errors before you push.
- **Tracked figures + supplementary directories.** `paper/figures/`
  (for source artwork) and `paper/supplementary/` (for appendices and
  extended data), both tracked.
- **Pre-push hook.** Installs the same `make validate` checks as the CI
  validate workflow, so errors are caught locally before the CI round-trip.
- **Empirical analysis pipeline.** `data/`, `analysis/`, `make analysis`
  for reproducible CSV → LaTeX table + PDF figure generation. Outputs go
  to `paper/tables/` and `paper/figures/` and are included conditionally.

## License of the template itself

The template files in this directory are released under the same license
as the project they scaffold (CC-BY-4.0 by default). The Cookiecutter
machinery (`cookiecutter.json`, `hooks/`) is generic and may be reused
under any permissive license.