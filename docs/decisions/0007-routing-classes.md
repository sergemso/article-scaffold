---
id: 0007-routing-classes
title: Routing distinguishes explore, plan, implement, review and debug
status: active
date: 2026-10-24
tags: [practice-packs, model-routing, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  routing-classes:
    explore: explore
    plan: plan
    implement: implement
    review: review
    debug: debug
  generated-by: cost-routing@0.2.0
  pack-answer: classes
  pack-option: five-classes
---

## Decision

Each task class is routed on its own, matching the agent roles (pack cost-routing@0.2.0).

## Why

Routing minimises expected total step cost among eligible models (decisions 0016, 0020, 0032); classes carry the quality bar.
