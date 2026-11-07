---
id: 0081-flow-orders-carry-a-compiled-brief-and-a-call-cap
title: Each flow order is handed over with a deterministic brief and a tool-call cap, and orders touching the same files share one agent
status: active
date: 2026-11-07
tags: [cost, orchestration, flow, host-neutral]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

- **Brief.** `flow next` emits, from the repo alone and with no model call, a brief for the order: the finding or gap row, the exact file and line anchors with the slices from the section and code index, the digest of the guardrails that apply, the ledger results (0079) already valid for those inputs, and the one verify command. The order names no model or host (0071).
- **Call cap.** An order carries `max_calls` (set from its tier in `flow.yaml`). On reaching it the agent hands back state, and the parent decides whether to continue in a fresh agent with the updated brief.
- **Grouping.** Orders whose anchors share a file are offered as one unit to one agent; the rest may run in parallel.
- **Verify once.** The verify command is a single quiet check that prints pass or fail and the failing lines only; slow suites run once per round in the parent (0079 cold gate), not per agent.

## Why

Agents in the reviewed round each started cold, re-read the guardrails and review notes, searched the same code, and ran 130 to 170 tool calls with a context of up to 300K tokens; cost grows with calls times context, so long runs are the expensive ones. A brief removes the discovery calls; a cap bounds the growth.

## Consequence

The order schema gains optional fields (existing flows stay valid). A brief can go stale if the code moves; it is rebuilt on each `flow next`. A cap that is too low costs a handoff, which is cheaper than a long run.
