# Canonical article-repo pattern

This document analyses the structure of a real article repository and
extracts the canonical pattern it implicitly follows. It then describes the
companion `article-scaffold/` cookiecutter template, which bootstraps new
article repos following the same pattern with three extensions: a single
metadata source of truth, tracked `figures/` and `supplementary/`
directories, and a local pre-push hook mirroring CI.

The goal is to turn an ad-hoc structure that happens to work well into an
explicit, reproducible scaffold so that the next article repo takes five
minutes to bootstrap rather than five hours of cut-and-paste from the
previous repo with stale metadata.

---

## 1. What the current repo does well

The repository is the working source of a single perspective / review essay
titled *"From AI Scaling to AI Governance: Technological Revolutions and the
Political Economy of Deployment."* It is structured so that a reader, a
co-author, or a future-self reviewer can clone the repo, run `make pdf`, and
produce a byte-identical PDF to the one published as a preprint. The
structure follows a small number of conventions that, taken together, make
the repo usable as a template without further work.

### 1.1 Repository naming and scope

The repo is named `articles.ai_governance`. The `articles.` prefix is a
namespace; the suffix is the topic slug. This convention has three useful
properties. It groups all article repos together when sorted
alphabetically in a GitHub user's repo list. It disambiguates article repos
from code repos, talks, or other writing projects that might share a topic
slug. And it makes the repo self-describing — the name is enough to know
what kind of repo it is and what it is about. The scaffold keeps this
convention as the default `repo_name` (`articles.<topic>`), but it is over
ridable per-repo.

### 1.2 Section decomposition under `paper/sections/`

The manuscript body is split into per-section files under
`paper/sections/`, named with a two-digit numerical prefix and a short
slug: `00_abstract.tex`, `01_introduction.tex`, `02_perez.tex`,
`03_empirical.tex`, `03b_gradient.tex`, `04_institutional.tex`,
`05_framework.tex`, `06_historical.tex`, `07_conclusion.tex`,
`08_backmatter.tex`, `09_references.tex`. The numerical prefix keeps the
section ordering stable in `ls` output even when sections are renamed, and
the slug makes the file's purpose obvious. The `03b_gradient.tex` file
demonstrates a useful idiom: a `b` suffix inserts a sub-section between
`03` and `04` without renumbering the rest. The main `article.tex` is a
thin shim that loads the preamble and `\input`s each section in order; the
body text never lives in `article.tex` itself.

### 1.3 Two-tier Makefile

