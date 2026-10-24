---
id: 0040-telemetry-export
title: Telemetry is not exported
status: active
date: 2026-10-24
tags: [practice-packs, observability, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  telemetry-export: none
  generated-by: telemetry@0.1.0
  pack-answer: export
  pack-option: none
---

## Decision

Telemetry stays on the machine (pack telemetry@0.1.0).

## Why

Team export arrives with the v0.2 observability pack; until then local data adds no new data-handling surface (decision 0018).
