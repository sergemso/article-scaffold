# article-scaffold — improvement plan

Status: accepted 2026-10-21; executable tasks in `plan/tasks.json`
Owner: Sergei
Last updated: 2026-10-21

> **Decisions settled 2026-10-21.** The answers to §10 are recorded in
> [`plan/decisions.md`](./plan/decisions.md). Where this document conflicts
> with that file or `plan/tasks.json`, the plan wins. Key changes: empirical
> is core, the v2 break has **no automated migration tool**, the license
> matrix is **CC-BY-4.0 + MIT**, and journal classes remain parked.

This plan consolidates the review findings (correctness bugs, SSOT leaks, CI
and DX gaps) with the proposed core/CLI/MCP architecture. It is ordered by
risk-reduction first, ergonomics second, extensions last. Each phase has a
gate and a definition of done; phases 1–2 are the only ones I would call
urgent.

---

## 1. Goals and constraints

Goals:

1. A generated repo must survive realistic input: titles with `&`, `%`, `_`,
   quotes, colons, unicode; abstracts with `%`/`R&D`/`#`; names like
   `Doe, Jane`, mononyms, multiple authors.
2. `metadata.yaml` must actually be the single source of truth for every
   derived artifact, including PDF metadata, README header, CHANGES and the
   Version Statement.
3. `make validate` and CI must run the same code, and that code must have
   both no false positives and few false negatives.
4. A fresh clone must be able to build with TeX + Python only. No service,
   no MCP server, no network in the critical path.
5. The template itself must be tested: render matrix, schema validation,
   build, idempotency.
6. Optional agent integration (MCP) must be an adapter, never the substrate.

Constraints:

- Keep generated repos self-contained and archival: vendored scripts,
  stdlib + PyYAML at runtime, no PyPI package required to build in 2030.
- Keep `make pdf` / `make validate` / `make metadata` working. Existing
  generated repos (e.g. `articles.ai_governance`) must not be forced to
  migrate.
- No MCP in CI, pre-push, or Make. MCP is opt-in and read-only by default.
- Template changes are semver'd and stamped into every generated repo.

---

## 2. Architecture decisions

### ADR-001 — Core library is canonical; CLI and MCP are adapters

The workflow logic lives in a plain Python package with pure functions. The
human CLI, the Makefile, the pre-push hook, CI and the MCP server all call
that package. The CLI is **not** backed by an MCP server, and the MCP server
contains no business logic.

```
                 ┌──────────────────────┐
                 │  scripts/article/    │  core.py (pure), schema.py
                 │  core library        │  no printing, no I/O side effects
                 └───────┬──────────────┘
             ┌───────────┼─────────────┬────────────────┐
             ▼           ▼             ▼                ▼
        cli.py       Makefile      pre-push / CI     mcp adapter
        (--json)     (wraps CLI)   (calls CLI)       (calls CLI --json
                                                      or imports core)
```

Rule: `mcp → core` or `mcp → cli --json`, never `cli → mcp`.

### ADR-002 — Stable JSON contract

Every command has a `--json` mode and a documented schema:

- `schemas/diagnostics.schema.json`
- `schemas/status.schema.json`
- `schemas/release-plan.schema.json`

Exit codes: `0` success, `1` diagnostics/failure, `2` usage error,
`3` internal error. Schemas are versioned with the template. This contract is
what lets CLI, CI, and MCP stay in sync, and it is tested by parity fixtures.

### ADR-003 — Metadata schema v1.1 → v2.0

- v1.1 (non-breaking): add optional `abstract`, keep `description` as an
  alias, generate more sentinel blocks.
- v2.0 (breaking): replace `author:` with `authors:` + `affiliations:`,
  add `license`/`code_license`, `manuscript_kind`, `citation_style`,
  `default_branch`, `publication_type`.
- The v2 break is accepted, but there is **no** automated migration tool:
  `docs/migrating-to-v2.md` gives a tested manual mapping and backup steps.

Backward compatibility: the loader accepts both `author:` (mapping) and
`authors:` (list) for the whole v2 line; deprecation warning for one minor
release, then removal at v3.

### ADR-004 — MCP is optional, separate, and gated

- Lives in the **template repo** (`mcp/`), not generated into article repos.
- Shells out to the target repo's own `python3 -m scripts.article ... --json`,
  so it works across template versions without importing repo code.
- Read-only tools first. Mutating tools require a plan id + confirmation.
- Never a CI dependency; pinned; documented as "optional agent adapter".

