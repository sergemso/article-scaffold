---
id: flow-gated-stages-need-out-of-band-confirm
title: Release-gate and publish orders are closed only by a confirmation in the owner's terminal
status: draft
date: 2026-11-02
tags: [orchestration, release, guardrail]
governed-by: 0071-flow-orders-are-host-neutral
grounded-in: [0071-flow-orders-are-host-neutral, companion-release-final-tags-only]
derivation-note: Given publishing mints a permanent DOI (scholar-mcp fact 0002) and the owner pushes the final tag, an order that publishes must not be closable by an agent alone.
go-getter:
  enforcement:
    - tier: 1
      check: Tests that `flow done` for a gated stage refuses without a real terminal and without a single-use token bound to the order, and that the MCP wrapper has no way to supply one.
---

## Guardrail

Orders in the release-gate and publish stages are marked gated. `flow done` closes a gated order only after the owner confirms in a real terminal (single use, bound to the order and its check result). Publishing dispatch stays dry-run first (decision 0063). Draft until the tests exist.
