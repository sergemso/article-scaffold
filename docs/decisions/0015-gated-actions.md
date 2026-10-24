---
id: 0015-gated-actions
title: Irreversible commands need a human
status: active
date: 2026-10-24
tags: [practice-packs, hooks, guardrail]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: hitl@0.6.0
  pack-answer: gated-classes
  pack-option: irreversible
---

## Decision

Irreversible shell commands (force-push, history rewrite, hard reset, `rm -rf`, destructive SQL, deleting a branch or tag) need a human: native ask rules on hosts that support them, a pre-tool hook hand-over on the others (pack hitl@0.6.0).

## Why

Decision 0043 asks agents to stop before costly actions; nothing enforces it without a gate (decision 0094).
