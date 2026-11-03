# Theses map extensions: arguments, adversarial standards, source fidelity, terms, formal checks, provenance

Repo: `/home/sergei/projects/sergemso/article-scaffold` (a cookiecutter template; run Python from the venv: `make setup`, then `.venv/bin/python -m pytest <file>`; the whole suite takes about five minutes, so run single files while iterating; `make lint` runs ruff). The template tree is `{{cookiecutter.repo_name}}/`; quote that path in shells. Code lives in `{{cookiecutter.repo_name}}/scripts/article/` (`theses.py`, `claims.py`, `index.py`, `flow.py`, `upgrade.py`), schemas in `{{cookiecutter.repo_name}}/schemas/`, tests in `tests/`.

This plan implements decisions 0073 to 0078 (they hold the why; this file holds the what; do not re-open them; if one proves wrong, stop and mark the step `[!]` with the reason): 0073 arguments, 0074 adversarial standards, 0075 source-claim fidelity, 0076 term registry, 0077 formal checks, 0078 AI-use log. They extend 0065 to 0072 and fact 0009. The proposals they came from are archived in `docs/plans/archive/notes-*.md` and hold the worked examples.

Constraints that apply to every step: every new field is optional so an existing `version: 1` map stays valid; claim, index, map and term code makes no network call (`tests/test_no_network_in_claim_code.py`); nothing shipped to an article repo names go-getter, a model or one agent host (guardrail `article-tooling-is-host-neutral`); agents propose and humans promote (0066, guardrail `agent-nodes-need-human-promotion`); `theses.yaml` and `flow.yaml` belong to the author and `upgrade` never overwrites them. Commit messages follow Conventional Commits with a `Refs:` trailer naming the decision ids. Stay out of `AGENTS.md`'s generated guardrail section; `go-getter apply` writes it. Never run `agentctl` or resume the archived T-queue.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked, `[>]` moved.

## 1. Schema and structural lint

### 1.1 Argument nodes — [x]
Class: implement · Effort: medium · Needs: none · Check: `.venv/bin/python -m pytest tests/test_theses_schema.py tests/test_theses_cli.py -q`
Decision: 0073. Scope: `schemas/theses.schema.json`, `scripts/article/theses.py` (`_check_node`, `_check_edge`), `theses.yaml` template comments.
Do: Add the `argument` node type with `conclusion`, numbered `premises` (`kind`, `role`, `ref`, `status`), closed `inference` list and optional `steps`. An objection reaches a premise through `premise-ref: {argument, n}`. Implement the structural lint rules of 0073 (conclusion and premises exist, numbers unique and consecutive, `ref` is a `source-claim`, single-premise deductive flagged, `proposed` implicit premise blocks `accepted`, accepted argument over a retired conclusion or required premise flagged).
Done-when: each lint rule has a failing and a passing test, and an existing map without arguments validates unchanged.
Resolved: `argument` nodes and `premise-ref` are in the schema and `theses.py` (codes T017 to T028; T026 and T027 are warnings, the rest errors); tests are in `tests/test_theses_arguments.py`. `theses accept` refuses an argument whose implicit premises are not yet accepted. `add_nodes` (the agent write path) still writes flat scalar fields only, so an agent cannot yet append an argument with premises; step 3.1 must cover that.

### 1.2 Objection and defense fields — [ ]
Class: implement · Effort: medium · Needs: 1.1 · Check: `.venv/bin/python -m pytest tests/test_theses_schema.py tests/test_theses_cli.py -q`
Decision: 0074. Scope: same files as 1.1, and `gaps` in `theses.py`.
Do: Add the optional objection fields (`author`, `target`, `form` as `strongest` or `standard`, `strongest-form`, `tradition`, `kind`, `counterexample`, `severity`, `premise-ref`) and defense fields (`answers`, `move`, `anchor`, `cost`). Implement the errors, gaps and duplicate warning listed in 0074. An unanswered `fatal` objection sorts first in `theses gaps`. The rival-tradition gap is off unless the thesis opts in.
Done-when: every lintable item of 0074 has a test; a `weak` form is rejected by the schema.

