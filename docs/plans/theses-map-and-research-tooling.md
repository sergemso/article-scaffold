# Theses map and research tooling: hypotheses, source checks, offense and defense

This plan is self-sufficient for a cold session. It spans three repositories on this host:

- **Scaffold** `S` = `/home/sergei/projects/sergemso/article-scaffold` (cookiecutter template plus workflows; the template tree is `S/{{cookiecutter.repo_name}}/`, quote that path in shells). Python from `S/.venv` (run `make setup` once if missing).
- **scholar-mcp** `M` = `/home/sergei/projects/sergemso/scholar-mcp` (MCP servers `scholar-authors`, `scholar-reviewers` on `scholar_core`; tests with `M/.venv/bin/python -m pytest`).
- **Article repo** `A` = `/home/sergei/projects/strebulaev-articles/articles.bridge_contract_for_agent_session_governance` (generated from the scaffold; first adopter). `A/CLAUDE.md` guardrails apply to any prose, metadata or code comment written there: never state counts of enumerable things (name the range or members), never reference specific draft versions; run `python3 scripts/lint-counts.py` before finishing. `A/metadata.yaml` is the abstract's source of truth (`make metadata`).

Host neutrality (fact 0007, guardrail `article-tooling-is-host-neutral`): go-getter is the maintainer's tooling for `S` and `M` only. Nothing shipped to an article repo may name go-getter, a model or one agent host; host-specific files are thin adapters. Steps that run `go-getter` are labelled maintainer-only.

Decisions this plan builds on, in `S/docs/decisions/`: 0065 theses map as YAML graph; 0066 gap-driven, propose-only agents; 0067 tiered local claim checks; 0068 tooling split; 0069 token economy; 0070 lifecycle derived from the repo; 0071 host-neutral work orders served over MCP; 0072 unit and retry budgets. In `M/docs/decisions/`: 0070 flow tools wrap the article CLI. In `M/docs/decisions/`: 0069 discovery tools extend the authors server; also 0057 (model never writes bibliographic fields), 0059 (egress carries identifiers and search strings only), 0060 (out-of-band confirmation), 0061 (threat model and golden corpus). Fact `S/docs/facts/0006` is the coverage matrix of scholar-mcp. Guardrails in draft that this plan activates: `theses-map-never-reaches-companion`, `agent-nodes-need-human-promotion`, `claim-check-input-stays-local` (in `S/docs/guardrails/`; set `status: active` in the file and its `INDEX.md` row only when its check exists and passes).

Why: authors need cheap, automated help with hypotheses, checking that sources support claims, and building the argument's offense and defense. Today scholar-mcp only checks bibliographic facts. The paper in `A` is about 6000 lines, so agents must read slices through an index and a map, never the whole file.

Status legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked, `[>]` moved. `‖` marks a step that can run in parallel.

## 0. Design first: specs and proposals that shape the schema and flow

Do these before any implementation. They are exploration and design; each ends with a spec or a proposal for the owner to accept as a decision, and none changes code. Step ids keep their original numbers (8.1, 9.1 to 9.5) so references elsewhere stay valid. Steps 9.1 to 9.4 shape the theses schema (step 2.1) and the agent procedures (3.2 to 3.4), and 8.1 shapes the flow (section 8), so those steps now depend on them. Nothing in sections 1 to 8 represents conceptual argument until 9.1 to 9.4 are accepted.

### 8.1 Specify stages, gates and orders — [x]
Class: plan · Effort: high · Needs: none · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/facts/0009-flow-stage-and-gate-spec.md`
Context: Decision 0070 requires every gate to be a cheap deterministic predicate. Evidence of the real loop is in the article repo `A`: `A/docs/plans/review-0.6.0-path-to-publication.md`, `review-response-v0.9.md`, `review-response-v0.10.md`, `bridge-contract-publication-readiness.md` (read these, do not copy their content). Available predicates: `theses gaps`, `claims quote-check`, `index --check`, `make validate`, `python3 scripts/check_pdf_layout.py`-style layout checks (in `A`), bibliography verification (scholar-mcp `verify_bibliography`, run by the human or MCP, not the CLI).
Do: For each stage write: entry condition, gate predicate (the exact existing command or a new one with its tests named), the order kinds it emits with tier hints, and which are gated. Mark any stage with no computable gate as a human-only step. Record as fact 0009 in `S/docs/facts/`, with a JSON schema outline for an order (fields: id, stage, nodes, outputs, tier, procedure, check, gated).
Done-when: every stage has a gate named by a runnable command, and the replay in step 8.10 can be derived from the spec.
Resolved: fact 0009 written in the slot (docs/facts/0009-flow-stage-and-gate-spec.md); the Check path names the main checkout, so it passes once this branch merges.

### 9.1 Argument form — [x]
Class: explore · Effort: medium · Needs: none · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/plans/notes-argument-form.md`
Do: Study how the theses map would hold explicit premise-conclusion arguments (numbered premises, inference type, hidden-premise slots), and what a deterministic validity or consistency check (for example propositional encoding with a solver) can and cannot do. Propose a node type and a check, with a worked example from `A/docs/notes/`.
Done-when: the note gives a schema proposal, one worked example, and the limits of automated checking in plain terms.
Resolved: note written in the slot (docs/plans/notes-argument-form.md); the Check path names the main checkout, so it passes once this branch merges.

