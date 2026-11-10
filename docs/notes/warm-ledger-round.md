# Warm-ledger round: order 3 with a warm and an empty ledger

Date: 2026-11-10. Plan step 1.2, `docs/plans/archive/token-economy-followup.md`.
Status: **one run per arm, no spread.** Read it as an indication only.

## What was run

Order 3 (`scripts/replay-orders/order3.json`, base `5aeec5f`, task hash `841fde17…`,
brief hash `7f1ed1c5…`) through `scripts/replay-order.py` at cap 40, model
`claude-sonnet-5-5`, same prompt and brief in both arms. The only difference:

- **warm:** `docs/ledger/` copied into the worktree from a probe worktree where
  `claims quote-check --all` and `check record` had run for each named check. It held
  6 check outcomes (`theses-lint`, `theses-gaps`, `index-check`, `claims-quote-check`,
  `make-validate`, `lint-counts`; `release-plan` is never stored, `layout-check` was
  evicted because PyMuPDF is missing). It held **no tier-2 claim verdicts**, which need a
  judge.
- **empty:** the plain `5aeec5f` worktree.

The toolchain wrapper and venv (`cryptography`, `hypothesis`, `jsonschema`, `pytest`)
were scratchpad files and are not committed.

## Figures

Transcripts counted one assistant message per `message.id`.

| | warm | empty |
|---|---|---|
| Segments, calls | 2: 40, 37 | 3: 40, 40, 7 |
| Total calls | 77 | 87 |
| Cache-read tokens | 3.33M | 3.90M |
| Slow-check calls (proxy of the pilot) | 49 | 46 |
| `sed -n` reads / `cat`,`head`,`tail` | 37 / 64 | 37 / 80 |
| `index slice` calls | 0 | 0 |
| `scripts.article` calls (any) | 2 | 2 |
| `ledger stats` hits / misses | 0 / 0 | 0 / 0 |
| Spend | 1.594 USD | 1.459 USD |
| Wall time, sum of segments | 2794 s | 2087 s |
| Outcome checks | all pass (see below) | all pass |

Outcome checks of the warm arm: the wrapper's own run reported 4 FAIL (`pytest`,
`mutation`, `vectors-paper`, `measure-paper`) with `No module named pytest` in the log.
The venv imports `pytest` normally, the cause of the missing module at that moment is
**not explained**, and re-running the same check script on the finished worktree passed
every check. The reported failures are not code failures.

## What it says

1. **The ledger was never consulted.** Both arms show 0 hits and 0 misses. The task text
   tells the agent to run `pytest`, `mutation_check.py`, `run_vectors.py`, `cargo test`
   and the rest directly, and neither agent ran `check` or `claims quote-check`. With this
   prompt a warm ledger cannot be used, so the round does not test the ledger. The
   question "does a warm ledger reduce slow checks" is **not answered**.
2. **Token cost and wall time are not separated by the arms.** Warm cache-read is 14%
   lower, but the warm arm also took fewer segments, and with one run per arm there is no
   spread to compare against. Slow-check calls are 49 against 46. Wall time was higher in
   the warm arm (2794 s against 2087 s) with the same ledger use, so it is run to run
   variance or machine load, not the ledger.
3. **No evidence for or against the ledger on token cost.** The earlier estimate (below
   1% of cache-read) is neither confirmed nor contradicted. This note does not recommend
   stopping work on the ledger for token cost, because the test could not have shown an
   effect.

## Cost

Valid runs 3.05 USD (warm 1.594, empty 1.459). Failed first attempts 0.97 USD (a wrapper
toolchain without `cryptography`, and a wrapper bug that treated the call cap as an
error), plus 0.004 USD for a key test. About 4.03 USD of the 8 USD budget.

## Second pair: the prompt names `check`

Order `order3-check` (`scripts/replay-orders/order3-check.json`): same task, brief and
cap, plus one sentence at the end of the prompt telling the agent to run
`python3 -m scripts.article check NAME` for `theses-lint`, `index-check`,
`claims-quote-check`, `make-validate` and `lint-counts` instead of the matching command
by hand. The transcripts confirm the sentence was in the prompt of both arms.

| | warm | empty |
|---|---|---|
| Segments, calls | 1: 39 | 2: 40, 24 |
| Cache-read tokens | 1.86M | 3.07M |
| Slow-check calls | 20 | 45 |
| `scripts.article check` / `claims` calls | **0** | **0** |
| `ledger stats` hits / misses | 0 / 0 | 0 / 0 |
| `index slice` calls | 0 | 1 |
| Spend | 0.671 USD | 1.271 USD |
| Wall time, sum of segments | 457 s | 2934 s |
| Outcome checks | `mutation` 115/116 killed and `mutation-rust` 25/27 killed: FAIL; the rest pass | all pass |

1. **The agents did not follow the sentence.** Neither ran `check`. Both ran
   `make validate` and `lint-counts.py` by hand, as the task text tells them to. A
   sentence at the end of the prompt lost to an explicit instruction earlier in it. The
   ledger was again not consulted, so this pair does not answer the question either.
2. **The warm arm is not comparable.** It stopped after one segment of 39 calls (a reply
   of `success`, not the cap) with surviving mutants in both mutation checks, so its work
   was incomplete. Its lower cache-read and spend (1.86M, 0.67 USD against 3.07M, 1.27
   USD) reflect less work done, not a saving. Why it stopped early is not examined.
3. **What would test the ledger.** The task text itself would have to name `check NAME`
   in place of the by-hand commands for those five checks, and the other slow commands
   (pytest, mutation checks, vectors, cargo) are not ledger checks at all, so at most the
   five could hit, and only while the files they read are unchanged. That is a change of
   the order's task text, not a prompt addition, and has not been run.

## Conclusion for step 1.2

Across two pairs (four runs, one per arm each time, no spread) the ledger was never read:
0 hits and 0 misses every time. The question whether a warm ledger saves tokens or wall
time is **not answered**, and these runs give no evidence of an effect in either
direction. The differences in wall time and cache-read between arms
cannot be read as a ledger effect: no spread was measured, and the arms did different amounts of work
(first pair: 3.33M against 3.90M with a different number of segments; second pair: the warm
arm stopped with its work incomplete). The note does not recommend stopping the ledger on
token-cost grounds, and it does not recommend investing: it records that an agent given an
instruction in the task text to run checks by hand does not switch to `check` when a later
sentence asks it to.

## Cost

Second pair 1.942 USD (warm 0.671, empty 1.271). With the first pair (3.05 USD), the
failed first attempts (0.97 USD) and the key test (0.004 USD): about 5.97 USD of the 8 USD,
about 2.03 USD left.
