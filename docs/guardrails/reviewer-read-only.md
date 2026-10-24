---
id: reviewer-read-only
title: The reviewer must not modify files
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, guardrail]
governed-by: 0022-reviewer-access
grounded-in: [0022-reviewer-access]
derivation-note: Given a findings-only reviewer, a reviewer that edits marks its own work.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction plus the agent file's tool restriction where the host has one
  generated-by: orchestration@0.1.1
  pack-answer: reviewer
  pack-option: read-only
---

## Guardrail

The reviewer reports findings and changes nothing. Hosts with tool lists restrict it natively; elsewhere this is advisory (tier 1).