### 9.2 Term registry and definitions — [x]
Class: explore · Effort: medium · Needs: none · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/plans/notes-term-registry.md`
Do: Propose a registry of defined terms with a first-use anchor, consistency lint (term used before defined, used in two senses) and a tier-2 sense-drift check. Cover how `A`'s paper currently defines its terms.
Done-when: the note includes a schema proposal and the lint's false-positive risks.
Resolved: note written in the slot (docs/plans/notes-term-registry.md); the Check path names the main checkout, so it passes once this branch merges.

### 9.3 Interpretive fidelity of quoted sources — [x]
Class: explore · Effort: medium · Needs: none · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/plans/notes-interpretive-fidelity.md`
Do: Extend decision 0067 for sources where meaning depends on edition, translation or context: locators across editions, quotation of translations, and a charitable-reading check beyond `supports/overstates/contradicts`.
Done-when: the note proposes node fields and tier rules, and names what remains human judgment.
Resolved: note written in the slot (docs/plans/notes-interpretive-fidelity.md); the Check path names the main checkout, so it passes once this branch merges.

### 9.4 Counterexample, steelman and objection standards — [x]
Class: explore · Effort: medium · Needs: none · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/plans/notes-adversarial-standards.md`
Do: Define what a red-team pass must produce (strongest form of each objection, counterexamples, objections from rival traditions) and what a blue-team defense must show, as a checklist the linter can partly enforce (an objection marked `strongest-form` must cite its source).
Done-when: the note has the checklist and which items are lintable.
Resolved: note written in the slot (docs/plans/notes-adversarial-standards.md); the Check path names the main checkout, so it passes once this branch merges.

### 9.5 Formal-methods hook and AI-use provenance — [x]
Class: explore · Effort: low · Needs: 8.1 · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/plans/notes-formal-and-provenance.md`
Context: `A` already runs a model checker (`scripts/run-tlc-docker.sh`, `docs/logs/p6-tlc`). The template's backmatter has an AI-use statement.
Do: Propose how formal checks become named flow checks, and a provenance log recording which orders agents performed, tier used and the human acceptance, from which the AI-use statement can be derived.
Done-when: the note proposes both and says what the log must never contain (manuscript text).
Resolved: note written in the slot (docs/plans/notes-formal-and-provenance.md); the Check path names the main checkout, so it passes once this branch merges.

## 1. Make the existing MCP server work

### 1.1 Build the scholar-mcp virtualenv — [ ] ‖
Class: implement · Effort: low · Needs: none · Check: `test -x /home/sergei/projects/sergemso/scholar-mcp/.venv/bin/scholar-authors`
Context: `M/.venv` does not exist on this host (the checkout was cloned on 2026-11-02), so the command named in `A/.mcp.json` cannot run. `M/README.md` documents `make setup` (hash-checked install from `requirements.lock`, Python 3.11 or newer).
Do: In `M`, run `make setup`. Do not edit lock files.
Done-when: `M/.venv/bin/scholar-authors` exists and prints usage when run with no arguments.

### 1.2 Fix the MCP host config in the article repo and the template — [ ]
Class: implement · Effort: low · Needs: 1.1 · Check: `cd /home/sergei/projects/strebulaev-articles/articles.bridge_contract_for_agent_session_governance && ! grep -q /home/ubuntu .mcp.json && grep -q /home/sergei/projects/sergemso/scholar-mcp .mcp.json`
Context: `A/.mcp.json` names `command: /home/ubuntu/projects/sergemso/scholar-mcp/.venv/bin/scholar-authors` and `SCHOLAR_REPO_ROOT: /home/ubuntu/projects/sergemso/articles.bridge_contract_for_agent_session_governance`; neither exists here, and the host reports EACCES. Per `M/README.md`, `SCHOLAR_REPO_ROOT` is the article repo and `SCHOLAR_CONTACT` goes into registry User-Agents. Do not put `ZENODO_TOKEN` in this file.
Do: Set `command` to `/home/sergei/projects/sergemso/scholar-mcp/.venv/bin/scholar-authors` and `SCHOLAR_REPO_ROOT` to `A`. Then check whether the scaffold template ships a `.mcp.json` (`ls -a "S/{{cookiecutter.repo_name}}"` and `grep -rn "/home/ubuntu" S --include=*.json --include=*.md --include=*.py -l`); if it hard-codes `/home/ubuntu`, record the finding in the step's `Resolved:` line and do not change the template here (step 5.1 owns template changes).
Done-when: the check passes, and a fresh host session lists `scholar-authors` as connected.

