# E.3 pilot: one review order, old flow against the new flow

Date: 2026-11-08. Plan step: E.3 (stage 2), `docs/plans/token-economy-ledger.md`.
Status: **one order, one run per arm, and the `old` arm was not re-run.** The
comparison is against the historical transcript of the same order. Read it as
an indication, not a measurement of a saving.

## What was compared

The order: findings G-B1, G-B3 and G-M1 of review 3 of the bridge-contract
article, base commit `61f7781`.

- **Baseline (`old`):** the 167-call agent `agent-ae2c061143d2e5e4a` of session
  `ccc79cc9` (the historical fix round), one continuous run.
- **`new`:** same task text plus a brief compiled by `brief.py` (26 anchors, over
  the 6000-byte cap, so addresses only), a 60-call segment cap, and a handoff
  between segments. Model `claude-sonnet-5-5`; the empty ledger of commit
  `5aeec5f`. Fix committed in its worktree as `630a6d7`.

Figures come from the two transcripts, one assistant message per `message.id`
(content blocks merged, usage taken from the last line). Script:
`proxies.py` in the session scratchpad (not committed).

## Figures

| Proxy | old (167 calls) | new, segment 1 (61 calls) | new, segment 2 (18 calls) |
|---|---|---|---|
| Cache-read tokens, whole run | 34.15M | 6.32M | 0.33M |
| Cache-read tokens, first 61 calls | 7.42M | 6.32M | |
| Mean cache-read per call, first 61 | 121.7K | 103.7K | 18.6K |
| Context at call 61 | 177K | 184K | 34K (at call 18) |
| Maximum context | 300K | 184K | 34K |
| Tool calls | 177 | 62 | 18 |
| Whole-file `Read` calls | 3 | 0 | 0 |
| `sed -n` range reads, per call | 0.27 | 0.49 | 0.39 |
| `cat`/`head`/`tail` of a source file | 26 | 17 | 4 |
| `index slice` calls | 0 | **0** | **0** |
| Calls running a slow check or suite | 41 | 33 | 8 |
| First `git status`/`diff` calls after resume | | | the first call |

Whole run, new: 6.66M cache-read against 34.15M (about 80% lower), over 80
calls against 167. The first-61-call figure is the like-for-like one: 14.8%
lower, at the plan's 15% line, so it neither clears nor fails the stop rule.

Segment 1 spent 1.80 USD (reported by the CLI), the handoff reply 1.84 USD, and
segment 2 0.24 USD: 3.88 USD with the handoff, 2.04 USD without. The handoff
used `--resume`, which re-sends the whole segment 1 context, so it cost as much
as the segment. Its tokens are not in the segment transcripts and are not in the
table above. **Dollars are secondary:** both arms ran `claude-sonnet-5-5` (checked in the
transcripts), but the price row is assumed list prices, and the handoff cost is a
resume artefact.

## Reading

1. **The saving is the segment reset, not the briefing.** Over the first 61
   calls the two runs are close (-15% cache-read, context 184K against 177K).
   The difference appears afterwards: the baseline kept growing to 300K over
   106 more calls (26.7M cache-read), while segment 2 started at about 34K and
   needed 18 calls. Capping and handing off bounds the context; it did not make
   the first 60 calls cheaper.
2. **The anchors and `index slice` were not used.** Neither segment ran
   `index slice`; the agent read ranges with `sed -n` and `cat` as before, at a
   higher rate per call in segment 1. The brief was addresses only because it
   was over the cap, and the agent used `Bash` for everything (no `Read` or
   `Edit` calls at all). So this pilot says nothing in favour of the anchor
   slices. A brief that fits the cap, or a prompt that makes `index slice` the
   first step, is untested.
3. **The ledger did nothing here.** It started empty, and the slow checks were
   run (33 calls in segment 1) because nothing had recorded them. The pilot does
   not test the ledger; the earlier estimate (below 1% of cache-read) stands.
4. **Handoff worked, with a caveat.** Segment 2 went straight to the remaining
   work: its first call was `git status`/`diff --stat`. But the handoff was
   rebuilt by the wrapper from the worktree (the agent's own reply was not saved
   by the first version of `run_arm.py`), and it listed files only, with nothing
   marked done or remaining. The agent recovered the state from the diff.
5. **The cap was advisory and the agent reached it.** Segment 1 ended at the
   60-turn limit with work in progress, as designed.

## Outcomes (not lost)

Run in the `new` worktree by `outcome_check.sh`: pytest `conformance_suite.py`
152 passed; `mutation_check.py` 121 of 121 killed; `mutation_check_rust.py`
33 of 33 killed; `run_vectors.py` plain, `--wire` and `--check-paper` pass;
`cargo test` passes; `lint-counts.py` and `scripts.article validate` pass; 15
test, vector or mutant files changed. The agent reports G-B2 (unauthenticated
`add_client`) as not fixed; it was not in the task.

Limits on parity: the baseline agent's result was not run through the same
check, and neither diff was compared with the reference fixes (`9ef3966`,
`5834582`). The agent states its new tests were written before the fix, but did
not re-run them against the old code to confirm they fail there.

## Order 2: F-1 and F-5 of review 2

