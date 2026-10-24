---
id: 0003-noisy-work-placement
title: Noisy work is delegated only when the cost model says the handoff is cheaper
status: active
date: 2026-10-24
tags: [practice-packs, harness, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: context@0.3.1
  pack-answer: noisy-work
  pack-option: delegate-when-cheaper
---

## Decision

Delegate searches, log reads and test runs to a subagent only when expected total step cost, including handoff and cache loss, is lower than running inline; see the cost-routing pack. (pack context@0.3.1.)

## Why

Every always-loaded token is paid on every request and every subagent; cached prefixes stay cheap only if stable (facts 0003, 0011).
