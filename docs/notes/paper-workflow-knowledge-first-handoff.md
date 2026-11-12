# Handoff for article-scaffold: make the workflow produce knowledge, not scored text

From: the deterministic-edge paper repo, 2026-11-11. Status: **a proposal for the scaffold owner, not applied.** The scaffold repo (`~/projects/sergemso/article-scaffold`) was not edited from here, and nothing here is sent without the owner's yes. It complements `scaffold-change-request.md` (2026-11-04: four small CLI and schema items); this one is about the process.

## What went wrong on this paper (evidence)

1. **The score gate drove the claims.** Score 0 (5.0), score 1 (5.3), score 2 (4.0), score 3 (4.9) on four claim sets; the claims were rewritten twice (C1 to C5 revised, then the enforcement-gradient reframing, `thesis-change-request-enforcement-gradient.md` section 1 names score 1 as the trigger) and the mean never left 4 to 5. The reframing chose the claims the data could back soonest (a census of 8 repos), not the ones the system exists for.
2. **The gate is uncalibrated.** Seven published source papers scored by the same protocol (text only, 3 blind reviewers each) have a mean of 5.9, a best of 7.0, and every one has defensibility at 5.7 or below. Our paper: 4.3. A gate of "mean 8, no dimension below 6" cannot be met by the reference set (`docs/plans/deterministic-edge-article-score-comparison.md`).
3. **Claims came before evidence.** `flow next` opens at `stage: frame`, kind `state-thesis`. Nothing asks what is measured about the system before a thesis is accepted. The system's own headline (5 to 10 times fewer human minutes per merged outcome, go-getter decision 0154) is a target; its baseline is an estimate (fact 0040: "an estimate, not a measurement"; owner attention 20 h stated, 3.7 h measured). The paper's registered test of it (AT4) asks for a 20 percent drop.
4. **Registered predictions did not test the goal.** Nothing checks that a registered prediction is the size of the goal it serves.
5. **A full paper was drafted around pending results.** AT1 to AT4 were all "pending" in three scoring rounds; completeness stayed at 3 to 4.5. The scaffold has no paper kind for "design registered, results pending".
6. **Scoring used one family.** Reviewers were Claude contexts; the one cross-family reviewer per round hit a flaky endpoint, and the cross-family classifier script is not in the repository (only its output, `data/census/xfamily_evidence.csv`, is). The rescore reviewer script was written ad hoc in a scratch directory.
7. **Flow friction.** `index-check` fails whenever a section is newer than `paper/build/section-index.json`; the retry cap (3) was reached on a plain `reindex` order and produced a `needs-human` order that one command (`scripts.article index`) cleared. Number provenance is free text: nothing distinguishes a measured number from an estimate in a headline.

## Proposed changes (smallest first)

1. **`flow` runs `index` itself** before `index-check`, or the error names the command and does not count against the retry cap.
2. **Provenance class on numbers.** Each number in `data/` or a claim carries `measured | estimated | asserted` (a column in the provenance header). `theses lint` fails an accepted claim whose headline number is `estimated` or `asserted` without that word in its text.
3. **Goal link on registered predictions.** A registered test names the goal or decision it tests and the goal's effect size; `theses gaps` flags a prediction whose threshold is below the goal's floor, as AT4 (20 percent) against the go-getter floor (5 to 10 times).
4. **Evidence stage before the frame stage.** New stage `evidence` with a table `evidence.yaml`: source, what it measures, provenance class, denominator, limits, what claim it could support, strength. `state-thesis` is blocked until at least one row is `measured`, and an accepted thesis must cite rows. The scaffold reads code, decisions and intents of the system; the owner is not asked which claim a datum supports.
5. **Paper kinds.** `kind: measurement-study | experience-report | registered-report | position`, each with a minimum: a registered report may leave results pending but must say so in the title and abstract and does not claim effects; an experience report must carry a measured baseline and a stated n. Review rubrics depend on the kind (the generic five dimensions penalise a measurement study on novelty).
6. **Reference-set calibration (`score --calibrate`).** Run the scoring protocol on the related-work papers whose text is in `paper/sources/` and report the table. The release gate is set against that table (for example "at or above the reference median, no dimension more than one below the reference median"), written in the plan before the first score. Protocol that worked here: pdftotext of each paper, title, authors and system names removed, opaque file names, three fresh reviewers per paper, same prompt, no repo access, integer 0 to 10 on five dimensions with a locator for each deduction.
7. **Scoring finds defects; it does not gate framing.** Allow review rounds to feed proposed objections (already exists) but remove claim switching as a response to a mean. A claim set may change only with a new evidence row or a new objection, recorded in the dated entry with the evidence row id.
8. **Cross-family reviewer as a script in the scaffold**, with streaming, a wall-clock deadline, token budget, endpoint fallback, and the raw reply saved. Classifier and review scripts used for a number in the paper must be committed (a `check` fails a data file whose provenance names a script that is not in git).
9. **Claim-set versions.** `theses` records a version per accepted claim set and `score` files name the claim-set version they were run on, so scores across a reframing are comparable (this note's table had to be rebuilt by hand).

## Acceptance for the scaffold owner
- A new paper in the scaffold cannot reach `state-thesis` without an evidence table that has a measured row.
- `score --calibrate` prints a table for the reference papers and writes the gate into the plan.
- This repo's history can be replayed to show the same stop at items 2, 3 and 4 (the AT4 20 percent against the 5 to 10 times floor; the 45 man-hour estimate).

## Not proposed
- Raising or lowering the gate to make a given paper pass.
- Changing what an accepted claim says without the A12 gate.
