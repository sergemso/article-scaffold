# Implementation journal

Append-only. New entries are written by `plan/agentctl.py`; do not rewrite
history after work has started.

## 2026-10-20T22:31:18Z — plan — init
- 44 tasks loaded from plan/tasks.json
- state initialised; T01 is the baseline-commit task

## 2026-10-20T22:31:18Z — T01 — claim
- owner=agent ttl=120m

## 2026-10-20T22:31:18Z — T01 — checkpoint
- harness files present; doctor/status/next verified

## 2026-10-20T22:31:20Z — T01 — done
- harness validated; baseline committed
- verify: passed
- scope: clean

## 2026-10-20T23:13:46Z — repo — public + bootstrap CI
- GitHub visibility changed to public: https://github.com/sergemso/article-scaffold
- `.github/workflows/plan-ci.yml` added: plan/state contract + default Cookiecutter render
- first run failed because the shallow checkout hid T01's recorded commit; `fetch-depth: 0` fixed it
- run 39513551797: both jobs green
- full template matrix remains T04; this workflow is the bootstrap check

## 2026-10-20T23:22:54Z — T02 — claim
- owner=agent ttl=120m

## 2026-10-20T23:24:31Z — T02 — done
- pyproject/Makefile/tests/docs added; make setup + make test pass; lint runs but reports pre-existing findings to be fixed in Phase 1
- verify: passed
- scope: clean

## 2026-10-20T23:25:51Z — T03 — claim
- owner=agent ttl=120m

## 2026-10-20T23:25:57Z — T03 — done
- render helper + 4 named xfail regressions; special chars/DOI/empty subtitle render
- verify: passed
- scope: clean

## 2026-10-20T23:27:01Z — T04 — claim
- owner=agent ttl=120m

## 2026-10-20T23:27:02Z — T04 — done
- test-template.yml: lint/unit/render; default metadata drift check; special chars via pytest xfail
- verify: passed
- scope: clean

## 2026-10-20T23:27:20Z — G0 — gate
- T02–T04 complete: dev tooling, render matrix, template CI
- `make test`: 7 passed, 4 xfailed (named Phase 1 bugs), 2 xpassed
- `audit`: 4 done, no scope or evidence errors
- `plan/STATUS.md` rendered
- `make lint`: clean

## 2026-10-20T23:30:05Z — T05 — claim
- owner=agent ttl=120m

## 2026-10-20T23:30:08Z — T05 — done
- tojson applied to YAML/JSON/CFF; hostile title/abstract/subtitle/keywords parse; special metadata generation passes
- verify: passed
- scope: clean

## 2026-10-20T23:32:19Z — T06 — claim
- owner=agent ttl=120m

## 2026-10-20T23:32:21Z — T06 — done
- abstract/abstract_note/keywords single-source; sentinels for abstract, README masthead, CHANGES, backmatter; idempotent generator
- verify: passed
- scope: clean

## 2026-10-20T23:33:25Z — T07 — claim
- owner=agent ttl=120m

## 2026-10-20T23:33:28Z — T07 — done
- hypersetup pdftitle/pdfauthor/pdfsubject/pdfkeywords generated in title block; hostile chars and empty subtitle covered
- verify: passed
- scope: clean

## 2026-10-20T23:34:14Z — T08 — claim
- owner=agent ttl=120m

## 2026-10-20T23:34:16Z — T08 — done
- single-pass escaper; title_tex override; 19 table/property tests including backslash, unicode, already_tex
- verify: passed
- scope: clean

## 2026-10-21T05:23:26Z — T09 — claim
- owner=agent ttl=120m

## 2026-10-21T05:23:30Z — T09 — done
- post_gen runs generator with sys.executable; fails loudly on PyYAML; render+metadata is clean for default, DOI and hostile fixtures
- verify: passed
- scope: clean

## 2026-10-21T11:06:45Z — T10 — claim
- owner=agent ttl=120m

## 2026-10-21T11:06:56Z — T10 — done
- check mode prints unified diff and exits 1; metadata-check target; CI checks default and special renders; drift, missing-file, read-only and pdf no-write tests; CFF strings JSON-escaped
- verify: passed
- scope: clean

