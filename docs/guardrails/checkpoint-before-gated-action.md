---
id: checkpoint-before-gated-action
title: A gated action is preceded by a checkpoint
status: active
date: 2026-10-24
tags: [practice-packs, hooks, guardrail]
governed-by: 0018-checkpoint-before-gated-action
grounded-in: [0018-checkpoint-before-gated-action, 0097-checkpoints-are-hidden-git-refs-taken-before-gated-actions]
derivation-note: Given work in progress must be recoverable after an irreversible command (0097), a checkpoint must exist before the command runs, since the host cannot undo what a shell command did.
go-getter:
  enforcement:
    - tier: 2
      check: The pre-tool hook takes a checkpoint before a gated command
      run: builtin:checkpoint-before-gated triggers="gated-action" keep=10
    - tier: 1
      check: Where no hook runs, run `go-getter checkpoint create --label <what>` before a gated command
  generated-by: checkpointing@0.2.0
  pack-answer: creation
  pack-option: hook-and-instruction
---

## Guardrail

Before a gated command, or a plan step when the project checkpoints those, a checkpoint of the working tree exists: the pre-tool hook takes it, or you run `go-getter checkpoint create --label <what>` where no hook runs. Restore with `go-getter checkpoint restore` (see the procedure).