## 2. Theses map in the scaffold CLI

### 2.1 Schema, template map and validation hook — [x]
Class: implement · Effort: medium · Needs: 8.1, 9.1, 9.2, 9.3 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_theses_schema.py -q`
Context: Decision 0065. Existing schemas live in `S/{{cookiecutter.repo_name}}/schemas/` (`metadata.schema.json` validates `metadata.yaml`; see `S/tests/test_schemas.py` for how they are tested). Validation logic is in `S/{{cookiecutter.repo_name}}/scripts/article/validate.py` and runs through `make validate`.
Do: Add `schemas/theses.schema.json` to the template. Node types `thesis`, `hypothesis`, `objection`, `defense`, `source-claim`; edge types `supports`, `attacks`, `rebuts`; node fields id, text (one line), status (`proposed`, `accepted`, `retired`), anchor (a LaTeX `\label` or null), bib_keys, accepted-by (required when status is `accepted`; must not name an agent role); `source-claim` nodes also require quote and locator. Add an empty-but-valid `theses.yaml` at the template root. Make `validate.py` validate it when present and fail on unknown fields, dangling edge ids and anchors that do not exist in `paper/`. Add `S/tests/test_theses_schema.py` with a valid fixture and one failing fixture per rule.
Done-when: the test passes; an `accepted` node without `accepted-by` fails validation; a rendered article (`S/tests/test_render.py` style) still passes `make validate` with the empty map.
Resolved: schema, `theses.yaml`, `scripts/article/theses.py` (stdlib+yaml checks, codes T001 to T016) and the `validate.py` hook added in the slot; `argument` nodes from note 9.1 are not in the schema (note not yet accepted as a decision).

### 2.2 Theses CLI: lint, gaps, slice, accept — [x]
Class: implement · Effort: high · Needs: 2.1 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_theses_cli.py -q`
Context: Decisions 0065, 0066. The CLI is `S/{{cookiecutter.repo_name}}/scripts/article/cli.py` (JSON-first, `python3 -m scripts.article ...`); follow how `status.py` and `release.py` register subcommands and emit JSON, and validate output against a schema in `schemas/` if that is the convention there (see `diagnostics.schema.json`).
Do: Add `scripts/article/theses.py` and subcommands `theses lint` (schema plus graph rules), `theses gaps` (thesis with no support; objection with no defense; claim resting on one source; node whose anchor label is missing), `theses slice <id> [--depth N]` (node plus neighbourhood, compact JSON, stable order) and `theses accept <id> --by <name>` (sets status and accepted-by; refuses an agent-role name; edits only that node and preserves comments and order). Keep output small: ids and one-line text, never source text.
Done-when: tests cover each gap kind, slice depth, accept on a proposed node, accept refused for an agent name, and idempotent re-run. Then set guardrail `agent-nodes-need-human-promotion` to `active` in `S/docs/guardrails/` and its `INDEX.md` row.
Resolved: `theses lint|gaps|slice|accept` in the slot; `gaps` exits 1 when it finds any, kinds `thesis-unsupported`, `objection-undefended`, `single-source`, `anchor-missing` by default and `thesis-unattacked` via `--kind` (names from fact 0009); guardrail activated.

