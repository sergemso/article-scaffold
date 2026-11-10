# Evidence-bearing handoff: order 3 at cap 40

Date: 2026-11-10. Plan step 1.3, `docs/plans/archive/token-economy-followup.md`.
Status: **one run of the new variant**, compared with runs of the other two variants that
were made for other reasons. One run per arm; the spread is unmeasured. Read it as an
indication.

## What was built

- `flow-handoff.schema.json` and `handoff.py` accept an optional `evidence` list: at most 50
  single-line strings of at most 200 characters, stored sorted and deduplicated, left out
  when empty. The CLI refuses a line that names a model or a vendor (the schema states the
  shape only). Tests: `tests/test_flow_handoff.py`.
- `scripts/replay-order.py --handoff evidence`: when a segment reaches its cap, the wrapper
  resumes that session once, with no tools and at most two turns, and asks for JSON with
  `done`, `remaining`, `verify` and one `evidence` line per done item (the command run and
  its result, or `not-run`). It adds the diff-derived fields itself. `--continue` resumes an
  interrupted run from its last saved handoff. `--handoff evidence` became the default afterwards (2026-11-11).
- A bug found on the way: a resumed session reports its **cumulative** cost, so the wrapper
  charged each evidence handoff with its whole segment again (0.82 and 0.44 USD recorded
  against 0.023 and 0.020 USD real) and refused segment 3 against the spend limit. The
  wrapper now keeps only the marginal cost. The run's `spend.json` was corrected by hand to
  the marginal figures, and segment 2's saved handoff was rebuilt from its saved reply
  (the saved file is truncated) before `--continue`.

## The run

Order 3 (`scripts/replay-orders/order3.json`, task hash `841fde17…`, brief hash
`7f1ed1c5…`), base `5aeec5f`, cap 40, empty ledger, `--handoff evidence`, model
`claude-sonnet-5-5`. Three segments (40, 40 and 12 calls), then the outcome check: **all ten
checks pass**, 10 test, vector or mutant files changed. Spend 1.379 USD (assumed prices);
wall time of the segments 2404 s.

Handoff after segment 1: 8 done items, 7 evidence lines, 8 remaining. It stated that
`pytest` ran before the later edits, that the mutation runs were started but their results
were not read, that `make measurements`, `lint-counts`, `make validate` and the rest were
`not-run`, and that the failing-test-first step was never done as a separate run. Handoff
after segment 2: 8 done, 6 evidence lines, 11 remaining (it named a mutation harness miss
and an unread Rust mutation result as open).

## Three variants side by side

| | resume (pilot, order 3, cap 60) | cheap (E.5, order 3, cap 60 / cap 40) | evidence (this run, cap 40) |
|---|---|---|---|
| Handoff cost | 1.37 USD | 0.015 USD / 0.013 USD | 0.023 and 0.020 USD (two handoffs) |
| Handoff call | resume of 139K context | fresh, 4K context | resume, 92K cache-read, 1.2K output |
| Segment 2 calls | 13 | 15 / 26 | 40 (then a third segment of 12) |
| Outcome checks | all pass | all pass | all pass |
| States what was not verified | the agent did, in prose | no: turned done work into "confirm" items | yes: `not-run` lines |

Same-setup cheap runs of this session (order 3 at cap 40, empty ledger, other runs of
`docs/notes/warm-ledger-round.md`): segment 2 had 40 and 24 calls, all outcome checks pass.

Commands run by segment 2 that repeat a family of checks from segment 1 (a count of Bash
calls, not of claims; some re-runs are legitimate after further edits):

| | `pytest` | `run_vectors` | `cargo test` | mutation (py / rust) | measurements | validate or lint |
|---|---|---|---|---|---|---|
| evidence, segment 2 | 2 | 0 | 2 | 3 / 2 | 5 | 3 |
| cheap, segment 2, first run | 4 | 8 | 2 | 3 / 5 | 8 | 4 |
| cheap, segment 2, second run | 3 | 7 | 1 | 1 / 5 | 6 | 5 |

The "number of segment 1 claims segment 2 re-checked" asked for in the plan could not be
measured cleanly: the agents edit through Bash, so there is no edit boundary to split
"verify first" from "work", and a re-run after new edits is not a re-check. The counts
above are the closest honest measure. The evidence segment 2 did not re-run the vector
modes that its handoff reported as passing; the cheap segments re-ran them 7 to 8 times.

## Reading

1. **The evidence handoff costs about 0.02 USD more than the cheap one and about 98% less
   than the resume of the pilot.** The pilot's 1.37 USD reply was mostly cache creation
   (E.5 part 1); this resume read 92K cached tokens and wrote 1.2K, so the cost depends on
   how much of the context is still cached when the final turn is sent. That was true in
   this run; it is not shown for a slower hand-over.
2. **It closes the gap E.5 found.** The gap was that the cheap handoff could not say what
   was verified. The evidence lines name what ran, what passed before later edits, what
   was not run, and what was never done (failing test first). That is the content the
   next segment needs to avoid redoing, or wrongly trusting, segment 1.
3. **Segment 2 ran no fewer calls.** It used the whole cap (40) and a third segment
   finished the work, because the work remaining was large. One run cannot say whether the
   evidence changed the number of calls.
4. **Parity held.** All ten outcome checks pass. Evidence lines are the agent's own
   statements; a wrong one would not be caught here.

**Default:** make the evidence handoff the default for capped runs (cost +0.02 USD, closes
the stated gap, outcome parity). The wrapper default was `cheap` when this note was
written; it is now `evidence` (2026-11-11), and `--handoff cheap` selects the old one.

## Refit of the threshold

`context-threshold.py` on the three segments of this run (92 calls): start context 13.7K,
growth 1.44K tokens per call (E.5 part 2: 27K and 2.06K). H of the evidence handoff in
cache-read equivalents, with the assumed price ratios (creation 12.5, output 50 times a
cache-read token): 91.7K + 0.7K x 12.5 + 1.2K x 50 = about 160K.

| H | n* (calls) | threshold (tokens) |
|---|---|---|
| 0.16M (evidence handoff, direct) | 15 | 35K |
| 0.10M | 12 | 31K |
| 0.50M | 26 | 52K |
| 2.00M (resume) | 53 | 89K |

On token cost alone the optimum falls to about 15 calls with this handoff. **The cap of 40
still holds**, for three reasons: the fit is one run with a lower growth than the earlier
fit, H leaves out the cost of segment 2 re-orienting itself, and the model has no term for
quality drift or for the extra handoffs each shorter segment adds. Caps below 40 are untested
and this note does not recommend them.

## Cost

Run 1.379 USD of the 4 USD budget for 1.3 (about 2.6 USD unspent). No second run, so no
spread.