There are two Makefiles: the root `Makefile` orchestrates the whole repo;
`paper/Makefile` is a paper-internal convenience for working inside
`paper/`. The root Makefile's targets are `pdf`, `docx`, `quick`, `clean`,
and the implicit `all` (which delegates to `pdf`). The `pdf` target uses
`latexmk` rather than the raw `pdflatex → bibtex → pdflatex → pdflatex`
sequence, which is what `paper/Makefile` does manually. Both approaches
work; `latexmk` is the more modern choice and handles the bibtex
re-runs automatically. The scaffold keeps both Makefiles and adds two
more targets: `validate` (a local mirror of the CI's lint checks) and
`metadata` (regenerates derived metadata from `metadata.yaml`).

### 1.4 Layered GitHub Actions: validate / build / release

The repo has three workflows, each with a single, well-bounded
responsibility:

- **`validate-latex.yml`** runs on every push and pull request that
  touches `paper/**` or the workflow file itself. It is a lint pass — it
  never compiles. It checks that every `\input{...}` in `article.tex`
  resolves to a file under `paper/`, that every `\cite{...}` key in
  `sections/*.tex` is defined in `refs.bib`, and that braces in
  `article.tex` are balanced. The point is to fail fast on cheap
  syntactic errors before the more expensive PDF build runs.

- **`build-artifacts.yml`** runs on push to `master` (when `paper/**` is
  touched), on pull requests, and on manual dispatch. It builds the PDF
  via `xu-cheng/texlive-action@v2` (a Docker action that wraps a full TeX
  Live distribution) and the DOCX via the official `pandoc/latex:3.1`
  Docker image. Both jobs upload their outputs as GitHub artifacts with
  a 7-day retention. The workflow uses `concurrency: cancel-in-progress:
  true` so that a new push to the same branch cancels the in-flight build.

- **`release.yml`** runs only on `v*` tags. It reuses the same build steps
  as `build-artifacts.yml` to produce `manuscript.pdf` and
  `manuscript.docx`, then uses `softprops/action-gh-release@v2` to attach
  them to a GitHub release named after the tag. The
  `cancel-in-progress: false` setting here is deliberate — a release
  should never be cancelled mid-flight.

This three-way split keeps the validate cycle short (about 30 seconds),
the build cycle medium (about 2 minutes), and the release cycle
deliberate (only on explicit tags). The scaffold preserves this split
exactly. One small fix: the original `validate-latex.yml` has a
`re.sub(...)` call wrapped in `if "re" in dir() else content` *before*
`import re`, which is dead code — the conditional always evaluates the
false branch because `re` is not yet in `dir()`. The scaffold version
imports `re` first and also properly handles escaped `\%` when stripping
comments before the brace-count check.

### 1.5 Tag-driven releases

Releases are tied to `v*` tags, not to commits. This is the right
convention because a release is an editorial decision (the author decides
"this is v3"), not a build decision. The release workflow uses
`generate_release_notes: true`, so the release body is auto-generated from
commits since the last tag — there is no separate release-notes file to
keep in sync. The CHANGES.md file mirrors the same history in a more
curated form, with explicit (a), (b), (c)-style entries that read like a
reviewer-facing note rather than a commit log.

### 1.6 Standardised backmatter

The `08_backmatter.tex` file carries four sections that are conventional
for preprints in the social sciences and policy-research fields:
*Use of AI Assistance*, *Conflicts of Interest*, *Data Availability*, and
*Version Statement*. Each is short, declarative, and structured so that
the same wording can be carried forward across article repos with only
the specifics changed. The COI section enumerates the firms and
regulators discussed in the body, which is a useful practice — it forces
the author to consider each named entity rather than write a generic
"no conflicts" statement. The Version Statement mirrors the
corresponding `CHANGES.md` entry, which is duplication but a useful one:
the PDF reader sees the version history without leaving the document,
and the repo reader sees it in a more git-friendly form.

### 1.7 Citability infrastructure: `CITATION.cff` + `.zenodo.json` + README bibtex

The repo carries three citation artefacts that all encode overlapping
information. `CITATION.cff` is the GitHub-native citation format; GitHub
renders a "Cite this repository" button from it. `.zenodo.json` carries
the metadata that Zenodo uses when the repo is deposited as a preprint.
The README contains a `@misc{...}` bibtex block for readers who want to
copy a citation directly. All three encode the same author, title,
version, date, license, and DOI. This is the most obvious duplication in
the repo, and the scaffold addresses it by introducing `metadata.yaml`
as a single source of truth (see §3.1).

### 1.8 `.gitignore` discipline

The `.gitignore` ignores LaTeX build artifacts (`*.aux`, `*.bbl`,
`*.log`, etc.) scoped to `paper/` so that the build outputs do not
pollute the repo. It also ignores `manuscript.docx` and `manuscript.pdf`
at the top level — these are CI outputs and should not be committed. The
scaffold extends this with entries for Python `__pycache__/` (since the
scaffold adds Python scripts) and explicitly does NOT ignore
`paper/figures/*.pdf` or `paper/supplementary/*.pdf` — those are source
artwork, not build outputs, and must be tracked.

---

## 2. Issues and improvement opportunities

The current repo is solid. The following issues are small but worth
fixing in the canonical version. None are blockers; most are "nice to
have" that the scaffold addresses.

### 2.1 Metadata duplication

The most significant issue is the duplication of author / title /
version / date / license / DOI across `CITATION.cff`, `.zenodo.json`,
and the README bibtex block. When the version bumps from v3 to v4, four
places need to be updated (including the LaTeX `\date{}` field in
`article.tex`). The scaffold introduces `metadata.yaml` as a single
source of truth and a `scripts/generate-metadata.py` script that
regenerates the four derived artefacts. Editing one file is easier than
editing four, and the consistency is enforced by construction.

### 2.2 The brace-check bug in `validate-latex.yml`

The original `validate-latex.yml` contains this snippet in the
`Sanity check balanced braces` step:

```python
stripped = re.sub(r"(?m)%.*$", "", content) if "re" in dir() else content
import re
stripped = re.sub(r"(?m)%.*$", "", content)
```

The first `re.sub` is dead code because `re` is not yet imported at the
point of the conditional, so the `else` branch (`content`) is always
taken. The second `re.sub` does the actual work. The bug does not affect
correctness because the second call works, but it is confusing to read
and would be a foot-gun if someone "cleaned up" by removing the second
call. The scaffold version imports `re` once at the top and uses a
single `re.sub` call. It also uses `(?<!\\)%` to correctly handle
escaped `\%` (which is a literal percent in LaTeX, not a comment) when
stripping comments before the brace count.

### 2.3 No local pre-push hook

The repo has `validate-latex.yml` for CI but no equivalent local
command. A push that fails validation in CI takes ~5 minutes to
discover and requires the author to switch contexts. The scaffold adds
a pre-push git hook (installed automatically by the cookiecutter
`post_gen_project.py` hook) that runs the same checks via
`make validate` in about one second. The hook is bypassable with
`git push --no-verify` for emergencies.

### 2.4 No `figures/` or `supplementary/` directories

The repo has no dedicated directories for source figures or
supplementary materials. A figure PDF placed in `paper/` top-level would
be ignored by `.gitignore` (because `paper/*.pdf` is ignored, since
`paper/article.pdf` is a build output). The scaffold adds two
explicitly tracked directories: `paper/figures/` (with a placeholder
README explaining conventions) and `paper/supplementary/` (with a
placeholder README explaining what belongs there). The preamble in
`article.tex` sets `\graphicspath{ {figures/} }` so that
`\includegraphics{example}` resolves to `paper/figures/example.pdf`
without a path prefix.

### 2.5 No mention of the `\input`-target convention in CI failure messages

The `validate-latex.yml` workflow prints `::error::\input{...} does not
resolve to a file` when a target is missing. This is good. The scaffold
version also prints `OK: \input{...}` for each target that does resolve,
which makes the failure message more readable when one of N targets
fails — the reader can see which ones are healthy. The scaffold also
skips commented-out `\input` lines, so a section that is intentionally
disabled (e.g. `% \input{sections/02_methods}`) does not fail
validation. The original did not skip commented-out `\input` lines,
which would cause a false positive when a section was temporarily
disabled.

### 2.6 No DOI badge in README

The README has a bibtex citation block but no shields.io-style badge
showing the DOI, license, or Zenodo deposit. This is a cosmetic
enhancement the scaffold does not add by default (to keep the README
clean), but it is easy to add later by inserting a `![DOI](https://img.shields.io/doi/...)`
line in the README.

---

## 3. The canonical structure

Combining the conventions from §1 with the fixes from §2, the canonical
article repo has this shape:

```
articles.<topic>/
├── README.md                  # abstract + build instructions + bibtex citation
├── LICENSE                    # CC-BY-4.0 (or chosen license)
├── CITATION.cff               # citation metadata (derived from metadata.yaml)
├── .zenodo.json               # Zenodo deposit metadata (derived from metadata.yaml)
├── metadata.yaml              # SINGLE SOURCE OF TRUTH for metadata
├── .gitignore
├── Makefile                   # pdf / docx / validate / metadata / clean
├── CHANGES.md                 # version history
├── .github/
│   └── workflows/
│       ├── build-artifacts.yml    # build PDF + DOCX on push to paper/**
│       ├── release.yml           # build + publish on v* tags
│       └── validate-latex.yml    # lint: \input resolves, \cite keys, braces
├── paper/
│   ├── article.tex            # main LaTeX doc; title block is metadata-driven
│   ├── refs.bib               # BibTeX bibliography
│   ├── Makefile               # direct paper/ build
│   ├── sections/
│   │   ├── 00_abstract.tex
│   │   ├── 01_introduction.tex
│   │   ├── 02_methods.tex          # optional; uncomment \input in article.tex
│   │   ├── 03_results.tex          # optional
│   │   ├── 04_discussion.tex       # optional
│   │   ├── 05_conclusion.tex
│   │   ├── 08_backmatter.tex       # COI / Data / AI-use / Version statements
│   │   └── 09_references.tex
│   ├── figures/               # tracked; referenced via \includegraphics
│   └── supplementary/          # tracked; appendices, extended tables, code
└── scripts/
    ├── generate-metadata.py   # metadata.yaml → CITATION.cff / .zenodo.json / article.tex title / README citation
    ├── validate-paper.py      # local mirror of validate-latex.yml
    └── pre-push               # installed by cookiecutter into .git/hooks/
```

### 3.1 Single source of truth: `metadata.yaml`

The `metadata.yaml` file at the repo root is the canonical source for
title, subtitle, author (name + ORCID + affiliation), version, version
label, date, license, target deposit, DOI, repo coordinates
(`github_user`, `repo_name`), keywords, description, references, and
Zenodo communities. The `scripts/generate-metadata.py` script reads
`metadata.yaml` and writes:

- `CITATION.cff` (full rewrite — generated from scratch each run)
- `.zenodo.json` (full rewrite — generated from scratch each run)
- the `METADATA:TITLE_BLOCK:START ... :END` block in `paper/article.tex`
  (idempotent block replacement; prose outside the block is preserved)
- the `BIBTEX:CITATION:START ... :END` block in `README.md`
  (idempotent block replacement; prose outside the block is preserved)

The two block-replacement edits are gated by sentinel comments so
that `make metadata` is safe to re-run after manual prose edits. The
script uses a lambda replacement (`re.sub(..., lambda m: new_block, text)`)
rather than a string replacement to avoid regex escape interpretation of
LaTeX backslashes (`\Large`, `\textbf`, etc.) in the replacement text.

The script is idempotent: running it twice in a row with the same
`metadata.yaml` produces byte-identical output. The cookiecutter
template is structured so that the initial render produces the same
output as a first `make metadata` run — verified by md5sum comparison
of all four derived files before and after the first run.

### 3.2 Section decomposition

Each section is a file under `paper/sections/` named `NN_slug.tex`
where `NN` is a two-digit number that establishes ordering and `slug`
is a short lowercase name. The numerical prefix means renaming a
section (e.g. `03_empirical` → `03_evidence`) does not require
re-ordering the `\input` list in `article.tex`. Inserting a new
section between `03` and `04` is done with a `b` suffix
(e.g. `03b_gradient.tex`) — the original repo uses this idiom. The
scaffold includes the conventional set of sections for a research
article (abstract, introduction, methods, results, discussion,
conclusion, backmatter, references); the methods, results, and
discussion sections are scaffolded but commented out in `article.tex`,
so a perspective / review essay (which has none of those) can be written
without un-scaffolding, and a research article can enable them by
uncommenting the corresponding `\input{...}` lines.

### 3.3 Layered build and CI

The root `Makefile` exposes five targets: `pdf`, `docx`, `quick`,
`validate`, `metadata`, and `clean` (plus the implicit `all` which
delegates to `pdf`). The `validate` target runs the same Python checks
as `.github/workflows/validate-latex.yml` locally, so the pre-push hook
catches the same errors as CI. The `metadata` target regenerates the
derived metadata files. The build targets (`pdf`, `docx`, `quick`) are
unchanged from the original repo.

CI is split into three workflows as in §1.4, with one cosmetic
improvement: the validate workflow prints `OK: \input{...}` for each
resolved target and skips commented-out `\input` lines (the original
did not, which would produce false positives when a section was
temporarily disabled). The build workflow and release workflow are
unchanged.

### 3.4 Tracked `figures/` and `supplementary/` directories

The `paper/figures/` directory holds source artwork. The `article.tex`
preamble sets `\graphicspath{ {figures/} }` so that
`\includegraphics{example_figure}` resolves to
`paper/figures/example_figure.pdf`. Figures are tracked in git (not
ignored); the `.gitignore` rule `paper/*.pdf` matches only the
top-level `paper/` directory, not subdirectories. The placeholder README
in `paper/figures/` documents the conventions: prefer vector PDFs, use
self-contained filenames, keep captions in LaTeX not in the figure
file, commit both the generation script and the rendered PDF.

The `paper/supplementary/` directory holds appendices, extended data
tables, code snippets, and source datasets. The placeholder README
explains the conventions: each file gets a short header explaining its
relationship to the main text, supplementary files are tracked (not
ignored), and regeneration scripts are committed alongside their
outputs.

### 3.5 Pre-push hook

The cookiecutter `post_gen_project.py` hook (which runs automatically
after the template is rendered) does three things. It makes the scripts
in `scripts/` executable. It initialises a git repository with the
`master` branch (matching the original repo's default branch) if one
does not already exist. And it installs `scripts/pre-push` into
`.git/hooks/pre-push` and makes it executable. The hook script itself
resolves the repo root via `git rev-parse --show-toplevel`, runs
`make validate`, and exits non-zero if validation fails. The hook is
bypassable with `git push --no-verify` for emergencies. It also degrades
gracefully: if `make` or `python3` is not on PATH, it prints a warning
and exits 0 rather than blocking the push.

### 3.6 Defaults

The scaffold defaults are neutral placeholders: license is CC-BY-4.0, the
author name and ORCID are left for the user to fill in (an ORCID is
optional), and the affiliation defaults to *Independent Researcher*. The
default branch is `master`, and the repo naming convention is
`articles.<topic>`. Every default is overridable at the cookiecutter
prompt; the user is free to change the author, ORCID, license, or
repo name on a per-repo basis without modifying the template.

---

## 4. Using the scaffold

### 4.1 Prerequisites

The cookiecutter template requires `cookiecutter` and `jinja2-time`:

```bash
pip install cookiecutter jinja2-time
```

The generated repo requires a LaTeX distribution (TeX Live, MiKTeX, or
MacTeX) for PDF builds, `pandoc` for DOCX builds, and Python 3.10+ for
`make metadata` and `make validate`. `pandoc` is only needed for the
DOCX target; the PDF target works without it.

### 4.2 Bootstrapping a new article repo

```bash
cookiecutter /path/to/article-scaffold
```

Cookiecutter prompts for the topic, title, author, ORCID, version,
license, and a handful of other fields (see the template's own
`README.md` for the full list). After the prompts, it creates a new
directory named after `repo_name`, runs the `post_gen_project.py` hook
(which initialises git, installs the pre-push hook, and prints next
steps), and exits. The user then edits `metadata.yaml` to refine any
fields, runs `make metadata` to regenerate the derived artefacts, opens
`paper/sections/00_abstract.tex` to start writing, runs `make validate`
locally (or relies on the pre-push hook), and runs `make pdf` to build.

### 4.3 The first commit

```bash
cd articles.<topic>
git add .
git commit -m "initial scaffold"
git branch -M master
git remote add origin git@github.com:<user>/articles.<topic>.git
git push -u origin master
```

### 4.4 Cutting a release

When the manuscript is ready for a preprint deposit:

1. Bump the version in `metadata.yaml` (e.g. `version: "1.0.0"` →
   `version: "1.1.0"` and `version_label: "v1 preprint"` →
   `"v1.1 preprint"`).
2. Add a `CHANGES.md` entry under a new `## v1.1 - <date>` heading.
3. Update the Version Statement in `paper/sections/08_backmatter.tex`
   (manually, since this is editorial prose not derived metadata).
4. Run `make metadata` to regenerate `CITATION.cff`, `.zenodo.json`,
   the README citation block, and the title block in `article.tex`.
5. Run `make pdf` and `make docx` to verify the build.
6. Commit the changes.
7. Deposit on Zenodo; copy the DOI back into `metadata.yaml` and
   re-run `make metadata` so the DOI flows into the citation block.
8. Commit the DOI update.
9. Tag the release: `git tag v1.1.0 && git push origin v1.1.0`. The
   `release.yml` workflow runs automatically and attaches the PDF
   and DOCX to a GitHub release named `v1.1.0`.

### 4.5 Idempotency

`make metadata` is idempotent. Running it twice in a row produces
byte-identical output. The cookiecutter initial render and the first
`make metadata` run also produce byte-identical output, verified by
md5sum comparison of `CITATION.cff`, `.zenodo.json`, `paper/article.tex`,
and `README.md`. This means the user can run `make metadata`
immediately after scaffolding without producing a spurious diff —
the diff is empty.

`make validate` is also idempotent — it does not modify any files. The
pre-push hook runs `make validate` and blocks the push if any check
fails. The same checks run in `.github/workflows/validate-latex.yml` on
push and pull request, so a push that passes the local hook also
passes the CI.

---

## 5. What the scaffold does NOT do

The scaffold is deliberately minimal. It does not:

- **Provide a bibliography manager.** The user is expected to maintain
  `paper/refs.bib` by hand or via a reference manager (Zotero, BibDesk,
  etc.). The validate workflow catches missing citation keys; it does
  not check for malformed BibTeX entries.
- **Provide a LaTeX class file.** The scaffold uses the standard
  `article` class with a small preamble of common packages. A journal
  submission that requires a specific class file (e.g. `elsarticle`,
  `revtex4-1`) should replace the `\documentclass{article}` line and
  adjust the preamble as needed.
- **Provide a `pre-commit` framework configuration.** The user wanted
  a pre-push hook specifically (not the `pre-commit` Python tool), so
  the scaffold uses a single git hook installed by cookiecutter. If
  the user later adopts `pre-commit`, they can add a
  `.pre-commit-config.yaml` that runs `make validate` as a hook; the
  existing pre-push hook can be removed in favour of `pre-commit`'s
  pre-push hook management.
- **Provide a Zenodo deposition action.** Zenodo deposition is a
  manual step (see §4.4 step 7). Automating it would require a Zenodo
  access token in GitHub secrets and a workflow that calls the Zenodo
  API; that is a useful enhancement but out of scope for the
  scaffold's first version.
- **Provide a multi-author workflow.** The scaffold defaults to a
  single author. Multiple authors are supported by editing
  `metadata.yaml` (which currently has a single `author:` block) and
  the LaTeX `\author{...}` field manually after running
  `make metadata`. A future enhancement could extend `metadata.yaml`
  to accept a list of authors and have `generate-metadata.py` produce
  the corresponding `\author{...}` and `creators: [...]` fields.

---

## 6. Summary

The canonical article-repo pattern extracted from the source article
repository has six load-bearing conventions:

1. **Repository naming** as `articles.<topic>` for sortability and
   self-description.
2. **Section decomposition** under `paper/sections/NN_slug.tex` for
   stable ordering across renames.
3. **Two-tier Makefile** (root orchestrates; `paper/Makefile` for
   paper-internal builds).
4. **Layered CI**: validate (lint) / build (continuous) / release
   (tag-driven), with non-overlapping triggers.
5. **Standardised backmatter**: AI-use, COI, Data Availability, Version
   Statement as four short sections in `08_backmatter.tex`.
6. **Citability infrastructure**: `CITATION.cff` + `.zenodo.json` +
   README bibtex, all derived from a single `metadata.yaml`.

The cookiecutter template in `article-scaffold/` implements this
pattern with three extensions: tracked `figures/` and `supplementary/`
directories, and a local pre-push hook mirroring the CI validate step.
The template is idempotent (cookiecutter render equals post-`make
metadata` state) and tested end-to-end: `cookiecutter` → `make
metadata` → `make validate` → `make pdf` all pass on a clean
render.

To bootstrap a new article repo:

```bash
pip install cookiecutter jinja2-time
cookiecutter /path/to/article-scaffold
```
