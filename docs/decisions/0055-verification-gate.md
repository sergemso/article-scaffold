---
id: 0055-verification-gate
title: "\"Done\" is blocked while the verification checks fail"
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-gate: block
  generated-by: verification-gate@0.4.0
  pack-answer: gate
  pack-option: block
---

## Decision

A stop hook runs the implement checks when the working tree has changes and keeps the agent working while they fail, at most the maximum number of escalations per session (decision 0032, default 2), then hands over to a human. On a clean tree pushed as it is, with checks placed in CI, it reads the CI result instead (`go-getter ci status`, decision 0071): red counts as failing, pending ends the stop with a hand-over message. Hosts without a blocking stop hook are advisory (pack verification-gate@0.4.0).

## Why

Without a blocking gate, cheaper tiers would ship failures instead of escalating (decision 0031).
