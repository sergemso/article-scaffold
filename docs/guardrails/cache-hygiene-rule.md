---
id: cache-hygiene-rule
title: No mid-task model, effort or instruction-file change; switches are confirmed
status: active
date: 2026-10-24
tags: [practice-packs, harness, guardrail]
governed-by: 0004-cache-hygiene
grounded-in: [0004-cache-hygiene]
derivation-note: Given the cache decision, a mid-task switch changes the prefix and re-pays full input price.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction only; the confirm-before-switch hook is not generated yet
  generated-by: context@0.3.1
  pack-answer: cache-hygiene
  pack-option: advisory-and-confirm
---

## Guardrail

Do not change model, effort or instruction files mid-task; confirm before any switch.
Advisory (tier 1 only).
