---
id: flow-checks-are-named-not-supplied
title: flow done runs only checks from a fixed table, never a command from the caller
status: draft
date: 2026-11-02
tags: [orchestration, security, guardrail]
governed-by: 0071-flow-orders-are-host-neutral
grounded-in: [0071-flow-orders-are-host-neutral]
derivation-note: Given an order's check runs on the owner's machine and a model or a hostile file can influence an order (0071), a caller-supplied command would be arbitrary execution.
go-getter:
  enforcement:
    - tier: 1
      check: Tests that `flow done` rejects an unknown check name, rejects any argument beyond the order id, and that every table entry is a fixed argument vector.
---

## Guardrail

Each order carries a check name, resolved by the CLI in a fixed table of argument vectors. No order, file or argument supplies a command line, shell string or extra flags. Draft until the tests exist.
