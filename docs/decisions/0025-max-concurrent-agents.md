---
id: 0025-max-concurrent-agents
title: At most 1 agents run at once
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  max-concurrent: "1"
  generated-by: orchestration@0.1.1
  pack-answer: max-concurrent
  pack-option: "1"
---

## Decision

Run at most 1 agents concurrently; `go-getter worktree new` refuses to exceed it (pack orchestration@0.1.1).

## Why

Each concurrent agent adds a cold cache and a merge to resolve.
