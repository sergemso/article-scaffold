---
id: 0084-dialectic-stage-is-order-driven-and-precedes-the-thesis
title: The dialectic stage issues work orders, runs before the thesis is fixed, and its gate demands development
status: draft
date: 2026-11-12
tags: [theses-map, lifecycle, dialectic, orchestration]
track: product
---

## Decision

Decision 0083 is amended in three ways; its sections, move types and required fields stand.

**Placement.** `dialectic` is the first stage, before `frame`. The stage applies when `flow.yaml` lists it under `required_stages` or when the map declares a contradiction or move; a map that does neither still sees no stage. The template ships `required_stages: [dialectic]`, so a new article cannot accept a thesis before its niche's tensions are mapped. An existing repo opts in by adding the line.

**Orders.** The stage is driven like every other stage (0071): `flow next` issues one order per gap, each with the `dialectic` procedure, tier `small`, check `theses-lint`, outputs `theses.yaml`. The order kinds are fixed: `map-contradictions` for the gap `niche-unmapped` (the stage applies and no live contradiction exists while the repo holds at least one `source-claim` node or one stored source), `move-contradiction` for `contradiction-unmoved`, `develop-move` for `move-without-opening` and `opening-undeveloped`, `trace-thesis` for `thesis-untraced` and `thesis-restates-pole`. Two orders are human-only: `ground-niche` when the stage applies but the repo holds no source and no source-claim (nothing to anchor a pole to), and `promote-dialectic` when the only remaining items are `proposed` (a person runs `theses accept` and `flow attest dialectic`). `theses add` and `theses accept` handle contradictions and moves, so an agent can write a proposal and a person can promote it with one command (0066).

**Development, not restatement.** Three structural checks are added so that the chain cannot close on one pole. The gap `thesis-restates-pole` fires when a thesis opened by an `opening` has the same text, after case, punctuation and whitespace folding, as a pole of a contradiction in its chain, or is contained in one. The gap `opening-undeveloped` fires when the citation chain behind an `opening` holds no `synthesis`, `aufhebung` or `negation-of-negation`: a thesis opened straight from a bare negation is the other pole. The lint error T095 rejects an `aufhebung` whose `lifted` equals its `preserved` or `cancelled` or a pole text. The gate of the stage passes when no dialectic gap remains and a person has attested the stage, as in 0083.

## Why

0083 promised a stage "before the thesis is fixed" but placed it after `frame`, whose gate is an accepted thesis; because the earliest failing gate is the current stage, the dialectic never ran first. The stage also issued no orders and was off until someone hand-wrote a contradiction, so nothing in the flow ever asked for one: the stage could be skipped without a trace. The first adopter's handoff (`docs/notes/paper-workflow-knowledge-first-handoff.md`) shows what that costs: claims chosen before the field's tensions were mapped, then rewritten to meet a score. A structural linter cannot judge whether a synthesis is sound, but it can refuse the two cheapest fakes, a thesis that repeats a pole and an opening with no synthesis behind it, and it can make every unmoved contradiction a standing order. Placing the stage before `frame` for every repo was rejected: a legacy map with no section keeps its `flow status` unchanged. A default of advisory in the template was rejected: an advisory stage issues no orders, so the guarantee would hold only for authors who already wanted it.

## Consequence

`flow.py` gains the stage ordering, the applicability rule, six order kinds and the row mappings for the brief; `dialectic.py` gains three gap kinds and one error; `theses.py` gains add and accept for the two sections; fact 0009's table gains the row; the procedure becomes order-driven; the template `flow.yaml` requires the stage; `upgrade --plan` prints an adoption notice. Containment and folded equality are the whole of the restatement check; a paraphrase passes it, and the reviewer still reads the chain.
