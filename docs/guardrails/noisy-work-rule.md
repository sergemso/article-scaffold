---
id: noisy-work-rule
title: Noisy work is delegated only when the cost model says the handoff is cheaper
status: active
date: 2026-10-24
tags: [practice-packs, harness, guardrail]
governed-by: 0003-noisy-work-placement
grounded-in: [0003-noisy-work-placement]
derivation-note: Given the placement decision, noise kept in the wrong context is re-paid on every request.
go-getter:
  enforcement:
    - tier: 1
      check: Noisy work follows the placement decision; reviewed with the change
  generated-by: context@0.3.1
  pack-answer: noisy-work
  pack-option: delegate-when-cheaper
---

## Guardrail

Delegate noisy work to a subagent only when the cost model says the handoff is cheaper.
Advisory (tier 1 only).
