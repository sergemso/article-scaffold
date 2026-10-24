---
id: 0039-telemetry-recording
title: Steps are not recorded
status: active
date: 2026-10-24
tags: [practice-packs, observability, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  telemetry-recording: off
  generated-by: telemetry@0.1.0
  pack-answer: recording
  pack-option: off
---

## Decision

Record nothing about agent steps (pack telemetry@0.1.0).

## Why

Nothing recorded means no new data-handling surface; routing then runs on defaults without calibration (decision 0017).
