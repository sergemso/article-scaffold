---
id: max-concurrent-agents-rule
title: No more than 1 agents run at once
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, guardrail]
governed-by: 0025-max-concurrent-agents
grounded-in: [0025-max-concurrent-agents]
derivation-note: Given the limit, each extra agent adds a cold cache and a merge.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction; worktree creation is refused beyond the limit
  generated-by: orchestration@0.1.1
  pack-answer: max-concurrent
  pack-option: "1"
---

## Guardrail

Run at most 1 agents at once. `go-getter worktree new` refuses more than that many worktrees. Advisory (tier 1) otherwise.
