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
