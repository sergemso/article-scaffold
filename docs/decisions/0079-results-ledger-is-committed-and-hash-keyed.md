---
id: 0079-results-ledger-is-committed-and-hash-keyed
title: Every inference and every costly check result is recorded in a committed, append-only ledger keyed by a hash of all its inputs
status: active
date: 2026-11-07
tags: [cost, cache, ledger, sources, orchestration]
track: process
accepted-by: Sergey Strebulaev
governed-facts: [0010-virage-is-semantic-and-injects-on-every-prompt]
---

## Decision

- **Ledger.** The vendored CLI keeps `docs/ledger/<kind>/<key>.json`, one file per result, append-only. A `kind` is a claim verdict (0067, 0075), a section summary (0069), or a declared check outcome (0077: tests, mutation, model checker, lint). Nothing else is cached.
- **Key.** The key is a hash over every input that can change the result: the content hash of each input file or source excerpt, the procedure or check version, the tier, and the tool versions the check declares. Changing any of them is a miss, never a stale hit.
- **Lookup first.** Every CLI command that would infer or run a declared check looks the key up first and returns the stored result with its provenance (when, by which tier, which procedure version). Only a miss runs the check or asks a model.
- **Cold gate.** At each release gate and when a review round closes, the parent session runs all declared checks uncached once and compares the outcome with the ledger. A difference fails the gate and evicts the entry.
- **Humans are unchanged.** Tier 3 attestations (0067) are never replaced by a ledger hit; a hit may only stand in for tier 1 and tier 2.
- **Shared by construction.** The ledger is in the repo, so worktrees, subagents and a session after `/clear` see the same results. 0069's untracked cache under `paper/build/` is replaced by this ledger for the kinds above.

## Why

A review of one fix round of the bridge-contract article (about 17 subagents, in fresh worktrees) found the same mutation, vector, cargo and model-checker runs repeated by six to fifteen agents, and the same large files read by each. An untracked cache starts empty in every worktree, so it cannot prevent that. Exact hash keys give deterministic, auditable lookups; a similarity index (fact 0010) cannot.

## Consequence

The repo gains small files and a merge surface; one file per key keeps conflicts to identical content. An input missing from the key would serve a wrong result silently, which is why the cold gate exists and why guardrail `ledger-keys-cover-every-input` is enforced by a test. A check that is nondeterministic must declare so and is not ledgered.
