---
id: 0019-checkpoint-trigger-gated-action
title: A checkpoint is taken before a gated command
status: active
date: 2026-10-24
tags: [practice-packs, hooks]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: checkpointing@0.2.0
  pack-answer: triggers
  pack-option: [gated-action]
---

## Decision

The pre-tool hook takes a checkpoint before any command in the gated catalog (pack checkpointing@0.2.0).

## Why

Force-pushes, hard resets and recursive deletes cannot be undone from the host, and a checkpoint costs a few kilobytes (decision 0097).