Rationale: the template's value is a self-contained repo. A per-repo MCP
server adds a dependency, a process, a security surface and protocol churn to
repos that mostly need `make`.

---

## 3. Target layout (template repo)

```
article-scaffold/
├── cookiecutter.json                  # + choices, __prompts__, template_version
├── hooks/
│   ├── pre_gen_project.py             # input validation
│   └── post_gen_project.py            # git init, generate metadata, hooks
├── {{cookiecutter.repo_name}}/
│   ├── metadata.yaml
│   ├── Makefile                       # human entry points only
│   ├── scripts/
│   │   ├── article/                   # vendored core + CLI
│   │   │   ├── __init__.py
│   │   │   ├── core.py
│   │   │   ├── cli.py
│   │   │   ├── metadata.py
│   │   │   ├── validate.py
│   │   │   ├── build.py
│   │   │   ├── release.py
│   │   │   └── __main__.py
│   │   ├── validate-paper.py          # thin deprecated shim
│   │   ├── generate-metadata.py       # thin deprecated shim
│   │   └── pre-push
│   ├── schemas/                       # JSON schemas for --json output
│   ├── tests/                         # core unit tests + fixtures
│   └── .mcp.json                      # opt-in only
├── mcp/
│   ├── server.py                      # optional adapter (template repo only)
│   └── README.md
├── tests/                             # cookiecutter render matrix, template tests
├── pyproject.toml                     # dev deps + ruff/pytest config
└── .github/workflows/test-template.yml
```

Inside a generated repo, `scripts/article/` is the only implementation;
`validate-paper.py` and `generate-metadata.py` remain as shims so existing
Makefiles, hooks and docs keep working.

---

## 4. Phases

Effort is in focused days, for one person, including tests but excluding
review latency.

### Phase 0 — Safety net (0.5–1 day)

Goal: make it possible to change behavior without guessing.

- [ ] Add `pyproject.toml` with dev deps: `pytest`, `cookiecutter`,
      `pyyaml`, `cffconvert`, `jsonschema`, `ruff`.
- [ ] Add `tests/conftest.py` with a helper that renders the template via
      the cookiecutter API with an explicit context (`--no-input` semantics),
      into a tmp path.
- [ ] Add `make test` (pytest) and `make lint` (ruff + shellcheck +
      yamllint + markdownlint if available).
- [ ] Add `.github/workflows/test-template.yml`: lint, unit tests, render
      default context, `make validate`. PDF build can start as a
      non-blocking job.
- [ ] Add `template_version` to `cookiecutter.json` and `metadata.yaml`.
- [ ] Decide Python floor (recommend 3.10+, matching README).
- [ ] Add `.gitattributes` (`* text=auto eol=lf`, `*.pdf binary`,
      `*.docx binary`) and `.editorconfig`.
- [ ] Add `tests/fixtures/` with one broken and one clean mini-repo for the
      validator.

Gate: CI is green on the current template, and `make test` reproduces the
current (buggy) behavior in at least one known-fail test, marked `xfail`.
Those `xfail` tests become the acceptance tests for Phase 1.

### Phase 1 — Correctness (v1.1, 2–3 days)

Goal: no realistic input can produce an unparseable metadata file or an
uncompilable PDF.

#### 1.1 Escaping and SSOT

- [ ] Use `| tojson` for every string interpolated into YAML/JSON:
      `metadata.yaml`, `.zenodo.json`, `CITATION.cff`, README (where it is
      inside a code block), `cookiecutter.json`-driven files.
- [ ] Stop interpolating free text into LaTeX at render time. Add
      `abstract:` and keep `keywords` in `metadata.yaml`; generate
      `00_abstract.tex` between `% ABSTRACT:START/END`.
- [ ] Extend `METADATA:TITLE_BLOCK` to include `\hypersetup` (or switch to
      `\hypersetup{pdfusetitle}` plus a generated `\paperKeywords`), so
      `make metadata` updates PDF metadata.
- [ ] Add sentinel blocks:
      - `README:META:START/END` (title, subtitle, type, version, date,
        license, deposit, DOI)
      - `BACKMATTER:VERSION:START/END` in `08_backmatter.tex`
      - `CHANGES:CURRENT:START/END` in `CHANGES.md`
- [ ] Fix `latex_escape` ordering (backslash must not be re-escaped) and add
      unit tests for `& % $ # _ { } \ ~ ^` and unicode.
- [ ] Add a `title_tex`/`latex: true` override for authors who want markup in
      the title; default remains escaped plain text.
