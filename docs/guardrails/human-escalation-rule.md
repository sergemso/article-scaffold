---
id: human-escalation-rule
title: Agents hand over to a human only when blocked
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, guardrail]
governed-by: 0026-human-escalation
grounded-in: [0026-human-escalation]
derivation-note: Given the escalation decision, agents proceed unless they cannot.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction only
  generated-by: orchestration@0.1.1
  pack-answer: escalation
  pack-option: only-when-blocked
---

## Guardrail

Ask a human only when you cannot proceed. Advisory (tier 1).
