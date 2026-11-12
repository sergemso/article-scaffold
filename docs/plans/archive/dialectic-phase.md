# Dialectic phase: contradictions, moves and TRIZ in the theses map

Archived 2026-11-12: every step is done and shipped in template 1.10.0. Decision 0084 amends 0083 (placement, orders, development checks); the follow-up plan is `docs/plans/dialectic-guarantee.md`.

Repo: `/home/sergei/projects/sergemso/article-scaffold` (a cookiecutter template; run Python from the venv: `make setup`, then `.venv/bin/python -m pytest <file>`; `make lint` runs ruff). Template tree is `{{cookiecutter.repo_name}}/` (quote it in shells). Code lives in `{{cookiecutter.repo_name}}/scripts/article/`, schemas in `{{cookiecutter.repo_name}}/schemas/`, tests in `tests/`.

This plan implements decision 0083 (below), accepted by the owner on 2026-11-11. It extends 0065 to 0076 and follows the pattern of 0073.

Constraints for every step: every new field is optional so a `version: 1` map stays valid; the stage is off unless `theses.yaml` declares a contradiction; no network in the new code (`tests/test_no_network_in_claim_code.py`); nothing shipped to an article repo names go-getter, a model or one agent host, and philosophers appear only as vocabulary (guardrail `article-tooling-is-host-neutral`); agents propose and humans promote (guardrail `agent-nodes-need-human-promotion`); `theses.yaml` and `flow.yaml` belong to the author and `upgrade` never overwrites them. Commit messages are Conventional Commits with a `Refs:` trailer. Stay out of `AGENTS.md`'s generated guardrail section.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked, `[>]` moved.

## Decision 0083 (as drafted; the accepted text is docs/decisions/0083-dialectic-stage-maps-contradictions-and-typed-moves.md)

Status: draft, awaiting the owner. Tags: theses-map, lifecycle, dialectic, triz. Track: product.

**Decision**

The lifecycle (0070) gains an advisory stage `dialectic` between `frame` and `map`. The theses map gains two optional sections.

`contradictions`: id, two `poles` (each anchored to a `source-claim` or a niche statement), `kind` (`dialectical`, `technical`, `physical`), `status`, `author`. A TRIZ contradiction may add `improving` and `worsening` (free-text parameters), `principle` (optional tag from a shipped closed list of the 40 inventive principles), `ideal-result` and `resources`. No parameter or principle matrix lookup in the first version.

`moves`: typed steps over contradictions, with a closed `type` list: `negation`, `negation-of-negation`, `synthesis`, `aufhebung`, `opening`. `aufhebung` is first-class and must record `preserved`, `cancelled` and `lifted`. A `synthesis` or `aufhebung` cites at least two contradictions or moves; a `negation-of-negation` cites a prior `negation`; a `opening` names the thesis or question node it opens. A `development` view (the chain of moves in order) is derived by `theses`, not stored.

`theses lint` checks structure only: references resolve, poles are anchored, move types carry their required fields, no cycles in the move chain. `theses gaps` adds kinds `contradiction-unmoved`, `move-without-opening` and `thesis-untraced` (a thesis with no `opening` or recorded reason). The gate of the stage passes when there are no such gaps and a human has attested the stage (`flow attest`); soundness of a synthesis is judged by a person. A procedure in `docs/procedures/` and a `dialectic` skill adapter have an agent run niche and topic analysis over sources already in `paper/sources/` and propose contradictions and moves as `proposed` nodes.

**Why**

A thesis chosen before the niche's tensions are mapped tends to restate one pole. Keeping the moves as typed nodes lets objections and arguments (0073, 0074) target them and lets `theses gaps` show what is still unresolved. Making the stage advisory and opt-in keeps existing article repos passing. Free-text TRIZ parameters were chosen over the full matrix because the matrix is large and mostly useful in technical domains; a tagged principle can be added later without a schema break. `aufhebung` as a mere tag on `synthesis` was rejected: the three required fields are the point of the concept and only a first-class type can be linted.

**Consequence**