- [ ] `post_gen_project.py` runs `generate-metadata.py` after rendering, so
      initial render == first `make metadata` for every context (including
      DOI set).
- [ ] Add `article metadata check` (or `generate-metadata.py --check`) that
      exits non-zero if regeneration would change files.

Acceptance:

- Render with special characters in title/subtitle/abstract/keywords/author:
  `yaml.safe_load(metadata.yaml)`, `json.load(.zenodo.json)`,
  `yaml.safe_load(CITATION.cff)` all succeed, and `latexmk` succeeds.
- Default render → `make metadata` → `git diff --exit-code` clean.
- DOI-set render → same.
- Version bump in `metadata.yaml` updates README header, CHANGES heading,
  Version Statement, `\date`, `pdftitle`, CFF, Zenodo, bibtex.

#### 1.2 Citation metadata (CFF + Zenodo)

- [ ] Generate `CITATION.cff` with `yaml.safe_dump(..., sort_keys=False,
      allow_unicode=True)` instead of f-strings.
- [ ] Root `type: software`; `preferred-citation.type: article` or
      `unpublished`; quote `version` and `date-released`; never emit empty
      `given-names`/`given`/`orcid`.
- [ ] Add `abstract`, `keywords`, `identifiers` (DOI) to CFF.
- [ ] Zenodo: `communities: []` by default; validate community ids against
      `https://zenodo.org/api/communities/<id>` in a network-marked test.
- [ ] Map SPDX license ids to Zenodo vocabulary ids (`CC-BY-4.0` →
      `cc-by-4.0`, `CC0-1.0` → `cc0-1.0`, `MIT` → `mit`).
- [ ] Omit `orcid` when empty; add `publication_type`, `related_identifiers`,
      optional `grants`, `contributors`.
- [ ] Add `description` vs `abstract` semantics: Zenodo uses `description`;
      LaTeX/README use `abstract`.

Acceptance:

- `cffconvert --validate` passes for all render contexts.
- `.zenodo.json` parses and its license/communities are valid (network test,
  non-blocking).
- No empty-string ORCID in output.

#### 1.3 License selection

- [ ] Make `license` a Cookiecutter **choice** variable:
      `CC-BY-4.0` (default) and `MIT`.
- [ ] Ship `licenses/` with the full text of each; copy the selected one to
      `LICENSE` (or render `{% include %}`), plus the correct README link.
- [ ] Fix the code license to `MIT`; emit `LICENSE-CODE` when the paper
      license is `CC-BY-4.0`, and a single `LICENSE` when the paper is MIT.
- [ ] Remove the hardcoded CC-BY text/link.

Acceptance: for each license choice, `LICENSE` matches the choice, README
links the right deed, and `metadata.yaml`/`CITATION.cff`/`.zenodo.json`
agree.

#### 1.4 Validator rewrite

- [ ] Move logic into `scripts/article/validate.py`, keep
      `scripts/validate-paper.py` as a shim.
- [ ] Strip comments with `(?m)` and escape awareness; skip inline
      `% \input{...}` on the same line as content.
- [ ] Support `\cite`, `\citep`, `\citet`, `\citealp`, `\autocite`,
      `\nocite`, optional args (`\cite[p.~2]{key}`), multiple keys, and
      `\nocite{*}`.
- [ ] Check `\input`, `\include`, `\subfile`, `\import`; verify targets
      resolve and stay inside `paper/`.
- [ ] Check braces in every active `.tex` (article + sections + included
      supplementary), not just `article.tex`.
- [ ] Check `\includegraphics` targets exist (respect `\graphicspath`).
- [ ] Check `\ref`/`\label`: unresolved refs fail; duplicate labels fail;
      unused labels warn.
- [ ] Check BibTeX: duplicate keys fail, malformed entries fail, unused
      entries warn (configurable), `@string`/`@comment` ignored.
- [ ] Warn on section files not `\input` anywhere (orphans).
- [ ] Add `--json` diagnostics; `--strict` promotes warnings to errors.
- [ ] Add fixtures: comments with braces, `\citep` missing key, inline
      commented input, missing figure, missing ref, duplicate label,
      duplicate bib key, orphan section.

Acceptance: every fixture fails/passes as specified; `make validate` output
is structured and the CI job is a single call to it.

#### 1.5 Hook installation and `git init`

- [ ] Fix `post_gen_project.py` to compare `git rev-parse --show-toplevel`
      with the project dir, not `--is-inside-work-tree`.
