---
id: 0024-worktree-location
title: Task worktrees live in the gitignored .worktrees directory
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  worktree-location: in-repo
  generated-by: orchestration@0.1.1
  pack-answer: worktree-location
  pack-option: in-repo-dir
---

## Decision

Create task worktrees in `.worktrees/<slug>` and keep the directory gitignored (pack orchestration@0.1.1).

## Why

A fixed location keeps worktrees discoverable and out of the main tree's way.
