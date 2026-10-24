---
id: parallel-tasks-use-worktrees
title: Parallel tasks must each use their own worktree
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, guardrail]
governed-by: 0023-parallel-isolation
grounded-in: [0023-parallel-isolation]
derivation-note: Given worktree isolation, two agents in one working tree overwrite each other.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction only
  generated-by: orchestration@0.1.1
  pack-answer: isolation
  pack-option: worktree-per-task
---

## Guardrail

Give each parallel task its own worktree (`go-getter worktree new <slug>`). Advisory (tier 1).
