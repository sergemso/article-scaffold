---
id: 0009-flow-stage-and-gate-spec
title: Each lifecycle stage has a computable gate and a fixed set of order kinds; stages without a gate are human steps
status: active
date: 2026-11-02
tags: [orchestration, lifecycle, flow, gates]
---

## Fact

This is the specification that decisions 0070 to 0072 require before `flow` is built (plan steps 8.2 to 8.4, replay in 8.10). Gates are cheap deterministic predicates over the repo; none reads stored stage state. Commands marked *exists* run today in a rendered article repo; commands marked *planned* name the plan step that adds them and the test file that proves them. Evidence of the real loop (read, not copied): the review-response plans in the first adopter article repo, where each round was a hand-kept table of tasks with verification gates (a grep finds nothing, the layout check passes at a tolerance, a fix is present), and where a status column drifted from the paper.

### Stages

Tier hints: `script` (cost 0), `small` (1), `large` (5), as in decision 0072. Order kinds are the `kind` field of an order; a gated order is closed only by out-of-band confirmation (step 8.8).

| Stage | Entry condition | Gate predicate | Order kinds (tier, gated) |
|---|---|---|---|
| frame | always | `theses lint` finds at least one `thesis` node with status `accepted` (planned 2.2, `tests/test_theses_cli.py`) | `state-thesis` (human-only, no order is issued; `flow next` returns a needs-human order) |
| map | frame gate passes | `theses lint` exits 0 and `theses gaps` reports no `thesis-unsupported`, `objection-undefended` or `anchor-missing` gap (planned 2.2) | `fill-gap` (small); `triage-proposed` (script: lists `proposed` nodes for a human); `promote-node` (human-only, `theses accept`) |
| discover | map gate passes | no `source-claim` or `thesis` node has the gap `single-source` (planned 2.2) | `find-related` (small, procedure uses scholar-mcp discovery tools, step 4.2); `plan-add-reference` (small, gated: adding a reference needs the human pick) |
| draft | discover gate passes | `index --check` exits 0 (planned 2.3, `tests/test_section_index.py`) and `make validate` exits 0 (exists) | `write-section` (large); `reindex` (script: runs `index`) |
| verify-sources | draft gate passes | `claims quote-check --all` reports no `not-found` and the check cache holds a fresh `supports` verdict or a tier-3 attestation for each `source-claim` node (planned 2.4, `tests/test_claims.py`) | `quote-check` (script); `claim-check` (small, tier 2, step 3.4); `attest-claim` (human-only, tier 3, recorded in the map) |
| adversarial | verify-sources gate passes | each `thesis` node has at least one `objection` node with status `accepted` or `retired`, and every accepted `objection` has a `defense` edge (`theses gaps` kinds `thesis-unattacked`, `objection-undefended`; planned 2.2) | `red-team` (small, step 3.2); `blue-team` (small, step 3.3); `ingest-review` (script, `flow round open`, step 8.5) |
| revise | adversarial gate passes | `make validate` exits 0 (exists), `index --check` exits 0 (planned 2.3), and `python3 scripts/lint-counts.py` where the repo ships it (exists in the first adopter, not in the template) | `revise-section` (large); `fix-validation` (small) |
| release-gate | revise gate passes | `make validate` exits 0 (exists); layout check `python3 scripts/check_pdf_layout.py <pdf>` exits 0 where the repo ships it (exists in the first adopter, not in the template); `python3 -m scripts.article release --plan` reports no blocking item (exists); bibliography verification has a passing attestation (the human or MCP runs `verify_bibliography`; the CLI only reads the attestation recorded in `flow.yaml`) | `run-validation` (script); `verify-bibliography` (gated: run by the human or by `scholar-authors`, closed by confirmation); `formal-check` (script, named check from step 9.5, only where a repo declares one) |
| publish | release-gate gate passes | none computable. The deposit and the tag are irreversible and external | human-only: `flow next` returns a needs-human order pointing at `release --plan`; the apply step stays gated by the existing release confirmation |

Re-entry: gates are evaluated top to bottom on every `flow status`. The earliest failing gate is the current stage. Editing the paper after the adversarial stage makes the draft and verify-sources gates fail again with no state change.

### Human-only stages and steps

`frame` (choosing the thesis), `publish`, and the promotion, attestation and reference-pick orders have no computable success predicate beyond a recorded human act. They are expressed as needs-human orders, never as work an agent can close.

### Check names

`flow done` runs a fixed name-to-argument-vector table (step 8.4). Names used above: `theses-lint`, `theses-gaps`, `index-check`, `claims-quote-check`, `make-validate`, `release-plan`, `layout-check`. The last exists only where the repo ships the layout script; a missing script makes the check report `unavailable`, not pass.

### Order schema outline

```json
{
  "id": "string, stable: stage + kind + sorted node ids hashed",
  "stage": "frame|map|discover|draft|verify-sources|adversarial|revise|release-gate|publish",
  "kind": "string, one of the order kinds above",
  "nodes": ["theses node ids to read with `theses slice`"],
  "outputs": ["paths the order may change"],
  "tier": "script|small|large",
  "procedure": "path of the procedure file, or null",
  "check": "a name from the fixed check table",
  "gated": "boolean, true when closing needs out-of-band confirmation",
  "retries": "integer, failed attempts so far",
  "needs_human": "boolean, true when the order only reports evidence"
}
```

An order carries ids, paths and names only. It never contains manuscript or source text; the host reads slices through `theses slice` and `index` output.

### Determinism rules for gates

- A gate reads files in the repo and runs the named command; it makes no network call and no model call.
- A gate that depends on a check cache is fresh only when the cache key (hash of claim text plus excerpt) matches the current text.
- A waiver in `flow.yaml` (who, when, why, expiry) turns a failing gate into `waived` until it expires; it never hides the failure in the output.
