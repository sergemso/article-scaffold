---
id: 0072-flow-budgets-are-unit-and-retry-caps
title: A round is bounded by tier-weighted units and a per-order retry cap, not by host token counts
status: active
date: 2026-11-02
tags: [orchestration, cost, host-neutral]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

Each round has a budget in units; a `script` order costs 0, `small` 1, `large` 5, tunable in `flow.yaml`. Each order has a retry cap on failed checks. When the budget is spent, or an order has failed past its cap, `flow next` refuses to issue a `large` order and returns a needs-human order carrying the evidence (the failing check output and the nodes involved). A host may report real token use into `flow.yaml`; the caps do not depend on it.

## Why

The CLI cannot see tokens, but it controls how many orders are issued, how often one is retried and which tier does the work. Those bound a looping agent on every host. An advisory-only budget stops nothing; a true token cap works only on hosts that report usage.

## Consequence

The weights are a proxy, not real cost, and need tuning against a few rounds. A refusal is an event for the owner, never silently skipped.