- [ ] Always create `.git` when the project dir is not itself a repo root.
- [ ] Install the hook via `git config --local core.hooksPath
      scripts/githooks` (versioned), with `.git/hooks` copy as fallback.
- [ ] Add `make hooks` for clones; document it in README.
- [ ] Handle missing `git` gracefully.

Acceptance: `cookiecutter .` from inside the template repo produces
`articles.x/.git`, and `git config --get core.hooksPath` returns
`scripts/githooks`; fresh clone + `make hooks` works.

#### 1.6 Bootstrap workflow hardening

- [ ] Pass every input through `env:` and reference `"$TITLE"` etc.; no
      `${{ inputs.* }}` inside `run:` strings that reach a shell.
- [ ] Derive `repo_name` from the rendered directory (or pass `repo_name`
      explicitly) instead of recomputing `articles.${TOPIC}`.
- [ ] Check whether the repo already exists; fail with a clear message.
- [ ] Set description/topics/homepage from metadata.
- [ ] `git push -u origin HEAD`; scrub token in a `trap`/`finally` step.
- [ ] Add `permissions: contents: read`; keep the PAT story but document a
      GitHub App as the safer alternative.
- [ ] Remove or clarify `skip_pre_push_hook` (the name/description is
      inverted).
- [ ] Keep `cancel-in-progress: false` for repo creation.

Acceptance: a workflow unit test or `act`-style dry run with a title
containing `"`, `'`, `$()`, backticks and `&` renders and pushes correctly;
no shell expansion of user data.

#### 1.7 DOCX parity

- [ ] Add `--resource-path=.:figures` to the Pandoc invocation.
- [ ] Add `--reference-doc=styles/reference.docx` (optional) and a `--csl`
      for consistent citations; document divergence from the PDF.
- [ ] Use `pandoc/core` (no TeX) for DOCX instead of `pandoc/latex`.
- [ ] Verify a figure actually appears in the DOCX (unzip and check
      `word/media/`).

Acceptance: a render with one figure produces a DOCX containing that image;
CI asserts it.

### Phase 2 — Core + CLI (v1.2, 2–3 days)

Goal: one implementation, three thin surfaces, structured output.

- [ ] Create `scripts/article/` with pure functions:
      `validate(repo)`, `sync_metadata(repo, check)`, `build(repo, target)`,
      `status(repo)`, `release_plan(repo, version, label)`.
- [ ] `cli.py` with subcommands and `--json`, `--check`, `--dry-run`,
      `--quiet`, `--no-color`; `python3 -m scripts.article`.
- [ ] Makefile targets delegate: `validate`, `metadata`, `status`, `build`,
      `release` (with `ARGS=` pass-through). Keep `make help`.
- [ ] Pre-push hook calls `make validate` (unchanged interface).
- [ ] CI validate job calls the same command.
- [ ] Add JSON schemas and emit schema-versioned output.
- [ ] Add `article status`: version, DOI, dirty files, metadata drift,
      last build artifact, tool versions (latexmk/pandoc/python).
- [ ] Keep `validate-paper.py` and `generate-metadata.py` as deprecated
      shims that print a one-line warning.
- [ ] Unit tests for core; CLI snapshot tests for `--json`; contract tests
      for exit codes.

Acceptance:

- `make validate` and CI run the same function (assert by a test that
  monkeypatches and checks the call path, or by deleting the inline copy).
- `article status --json` validates against `status.schema.json`.
- No output changes for `make metadata` on the default render.

### Phase 3 — Robustness and DX (v2.0, 3–4 days)

Goal: the template is pleasant for real authors and maintainable for you.

#### 3.1 Author and affiliation model

- [ ] `authors:` list with `given`, `family`, `name`, `orcid`, `email`,
      `affiliations: [1]`, `corresponding: true`.
- [ ] `affiliations:` list with `id`, `name`, `ror` (optional).
- [ ] LaTeX: `authblk` (or manual superscripts) + `\thanks` for
      corresponding author/email; optional `orcidlink`.
- [ ] CFF `authors`, Zenodo `creators`, README author line, and
      `\author{}` all from the same model.
- [ ] Backward-compatible loader for the old `author:` mapping.
- [ ] ORCID checksum validation in `pre_gen_project.py` and in the loader.
- [ ] Handle mononyms (`name:` only) and name particles/suffixes explicitly.

Acceptance: single-author legacy metadata, multi-author, mononym, and
particle/suffix cases all render valid CFF/Zenodo/PDF.

#### 3.2 Manuscript kind and citation style