Baseline: agent `agent-a5474c215d6773417` of the same session (105 calls), base
commit `dad3897` (last master commit before it started). Same protocol as
order 1: tooling overlay with an empty ledger, brief of 14 anchors (addresses
only, 4 KB), 60-call advisory cap, agent's own handoff to be saved. Fix committed
in its worktree as `dfb36ea`.

| Proxy | old (105 calls) | new (60 calls, one segment) |
|---|---|---|
| Cache-read tokens, whole run | 14.51M | 4.98M (65.7% lower) |
| Cache-read tokens, first 62 calls | 6.51M | 4.98M (23.6% lower) |
| Mean cache-read per call | 105.1K | 83.0K |
| Context at call 62 / maximum | 159K / 209K | 130K / 130K |
| `sed -n` range reads | 32 | 26 |
| `cat`/`head`/`tail` of a source file | 21 | 10 |
| `index slice` calls | 0 | **0** |
| Calls running a slow check or suite | 26 | 41 |

The run finished by itself at 62 turns (`success`), so **no handoff happened and
the cap never forced a reset.** Cost 1.40 USD (assumed prices).

Outcomes, by `outcome_check.sh`: pytest, both mutant sets, the three vector
modes, cargo test, `lint-counts` and `validate` all pass; 6 test, vector or
mutant files changed; the agent reports F-1 and F-5 done with the TLA+ files and
`flow.yaml` untouched. Same limits on parity as order 1 (no diff against a
reference fix).

Reading: here the saving is **fewer calls, not a context reset** (60 against
105), and per-call context was also lower (83K against 105K). The pilot cannot
say why. Candidates, none isolated: the advisory budget text in the prompt, the
brief and guardrail digest, the empty-ledger tooling in the worktree, or run
to run variance (one run per arm, so variance is unmeasured). The agent again
ran no `index slice`, and ran more slow checks (41 against 26) because the ledger
was empty. Order 1 and order 2 together: the new arm used fewer calls and less
context in both, with outcomes intact, but only order 1 involved a handoff.

## Order 3: G-B2, G-M3, G-M5 and minor items of review 3 (with a handoff)

Baseline: `agent-a86c5a470c782b78e` (174 calls, the largest of the round), base
`61f7781` (the order 1 base, so the order 1 overlay commit `5aeec5f` was used).
The concurrency and push instructions were removed as before. This time the
agent's own handoff reply was saved and passed to segment 2 unchanged by the
wrapper. Fix committed in its worktree as `1a60645`.

| Proxy | old (174 calls) | new, segment 1 (62) | new, segment 2 (13) |
|---|---|---|---|
| Cache-read tokens, whole run | 33.22M | 4.83M | 0.14M (4.96M total, 85.1% lower) |
| Cache-read tokens, first 61 or 62 calls | 6.60M | 4.83M (26.8% lower) | |
| Mean cache-read per call, first 61 or 62 | 108.1K | 77.8K | 10.6K |
| Context at call 61 or 62 / maximum | 167K / 288K | 139K / 139K | 17K / 17K |
| `sed -n` range reads | 60 | 30 | 2 |
| `cat`/`head`/`tail` of a source file | 17 | 13 | 5 |
| `index slice` calls | 0 | **0** | **0** |
| Calls running a slow check or suite | 58 | 28 | 10 |

Segment 1 stopped at the 60-turn limit (61 turns); segment 2 finished in 14 turns
and reported the work committed. Cost by the CLI: segment 1 1.32 USD, handoff
reply 1.37 USD, segment 2 0.15 USD (assumed prices). The handoff reply costs as
much as the segment, as in order 1 (a `--resume` re-sends the context).

Handoff content: the agent's reply was JSON with `done` and `remaining`, but
long prose strings rather than anchor names. `remaining` listed eleven items
(commit, re-run suites, regenerate the vector table, mark the plan, a
limitations row, and so on). Segment 2 opened with `git status` and a grep of the
plan section, then worked through them; it did not redo the done items.

Outcomes (`outcome_check.sh`): pytest, both mutant sets, the three vector modes,
cargo test, `measure_faults.py --check-paper`, `lint-counts` and `validate` all
pass; 11 test, vector or mutant files changed. The agent reports B1 and B3 still
open (they were separate tasks) and G-min partly open: attach domain tag, grant
replay across bridges and the empty image digest. Same limits on parity as the
other orders.

Reading: this is the first order where the cap and handoff were both exercised
and outcomes held. Over the first 61 calls the new arm is 26.8% lower, so a
reset is not the only source; after the reset the second segment ran at 17K
context. Together the three orders give a whole-run reduction of 65% to 85% and
a like-for-like (first 61 calls) reduction of 15% to 27%, with all outcome checks
green. `index slice` was never used in any order, and the ledger was empty in
all of them.

## Decision for stage 3

Stop rule: cache-read at least 15% lower with parity. The whole-run figure
passes (about 80%), the like-for-like figure sits at the line (14.8%), parity
holds on the checks above but is unverified against the reference fix. Going to
stage 3 would test more orders; before that, two changes make the result
informative: (a) save the agent's own handoff and let the wrapper pass it
unchanged, and (b) make the brief fit the cap or tell the agent to read with
`index slice`, so the anchor claim is tested at all. The `old` arm re-run
(up to 14.5 USD) would replace the transcript comparison; the owner declined it.
