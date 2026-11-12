---
id: 0085-flow-outcomes-ratchet-and-reframing-needs-a-cause
title: An order cannot close by lowering what was accepted, and an accepted node changes only with a recorded cause
status: draft
date: 2026-11-12
tags: [orchestration, flow, theses-map, quality]
track: process
---

## Decision

**Ratchet on close.** When `flow next` issues an order it records, in the order's entry in `flow.yaml`, a hash of the accepted set: the sorted pairs of id and text of every `accepted` node, contradiction, move and term. `flow done` recomputes the hash. If any node that was accepted at issue is now missing, `retired` or `proposed`, or its text differs, the close fails and names the ids; the failure counts against the retry cap like a failed check. A person may still retire or rewrite an accepted node, outside an order, with the command below.

**Acceptance is recorded.** `theses accept` writes a ledger entry (0079) of kind `accept` with the node id, the text hash, who accepted and, optionally, `because: <id>` naming an objection, contradiction, move or source-claim. `theses lint` compares each accepted node's text hash with its latest acceptance record: a mismatch is the error T096, cleared only by `theses accept <id> --by NAME --because <id>`, so a thesis changes only with a named cause in the map. A node accepted before this decision has no record; lint reports that as a note, not an error, until the next `theses accept` records one.

**The outcome is visible.** `flow status` reports a `quality` vector computed from the repo: accepted theses, theses opened by an accepted opening, contradictions moved, source-claims with a fresh verdict or attestation, objections defended, gaps by kind. It is derived, never stored, and the stage table is unchanged.

**Derived files do not burn retries.** The section index is a derived file; `flow next` and `flow done` refresh it when stale before `index-check` runs, so a `reindex` order never reaches the retry cap.

## Why

Gates re-fail when the paper regresses (0070), but nothing stopped an order from closing its own gap by degrading something else: retiring an objection closes `objection-undefended`, and rewriting an accepted thesis to fit a score closes nothing yet costs the argument. The first adopter did exactly that twice (`docs/notes/paper-workflow-knowledge-first-handoff.md`, items 1 and 7): the claim set was rewritten to move a review mean, and the mean never moved. The same handoff shows a plain `reindex` order reaching the retry cap and stalling the loop on a file the flow could have rebuilt. A stored high-water mark per stage was rejected: it is a second source of truth beside the repo. A ledger-keyed acceptance record was chosen over a hash field in the node because the map file belongs to the author and a hash in it would be edited by hand. Requiring a cause for a change is the smallest form of the handoff's item 7: a claim may change only with a new objection or a new piece of evidence.

## Consequence

The ledger gains the kind `accept`; `theses accept` gains `--because`; `theses lint` gains T096; the order entry in `flow.yaml` gains `accepted_hash`; `flow-status.schema.json` gains `quality`; the lifecycle procedure tells an agent what to do when a close fails on the ratchet (stop and report; never retire or edit what it did not write). An author who rewrites an accepted thesis by hand sees a lint error until they name the cause.