- [ ] `manuscript_kind` choice: `perspective` (default), `empirical`,
      `review`, `theory`.
  - `perspective`/`review`: methods/results/discussion commented out
    (current behavior).
  - `empirical`: all `\input`s active, plus `amsmath`, `amssymb`,
    `mathtools`, `siunitx`, `booktabs` (already), figure example.
  - `theory`: methods/results off, `amsthm`/`cleveref` on.
- [ ] `citation_style` choice: `cite` (current), `natbib` (author-year or
      numeric), `biblatex+biber`. Adjust preamble, `09_references.tex`,
      validator, Pandoc flags (`--biblatex`/`--citeproc`).
- [ ] `__prompts__` for human-readable prompts; keep `--no-input` working.
- [ ] `pre_gen_project.py`: slug regex, semver, SPDX license, ORCID checksum,
      non-empty title/author, unknown kind/style.

Acceptance: render matrix `kind × citation_style` all validate and at least
one builds per kind; `--no-input` defaults still work.

#### 3.3 Branching

- [ ] Remove `branches: [master]` filters from workflows; rely on `paths`
      and tags. This makes the default branch name irrelevant.
- [ ] Add `default_branch` variable (default `main` for new repos) or keep
      `master` for continuity — decide before v2.0.
- [ ] Update `post_gen` and bootstrap to use `HEAD`/configured branch.

Acceptance: scaffold with `default_branch=main` and `master` both pass CI
and push.

#### 3.4 LaTeX quality

- [ ] Move `titlesec` before `hyperref`; keep `hyperref` last.
- [ ] `\hypersetup{pdfusetitle}` (or generated `\paperTitle`), `pdflang`.
- [ ] Add `csquotes`; optional `cleveref` after `hyperref`; optional
      `lineno` for review mode.
- [ ] Replace `\usepackage[utf8]{inputenc}` with a modern default, or add a
      XeLaTeX/LuaLaTeX option (`fontspec`).
- [ ] Add `\usepackage{siunitx}` only for empirical/theory kinds.
- [ ] Add `.latexmkrc` with `-halt-on-error`, `-file-line-error`, `-synctex`,
      and `-outdir=build`; update Makefile/CI to use it.
- [ ] `make clean` uses the build dir; keep `paper/` clean.

Acceptance: out-of-tree build leaves only sources in `paper/`; PDF metadata
matches `metadata.yaml`; no package-order warnings.

#### 3.5 Repo hygiene and docs

- [ ] Drop `jinja2-time`; use built-in `cookiecutter.extensions.TimeExtension`
      with `{% now 'utc', '%Y-%m-%d' %}`.
- [ ] `.gitignore`: keep `paper/figures/*.pdf` and
      `paper/supplementary/*.pdf` tracked; add `*.bcf`, `*.run.xml`,
      `*.xdv`, `build/`; reconcile the supplementary README contradiction.
- [ ] Fix README drift: add `validate-paper.py` to the tree, `latexmk` to
      prerequisites, correct the “every push” claim, make the license link
      dynamic, add a target table and troubleshooting.
- [ ] Reconcile `canonical-pattern.md` claims (CI behavior, idempotency,
      “three extensions”).
- [ ] Add `CONTRIBUTING.md` for the template (how to test a change).
- [ ] Add badges (build, DOI, license) derived from metadata.
- [ ] Neutral defaults: document `sergemso`/personal ORCID as defaults, or
      read them from `~/.cookiecutterrc`; don't ship personal data as the
      only default.

Acceptance: a new contributor can render, test and build using only README
+ CONTRIBUTING; docs match behavior.

#### 3.6 CI hardening

- [ ] Reusable `build.yml` with `workflow_call`; `build-artifacts.yml` and
      `release.yml` both call it (no duplicated build steps).
- [ ] Release guard: fail if `github.ref_name` != `v{metadata.version}`;
      run validate before build.
- [ ] `permissions: contents: read` on build/validate; `contents: write`
      only on release.
- [ ] `-halt-on-error` in CI; `actions/checkout/setup-python/upload-artifact`
      pinned by SHA; Dependabot for Actions.
- [ ] `xu-cheng/texlive-action@v3` with explicit `texlive_version`.
- [ ] Validate workflow paths include `scripts/**`, `metadata.yaml`,
      `tests/**`.
- [ ] `test-template.yml` matrix (see §5) + `make metadata` drift check.

Acceptance: one workflow owns builds; dependabot opens PRs; a version/tag
mismatch fails the release before any artifact is published.

