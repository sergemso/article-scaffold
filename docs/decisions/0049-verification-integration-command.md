---
id: 0049-verification-integration-command
title: The verification integration command is ""
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-integration-command: ""
  generated-by: verification-gate@0.4.0
  pack-answer: integration-command
  pack-option: ""
---

## Decision

Verification runs `` for the integration check, where the machine profile places it; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
