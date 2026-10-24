---
id: handoff-has-brief-result-evidence
title: Handoffs must carry a brief, a result and evidence
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, guardrail]
governed-by: 0027-handoff-contract
grounded-in: [0027-handoff-contract]
derivation-note: Given the contract, a result without evidence cannot be checked and a brief without done-when cannot be verified.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction only
  generated-by: orchestration@0.1.1
  pack-answer: handoff
  pack-option: brief-result-evidence
---

## Guardrail

Delegate with goal, scope and done-when; reply with the result and its evidence. Advisory (tier 1).
