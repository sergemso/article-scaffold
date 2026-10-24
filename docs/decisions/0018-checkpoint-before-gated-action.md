---
id: 0018-checkpoint-before-gated-action
title: Work is checkpointed before a gated action
status: active
date: 2026-10-24
tags: [practice-packs, hooks, guardrail]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: checkpointing@0.2.0
  pack-answer: creation
  pack-option: hook-and-instruction
---

## Decision

The pre-tool hook saves the working tree to a hidden git ref before a gated command (triggers: gated-action; keep: 10), and the agent does it where no hook runs (pack checkpointing@0.2.0).

## Why

A hard reset or a recursive delete cannot be undone from the host (decision 0097); a checkpoint costs a few kilobytes.
