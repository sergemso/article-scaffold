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
