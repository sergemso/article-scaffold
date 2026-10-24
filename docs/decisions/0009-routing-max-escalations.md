---
id: 0009-routing-max-escalations
title: A failed step escalates at most 2 times, then a human decides
status: active
date: 2026-10-24
tags: [practice-packs, model-routing, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  max-escalations: "2"
  generated-by: cost-routing@0.2.0
  pack-answer: max-escalations
  pack-option: "2"
---

## Decision

A step that fails verification moves one tier up at most 2 times; after that it goes to a human and is never retried (pack cost-routing@0.2.0). The verification gate stops use the same bound.

## Why

An unbounded retry loop can burn unlimited tokens (guardrail routing-escalation-bounded).
