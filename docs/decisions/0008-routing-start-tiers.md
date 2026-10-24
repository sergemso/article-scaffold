---
id: 0008-routing-start-tiers
title: Classes start at balanced tiers and the lowest effort they allow
status: active
date: 2026-10-24
tags: [practice-packs, model-routing, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  routing-start-tiers:
    explore: small
    plan: large
    implement: medium
    review: large
    debug: large
  routing-efforts:
    explore: low
    plan: medium
    implement: medium
    review: medium
    debug: medium
  generated-by: cost-routing@0.2.0
  pack-answer: tiers
  pack-option: balanced
---

## Decision

Starting tiers and efforts per task class are recorded in this decision's data; verification escalates a failed step one tier up (pack cost-routing@0.2.0).

## Why

Routing minimises expected total step cost among eligible models (decisions 0016, 0020, 0032); classes carry the quality bar.