### Phase 4 — Workflow automation (v2.1, 3–5 days)

Goal: make release and supporting documents boring.

- [ ] `article release plan` → JSON diff of files, tag, artifacts.
- [ ] `article release apply --confirm <plan-id>`: bump `metadata.yaml`,
      prepend CHANGES entry, regenerate, validate, build, commit, tag,
      push. `--dry-run` default.
- [ ] `article doi set <doi>`: validate format, update metadata, regenerate,
      optionally resolve via `doi.org`/Crossref.
- [ ] Document Zenodo's GitHub integration (enable repo → release → DOI),
      replacing the manual deposit steps where possible.
- [ ] `make diff PREV=v1.0.0` (`latexdiff`), `make arxiv` (flatten, strip
      comments, include `.bbl`, tarball), `make wordcount` (`texcount`),
      `make watch` (`latexmk -pvc`), `make spell`/`make lint`
      (`aspell`, `chktex`, `proselint`), `make figures`.
- [ ] Figure pipeline: `paper/figures/src/` + manifest + `make figures`;
      deterministic output; commit script + rendered PDF.
- [ ] Reproducible PDFs: `SOURCE_DATE_EPOCH`, `FORCE_SOURCE_DATE=1`, pinned
      TeX Live; CI test builds twice and compares hashes.
- [ ] `gitinfo2` or a generated commit hash in the PDF footer.
- [ ] Optional GitHub Pages job publishing `latest.pdf` on release.
- [ ] Supplementary build target and release-asset inclusion (opt-in).
- [ ] `make clean` removes build dir and manuscript outputs.

Acceptance: `release plan` output is reviewable; `release apply` is
re-runnable after a failure; arxiv tarball compiles standalone; two builds
with the same epoch are byte-identical.

### Phase 5 — Scientific/structural extensions (v2.2+, 5–10 days, optional)

Prioritize only what you will use.

- [ ] Empirical layout: `data/`, `analysis/` (uv or renv), `make analysis`,
      CSV→LaTeX table generation, checksums, Data Availability generated
      from a manifest.
- [ ] Journal class choice: `plain`, `elsarticle`, `revtex4-2`, `acmart`,
      `IEEEtran`, `sn-jnl`; class + bibliography style + preamble +
      submission checklist.
- [ ] Reviewer mode: `lineno`, anonymous author block (`review_mode`),
      response-to-reviewers template, cover-letter template.
- [ ] Devcontainer / Dockerfile with TeX Live + Pandoc + Python + uv.
- [ ] REUSE/SPDX headers; dual licensing (text vs code).
- [ ] Template upgrades: evaluate `cruft` vs Copier; stamp
      `template_version`; provide `docs/upgrading.md` and a migration
      command for existing repos.
- [ ] Language/typography: `babel` choice, quote styles, date formats.
- [ ] Preprint metadata extensions: arXiv/SSRN fields, `related_identifiers`,
      `grants`, `contributors`.

### Phase 6 — MCP adapter (optional, 1–2 days)

Gate: only start when you use an agent client for writing/review at least
weekly, and Phase 2 is merged (CLI + JSON contract stable).

Read-only tools first:

| Tool | Mutates | Output |
| --- | --- | --- |
| `article_status(repo)` | no | status schema |
| `article_validate(repo, strict)` | no | diagnostics schema |
| `article_metadata_check(repo)` | no | diff summary |
| `article_outline(repo)` | no | sections, word counts |
| `article_build(repo, target)` | artifacts | build result + log tail |
| `article_release_plan(repo, version, label)` | no | release plan |
| `article_metadata_sync(repo)` | yes | sync result |
| `article_release_apply(repo, plan_id, confirm)` | yes | release result |

Resources: `article://<repo>/metadata`, `article://<repo>/diagnostics`,
`article://<repo>/outline`, `article://<repo>/changelog`.

Implementation rules:

- [ ] `mcp/server.py` shells out to `python3 -m scripts.article ... --json`
      in the target repo; no business logic, no imports from the repo.
- [ ] `repo` path validated against configured roots/allowlist; default to
      the server's cwd only if explicitly allowed.
- [ ] No PATs or secrets in tool args; bootstrap/repo creation stays out of
      MCP until there is a separate, gated tool.
- [ ] Mutating tools return a plan id; `apply` requires the id and a
      `confirm: true` argument.