### 1.3 Terms section — [ ]
Class: implement · Effort: medium · Needs: none · Check: `.venv/bin/python -m pytest tests/test_terms.py tests/test_section_index.py -q`
Decision: 0076. Scope: `schemas/theses.schema.json`, new `scripts/article/terms.py`, `scripts/article/index.py`, `scripts/article/cli.py`.
Do: Add the `terms` section (id, name, forms, kind, anchor, definition, senses, status, author, children, `match` defaulting to `phrase-only`, optional `scope`) and the kind rules. Implement the tier 0 checks of 0076 on the section index and the `.tex` sources: dangling anchor, use before definition (with the `\ref` exemption), second defining site, unregistered `definition` environment as a gap, orphan, case and plural drift. The scanner skips math, verbatim, listings, comments, label strings, quotations and generated section files.
Done-when: each check has a fixture test including the false-positive cases of 0076, and `theses gaps` lists unregistered definitions.

## 2. Source-claim fidelity and claim checks

### 2.1 Source-claim fields and tier 1 — [ ]
Class: implement · Effort: high · Needs: none · Check: `.venv/bin/python -m pytest tests/test_claims.py tests/test_theses_schema.py -q`
Decision: 0075. Scope: `schemas/theses.schema.json`, `scripts/article/claims.py`.
Do: Add the optional `source-claim` fields (structured `locator`, `bib`, `rests-on`, `edition-map`, `translation`, `context`, `reading`); a string `locator` stays valid. The quote matcher reads the named edition's file under `paper/sources/`, matches `original-quote` when the original is local (otherwise reports `original-unavailable` as advice), checks the structure of the new fields and reports quote drift with the normalisation used.
Done-when: tests cover a string locator, an edition file, a missing edition (listed, not guessed), a translation with and without a local original, and each normalisation.

### 2.2 Tier 2 verdicts, window and tier 3 — [ ]
Class: implement · Effort: medium · Needs: 2.1 · Check: `.venv/bin/python -m pytest tests/test_claims.py tests/test_no_network_in_claim_code.py -q`
Decision: 0075. Scope: `scripts/article/claims.py`, cache key code.
Do: Add the verdicts `out-of-context`, `translation-sensitive`, `needs-wider-context` and `supports-with-reading`; widen the window once on `needs-wider-context`, then report `unclear`; include claim, excerpt, window, stance and original-quote in the cache key; route every `interpretive` reading and every kept `translation-sensitive` or `out-of-context` verdict to tier 3, which records who, when, why, edition and translation.
Done-when: a changed `context` field invalidates the cached verdict, the widening happens exactly once, and tier 3 attestation is required in the cases 0075 lists.

### 2.3 Tier 2 sense-drift check for terms — [ ]
Class: implement · Effort: medium · Needs: 1.3, 2.2 · Check: `.venv/bin/python -m pytest tests/test_terms.py tests/test_no_network_in_claim_code.py -q`
Decision: 0076 with 0067. Scope: `scripts/article/terms.py`, `scripts/article/claims.py`.
Do: Build the usage windows around lint-chosen occurrences and pass only the gloss, the defining paragraph and a small fixed number of windows, never the whole paper. Verdicts `consistent`, `narrower`, `broader`, `different-sense`, `unclear`, cached by gloss and window hash; only `different-sense` and `broader` produce a gap.
Done-when: unchanged terms cost nothing on a re-run and the input never exceeds the window bound.

## 3. Procedures

### 3.1 Update the red-team, blue-team and claim-check skills — [ ]
Class: implement · Effort: medium · Needs: 1.2, 2.2 · Check: `.venv/bin/python -m pytest tests/test_theses_cli.py -q`
Decision: 0074, 0075, 0076. Scope: the shipped `red-team`, `blue-team` and `claim-check` skills (`{{cookiecutter.repo_name}}/.claude/skills/`) and any host-neutral procedure text they adapt.
Do: Put the red-team and blue-team checklists of 0074 into the procedures, including the duplicate and not-already-answered checks and severity as a proposal for a human to confirm. Teach the claim-check procedure the new fields and verdicts. Keep host-specific wording in the thin adapters only.
Done-when: each checklist item of 0074 appears in a procedure, and no shipped file names go-getter, a model or one host.

## 4. Flow: formal checks

