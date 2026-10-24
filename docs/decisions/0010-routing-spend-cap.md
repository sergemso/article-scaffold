---
id: 0010-routing-spend-cap
title: Headless runs are capped at 1 USD where the host has a cap
status: active
date: 2026-10-24
tags: [practice-packs, model-routing, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  headless-spend-cap-usd: "1"
  generated-by: cost-routing@0.2.0
  pack-answer: spend-cap
  pack-option: "1"
---

## Decision

Headless runs pass the host's native spend-cap flag with 1 USD; `go-getter route --headless-flags --host <id>` prints it (pack cost-routing@0.2.0). Hosts without a headless cap are not capped.

## Why

An unattended run has no human to notice runaway spend.