### 2.3 Section index — [x] ‖
Class: implement · Effort: medium · Needs: none · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_section_index.py -q`
Context: Decision 0069. Sections are `paper/sections/NN_name.tex`; labels are `\label{...}`. The script library is `S/{{cookiecutter.repo_name}}/scripts/article/`.
Do: Add `scripts/article/index.py` and subcommand `index` writing `paper/build/section-index.json` (gitignored build output): per label, file and line range; per section a one-line summary taken from the first sentence of its first paragraph (no model call). Add `index --check` that fails when the file is older than any `paper/sections/*.tex`. Wire `--check` into `make validate`.
Done-when: tests pass on a rendered article; `index` output for a 3000-line section set is under a few kilobytes; an edited section makes `index --check` fail until `index` is rerun.
Resolved: `scripts/article/index.py` and `index [--check]` in the slot; `make validate` runs the check only when the index file exists (it is gitignored build output, so a fresh clone has none).

### 2.4 Quote match (tier 1) and check cache — [x]
Class: implement · Effort: high · Needs: 2.1 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_claims.py -q`
Context: Decision 0067. Local source texts live in `paper/sources/` (in `A`: PDFs and `.txt` files with `MANIFEST.md` and `NOTICE.md` stating their terms). `source-claim` nodes carry `quote` and `locator`.
Do: Add `scripts/article/claims.py` and subcommands `claims quote-check [<id>|--all]` (normalise whitespace, hyphenation and Unicode quotes, then find the quote in the source text file named by the node's bib key via a mapping in `paper/sources/MANIFEST.md` or a `source:` field; report `found`, `not-found` or `no-local-text`), and a cache under `.theses/` keyed by the SHA-256 of claim text plus excerpt (read and write helpers used by tier 2 in step 3.4). PDFs are read only through an already-extracted `.txt`; do not add a PDF dependency here. Add `.theses/` to the template `.gitignore`.
Done-when: tests cover exact match, whitespace and hyphen differences, a changed quote, a missing source file, and a cache hit that skips recomputation. Output is verdicts and locators only.
Resolved: `scripts/article/claims.py` with `claims quote-check [<id>|--all]` (exit 1 on `not-found`), `claims excerpt <id>` and `claims cache <id> [--set supports|overstates|contradicts]` (cache file `.theses/claims-cache.json`, hashes and verdicts only) in the slot; `.theses/` added to the template `.gitignore`.

### 2.5 Keep the map out of the companion — [x]
Class: implement · Effort: low · Needs: 2.1 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_companion_build.py -q`
Context: Guardrail `theses-map-never-reaches-companion`. `S/{{cookiecutter.repo_name}}/companion.yaml` has an `include` allowlist and an `exclude` deny list ("yours after the first render; `upgrade` never overwrites it"). The snapshot builder is `scripts/article/companion.py`.
Do: Add `theses.yaml` and `.theses/**` to the template's `exclude`. Add a test in `S/tests/test_companion_build.py` that puts both in a rendered repo, even with a broad `include`, and asserts the build fails or omits them as the existing deny-pattern tests do.
Done-when: the test passes; set the guardrail to `active` in its file and `INDEX.md` row. Existing repos need a manual `companion.yaml` edit (step 6.1).
Resolved: deny patterns and tests added in the slot; guardrail activated. The snapshot omits the files and prunes `.theses` (reported in `excluded` only for `theses.yaml`).

### 2.6 No network use in the claim, index and map code — [x] ‖
Class: implement · Effort: low · Needs: 2.2, 2.3, 2.4 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_no_network_in_claim_code.py -q`
Context: Guardrail `claim-check-input-stays-local`.
Do: Add a test that parses `theses.py`, `index.py` and `claims.py` in the template with `ast` and fails on any import of `socket`, `http`, `urllib`, `requests`, `ssl`, `ftplib`, `smtplib`, `subprocess` calls to `curl` or `wget`, or `os.system`.
Done-when: the test passes and fails on a deliberate violating fixture; set the guardrail to `active` in its file and `INDEX.md` row.
Resolved: `tests/test_no_network_in_claim_code.py` scans the three modules and the local modules they import (`latex.py`, `diagnostics.py`); guardrail activated.

## 3. Agent procedures (skills) shipped in the template

### 3.1 Find where procedures and host adapters belong — [x]
Class: explore · Effort: low · Needs: none · Check: `test -s /home/sergei/projects/sergemso/article-scaffold/docs/facts/0008-where-template-procedures-live.md`
Context: The template has no `.claude/`, `.go-getter/` or `.mcp.json` (fact 0007). `companion.yaml` already excludes `.claude/**`. Procedures must be host-neutral (guardrail `article-tooling-is-host-neutral`): plain markdown the work orders reference, for example under `docs/procedures/`, plus thin adapters for hosts (a skill file, an instruction-file pointer). `scripts/article/upgrade.py` decides which files `upgrade` overwrites or leaves user-owned.
Do: Establish the neutral procedures path and the adapter locations so `upgrade` delivers and updates them, whether `upgrade` treats them as template-owned, and what pointer line an instruction file needs. Record it as fact 0008 in `S/docs/facts/` (frontmatter as in fact 0006).
Done-when: the fact names both paths, the upgrade ownership rule with a quote from `upgrade.py`, and the adapter pointer text. Steps 3.2 to 3.4 write procedure files at the neutral path, plus adapters.
Resolved: fact 0008 written in the slot; it also records that `AGENTS.md` and `theses.yaml` need adding to `_OWNED_AFTER_ADD` (step 5.1).

### 3.2 Red-team skill: objections and hypotheses — [x]
Class: implement · Effort: medium · Needs: 2.2, 3.1, 9.4 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_skills.py -q -k red_team`
Context: Decision 0066. The skill receives one gap from `theses gaps` and the output of `theses slice <id>`; it must not read `article.tex` or whole sections.
Do: Write the skill at the neutral procedures path from fact 0008. Procedure: run `theses gaps`, take one gap, run `theses slice`, read at most the section lines named by the anchor via the section index, draft objections or hypotheses as nodes with `status: proposed` (never `accepted`), each with an anchor or bib keys, and append them with a CLI or file edit that passes `theses lint`. Tell the model to stop after one gap and report ids. Add `tests/test_skills.py` asserting the skill file exists in a rendered repo, is under 150 lines, and names the CLI commands it uses.
Done-when: the test passes; a rendered repo contains the skill; the skill never instructs setting `accepted`.
Resolved: `docs/procedures/red-team.md`, adapter `.claude/skills/red-team/SKILL.md` and a template `AGENTS.md` pointer added in the slot. The procedure uses only fields in the 2.1 schema; the extra fields from note 9.4 (form, tradition, severity) are not in the map until that note is accepted, so the skill asks for them in its report.

### 3.3 Blue-team skill: defenses — [x]
Class: implement · Effort: medium · Needs: 2.2, 3.1, 9.4 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_skills.py -q -k blue_team`
Context: As step 3.2; the gap is an objection with no defense or a thesis with weak support.
Do: Write the blue-team skill alike: one gap, one slice, draft `defense` nodes with `rebuts` edges and bib keys for evidence, all `proposed`; each claim of evidence must point at a `source-claim` node, to be checked by step 3.4.
Done-when: the test passes and the skill refuses to cite a source that has no `source-claim` node.
Resolved: `docs/procedures/blue-team.md` and adapter `.claude/skills/blue-team/SKILL.md` added in the slot.

### 3.4 Claim-check skill (tier 2) — [x]
Class: implement · Effort: medium · Needs: 2.4, 3.1 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_skills.py -q -k claim_check`
Context: Decision 0067. Tier 1 is `claims quote-check`. Tier 2 sends the model only the matched excerpt and the paper's claim wording and asks for `supports`, `overstates` or `contradicts`; results go to the cache from step 2.4. This is the one place a small model is used; the skill states that routing class (decision 0007, 0069).
Do: Write the skill: run `claims quote-check --all`; for each `found` node without a fresh cache entry, judge excerpt versus claim; write the verdict to the cache; list `overstates` and `contradicts` for the human; leave tier 3 attestation to the human (`theses accept`/an attestation field).
Done-when: the test passes and the skill names the cache and never reads outside the excerpt.
Resolved: `docs/procedures/claim-check.md` and adapter `.claude/skills/claim-check/SKILL.md` added in the slot; the skill uses `claims excerpt` and `claims cache --set` from step 2.4. Tier 3 attestation has no CLI or map field yet; the skill leaves it to the author.

## 4. Discovery tools in scholar-mcp

### 4.1 Find the related, cited-by and venue endpoints — [ ] ‖
Class: explore · Effort: medium · Needs: none · Check: `test -s /home/sergei/projects/sergemso/scholar-mcp/docs/facts/0005-discovery-endpoints.md`
Context: `M/docs/decisions/0069` (discovery tools, read-only, candidate-only) and 0059 (egress allowlist, identifiers and search strings only). Registry clients are in `M/packages/core/src/scholar_core/sources.py` and `registries.py`; the allowlist is `egress.py`. OpenAlex, Crossref and arXiv are already allowlisted; no new host may be added without a decision.
Do: Establish, from recorded responses (add a few to `M/tests/corpus/records/` if none fit), how to get related works, works that cite a given work, and venue candidates from hosts already allowlisted. Record the exact endpoints and fields per source, rate and size limits, and what is authoritative, in fact 0005 (frontmatter as in `M/docs/facts/0004-*.md`).
Done-when: the fact names an endpoint and field per tool, with one quoted recorded example each.

### 4.2 Implement the discovery tools — [ ]
Class: implement · Effort: high · Needs: 4.1 · Check: `cd /home/sergei/projects/sergemso/scholar-mcp && .venv/bin/python -m pytest tests/authors tests/core tests/guardrails tests/corpus -q`
Context: Decision 0069; patterns in `M/packages/authors/src/scholar_authors/reference_tools.py` (`search_candidates`, `isbn_candidates` return candidates only) and its closed JSON schemas. Output is data, fenced as other registry strings are. Tool-schema text counts against every session: keep descriptions to one or two sentences.
Do: Add `related_works`, `cited_by` and `venue_candidates` to the authors server. Inputs are an identifier or a short search string, a small result limit with a hard cap, and nothing else (unknown arguments rejected). Results are candidate records with source, retrieval time and hash, never inserted into the bibliography; adding stays `plan_add_reference` with a human pick. Add corpus cases, tests under `M/tests/authors/` and `M/tests/guardrails/` (egress allowlist, closed schemas, no write), and threat-model rows in `M/docs/threat-model.md` (prompt injection through a candidate title; oversized results).
Done-when: the full suite and `ruff check .` pass; every new threat-model row names a passing test; the tools list shows three new tools with short descriptions.

### 4.3 Live run, README and tag — [ ]
Class: review · Effort: medium · Needs: 4.2 · Check: `test -s /home/sergei/projects/sergemso/scholar-mcp/docs/e2e-0.1.4.md`
Human: tagging and pushing needs the owner's explicit go-ahead.
Context: Earlier runs are `M/docs/e2e-0.1.*.md`; release practice is in `M/docs/plans/scholar-reviewers.md` step 5.2 (`chore(release): set version X`, annotated tag, ask before pushing).
Do: Run the three tools through a real stdio session against `A`, including a hostile candidate title and an over-limit request; write the transcript to `docs/e2e-0.1.4.md`; add the tools to `M/README.md`; set the version and tag locally; ask the owner before pushing.
Done-when: the transcript shows each refusal; the README lists the tools; the tag exists locally.

## 5. Delivery to existing repos

### 5.1 Upgrade delivers the new files and leaves the map alone — [x]
Class: implement · Effort: medium · Needs: 2.2, 2.3, 2.4, 3.1 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_upgrade_user_owned.py tests/test_upgrade_apply.py tests/test_bootstrap_upgrader.py -q`
Context: `upgrade --plan/--apply/--finish` (`scripts/article/upgrade.py`) keeps `metadata.yaml` and `companion.yaml` user-owned. `theses.yaml` is the author's argument and must never be overwritten or removed. Existing `companion.yaml` files are not updated by `upgrade`.
Do: Declare `theses.yaml` and `.theses/` user-owned in the upgrade rules; make `upgrade --plan` print a notice when an existing `companion.yaml` lacks the two deny patterns from step 2.5. Add tests: an old rendered repo upgrades and gains the CLI, schema, skills and index; its `theses.yaml` is untouched; the notice appears.
Done-when: the check passes; the pre-existing upgrade tests still pass. If step 1.2 found a hard-coded `/home/ubuntu` in the template, remove it here (use a placeholder the user fills) with a test.
Resolved: `theses.yaml` and `AGENTS.md` added to `_OWNED_AFTER_ADD`; `upgrade --plan` returns `notices` (code `N001`) for a `companion.yaml` lacking the two deny patterns; new tests in `tests/test_upgrade_theses.py`; documented in `docs/upgrading.md`. Step 1.2 itself was not run here, but `grep -rn /home/ubuntu` over the template, hooks and tests finds nothing, so there was nothing to remove. Check `tests/test_bootstrap_upgrader.py` passes unchanged.

### 5.2 Series report of map gaps — [x]
Class: implement · Effort: medium · Needs: 2.2 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_track_articles.py -q`
Context: `S/scripts/track_articles.py` and `S/.github/workflows/track-articles.yml` list the installation's article repos and write a registry to the job summary; it never publishes. Articles in a series link through `related_identifiers`. The map is private; a report must carry counts and ids only, to the owner's job summary, never to the companion.
Do: Add per-repo gap kinds and counts (from `theses gaps` output, read through the repo contents API or the checkout the tracker already makes) to the summary table; skip repos without `theses.yaml`.
Done-when: the test passes with a fixture repo that has gaps and one that has no map.
Resolved: `scripts/track_articles.py` reads `theses.yaml` through the contents API, reuses the template's `theses.gaps` (anchor-missing is not reported, since section files are not read), shows kind and count in a new `Map gaps` column and ids in `--json`, never node text.

## 6. Adopt in this article repo

### 6.1 Upgrade the article repo — [ ]
Class: implement · Effort: medium · Needs: 5.1, 1.2 · Check: `cd /home/sergei/projects/strebulaev-articles/articles.bridge_contract_for_agent_session_governance && python3 -m scripts.article theses lint && python3 -m scripts.article index --check && grep -q 'theses.yaml' companion.yaml`
Context: Procedure `S/docs/skills/adopting-the-theses-map-in-an-existing-article.md`. `A` starts clean on `master`; use a branch and a pull request. `A/CLAUDE.md` forbids counts of enumerable things and draft-version references in prose and comments; run `python3 scripts/lint-counts.py`.
Do: Follow the procedure steps 1 to 4 and 7: `upgrade --plan`, read it, `--apply`, resolve conflicts, `--finish`; add `theses.yaml` and `.theses/**` to `companion.yaml` `exclude`; run the companion dry run in the scaffold and read the file list; run `make validate`.
Done-when: the check passes and `make validate` and `python3 scripts/lint-counts.py` exit 0.

### 6.2 Seed the map from existing notes — [ ]
Class: implement · Effort: high · Needs: 6.1 · Check: `cd /home/sergei/projects/strebulaev-articles/articles.bridge_contract_for_agent_session_governance && python3 -m scripts.article theses lint && python3 -m scripts.article theses gaps`
Context: Offense material already exists as prose: `A/docs/notes/2026-10-28-enemies-list.tex` (competitors and response strategies; marked "not re-verified"), `A/docs/plans/review-response-v0.10.md` (a review's twelve-item list of defects, some of them objections) and sibling plans in `A/docs/plans/`. Third-party source texts are in `A/paper/sources/` (read `NOTICE.md` before reusing any text). The paper is `A/paper/article.tex` with sections in `A/paper/sections/`; read it only through `index` output and the labels you need.
Do: Create nodes, all `status: proposed`: each competitor as an `objection` or `hypothesis` with its response strategy as a `defense`; each objection from the review plan with an anchor label; `source-claim` nodes only where a verbatim quote and locator can be found in a local source text. Keep node text to one line; no counts or draft-version references in any text you write.
Done-when: `theses lint` passes, `theses gaps` runs and lists the real gaps, and no node is `accepted`.

### 6.3 First claim check on the seeded map — [ ]
Class: review · Effort: medium · Needs: 6.2, 2.4, 3.4 · Check: `cd /home/sergei/projects/strebulaev-articles/articles.bridge_contract_for_agent_session_governance && python3 -m scripts.article claims quote-check --all`
Context: Decision 0067. Tier 1 is deterministic; tier 2 uses the claim-check skill; tier 3 is the owner's.
Do: Run tier 1 on every `source-claim` node and report `not-found` and `no-local-text` nodes to the owner; run tier 2 on `found` ones; list `overstates` and `contradicts`. Do not edit the paper.
Done-when: the owner has a list of failures and weak claims with node ids.

## 7. Regenerate the instruction file

### 7.1 Apply the activated guardrails (maintainer-only) — [!]
Class: implement · Effort: low · Needs: 2.2, 2.5, 2.6, 8.9 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && grep -q agent-nodes-need-human-promotion AGENTS.md && wc -l < AGENTS.md | awk '{exit !($1<=150)}'`
Context: `S/AGENTS.md` has a generated block between `go-getter:start` and `go-getter:end` ("Generated by `go-getter apply` from `docs/guardrails/`; do not edit this section"). The binary is `S/.go-getter/bin/go-getter` (not on PATH). The 150-line cap is guardrail `instruction-file-within-cap`.
Do: In `S`, run `.go-getter/bin/go-getter apply` once the three guardrails are active; do not edit the generated block by hand.
Done-when: the check passes.
Blocked: maintainer-only (`go-getter apply`); not run by a delegated agent. Also waits for 8.9. Guardrails `agent-nodes-need-human-promotion`, `theses-map-never-reaches-companion` and `claim-check-input-stays-local` are active in `docs/guardrails/` and ready for the maintainer to apply.

## 8. Lifecycle orchestration (decisions 0070 to 0072; scholar-mcp 0070)

Stages (names fixed by decision 0070): frame, map, discover, draft, verify-sources, adversarial, revise, release-gate, publish. Everything here ships in the vendored CLI `S/{{cookiecutter.repo_name}}/scripts/article/` (new `flow.py`) and the template, and must stay host-neutral.

### 8.2 `flow.yaml` schema and `flow status` — [ ]
Class: implement · Effort: medium · Needs: 8.1, 9.5 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_flow_status.py -q`
Context: Decision 0070: stored state is only round number, attestations and waivers (who, when, why), and budget used. Follow `schemas/*.schema.json` and `scripts/article/status.py` for JSON-first output.
Do: Add `schemas/flow.schema.json`, an initial `flow.yaml` in the template, and `flow status` printing per-stage gate results computed from the repo, each with a one-line reason and the failing command. No stored stage pointer.
Done-when: tests cover a fresh repo, a repo with map gaps, a stale check cache, and a waiver that expires; editing the paper outside the flow changes the output with no state update.

### 8.3 Order emitters per stage — [ ]
Class: implement · Effort: high · Needs: 8.2, 2.3, 2.4 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_flow_orders.py -q`
Context: Decision 0071. Orders reference node ids and procedure files; they carry no manuscript or source text (they point at slices).
Do: `flow next` prints the first open order for the earliest failing gate, as JSON validated against `schemas/flow-order.schema.json`. Idempotent: calling it again re-issues the same open order.
Done-when: tests cover one order per stage kind and the idempotent re-issue; order JSON stays under a size cap.

### 8.4 `flow done`, named checks, retry caps and budget — [ ]
Class: implement · Effort: high · Needs: 8.3 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_flow_done.py -q`
Context: Decisions 0071 and 0072; guardrails `flow-checks-are-named-not-supplied`, `flow-gated-stages-need-out-of-band-confirm`.
Do: A fixed table maps check names to argument vectors. `flow done <order-id>` accepts nothing else, runs the check, and records a pass in `flow.yaml`; a fail increments the order's retry count. Enforce unit weights, the round budget and the retry cap: past either, `flow next` returns a needs-human order carrying the failing output and node ids and refuses `large` orders. Gated orders are closed only through the terminal confirm path from step 8.8.
Done-when: tests cover an unknown check name, extra arguments, a retry cap hit, a spent budget refusing a `large` order, a crash between `next` and `done` (re-issued order, no double count), and a gated order refused without confirmation. Then set guardrail `flow-checks-are-named-not-supplied` to `active` in its file and `INDEX.md` row.

### 8.5 Review-round loop: ingest a review — [ ]
Class: implement · Effort: high · Needs: 8.4, 2.2 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_flow_round.py -q`
Context: A round replaces hand-written review-response plans. The review is local text (markdown or plain) given as a file; it is never sent anywhere (guardrail `claim-check-input-stays-local`).
Do: `flow round open --review <file>` increments the round, splits the review into items by a simple deterministic rule (headings or numbered list), and creates one `proposed` `objection` node per item with the item text as one line and a pointer to the review file and line. Triage (anchor, severity, which stage reopens) is then done by orders of tier `small`. `flow round close` requires the release-gate predicates and records the result.
Done-when: tests cover a numbered-list review, a heading review, a review with an injected instruction (treated as data, never an order field), and re-opening the same file (no duplicate nodes).

### 8.6 Parallel orders and map merges — [ ]
Class: implement · Effort: medium · Needs: 8.3 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_flow_parallel.py -q`
Context: Several agents may work at once; the map is one file (decision 0065).
Do: Mark orders `parallel-safe` only when their node sets and output files are disjoint. Make map writes touch only the named nodes and keep node order stable, so two branches editing different nodes merge cleanly. Document the rule for hosts: one working copy per concurrent order.
Done-when: tests show two disjoint orders marked parallel-safe and overlapping ones not; a git merge of two branches editing different nodes has no conflict.

### 8.7 Procedures and adapters for orders — [ ]
Class: implement · Effort: medium · Needs: 3.1, 8.3 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_skills.py tests/test_host_neutral.py -q`
Context: Fact 0008 gives the paths. Steps 3.2 to 3.4 write the red-team, blue-team and claim-check procedures there.
Do: Add the lifecycle procedure ("run `flow next`, do the order, `flow done`, stop on needs-human") at the neutral path, one thin adapter for Claude Code and an instruction-file pointer. Add `tests/test_host_neutral.py`: scan the rendered template for `go-getter` and model names; allow host-specific paths only in the adapter location.
Done-when: the tests pass; set guardrail `article-tooling-is-host-neutral` to `active` in its file and `INDEX.md` row.

### 8.8 MCP wrapper in scholar-authors — [ ]
Class: implement · Effort: high · Needs: 8.4 · Check: `cd /home/sergei/projects/sergemso/scholar-mcp && .venv/bin/python -m pytest tests/authors tests/guardrails -q`
Context: scholar-mcp decision 0070; patterns in `M/packages/authors/src/scholar_authors/repo_tools.py` (fixed argument vectors) and `release_tools.py` plus `scholar_core/confirm.py` (plan, hash, terminal confirm).
Do: Add `flow_status`, `flow_next`, `flow_done` with closed schemas (`flow_done` takes only an order id). Gated orders return a plan id and are closed by `scholar-authors confirm`. Fence order text that carries manuscript or registry strings. Add threat-model rows (smuggled check, gated order closed without confirm, injected order text) with named tests, and audit-log entries per call.
Done-when: the suite and `ruff check .` pass; each new threat-model row names a passing test; set the scaffold guardrail `flow-gated-stages-need-out-of-band-confirm` to `active` once its tests exist.

### 8.9 Upgrade delivery of flow — [ ]
Class: implement · Effort: medium · Needs: 8.4, 8.7, 5.1 · Check: `cd /home/sergei/projects/sergemso/article-scaffold && .venv/bin/python -m pytest tests/test_upgrade_apply.py tests/test_upgrade_user_owned.py -q`
Do: Make `flow.yaml` user-owned (like `metadata.yaml`); deliver `flow.py`, schemas, procedures and adapters through `upgrade`.
Done-when: an old rendered repo upgrades to include flow with its own `flow.yaml` untouched.

### 8.10 Acceptance replay on the article repo — [ ]
Class: review · Effort: high · Needs: 8.5, 6.2, 8.4 · Check: `cd /home/sergei/projects/strebulaev-articles/articles.bridge_contract_for_agent_session_governance && python3 -m scripts.article flow status`
Context: `A/docs/plans/review-response-v0.10.md` records a real review round (its items and fixes). Comply with `A/CLAUDE.md`: no counts of enumerable things, no draft-version references in anything you write; run `python3 scripts/lint-counts.py`.
Do: In a branch, run `flow round open` on a text copy of that review's item list, drive the loop with `flow next`/`flow done`, and compare the orders it issues and the gaps it finds against the hand-written plan. Record in `A/docs/notes/` which of the plan's items the flow found, missed, or found additionally, and what the weights cost in units.
Done-when: the note lists matches and misses with evidence; no paper text changed by this step.
