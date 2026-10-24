---
id: 0026-human-escalation
title: Agents hand over to a human only when blocked
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  escalation: Stop and hand over to a human only when you cannot proceed.
  generated-by: orchestration@0.1.1
  pack-answer: escalation
  pack-option: only-when-blocked
---

## Decision

Hand over to a human only when blocked (pack orchestration@0.1.1).

## Why

Agents must stop where a wrong guess is costly or the way forward needs a person (decision 0009).