- [ ] Timeouts, cancellation, and progress notifications for builds.
- [ ] Pin the MCP SDK; document `uv run --with mcp ...` or a venv.
- [ ] `.mcp.json` is opt-in and not added to generated repos by default.
- [ ] Parity tests: same fixture → CLI `--json` and MCP tool output are
      identical after canonicalization.

Do not: `article_cli(command: string)` as a single generic tool; MCP in CI;
MCP as the implementation of the CLI.

---

## 5. Test and CI plan

Render matrix (cheap checks for all, build only a subset):

| Context | Checks |
| --- | --- |
| default | parse YAML/JSON/CFF, validate, metadata idempotency |
| minimal (empty subtitle/DOI, short abstract) | parse, validate |
| special chars (`& % $ # _ { } \ ~ ^ " ' :`) | parse, validate, PDF build |
| unicode (accents, CJK) | parse, validate, PDF build |
| multi-author + affiliations + ROR | CFF/Zenodo/PDF |
| mononym + particle/suffix | CFF/Zenodo |
| license variants (4) | LICENSE text, README link, metadata |
| kind × citation style | validate; one build per kind |
| DOI set | idempotency, CFF identifiers, bibtex |
| deficient metadata (empty title) | pre_gen fails clearly |

Jobs:

1. `lint`: ruff, shellcheck, yamllint, markdownlint, actionlint.
2. `unit`: pytest for `scripts/article/`, validator fixtures, CLI snapshots.
3. `render`: cookiecutter matrix (no TeX), schema validation, idempotency,
   `make validate`.
4. `build`: one or two TeX builds + DOCX with a figure; upload artifacts.
5. `schema` (network, non-blocking): cffconvert, Zenodo communities/license,
   DOI resolution.
6. `template-drift`: `make metadata && git diff --exit-code` inside the
   rendered repo.
7. `parity` (after Phase 6): CLI vs MCP JSON equality.

Local: `make test` runs 1–3; `make test-full` adds build; `make lint`.
Target: core coverage ≥ 80%; every fixed bug gets a regression fixture.

---

## 6. Compatibility and migration

- Template semver; `template_version` stamped in `metadata.yaml` and shown
  in `README`/`article status`.
- v1.1: behavior fixes only; shims preserved; existing repos can adopt
  manually or via `cruft update` once Phase 5 lands.
- v2.0: metadata schema v2 (authors/affiliations/license/kind). Ship
  `docs/migrating-to-v2.md` with a tested **manual** mapping; no automated
  migration command. Keep the old `author:` and `license` shapes readable
  through v2.x.
- Deprecation: one minor release with warnings before removal.
- MCP: independent version (0.x); it targets the CLI JSON contract, not the
  template internals, so it survives template majors.

---

## 7. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Escaping bugs (LaTeX is full of edge cases) | Central escaper + table-driven tests + one real build per context; `title_tex` escape hatch |
| Breaking existing generated repos | Semver, shims, manual migration guide, no forced upgrade |
| Template complexity grows past “five-minute bootstrap” | Keep core stdlib+PyYAML; CLI < 800 LOC; choices default to current behavior; gate Phase 5 |
| CI time/cost | Build only 1–2 matrix cells; everything else parse/validate; cache where possible |
| Network tests flake | Separate non-blocking job; cache vocabulary responses |
| TeX Live drift | Pin `texlive_version`; reproducible-epoch test |
| MCP churn / security | Adapter-only, pinned, read-only default, plan+confirm for mutations, never in CI |
| Author parsing still wrong at edges | Explicit `given`/`family` fields; derive only as a fallback |
| Over-automation of release | `plan`/`apply` split, dry-run default, clean-tree check, tag guard |

---

## 8. Non-goals

- A bibliography manager or reference-manager UI.
- Collaborative editing or a web editor.
- Automatic journal submission.
- Full Zenodo deposit automation from CI (GitHub integration + DOI writeback
  is enough; API deposition can be a later opt-in).
- Replacing `make` with a bespoke CLI for humans.
- Making MCP or any service a build dependency.
- Supporting every journal class; the choice list should stay short.

---

## 9. Backlog traceability (everything from the review)