## 2026-10-21T11:07:13Z — G1 — gate
- T05–T10 complete: structured escaping, abstract SSOT, PDF metadata, single-pass escaper, post-gen generation, metadata --check
- `make test`: 41 passed, 1 xfailed (CFF type, T11), 5 xpassed
- `audit`: 10 done, no scope or evidence errors
- `plan/STATUS.md` rendered
- CFF strings are JSON-escaped so hostile input remains parseable; schema type is T11

## 2026-10-21T11:09:52Z — T11 — claim
- owner=agent ttl=120m

## 2026-10-21T11:09:59Z — T11 — done
- CFF generated with yaml.safe_dump; root type software, preferred-citation unpublished; version/date strings; abstract, keywords, DOI identifiers, authors; empty optionals omitted; cffconvert validates
- verify: passed
- scope: clean

## 2026-10-21T11:12:00Z — T12 — claim
- owner=agent ttl=120m

## 2026-10-21T11:12:08Z — T12 — done
- Zenodo JSON via json.dumps; SPDX->Zenodo license map; communities default []; publication_type explicit; creators list with optional orcid/affiliation; empty doi/related_identifiers omitted; 11 tests
- verify: passed
- scope: clean

## 2026-10-21T11:14:06Z — T13 — claim
- owner=agent ttl=120m

## 2026-10-21T11:14:12Z — T13 — done
- Offline CFF/Zenodo type+schema checks; cffconvert offline; network tests gated by RUN_NETWORK=1; non-blocking CI network job; Zenodo cc0-1.0 fix
- verify: passed
- scope: clean

## 2026-10-21T11:17:49Z — T14 — claim
- owner=agent ttl=120m

## 2026-10-21T11:17:49Z — T14 — checkpoint
- license choice restricted; vendored texts; hook installs LICENSE/LICENSE-CODE; README and metadata updated; render-matrix test added

## 2026-10-21T11:17:55Z — T14 — done
- CC-BY-4.0/MIT choice; full texts vendored and copied by post-gen; LICENSE-CODE MIT for CC-BY, single MIT for MIT; README links and metadata SPDX ids; render matrix tests
- verify: passed
- scope: clean

## 2026-10-21T11:20:16Z — T15 — claim
- owner=agent ttl=120m

## 2026-10-21T11:20:17Z — T15 — checkpoint
- multiline-aware comment stripping; cite variants and comma lists; input/include; structured diagnostics; fixtures

## 2026-10-21T11:20:26Z — T15 — done
- comments respect escaped percent; all cite commands and comma lists; input/include across paper; structured path:line:code diagnostics; fixtures for false positives/negatives
- verify: passed
- scope: clean

## 2026-10-21T11:24:17Z — T16 — claim
- owner=agent ttl=120m

## 2026-10-21T11:24:18Z — T16 — checkpoint
- graphicspath/includegraphics; labels/refs warnings; duplicate/orphan bib; recursive includes with depth/escape checks

## 2026-10-21T11:24:30Z — T16 — done
- structural checks for figures, refs, labels, duplicate/orphan bib keys, recursive includes with depth and paper-root enforcement; warnings separate from errors; fixtures
- verify: passed
- scope: clean

## 2026-10-21T11:25:15Z — T17 — claim
- owner=agent ttl=120m

## 2026-10-21T11:25:15Z — T17 — checkpoint
- workflow delegates to scripts/validate-paper.py; Makefile same command; permissions/concurrency/path filters; parity test

## 2026-10-21T11:25:19Z — T17 — done
- single validator entry point in CI and make validate; no inline validation; contents:read, concurrency, generated-layout paths; parity test
- verify: passed
- scope: clean

## 2026-10-21T11:26:57Z — G1b — gate
- T11–T17 complete: valid CFF/Zenodo, schema/network checks, license choice, structural validator, CI parity
- `make test`: 99 passed, 3 skipped (network opt-in)
- `audit`: 17 done, no scope or evidence errors
- `plan/STATUS.md` rendered
- One validator implementation is invoked by both `make validate` and CI

## 2026-10-21T11:31:29Z — T18 — claim
- owner=agent ttl=120m

## 2026-10-21T11:31:29Z — T18 — checkpoint
- nested repo detection via show-toplevel; core.hooksPath scripts/githooks; make hooks; missing git warning; integration tests

## 2026-10-21T11:31:33Z — T18 — done
- nested render creates its own .git; hook installed once via scripts/githooks/core.hooksPath; make hooks idempotent; missing git warns without failing render
- verify: passed
- scope: clean

