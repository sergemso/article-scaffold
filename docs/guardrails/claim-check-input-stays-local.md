---
id: claim-check-input-stays-local
title: Manuscript and source text are never an argument to an outbound call
status: draft
date: 2026-11-02
tags: [theses-map, privacy, sources, guardrail]
governed-by: 0067-claim-checks-are-tiered-and-local
grounded-in: [0067-claim-checks-are-tiered-and-local]
derivation-note: Given claim checking reads manuscript and third-party source text (0067) and scholar-mcp sends only identifiers and search strings (its decision 0059), no CLI code path may send text off the machine.
go-getter:
  enforcement:
    - tier: 1
      check: A test that scans `scripts/article` for network imports outside an explicit allowlist of modules, and fails on any new one.
---

## Guardrail

The vendored CLI opens no network connection from the claim-check, index, cache or theses code. Text reaches a model only through the host session. Draft until the scan test exists.
