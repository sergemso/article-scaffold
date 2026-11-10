# Brief that fits the cap, and an `index slice` prompt: order 1 at cap 40

Date: 2026-11-10. Plan step 1.4, `docs/plans/token-economy-followup.md`.
Status: **one run per arm, no spread.** Read it as an indication only. The arms did
different amounts of work (see Caveats), so only the first segment is like for like.

## What was run

Order 1 (G-B1, G-B3, G-M1; base `5aeec5f`, outcome diff against `61f7781`, task hash
`f155607d…`) through `scripts/replay-order.py` at cap 40, cheap handoff, model
`claude-sonnet-5-5`, empty ledger. Three arms, same task text, same cap, same outcome check:

| Arm | Order file | Brief | Prompt tail |
|---|---|---|---|
| (a) | `order1.json` | pilot brief, 26 anchors, addresses only, 6749 bytes | default |
| (b) | `order1-fit.json` | six anchors with slices, 5521 bytes, not degraded | default |
| (c) | `order1-slice.json` | same as (b) | default plus one sentence: before opening any source file with sed, cat or Read, read the brief's symbols with `index slice NAME` (run `index` first if it says the index is stale) |

The six anchors of (b) and (c): `Bridge.attach` (Python), `Bridge::attach` (Rust),
`OperatorKey.grant`, `OperatorKey::grant`, `GrantVerifier for OperatorGrantVerifier::verify`,
`ClientKey::scheme`. They were chosen by hand from the pilot's 26 for the registry and grant
work; the brief keeps the pilot's row, notes and `max_calls` (60) so that only anchors and
slices differ. The default tail of every arm already said "read symbols with `index slice`
instead of whole files", so the pilot prompt had a weak form of (c)'s sentence.

All three worktrees had `paper/build/code-index.json` built before the run. It is gitignored,
so a fresh worktree has none and `index slice` fails with "index is missing"; the pilot
worktrees may have lacked it. Building it removes that excuse in every arm.

Counts come from the transcripts, one assistant message per `message.id`.

## First segment, like for like

| | (a) | (b) | (c) |
|---|---|---|---|
| Tool calls | 36 (stopped itself) | 43 | 43 |
| Cache-read tokens | 2.10M | 2.60M | 2.82M |
| Cache-read per call | 58K | 60K | 66K |
| `index slice` calls | 1 | 0 | 0 |
| `sed -n` reads | 22 | 29 | 25 |
| `cat`/`head`/`tail` of source files | 26 | 29 | 29 |
| `Read` calls | 0 | 0 | 2 |
| Slow-check calls | 17 | 19 | 24 |

The one `index slice` call of (a) was `index slice Bridge.attach | head -5` followed in the
same command by `sed -n 330,440p` on the file: a peek, not a change of reading habit.

## Whole runs

| | (a) | (b) | (c) |
|---|---|---|---|
| Segments (calls) | 1 (36) | 2 (43, 41) | 3 (43, 41, 35) |
| Cache-read tokens | 2.10M | 3.81M | 4.89M |
| `index slice` calls | 1 | 0 | 0 |
| Spend (USD) | 0.822 | 1.568 | 2.036 |
| Wall time, sum of segments | 552 s | 1409 s | 2993 s |
| Outcome checks | FAIL `mutation`, `mutation-rust`, `vectors-paper`, `cargo` | FAIL `mutation`, `vectors-paper` | all pass |

## What it says

1. **A brief that fits the cap did not make the agent use slices.** (b) had six slices in
   the brief and made no `index slice` call in two segments. It read source with `sed -n`
   and `cat` at the same or a higher rate than (a).
2. **A prompt sentence that names `index slice` as the first step did not either.** The
   transcripts confirm the sentence was in (c)'s prompt. (c) made no `index slice` call in
   three segments. An explicit instruction at the end of the prompt lost to the habit, as the
   `check` sentence did in step 1.2.
3. **File reads and cache-read did not fall.** Reads of source files are 29 against 26 in the
   first segment, and cache-read per call is 60K and 66K against 58K. Cache-read is higher
   in (b) and (c), mostly because they ran more calls. No arm is lower than the others by
   more than the spread could hide: step 1.2 recorded no spread, and the only noise
   figures there are pair differences of 14% and 40% between arms that did different work.
4. **The pilot's "never used" holds.** Across the three arms, 1 call of about 280 was an
   `index slice`, and it did not replace a read.

## Caveats

- **The arms did not do the same work.** (a) stopped at 36 calls by itself ("I stopped at
  the tool-call budget") with the Rust half, paper text and vector ranges undone; the CLI
  reported `success`, so the wrapper ran no handoff and no second segment. (b) hit the cap
  twice and was refused a third segment by the wrapper's spend reserve (1.57 + 1.2 against
  its 2.6 USD limit), so it also ended unfinished. Only (c) ran to completion. Whole-run
  totals and the outcome checks therefore say nothing about the briefs. The outcome checks
  of (b) were run afterwards on its worktree with no API spend.
- **The wrapper ends a run when the agent calls itself done, even a few calls under the
  cap.** The prompt line "If you reach the budget, stop and say so" produces it. This is a
  harness behaviour seen in step 1.2 and here; it is not changed in this step.
- The anchors were chosen by hand and the code index goes stale once a file is edited
  (`index slice` then says to rebuild it). Both are real costs of the feature; neither was
  the reason for the zero use, which no arm explained.
- One run per arm, no spread. Wall times include machine load and the outcome check is not
  in them.

## Decision for the plan

Neither (b) nor (c) helped: no `index slice` use, no fall in file reads or cache-read per
call. Per the done-when of step 1.4: **stop tuning briefs and anchors for token cost.**
`brief` anchors stay as a debugging aid (they print the addresses of the code a finding
names) and are not a token saving. The saving of the pilot came from the call cap and the
handoff, not from the stored or compiled material.

## Cost

Valid runs 4.426 USD of the 6 USD budget for 1.4: (a) 0.822, (b) 1.568, (c) 2.036. About
1.57 USD unspent.
