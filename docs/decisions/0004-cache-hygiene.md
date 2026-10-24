---
id: 0004-cache-hygiene
title: No mid-task model, effort or instruction-file change; switches are confirmed
status: active
date: 2026-10-24
tags: [practice-packs, harness, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: context@0.3.1
  pack-answer: cache-hygiene
  pack-option: advisory-and-confirm
---

## Decision

Do not change model, effort or the instruction file mid-task. Where a host offers a pre-model-switch hook, switches ask for confirmation. (pack context@0.3.1.)

## Why

Every always-loaded token is paid on every request and every subagent; cached prefixes stay cheap only if stable (facts 0003, 0011).