## 2026-10-21T11:34:56Z — T19 — claim
- owner=agent ttl=120m

## 2026-10-21T11:34:56Z — T19 — checkpoint
- workflow inputs moved to env; validation before cookiecutter/gh; explicit no-input context; idempotent repo creation; topics/permissions; parser tests

## 2026-10-21T11:34:58Z — T19 — done
- all inputs flow through env and quoted shell vars; slug/repo/semver/license/visibility/owner validation; explicit cookiecutter context; refuse existing repo; explicit topics; contents:read; YAML parser tests
- verify: passed
- scope: clean

## 2026-10-21T11:38:19Z — T20 — claim
- owner=agent ttl=120m

## 2026-10-21T11:38:20Z — T20 — checkpoint
- pandoc resource path covers paper, paper/figures, root; optional reference.docx; pinned pandoc/core:3.1; DOCX media test

## 2026-10-21T11:38:23Z — T20 — done
- resource-path shared by make/CI; optional reference doc; pinned pandoc/core; DOCX embeds figures and leaves PDF images untouched
- verify: passed
- scope: clean

## 2026-10-21T11:43:39Z — T21 — claim
- owner=agent ttl=120m

## 2026-10-21T11:43:39Z — T21 — checkpoint
- vendored article package with pure diagnostics/latex/metadata/validate/build modules; diagnostics/status schemas; parity tests

## 2026-10-21T11:43:46Z — T21 — done
- scripts/article core is importable, side-effect-free, stdlib+PyYAML; stable diagnostics/status schemas; byte-identical metadata outputs and validation tests
- verify: passed
- scope: clean

## 2026-10-21T11:47:14Z — T22 — claim
- owner=agent ttl=120m

## 2026-10-21T11:47:14Z — T22 — checkpoint
- JSON-first CLI with validate/metadata/status/build/release; stable exit codes; metadata check/dry-run; build plans; tests

## 2026-10-21T11:47:25Z — T22 — done
- all subcommands support --json; 0/1/2/3 exit codes; metadata --check/--dry-run write nothing; build --dry-run exposes core plans; status delegates to optional status.py; no MCP imports
- verify: passed
- scope: clean

## 2026-10-21T11:52:44Z — T23 — claim
- owner=agent ttl=120m

## 2026-10-21T11:52:44Z — T23 — checkpoint
- Make pdf/metadata delegate to CLI; pre-push calls CLI with safe missing-CLI warning; legacy validator/generator are core-backed shims preserving diagnostics and --check output

## 2026-10-21T11:52:52Z — T23 — done
- Make/CLI/hook/CI converge on scripts.article; legacy scripts only format/delegate; generated metadata byte-identical; pre-push skips safely without CLI; delegation parity tests
- verify: passed
- scope: clean

## 2026-10-21T11:56:12Z — T24 — claim
- owner=agent ttl=120m

## 2026-10-21T11:56:12Z — T24 — checkpoint
- status.py reports template/repo/metadata/diagnostics/tools; strict status schema; docs/cli.md; read-only and drift/invalid metadata tests

## 2026-10-21T11:56:22Z — T24 — done
- article status --json is offline/read-only, schema-valid, robust for unborn/detached git and invalid metadata; docs publish exit codes and versioned fields
- verify: passed
- scope: clean

## 2026-10-21T11:57:36Z — G2 gate — passed
- make test: 136 passed, 3 skipped (network opt-in)
- audit: 44 tasks, 24 done; no consistency errors
- rendered plan/STATUS.md
- T20–T24: DOCX resources, vendored core, JSON CLI, delegation, status contract

## 2026-10-21T12:06:42Z — T25 — claim
- owner=agent ttl=120m

## 2026-10-21T12:06:42Z — T25 — checkpoint
- v2 authors/affiliations loader with legacy normalization, ORCID/ROR checks, duplicate/missing-corresponding diagnostics, metadata_schema 2, schema and tests

## 2026-10-21T12:06:45Z — T25 — done
- v2 and v1 metadata load through one normalized model; ORCID checksum/ROR shape/duplicates/corresponding diagnostics; default generated files byte-identical; metadata schema published
- verify: passed
- scope: clean

## 2026-10-21T12:10:08Z — T26 — claim
- owner=agent ttl=120m

