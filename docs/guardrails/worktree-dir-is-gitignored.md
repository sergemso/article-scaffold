---
id: worktree-dir-is-gitignored
title: The .worktrees directory must be gitignored
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, guardrail]
governed-by: 0024-worktree-location
grounded-in: [0024-worktree-location]
derivation-note: Given worktrees inside the repo, an unignored directory gets committed as untracked noise.
go-getter:
  enforcement:
    - tier: 3
      check: .gitignore lists .worktrees/
      run: builtin:gitignore-includes patterns=.worktrees/
  generated-by: orchestration@0.1.1
  pack-answer: worktree-location
  pack-option: in-repo-dir
---

## Guardrail

Keep `.worktrees/` in `.gitignore`.