### 4.1 Declared formal checks and `run-formal` orders — [ ]
Class: implement · Effort: high · Needs: none · Check: `.venv/bin/python -m pytest tests/test_flow_done.py tests/test_flow_orders.py tests/test_flow_status.py -q`
Decision: 0077. Scope: `schemas/flow.schema.json`, `schemas/flow-order.schema.json`, `scripts/article/flow.py`.
Do: Add the `formal` declarations (name prefixed `formal-`, closed `kind: log-verdict`, `log_dir` under `docs/logs/`, hashed `inputs`, `required_logs`, `pass_when`, `run_hint`). `flow done` for a `formal-check` order is a pure file read reporting `pass`, `fail`, `stale` or `unavailable`. Add the gated `run-formal` order kind whose human text shows `run_hint`; the flow never executes it. A repo with no `formal` entries emits no `formal-check` order.
Done-when: tests show stale after an input change, `unavailable` for a missing log or environment record, which rule failed in the report, and that nothing in the reader can execute a command (guardrail `flow-checks-are-named-not-supplied`).

## 5. Provenance

### 5.1 Log writer, lint and report — [ ]
Class: implement · Effort: high · Needs: none · Check: `.venv/bin/python -m pytest tests/test_provenance.py -q`
Decision: 0078. Scope: new `scripts/article/provenance.py`, new `schemas/provenance.schema.json`, `scripts/article/cli.py`.
Do: Write `docs/provenance/ai-use.jsonl` with only the fields of 0078 (no free text; node ids and repo-relative paths matched by pattern). `provenance lint` rejects an unknown key or an over-long value. `provenance report` prints a draft AI-use paragraph grouped by kind and tool class, flags mismatches with the current statement, says what the log does not cover, and never writes the backmatter.
Done-when: tests show a line with an extra key, a long value, an absolute path or a model name is rejected, and the report derives counts on demand without writing them to the repo.

### 5.2 Write events from `flow done` and `theses accept` — [ ]
Class: implement · Effort: medium · Needs: 5.1 · Check: `.venv/bin/python -m pytest tests/test_provenance.py tests/test_flow_done.py tests/test_theses_cli.py -q`
Decision: 0078. Scope: `scripts/article/flow.py`, `scripts/article/theses.py`.
Do: Append an event when an order is closed and a separate `accepted` line referencing the same order when a human accepts. An agent-authored node stays `proposed` until such a line exists.
Done-when: closing an order and accepting a node each leave the expected lines, and an agent node with no acceptance line cannot be `accepted`.

## 6. Delivery

### 6.1 Keep the provenance log out of the companion — [ ]
Class: implement · Effort: low · Needs: 5.1 · Check: `.venv/bin/python -m pytest tests/test_companion_build.py tests/test_companion_config.py tests/test_upgrade_companion.py -q`
Decision: 0078; guardrail `theses-map-never-reaches-companion`. Scope: `{{cookiecutter.repo_name}}/companion.yaml`, `_COMPANION_DENY` and its warning text in `scripts/article/upgrade.py`, `scripts/article/companion.py`.
Do: Add `docs/provenance/**` to the template's deny patterns and to `_COMPANION_DENY`, so an existing `companion.yaml` (which `upgrade` never edits) gets the same warning it gets for the map. Add a snapshot test that fails when the log is present in the result.
Done-when: the snapshot build fails, publishing nothing, if `docs/provenance/` reaches the result. Human: `AGENTS.md` still shows the old guardrail title; the maintainer runs `go-getter apply` to refresh its generated section.

### 6.2 Upgrade delivery and adoption procedure — [ ]
Class: implement · Effort: medium · Needs: 1.1, 1.2, 1.3, 2.1, 4.1, 5.1 · Check: `.venv/bin/python -m pytest tests/test_upgrade_theses.py tests/test_upgrade_flow.py tests/test_upgrade_apply.py -q`
Decision: 0073 to 0078. Scope: `scripts/article/upgrade.py`, `docs/skills/adopting-the-theses-map-in-an-existing-article.md`, `{{cookiecutter.repo_name}}/CHANGES.md`.
Do: Confirm an upgrade delivers the new schemas, code and skills and leaves `theses.yaml` and `flow.yaml` alone. Extend the adoption procedure with the new optional fields, the `terms` section, `formal` declarations and the provenance log. Record the changes in `CHANGES.md`.
Done-when: an upgrade of a repo with a `version: 1` map passes lint unchanged, and the adoption procedure mentions each new feature once.

## 7. Release

### 7.1 Full suite and version — [ ]
Class: verify · Effort: low · Needs: 6.2 · Check: `make test && make lint`
Human: tagging and pushing needs the owner's explicit go-ahead.
Do: Run the whole suite and lint, then prepare the version bump in the repo's release practice and ask before tagging.
Done-when: `make test` and `make lint` pass and the release notes list each decision.