## 2026-10-21T12:10:08Z — T26 — checkpoint
- multi-author LaTeX \author/\thanks, CFF/Zenodo/README/BibTeX from _authors, ORCID/ROR links, 3-author consistency and PDF test

## 2026-10-21T12:10:15Z — T26 — done
- 3-author fixture agrees across LaTeX/CFF/Zenodo/README; ORCID/ROR links where supported; PDF builds with latexmk; core metadata.py touched because T23 moved renderers out of the legacy shim (recorded in decisions.md)
- verify: passed
- scope: override

## 2026-10-21T12:46:28Z — T27 — claim
- owner=agent ttl=120m

## 2026-10-21T12:46:28Z — T27 — checkpoint
- kind/style choices, conditional empirical sections/packages/tables path, natbib/apalike vs cite/plain, DOCX/HTML style passthrough, 6-cell render matrix; default perspective output byte-identical

## 2026-10-21T12:46:35Z — T27 — done
- 6 kind/style combinations render; perspective+numeric generated article/references/CFF/Zenodo/README byte-identical to T26; empirical PDF and HTML build; scope extension recorded in decisions.md because metadata state and renderers live in core after T21/T23
- verify: passed
- scope: override

## 2026-10-21T12:53:58Z — T28 — claim
- owner=agent ttl=120m

## 2026-10-21T12:53:58Z — T28 — checkpoint
- pre-gen validator for slug/repo/semver/ORCID/license/DOI/title; plain-language __prompts__; API tests valid/invalid and empty ORCID; full suite 172 passed

## 2026-10-21T12:54:05Z — T28 — done
- invalid contexts fail before rendering with one field-specific ERROR each; empty ORCID accepted; prompts labelled; --no-input green; adjusted the old float-like CFF regression to edit metadata after rendering because 1.0 is intentionally not semver (recorded in decisions.md)
- verify: passed
- scope: override

## 2026-10-21T13:48:03Z — T37 — claim
- owner=agent ttl=120m

## 2026-10-21T13:48:03Z — T37 — checkpoint
- starting empirical data/analysis pipeline

## 2026-10-21T17:09:40Z — T37 — done
- data/ and analysis/ directories with uv.lock, checksums, stdlib-only pipeline, make analysis, make analysis-check, paper/tables and paper/figures outputs consumed by empirical manuscript via InputIfFileExists in 03_results.tex; full suite 179 passed
- verify: passed
- scope: override

## 2026-10-21T17:11:08Z — T29 — claim
- owner=agent ttl=120m

## 2026-10-21T17:11:08Z — T29 — checkpoint
- starting branch-agnostic workflows

## 2026-10-21T17:20:35Z — T29 — done
- branch-agnostic workflows using github.event.repository.default_branch; cookiecutter default_branch choice with main/master; post_gen hook uses {{ cookiecutter.default_branch }}; test_status.py updated to accept main/master since default is now main; full suite 184 passed
- verify: passed
- scope: override

## 2026-10-21T17:21:43Z — T30 — claim
- owner=agent ttl=120m

## 2026-10-21T17:21:43Z — T30 — checkpoint
- starting preamble fix and out-of-tree build

## 2026-10-21T17:34:01Z — T30 — done
- preamble package order fixed: titlesec before hyperref, cleveref after hyperref, cite/natbib before hyperref; csquotes/siunitx optional; .latexmkrc in paper/ with outdir=build, SOURCE_DATE_EPOCH, halt-on-error; Makefile copies from build/ and cleans build/; build.py output is paper/build/article.pdf; CI workflows updated; tests updated for new paths; full suite 196 passed
- verify: passed
- scope: override

## 2026-10-21T17:34:28Z — T31 — claim
- owner=agent ttl=120m

## 2026-10-21T17:34:28Z — T31 — checkpoint
- starting repo hygiene, docs and neutral defaults

## 2026-10-21T18:03:50Z — T31 — done
- removed jinja2_time extension, date now YYYY-MM-DD placeholder filled by post_gen; neutral defaults for author/github_user/affiliation/keywords; optional user config via ~/.config/article-scaffold/config.yaml or ARTICLE_SCAFFOLD_CONFIG env; updated .gitignore with build/, .venv, generated dirs, biblatex; refreshed README and template README with accurate tree; added CONTRIBUTING.md; added test_docs.py for doc hygiene; full suite 207 passed
- verify: passed
- scope: clean
