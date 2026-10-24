---
id: restoring-a-checkpoint
title: Restore work from a checkpoint
status: active
date: 2026-10-24
tags: [practice-packs, hooks, procedural]
operationalizes: [checkpoint-before-gated-action]
go-getter:
  generated-by: checkpointing@0.2.0
  pack-answer: creation
  pack-option: hook-and-instruction
---

## Procedure

1. `go-getter checkpoint list`: newest first, with the label and ref.
2. `go-getter checkpoint restore <label>` shows what would change (M modified, D deleted, A created since) and changes nothing.
3. If the list is right, add `--yes`: it puts back the M and D files in the working tree only. Files created since stay; remove them yourself if unwanted.
4. A host's own rewind or restore command may undo editor changes, but not what a shell command did: use the checkpoint for that.