Schema, linter, gap kinds, the shipped principle list, one procedure, one skill adapter and an upgrade/adoption note are needed. A repo that never declares a contradiction sees no change. Whether a synthesis is philosophically sound stays a human judgment.

## 1. Schema and structural lint

### 1.1 Contradictions section — [x]
Class: implement · Effort: medium · Needs: none · Check: `.venv/bin/python -m pytest tests/test_theses_schema.py tests/test_dialectic.py -q`
Decision: 0083. Scope: `schemas/theses.schema.json`, `scripts/article/theses.py`, new `scripts/article/dialectic.py`, `schemas/triz-principles.json`, `theses.yaml` template comments.
Do: Add the `contradictions` section and its TRIZ fields; ship the closed list of 40 principles; lint pole anchors, kind rules and `principle` membership.
Done-when: each rule has a failing and a passing test, and an existing map validates unchanged.

### 1.2 Moves section — [x]
Class: implement · Effort: medium · Needs: 1.1 · Check: `.venv/bin/python -m pytest tests/test_dialectic.py -q`
Decision: 0083. Scope: same files as 1.1.
Do: Add `moves` with the five types and their required fields (`preserved`/`cancelled`/`lifted` for `aufhebung`, citations for `synthesis`, a prior `negation` for `negation-of-negation`, an opened node for `opening`). Lint references and cycles. Derive the development chain.
Done-when: every move type has a valid and an invalid fixture; the cycle check has a test.

## 2. Gaps, gate and CLI

### 2.1 Gap kinds and `theses dialectic` view — [x]
Class: implement · Effort: medium · Needs: 1.2 · Check: `.venv/bin/python -m pytest tests/test_dialectic.py tests/test_theses_cli.py -q`
Decision: 0083. Scope: `scripts/article/theses.py` (`gaps`), `scripts/article/cli.py`, `scripts/article/dialectic.py`.
Do: Add the gap kinds `contradiction-unmoved`, `move-without-opening`, `thesis-untraced` (only for maps that use the section). Add a read-only `theses dialectic` command printing contradictions and the move chain, with `--json`.
Done-when: gaps appear only when the section is used; output is deterministic.

### 2.2 Advisory lifecycle gate — [x]
Class: implement · Effort: medium · Needs: 2.1 · Check: `.venv/bin/python -m pytest tests/test_flow.py -q`
Decision: 0083 with 0070. Scope: `scripts/article/flow.py`, `schemas/flow.schema.json`.
Do: Add stage `dialectic` before `map`, advisory by default, computed from the gap kinds plus a human attestation; `flow.yaml` can promote it to required. A repo without contradictions skips the stage.
Done-when: `flow status` on an existing repo is unchanged; a repo with an unmoved contradiction shows the stage open.

## 3. Procedure

### 3.1 Dialectic procedure and skill adapter — [x]
Class: implement · Effort: medium · Needs: 2.1 · Check: `.venv/bin/python -m pytest tests/test_theses_cli.py -q`
Decision: 0083. Scope: `{{cookiecutter.repo_name}}/docs/procedures/dialectic.md`, `{{cookiecutter.repo_name}}/.claude/skills/dialectic/SKILL.md`.
Do: Write the host-neutral procedure: niche scan and topic scan over sources already in `paper/sources/`, propose contradictions (with poles anchored), propose moves, leave everything `proposed`, ask a human to accept. Keep the skill a thin pointer like `lifecycle`. Note that `add_nodes` writes flat scalar fields only (see 1.1 of the theses plan), so state how proposals are written until that is fixed.
Done-when: the procedure covers each move type; no shipped file names go-getter, a model or one host.

## 4. Delivery

### 4.1 Upgrade note, companion check, full suite — [x]
Class: review · Effort: low · Needs: 3.1, 2.2 · Check: `make test && make lint`
Human: tagging and pushing needs the owner's explicit go-ahead. Status: tagging/push awaiting owner; version not bumped, CHANGELOG item is under Unreleased.
Do: Add the adoption note (once per feature), confirm `upgrade` leaves `theses.yaml` alone and the companion excludes nothing new that it should keep out, then run the whole suite and lint and prepare the version bump.
Done-when: `make test` and `make lint` pass and the release notes list decision 0083.
