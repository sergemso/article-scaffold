---
id: 0005-compaction-timing
title: Context is compacted at task boundaries
status: active
date: 2026-10-24
tags: [practice-packs, harness, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: context@0.3.1
  pack-answer: compaction
  pack-option: task-boundaries
---

## Decision

Compact context when a task finishes, not mid-task. (pack context@0.3.1.)

## Why

Every always-loaded token is paid on every request and every subagent; cached prefixes stay cheap only if stable (facts 0003, 0011).
