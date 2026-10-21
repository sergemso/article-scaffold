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