| ID | Item | Phase |
| --- | --- | --- |
| E1 | Escape YAML/JSON/LaTeX; abstract/keywords in metadata | 1.1 |
| E2 | `post_gen` runs generator; render == first metadata | 1.1 |
| E3 | README/CHANGES/Version Statement/hypersetup sentinels | 1.1 |
| E4 | `latex_escape` ordering; title override | 1.1 |
| C1 | CFF schema validity (`type`, quoting, yaml.safe_dump) | 1.2 |
| C2 | Zenodo communities/license/ORCID/publication_type | 1.2 |
| L1 | License choice + README link + code license | 1.3 |
| V1 | Validator comment/`\citep`/inline/`\input` bugs | 1.4 |
| V2 | Graphics/ref/label/duplicate-bib/orphan checks | 1.4 |
| H1 | `git init` nested-repo bug | 1.5 |
| H2 | `core.hooksPath`, `make hooks` | 1.5 |
| B1 | Bootstrap quoting/injection, repo name, idempotency | 1.6 |
| D1 | DOCX resource path, reference doc, smaller image | 1.7 |
| A1 | Core package + CLI + JSON schemas | 2 |
| A2 | Makefile/pre-push/CI delegate; shims | 2 |
| A3 | `article status` + drift check | 2 |
| T1 | Render matrix + unit tests + schema tests | 0, 5 |
| T2 | Template CI + dependabot + SHA pins | 0, 3.6 |
| R1 | Multi-author/affiliations/ROR/corresponding | 3.1 |
| R2 | `manuscript_kind`, `citation_style`, `__prompts__` | 3.2 |
| R3 | `pre_gen` validation (slug/semver/SPDX/ORCID) | 3.2 |
| P1 | Branch-agnostic workflows / `default_branch` | 3.3 |
| P2 | Preamble order, `pdfusetitle`, `csquotes`, `siunitx` | 3.4 |
| P3 | `.latexmkrc`, out-of-tree build, reproducible PDF | 3.4, 4 |
| G1 | Drop `jinja2-time`, UTC date | 3.5 |
| G2 | `.gitignore` figures/supplementary/biblatex | 3.5 |
| G3 | README/canonical-pattern drift, CONTRIBUTING, badges | 3.5 |
| G4 | Neutral/personal defaults | 3.5 |
| I1 | Reusable build workflow, release tag guard | 3.6 |
| I2 | Permissions, `-halt-on-error`, TeX Live pin | 3.6 |
| W1 | `release plan/apply`, DOI writeback, Zenodo integration | 4 |
| W2 | latexdiff/arxiv/wordcount/spell/watch/figures | 4 |
| W3 | Pages PDF, supplementary build | 4 |
| S1 | data/analysis pipeline, CSV→LaTeX | 5 |
| S2 | Journal classes | 5 |
| S3 | Reviewer mode, response letter, cover letter | 5 |
| S4 | Devcontainer/Dockerfile | 5 |
| S5 | REUSE/SPDX, dual licensing | 5 |
| S6 | cruft/Copier upgrades, migration doc | 5 |
| M1 | MCP adapter, tools/resources, guardrails, parity tests | 6 |

---

## 10. Open questions (answered 2026-10-21 — see `plan/decisions.md`)

1. **Audience:** personal template only, or shared/public? Affects default
   neutrality, docs, and how much migration tooling is worth building.
2. **Primary manuscript kind:** perspective/review only, or empirical too?
   Determines whether Phase 5 is core or optional.
3. **Branch policy:** keep `master`, or move new repos to `main` (with
   `default_branch` configurable)?
4. **Backward compatibility:** is a v2.0 metadata break acceptable, or must
   `author:`/`license` shapes remain indefinitely?
5. **License matrix:** which licenses do you actually want (CC-BY-4.0,
   CC-BY-SA-4.0, CC0-1.0, MIT, other)?
6. **Journal targets:** any specific classes (elsarticle, revtex, acmart,
   IEEEtran, sn-jnl) you submit to?
7. **Python floor / dependency policy:** is “stdlib + PyYAML only” the rule,
   or can the CLI use `click`/`typer`/`rich`?
8. **MCP timing:** after Phase 2 (recommended) or not at all for now?
9. **Personal defaults:** keep your ORCID/`github_user` as defaults, or move
   them to a user config?
10. **Plan doc:** keep this file in the repo, or move it to a private notes
    repo?

---

## 11. Definition of done (overall)

- All P0 items have regression tests in `tests/`.
- The render matrix passes, including special characters, multi-author,
  license variants, and DOI set.
- `make metadata` is a no-op on a fresh render in every context.
- `make validate` and CI run the same code; validator fixtures cover every
  historical bug.
- `cffconvert` and Zenodo metadata validation pass.
- `make pdf`, `make docx` (with figures), `make release plan` work on a
  clean render.
- A fresh clone can build with TeX + Python only; MCP is not installed
  unless opted in.
- README, canonical-pattern and CONTRIBUTING describe actual behavior.
